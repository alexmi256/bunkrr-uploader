import asyncio
import csv
import logging
import re
import tempfile
import time
from pathlib import Path
from pprint import pformat, pprint
from typing import Any, List, Optional

from .api import BunkrrAPI
from .cli import cli
from .logging_manager import USE_MAIN_NAME, setup_logger

logger = logging.getLogger(__name__)


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
        logger.debug(dict(raw_req))
        max_file_size = raw_req.get("maxSize", "0B")
        max_chunk_size = raw_req.get("chunkSize", {}).get("max", "0B")
        default_chunk_size = raw_req.get("chunkSize", {}).get("default", "0B")
        self.api.file_blacklist.extend(raw_req.get("stripTags", {}).get("blacklistExtensions", []))

        # Choose a chunk size, default or max
        chunk_size = default_chunk_size
        if self.options.get("use_max_chunk_size"):
            chunk_size = max_chunk_size

        if max_file_size == "0B" or chunk_size == "0B":
            raise ValueError("Invalid max file size or chunk size")

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
        file_size = file.stat().st_size

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
            logger.warning(f"only files at the root of the input folder will be uploaded (no recursion)")
            paths = sorted([x for x in path.iterdir() if x.is_file()], key=lambda p: str(p))
            if folder is None:
                folder = path.name

        if len(paths) == 0:
            logger.error("No file paths left to upload")
            return

        # The server may not accept certain file types and those over a certain size so we need to create temporary files
        filtered_paths = []
        for file_path in paths:
            filtered_paths.extend(self.prepare_file_for_upload(file_path))

        # TODO: Delete the extra created files after upload
        self.temporary_files = [x for x in filtered_paths if x not in paths]

        folder_id = None
        if folder:
            existing_folders = await self.api.get_albums()
            existing_folder = next((x for x in existing_folders["albums"] if x["name"] == folder), None)
            if existing_folder:
                folder_id = str(existing_folder["id"])
            else:
                logger.debug(f"album '{folder}' does not exists, creating")
                created_folder = await self.api.create_album(folder, folder)
                folder_id = str(created_folder["id"])
            logger.debug(f"album id: '{folder_id}'")

        if paths:
            responses = await self.api.upload_files(filtered_paths, folder_id)

            if self.options.get("save") and responses:
                expected_fieldnames = ["albumid", "filePathMD5", "fileNameMD5", "filePath", "fileName", "uploadSuccess"]
                response_fields = list(
                    set(expected_fieldnames + list(set().union(*[x.keys() for x in responses[0]["files"] if x])))
                )

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
    setup_logger(
        log_file=USE_MAIN_NAME,
        log_level=logging.DEBUG if args.verbose else logging.INFO,
        logs_folder_overrride=Path(__file__).parents[-3] / "logs",
    )

    logger.debug(dict(vars(args)))

    options = {"save": args.save, "chunk_retries": args.chunk_retries, "use_max_chunk_size": args.max_chunk_size}

    bunkrr_client = BunkrrUploader(args.token, max_connections=args.connections, retries=args.retries, options=options)
    try:
        await bunkrr_client.init()
        if args.dry_run:
            logger.warning("Dry run only, uploading skipped")
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
