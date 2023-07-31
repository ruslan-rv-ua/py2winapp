from pathlib import Path
from typing import Union

import requests


class Dwwnloader:
    def __init__(self, download_dir_path: Path):
        if not download_dir_path.exists() or not download_dir_path.is_dir():
            raise FileNotFoundError(f"{download_dir_path} is not found.")
        self._download_dir_path = download_dir_path

    def download(self, url: str, file: str) -> Path:
        file_path = self._download_dir_path / file
        if file_path.exists() and file_path.is_file():  # cached
            return file_path
        self._download_file(url, file_path)
        return file_path

    def _download_file(
        self, url: str, local_file_path: Path, chunk_size: int = 128
    ) -> None:
        """
        Download a file from a given URL and save it to a local file path.

        Args:
            url (str): The URL of the file to download.
            local_file_path (Path): The local file path to save the downloaded file to.
            chunk_size (int, optional): The size of each chunk to download. Defaults to 128.
        """
        resp = requests.get(url, stream=True)
        with open(local_file_path, "wb") as file:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                file.write(chunk)
