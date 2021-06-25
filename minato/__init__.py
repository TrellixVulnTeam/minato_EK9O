from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Iterator, Optional, Union

from minato.cache import Cache
from minato.config import Config
from minato.filesystems import FileSystem
from minato.minato import Minato

__version__ = "0.3.0"
__all__ = [
    "Cache",
    "Config",
    "FileSystem",
    "Minato",
    "cached_path",
    "download",
    "open",
    "upload",
]


@contextmanager
def open(
    url_or_filename: Union[str, Path],
    mode: str = "r",
    extract: bool = False,
    auto_update: Optional[bool] = None,
    use_cache: bool = True,
    force_download: bool = False,
    force_extract: bool = False,
    cache_root: Optional[Union[str, Path]] = None,
    expire_days: Optional[int] = None,
) -> Iterator[IO[Any]]:
    config = Config.load(
        cache_root=cache_root,
    )

    with Minato(config).open(
        url_or_filename,
        mode=mode,
        extract=extract,
        auto_update=auto_update,
        use_cache=use_cache,
        force_download=force_download,
        force_extract=force_extract,
        expire_days=expire_days,
    ) as fp:
        yield fp


def cached_path(
    url_or_filename: Union[str, Path],
    extract: bool = False,
    auto_update: Optional[bool] = None,
    force_download: bool = False,
    force_extract: bool = False,
    retry: bool = True,
    cache_root: Optional[Union[str, Path]] = None,
    expire_days: Optional[int] = None,
) -> Path:
    config = Config.load(
        cache_root=cache_root,
    )

    return Minato(config).cached_path(
        url_or_filename,
        extract=extract,
        auto_update=auto_update,
        force_download=force_download,
        force_extract=force_extract,
        expire_days=expire_days,
        retry=retry,
    )


def remove_cache(
    url_or_filename: Union[str, Path],
    cache_root: Optional[Union[str, Path]] = None,
) -> None:
    config = Config.load(
        cache_root=cache_root,
    )
    Minato(config).remove_cache(url_or_filename)


def download(url: str, filename: Union[str, Path]) -> None:
    filename = Path(filename)
    Minato.download(url, filename)


def upload(filename: Union[str, Path], url: str) -> None:
    filename = Path(filename)
    Minato.upload(filename, url)


def delete(url_or_filename: Union[str, Path]) -> None:
    Minato.delete(url_or_filename)
