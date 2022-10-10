"""Class for the creation, caching, and management of artwork images"""
from __future__ import annotations

from io import BytesIO
from logging import DEBUG, getLogger
from os.path import exists, isdir, isfile, join
from pathlib import Path
from re import compile as compile_regex

from PIL.Image import Image, Resampling
from PIL.Image import open as open_image
from requests import get
from wg_utilities.functions import force_mkdir
from wg_utilities.loggers import add_stream_handler

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


class ArtworkImage:
    """Class for the creation, caching, and management of artwork images"""

    ARTWORK_DIR = Path("/home/pi/crt_artwork")
    ALPHANUM_PATTERN = compile_regex(r"[\W_]+")

    def __init__(self, album: str, artist: str, url: str) -> None:
        self.album = album
        self.artist = artist or "unknown"
        self.url = url

    def download(self) -> None:
        """Download the image from the URL to store it locally for future use"""

        if not isdir(self.ARTWORK_DIR / self.artist_directory):
            force_mkdir(self.ARTWORK_DIR / self.artist_directory)

        if isfile(self.url):
            LOGGER.debug("Opening local image: %s", self.url)
            with open(self.url, "rb") as fin:
                artwork_bytes = fin.read()
        else:
            LOGGER.debug("Downloading artwork from remote URL: %s", self.url)
            artwork_bytes = get(self.url).content

        with open(self.file_path, "wb") as fout:
            fout.write(artwork_bytes)

        LOGGER.info("New image saved at %s", self.file_path)

    def get_image(
        self,
        size: int | None = None,
        convert: str | None = None,
    ) -> Image:
        """Returns the image as a PIL Image object, with optional resizing

        Args:
            size (int): integer value to use as height and width of artwork, in pixels
            convert (str): optional color conversion to apply to the image

        Returns:
            Image: PIL Image object of artwork
        """

        if not exists(self.file_path):
            self.download()

        with open(self.file_path, "rb") as fin:
            tk_img: Image = open_image(BytesIO(fin.read()))

        if size:
            tk_img = tk_img.resize((size, size), Resampling.LANCZOS)

        if convert:
            tk_img = tk_img.convert(convert)

        LOGGER.debug("Returning image from path %s", self.file_path)

        return tk_img

    @property
    def artist_directory(self) -> str:
        """Strips all non-alphanumeric characters from the artist name for use as the
        directory name

        Returns:
            str: the artist name, with all non-alphanumeric characters removed
        """
        return ArtworkImage.ALPHANUM_PATTERN.sub("", self.artist).lower()

    @property
    def filename(self) -> str:
        """Strip all non-alphanumeric characters from the album name for use as the
        file name

        Returns:
            str: the filename of the artwork image
        """
        return ArtworkImage.ALPHANUM_PATTERN.sub("", self.album).lower() + ".png"

    @property
    def file_path(self) -> str:
        """
        Returns:
            str: fully-qualified path to the artwork image
        """
        return join(self.ARTWORK_DIR, self.artist_directory, self.filename)

    def __hash__(self) -> int:
        return hash((self.artist, self.album, self.url))

    def __str__(self) -> str:
        """Returns the string representation of the object"""
        return self.__repr__()

    def __repr__(self) -> str:
        """Returns the string representation of the object"""
        return f"ArtworkImage({self.artist}, {self.album}, {self.url})"


NULL_IMAGE = ArtworkImage(
    "null", "null", str(Path(__file__).parents[3] / "assets" / "images" / "null.png")
)
