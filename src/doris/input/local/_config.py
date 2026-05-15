from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path


# Local copy request parameters
@dataclass(slots=True)
class LocalCopyRequest:
    source_dir: Path
    local_dir: Path
    filename_pattern: str | None = None
    solution: str | None = None
    satellite: str | None = None
    overwrite: bool = True


# Local decompression options
@dataclass(slots=True)
class LocalDecompressOptions:
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
