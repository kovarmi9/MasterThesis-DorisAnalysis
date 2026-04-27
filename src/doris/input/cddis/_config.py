from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


__all__ = [
    "AuthConfig",
    "CddisRequest",
    "DownloadOptions",
    "DecompressOptions",
    "LoadConfig",
]


# Authentication configuration
@dataclass(frozen=True, slots=True)
class AuthConfig:
    """
    Configuration for CDDIS Earthdata authentication

    This object stores information about where credentials are located and how authentication should behave

    Parameters
    ----------
    token_file : Path
        Path to the file containing an Earthdata API token

    login_file : Path
        Path to a file containing stored username/password credentials

    allow_interactive : bool
        If True, the program may prompt the user for credentials

    save_login_on_success : bool
        If True, credentials entered interactively may be stored
    """

    token_file: Path = Path("token.txt")
    login_file: Path = Path("login.txt")
    allow_interactive: bool = True
    save_login_on_success: bool = True

    # Conversion to path object
    def __post_init__(self) -> None:
        object.__setattr__(self, 'token_file', Path(self.token_file))
        object.__setattr__(self, 'login_file', Path(self.login_file))


# Dataset request description
@dataclass(frozen=True, slots=True)
class CddisRequest:
    """
    Describes a dataset request for the CDDIS archive

    This object defines what dataset should be downloaded

    Parameters
    ----------
    technique : str
        Observation technique (e.g. "doris", "gnss", etc.)

    subtree : str
        Archive subtree, typically something like "products"

    product : str
        Product type (e.g. "stcd", "orbits", etc.)

    solution : str
        Specific solution identifier

    satellite : str | None
        Optional satellite identifier

    archive_root : str
        Base URL of the archive

    output_root : Path
        Local root directory where downloaded data will be stored
    """

    technique: str
    subtree: str
    product: str
    solution: str
    satellite: str | None = None

    archive_root: str = "https://cddis.nasa.gov/archive"
    output_root: Path = Path("data")

    def __post_init__(self) -> None:
        # Validate required text fields
        if not self.technique or not self.technique.strip():
            raise ValueError("technique must be a non-empty string")
        if not self.subtree or not self.subtree.strip():
            raise ValueError("subtree must be a non-empty string")
        if not self.product or not self.product.strip():
            raise ValueError("product must be a non-empty string")
        if not self.solution or not self.solution.strip():
            raise ValueError("solution must be a non-empty string")
        if self.satellite is not None and not self.satellite.strip():
            raise ValueError("satellite must not be empty when provided")

        # Conversion to path object
        object.__setattr__(self, 'output_root', Path(self.output_root))

    # Normalized values when constructing URLs
    @property
    def normalized_technique(self) -> str:
        """Lowercase, trimmed technique name."""
        return self.technique.strip().lower()

    @property
    def normalized_subtree(self) -> str:
        """Lowercase, trimmed subtree name."""
        return self.subtree.strip().lower()

    @property
    def normalized_product(self) -> str:
        """Lowercase, trimmed product name."""
        return self.product.strip().lower()

    @property
    def normalized_solution(self) -> str:
        """Lowercase, trimmed solution name."""
        return self.solution.strip().lower()

    @property
    def normalized_satellite(self) -> str | None:
        """Lowercase, trimmed satellite identifier (if provided)."""
        if self.satellite is None:
            return None
        return self.satellite.strip().lower()

    # Build dataset path
    @property
    def relative_dataset_path(self) -> str:
        """
        Relative path inside the archive for this dataset

        Example
        -------
        stcd/gop25wd03
        stcd/gop25wd03/ja3
        """
        parts = [
            self.normalized_product,
            self.normalized_solution,
        ]

        if self.normalized_satellite:
            parts.append(self.normalized_satellite)

        return "/".join(parts)


# Download behavior configuration
@dataclass(frozen=True, slots=True)
class DownloadOptions:
    """
    Options controlling how dataset files are downloaded

    These parameters affect file handling and network behaviour

    Parameters
    ----------
    overwrite : bool
        If True, existing local files are overwritten

    create_dirs : bool
        If True, output directories are created automatically

    fail_on_missing : bool
        If True, the workflow raises an exception when a file cannot be downloaded. If False, the file is skipped

    keep_md5_file : bool
        If True, the downloaded MD5SUMS file is kept locally

    request_timeout : float
        Timeout in seconds for a single HTTP request

    retry_count : int
        Number of download attempts for a file before giving up

    retry_delay_seconds : float
        Delay between retry attempts in seconds

    chunk_size : int
        Streaming chunk size in bytes used while downloading files

    parallel_download : bool
        If True, dataset archive files may be downloaded in parallel
        using multiple worker threads. If False, files are downloaded
        sequentially

    max_workers : int
        Maximum number of worker threads used for parallel download.
        This value is only relevant when parallel_download=True
    """

    overwrite: bool = True
    create_dirs: bool = True
    fail_on_missing: bool = False
    keep_md5_file: bool = False

    request_timeout: float = 60.0
    retry_count: int = 3
    retry_delay_seconds: float = 2.0
    chunk_size: int = 1024 * 64

    parallel_download: bool = False
    max_workers: int = 4

    def __post_init__(self) -> None:
        """Validate download-related parameters"""
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be > 0")

        if self.retry_count < 1:
            raise ValueError("retry_count must be >= 1")

        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be >= 0")

        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")

        if self.max_workers < 1:
            raise ValueError("max_workers must be >= 1")

        if not self.parallel_download and self.max_workers != 4:
            raise ValueError(
                "max_workers is only relevant when parallel_download=True"
            )


# Decompression configuration
@dataclass(frozen=True, slots=True)
class DecompressOptions:
    """
    Options controlling decompression of downloaded archives

    These settings define how compressed files (.Z, .gz, etc.) should be handled after download
    """

    decompress: bool = True
    keep_compressed: bool = False
    overwrite_decompressed: bool = True

    def __post_init__(self) -> None:
        """
        Validate decompression configuration

        The combination decompress=False AND keep_compressed=False
        would effectively discard the downloaded file.
        """
        if not self.decompress and not self.keep_compressed:
            raise ValueError(
                "Invalid options: if decompress=False, keep_compressed should usually be True"
            )


# Unified configuration object
@dataclass(frozen=True, slots=True)
class LoadConfig:
    """
    Unified configuration object

    This class group together all configuration components:

    CddisRequest
    AuthConfig
    DownloadOptions
    DecompressOptions
    """

    request: CddisRequest # no dafault
    auth: AuthConfig = field(default_factory=AuthConfig)
    download: DownloadOptions = field(default_factory=DownloadOptions)
    decompress: DecompressOptions = field(default_factory=DecompressOptions)
