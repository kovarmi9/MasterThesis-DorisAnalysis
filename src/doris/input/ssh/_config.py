from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path


# SSH connection configuration
@dataclass(slots=True)
class SshConfig:
    host: str
    username: str
    port: int = 22

    password: str | None = None
    private_key_path: Path | None = None
    private_key_passphrase: str | None = None

    timeout: float = 30.0
    allow_unknown_host_keys: bool = False


# SSH authentication options
@dataclass(slots=True)
class SshAuthOptions:
    login_file: Path = Path("login_ssh.txt")
    allow_interactive: bool = True
    save_login_on_success: bool = True


# SSH download request parameters
@dataclass(slots=True)
class SshDownloadRequest:
    remote_dir: str
    local_dir: Path
    filename_pattern: str | None = None
    solution: str | None = None
    satellite: str | None = None
    overwrite: bool = True


# SSH decompression options
@dataclass(slots=True)
class SshDecompressOptions:
    decompress: bool = True
    keep_compressed: bool = False
    overwrite_decompressed: bool = True

    def __post_init__(self) -> None:
        if not self.decompress and not self.keep_compressed:
            warnings.warn(
                "decompress=False and keep_compressed=False: files will be copied as-is.",
                UserWarning,
                stacklevel=2,
            )
