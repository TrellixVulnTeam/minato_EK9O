from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Iterator, Optional, Union

from minato.cache import Cache
from minato.config import Config
from minato.filesystems import download, open_file
from minato.util import (
    extract_archive_file,
    extract_path,
    is_archive_file,
    is_local,
    remove_file_or_directory,
)


class Minato:
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config.load()
        self._cache = Cache(
            artifact_dir=self._config.cache_artifact_dir,
            sqlite_path=self._config.cache_db_path,
            expire_days=self._config.expire_days,
        )

    @property
    def cache(self) -> Cache:
        return self._cache

    @contextmanager
    def open(
        self,
        url_or_filename: Union[str, Path],
        mode: str = "r",
        extract: bool = False,
        use_cache: bool = True,
        force_download: bool = False,
        force_extract: bool = False,
    ) -> Iterator[IO[Any]]:
        if (
            not ("a" in mode and "w" in mode and "x" in mode and "+" in mode)
            and use_cache
        ):
            url_or_filename = self.cached_path(
                url_or_filename,
                extract=extract,
                force_download=force_download,
                force_extract=force_extract,
            )

        with open_file(url_or_filename, mode) as fp:
            yield fp

    def cached_path(
        self,
        url_or_filename: Union[str, Path],
        extract: bool = False,
        force_download: bool = False,
        force_extract: bool = False,
    ) -> Path:
        url_or_filename = str(url_or_filename)

        if "!" in url_or_filename:
            remote_archive_path, file_path = url_or_filename.rsplit("!", 1)
            archive_path = self.cached_path(
                remote_archive_path,
                extract=True,
                force_extract=force_extract,
                force_download=force_download,
            )
            if not archive_path.is_dir():
                raise ValueError(
                    f"{url_or_filename} uses the ! syntax, but this is not an archive file."
                )

            file_path = extract_path(file_path)
            filename = archive_path / file_path
            return filename

        if is_local(url_or_filename):
            url_or_filename = extract_path(url_or_filename)
            if not extract and not is_archive_file(url_or_filename):
                return Path(url_or_filename)

        with self._cache:
            url = str(url_or_filename)
            if url in self._cache:
                cached_file = self._cache.by_url(url)
            else:
                cached_file = self._cache.add(url)

            try:
                downloaded = False
                if (
                    not cached_file.local_path.exists()
                    or self._cache.is_expired(cached_file)
                    or force_download
                ):
                    self.download(cached_file.url, cached_file.local_path)
                    downloaded = True

                extracted = False
                if (
                    (extract and cached_file.extraction_path is None)
                    or (downloaded and cached_file.extraction_path is not None)
                    or force_extract
                ) and is_archive_file(cached_file.local_path):
                    cached_file.extraction_path = Path(
                        str(cached_file.local_path) + "-extracted"
                    )
                    if cached_file.extraction_path.exists():
                        remove_file_or_directory(cached_file.extraction_path)
                    extract_archive_file(
                        cached_file.local_path, cached_file.extraction_path
                    )
                    extracted = True

                if downloaded or extracted:
                    self._cache.update(cached_file)

                if (extract or force_extract) and cached_file.extraction_path:
                    return cached_file.extraction_path
            except (Exception, SystemExit, KeyboardInterrupt):
                remove_file_or_directory(cached_file.local_path)
                if cached_file.extraction_path:
                    remove_file_or_directory(cached_file.extraction_path)
                raise

        return cached_file.local_path

    @staticmethod
    def download(url: str, filename: Path) -> None:
        download(url, filename)

    @staticmethod
    def upload(filename: Path, url: str) -> None:
        with open(filename, "rb") as local_file:
            with open_file(url, "wb") as remote_file:
                content = local_file.read()
                remote_file.write(content)

    def remove(self, id_or_url: Union[int, str]) -> None:
        if isinstance(id_or_url, int):
            cache_id = id_or_url
            cached_file = self._cache.by_id(cache_id)
        else:
            url = id_or_url
            cached_file = self._cache.by_url(url)

        remove_file_or_directory(cached_file.local_path)
        if cached_file.extraction_path is not None:
            remove_file_or_directory(cached_file.extraction_path)
        self._cache.delete(cached_file)
