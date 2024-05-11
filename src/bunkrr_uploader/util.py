from io import BufferedReader
from pathlib import Path
from typing import Callable, Optional

from tqdm import tqdm


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
