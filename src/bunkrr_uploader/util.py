import logging
from io import BufferedReader
from pathlib import Path
from typing import Callable, Optional

import multivolumefile
from tqdm import tqdm

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ProgressFileReader(BufferedReader):
    def __init__(self, filename: Path, read_callback: Optional[Callable[[int, int, Optional[int]], None]] = None):
        # Don't use with because we need the file to be open for future progress
        # No idea if this causes memory issues
        f = open(filename, "rb")
        self.__read_callback = read_callback
        super().__init__(raw=f)
        self.length = Path(filename).stat().st_size

    def read(self, size: Optional[int] = None):
        calc_sz = size
        if not calc_sz:
            calc_sz = self.length - self.tell()
        if self.__read_callback:
            self.__read_callback(self.tell(), round(self.tell() / self.length), self.length)
        return super(ProgressFileReader, self).read(size)


class TqdmUpTo(tqdm):
    """Provides `update_to(n)` which uses `tqdm.update(delta_n)`."""

    def update_to(self, b=1, bsize=1, tsize=None):
        """
        b  : int, optional
            Number of blocks transferred so far [default: 1].
        bsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        tsize  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if tsize is not None:
            self.total = tsize
        return self.update(b * bsize - self.n)  # also sets self.n = b * bsize


def create_multivolume_archive(file_path: Path, volume_size: int) -> list[Path]:
    temp_files_path = Path.cwd().joinpath("temp")

    if not temp_files_path.exists():
        logger.info(f"Creating directory for temporary multi volume archive files at {temp_files_path}")
        temp_files_path.mkdir(parents=True, exist_ok=True)
    else:
        logger.info(f"Temporary directory for multi volume archive files already exists at: {temp_files_path}")

    with open(file_path, "rb") as original_file:
        # The new files will be created in our local temporary path
        split_file_name = temp_files_path.joinpath(f"{file_path.name}.zip")
        original_file_data = original_file.read()

        with multivolumefile.open(split_file_name, "wb", volume=volume_size) as vol:
            with zipfile.ZipFile(vol, "w", compression=zipfile.ZIP_STORED) as archive:  # type: ignore
                archive.writestr(file_path.name, original_file_data)

    if split_file_name:
        created_files = [
            x for x in temp_files_path.iterdir() if x.is_file() and x.name.startswith(split_file_name.name)
        ]
        return created_files
    else:
        logger.info(f"Failed to create split files")

    return []
