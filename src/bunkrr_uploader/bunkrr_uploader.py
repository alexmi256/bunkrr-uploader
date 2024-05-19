import asyncio
import csv
import functools
import logging
import os
import re
import time
from pathlib import Path
from pprint import pformat, pprint
from typing import Any, List, Optional

from .api import BunkrrAPI
from .cli import cli

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)


class BunkrrUploader:
    def __init__(
        self,
        token: str,
        max_connections: int = 1,
        retries: int = 1,
        options: Optional[dict[str, Any]] = None,
    ):
        if options is None:
            options = {}
        self.options = options
        self.api = BunkrrAPI(token, max_connections, retries, options)
        self.temporary_files = []

    async def init(self):
        raw_req = await self.api.get_check()
        logger.debug(pformat(raw_req))
        max_file_size = raw_req.get("maxSize", "0B")
        max_chunk_size = raw_req.get("chunkSize", {}).get("max", "0B")
        default_chunk_size = raw_req.get("chunkSize", {}).get("default", "0B")
        self.api.file_blacklist.extend(raw_req.get("stripTags", {}).get("blacklistExtensions", []))

        # Choose a chunk size, default or max
        chunk_size = default_chunk_size
        # chunk_size = '1MB'

        if max_file_size == "0B" or chunk_size == "0B":
            raise Exception("Invalid max file size or chunk size")

        # TODO: check if either one is 0 and abort

        units_to_calc = [max_file_size, chunk_size]
        units_calculated = []

        for unit in units_to_calc:
            size_str = unit.lower()
            unit_multiplier = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}
            match = re.match(r"^(\d+)([a-z]+)$", size_str)

            if match:
                value, unit = match.groups()
                bytes_size = int(value) * unit_multiplier.get(unit, 1)
                units_calculated.append(bytes_size)
            else:
                raise ValueError("Invalid input format")

        self.api.max_file_size = units_calculated[0]
        self.api.chunk_size = units_calculated[1]

    def prepare_file_for_upload(self, file: Path) -> List[Path]:
        file_size = os.stat(file).st_size

        # TODO: Truncate the file name if it is too long
        file_name = (file.name[:240] + "..") if len(file.name) > 240 else file.name

        if file.suffix in self.api.file_blacklist:
            logger.error(f"File {file} has blacklisted extension {file.suffix}")
            return []

        if file_size > self.api.max_file_size:
            # TODO: Create temporary file archive
            logger.error(f"File {file} is bigger than max file size {self.api.max_file_size}")
            return []

        return [file]

    async def upload_files(self, path: Path, folder: Optional[str] = None) -> None:
        if path.is_file():
            paths = [path]
        else:
            paths = [x for x in path.iterdir() if x.is_file()]
            if folder is None:
                folder = path.name

        # The server may not accept certain file types and those over a certain size so we need to create temporary files
        filtered_paths = []
        for file_path in paths:
            filtered_paths.extend(self.prepare_file_for_upload(file_path))

        if len(paths) == 0:
            print("No file paths left to upload")
            return

        # TODO: Delete the extra created files after upload
        self.temporary_files = [x for x in filtered_paths if x not in paths]

        folder_id = None
        if folder:
            existing_folders = await self.api.get_albums()
            existing_folder = next((x for x in existing_folders["albums"] if x["name"] == folder), None)
            if existing_folder:
                folder_id = str(existing_folder["id"])
            else:
                created_folder = await self.api.create_album(folder, folder)
                folder_id = str(created_folder["id"])

        if paths:
            responses = await self.api.upload_files(filtered_paths, folder_id)
            # pprint(responses)

            if self.options.get("save") is True and responses:
                response_fields = list(set().union(*[x.values() for x in responses[0]["files"] if x]))

                file_name = f"bunkrr_upload_{int(time.time())}.csv"
                with open(file_name, "w", newline="") as csvfile:
                    logger.info(f"Saving uploaded files to {file_name}")
                    csv_writer = csv.DictWriter(csvfile, dialect="excel", fieldnames=response_fields)
                    csv_writer.writeheader()
                    for row in responses:
                        csv_writer.writerow(row["files"][0])

            else:
                pprint(responses)


async def async_main() -> None:
    args = cli()
    logger.debug(args)

    options = {"save": args.save, "chunk_retries": args.chunk_retries}

    bunkrr_client = BunkrrUploader(args.token, max_connections=args.connections, retries=args.retries, options=options)
    try:
        await bunkrr_client.init()
        if args.dry_run:
            print("Dry run only, uploading skipped")
        else:
            await bunkrr_client.upload_files(args.file, folder=args.folder)
    finally:
        if not bunkrr_client.api.session.closed:
            await bunkrr_client.api.session.close()
        for server_session in bunkrr_client.api.server_sessions.values():
            if not server_session.closed:
                server_session.close()


def main():
    asyncio.run(async_main())
