import asyncio
import hashlib
import logging
import mimetypes
import os
import uuid
from pathlib import Path
from pprint import pformat, pprint
from typing import Any, BinaryIO, Optional, Union

import aiohttp
from tqdm.asyncio import tqdm_asyncio

from .types import (
    AlbumsResponse,
    CheckResponse,
    CreateAlbumResponse,
    NodeResponse,
    UploadResponse,
    VerifyTokenResponse,
)
from .util import ProgressFileReader, TqdmUpTo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class BunkrrAPI:
    def __init__(
        self,
        token: str,
        max_connections: int = 2,
        retries: int = 2,
        options: Optional[dict[str, Any]] = None,
    ):
        if options is None:
            options = {}

        self.token = token
        self.url = "https://app.bunkrr.su/"
        self.download_url_base = "https://bunkrr.ru/d/"

        # These all need to be initialized later on before the API is used
        self.max_file_size = None
        self.chunk_size = None
        self.file_blacklist = []

        self.options = options

        self.session_headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "token": self.token,
        }
        self.session = aiohttp.ClientSession("https://app.bunkrr.su", headers=self.session_headers)

        self.server_sessions = {}
        self.created_folders = {}
        self.sem = asyncio.Semaphore(max_connections)
        self.retries = retries
        self.max_chunk_retries = options.get("chunk_retries") or 1

    async def get_check(self) -> CheckResponse:
        async with self.session.get("/api/check") as resp:
            response = await resp.json()
            return response

    async def get_node(self) -> NodeResponse:
        async with self.session.get("/api/node") as resp:
            response = await resp.json()
            return response

    async def verify_token(self) -> VerifyTokenResponse:
        data = {"token": self.token}
        async with self.session.post("/api/tokens/verify", data=data) as resp:
            response = await resp.json()
            return response

    async def get_albums(self) -> AlbumsResponse:
        async with self.session.get("/api/albums") as resp:
            response = await resp.json()
            return response

    async def create_album(
        self, name: str, description: str, public: bool = True, download: bool = True
    ) -> CreateAlbumResponse:
        data = {"name": name, "description": description, "public": public, "download": download}
        async with self.session.post("/api/albums", json=data) as resp:
            response = await resp.json()
            return response

    async def upload_chunks(
        self,
        file_data: Union[BinaryIO, ProgressFileReader],
        file_name: str,
        file_uuid: str,
        file_size: int,
        session,
        server: str,
    ) -> None:
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        chunk_index = 0
        dzchunkbyteoffset = 0

        # Iterates all chunks
        while chunk_index < total_chunks:
            # logger.debug(f"Processing chunk {chunk_index + 1}/{total_chunks} for {file_name}")

            chunk_data = file_data.read(self.chunk_size)
            chunk_upload_success = False
            chunk_upload_attempt = 0
            if not chunk_data:
                print("No more chunks to upload")
                break  # Exit the loop if we've reached the end of the file

            # likely using https://gitlab.com/meno/dropzone/-/wikis/faq#chunked-uploads
            # https://github.com/Dodotree/DropzonePHPchunks/issues/3
            data = aiohttp.FormData()
            data.add_field("dzuuid", file_uuid)
            data.add_field("dzchunkindex", str(chunk_index))
            data.add_field("dztotalfilesize", str(file_size))
            data.add_field("dzchunksize", str(self.chunk_size))
            data.add_field("dztotalchunkcount", str(total_chunks))
            data.add_field("dzchunkbyteoffset", str(dzchunkbyteoffset))
            data.add_field(
                "files[]",
                chunk_data,
                filename=file_name,
                content_type="application/octet-stream",
            )

            # Retries chunks if they ever fail
            while chunk_upload_attempt < self.max_chunk_retries and chunk_upload_success is False:
                try:
                    async with session.post("/api/upload", data=data) as resp:
                        response = await resp.json()
                        if response.get("success"):
                            chunk_index += 1
                            dzchunkbyteoffset += self.chunk_size
                            chunk_upload_success = True
                        else:
                            msg = f"{file_uuid} failed uploading chunk #{chunk_index}/{total_chunks} to {server} [{chunk_upload_attempt}/{self.max_chunk_retries}]"
                            logger.error(msg)
                            raise Exception(msg)
                except Exception:
                    chunk_upload_attempt += 1

            if chunk_upload_success is False:
                msg = f"Failed uploading chunks for {file_uuid} too many times times to {server}, cannot continue"
                logger.error(msg)
                raise Exception(msg)

    # TODO: This should probably move out of API
    async def upload(self, file: Path, album_id: Optional[str] = None) -> UploadResponse:
        metadata = {
            "success": False,
            "files": [
                {
                    "fileName": file.name,
                    "albumid": album_id,
                    "filePath": str(file),
                    "filePathMD5": hashlib.md5(str(file).encode("utf-8")).hexdigest(),
                    "fileNameMD5": hashlib.md5(str(file.name).encode("utf-8")).hexdigest(),
                    "uploadSuccess": None,
                }
            ],
        }
        file_size = os.stat(file).st_size
        file_mimetype = mimetypes.guess_type(file)[0] or "application/octet-stream"
        node_response = await self.get_node()
        if not node_response.get("success"):
            logger.error(f"Failed to get server to upload to: {pformat(node_response)}")
            return metadata
        server = "/".join(node_response["url"].split("/")[:3])

        if server not in self.server_sessions:
            logger.info(f"Using new server connection to {server}")
            self.server_sessions[server] = aiohttp.ClientSession(server, headers=self.session_headers)

        session = self.server_sessions[server]

        headers = {"albumid": album_id} if album_id else None

        file_uuid = str(uuid.uuid4())

        async with self.sem:
            retries = 0
            while retries < self.retries:
                try:
                    with open(file, "rb") as file_data:
                        with TqdmUpTo(
                            unit="B",
                            unit_scale=True,
                            unit_divisor=1024,
                            miniters=1,
                            desc=f"{file.name} [{retries + 1}/{self.retries}]",
                        ) as t:
                            with ProgressFileReader(filename=file, read_callback=t.update_to) as file_data:
                                if file_size <= self.chunk_size:
                                    chunk_data = file_data.read(self.chunk_size)
                                    data = aiohttp.FormData()
                                    data.add_field(
                                        "files[]", chunk_data, filename=file.name, content_type=file_mimetype
                                    )

                                    async with session.post("/api/upload", data=data, headers=headers) as resp:
                                        response = await resp.json()
                                        if not response.get("success"):
                                            raise Exception(f"{file.name} failed uploading without chunks")

                                        return response
                                else:
                                    logger.debug(f"{file.name} will use UUID {file_uuid}")
                                    await self.upload_chunks(
                                        file_data, file.name, file_uuid, file_size, session, server
                                    )

                                    upload_data = {
                                        "files": [
                                            {
                                                "uuid": file_uuid,
                                                "original": file.name,
                                                "type": file_mimetype,
                                                "albumid": album_id or "",
                                                "filelength": "",
                                                "age": "",
                                            }
                                        ]
                                    }
                                    finish_chunks_attempt = 0
                                    while True:
                                        try:
                                            async with session.post(
                                                "/api/upload/finishchunks", json=upload_data
                                            ) as resp:
                                                response = await resp.json()
                                                if response.get("success") is False:
                                                    msg = f"{file_uuid} failed finishing chunks to {server} [{finish_chunks_attempt + 1}/{self.max_chunk_retries}]\n{pformat(response)}"
                                                    logger.error(msg)
                                                    raise Exception(msg)
                                                # chunk_upload_success = True
                                                response.update(metadata)
                                                return response
                                        except Exception:
                                            finish_chunks_attempt += 1
                                            if finish_chunks_attempt >= self.max_chunk_retries:
                                                raise
                                    # TODO: Should probably return here
                except Exception:
                    logger.exception(f"Upload failed for {file.name} to {server} Attempt #{retries + 1}")
                    retries += 1
            return {"success": False, "files": [{"name": file.name, "url": ""}]}

    # TODO: This should probably move out of API
    async def upload_files(self, paths: list[Path], folder_id: Optional[str] = None) -> list[UploadResponse]:
        try:
            tasks = [self.upload(test_file, folder_id) for i, test_file in enumerate(paths)]
            responses = await tqdm_asyncio.gather(*tasks, desc="Files uploaded")
            return responses
        finally:
            # This should happen in the API client itself
            await self.session.close()
            for server_session in self.server_sessions.values():
                await server_session.close()
