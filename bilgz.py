# library to handle g-zipped .bil files

from pathlib import Path
import gzip


def open(filename):
    return gzip.open(filename,
                     mode='rb',
                     compresslevel=9,
                     encoding=None,
                     errors=None,
                     newline=None)
