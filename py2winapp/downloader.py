"""Ddownloader class for downloading files from a given URL to a local file path."""

from pathlib import Path

import requests
from loguru import logger


class Dwwnloader:
    """Class for downloading files from a given URL to a local file path."""

    def __init__(self, download_dir_path: Path):
        """Initialize the Downloader object.

        Args:
            download_dir_path (Path): The path to the directory
            where downloaded files will be saved.
        """
        if not download_dir_path.exists() or not download_dir_path.is_dir():
            raise FileNotFoundError(f"{download_dir_path} is not found.")
        self._download_dir_path = download_dir_path

    def download(self, url: str, file: str) -> Path:
        """Download a file from a given URL and save it to a local file path.

        It will check if the file is already downloaded and cached. If so, it will
        return the cached file path. Otherwise, it will download the file and save it

        Args:
            url (str): The URL of the file to download.
            file (str): The name of the file to save the downloaded file to.

        Returns:
            Path: The local file path of the downloaded file.
        """
        logger.debug(f"Downloading {url} to {file}")
        file_path = self._download_dir_path / file
        if file_path.exists() and file_path.is_file():  # cached
            logger.debug(f"{file_path} is cached.")
            return file_path
        logger.debug(f"{file_path} is not cached. Downloading...")
        self._download_file(url, file_path)
        return file_path

    def _download_file(self, url: str, local_file_path: Path, chunk_size: int = 128) -> None:
        """Download a file from a given URL and save it to a local file path.

        Args:
            url (str): The URL of the file to download.
            local_file_path (Path): The local file path to save the downloaded file to.
            chunk_size (int, optional): The size of each chunk to download.
            Defaults to 128.
        """
        resp = requests.get(url, stream=True)
        with open(local_file_path, "wb") as file:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                file.write(chunk)
