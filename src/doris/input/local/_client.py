from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
import shutil


# Local file entry descriptor
@dataclass(frozen=True, slots=True)
class LocalEntry:
    path: Path
    name: str
    size: int


# List files in source directory
def list_files(
    source_dir: Path,
    filename_pattern: str | None = None,
) -> list[LocalEntry]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    entries: list[LocalEntry] = []

    for path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue

        if filename_pattern is not None and not fnmatch(path.name, filename_pattern):
            continue

        entries.append(
            LocalEntry(
                path=path,
                name=path.name,
                size=path.stat().st_size,
            )
        )

    return entries


# Copy single file to destination
def copy_file(
    source_path: Path,
    local_path: Path,
    *,
    overwrite: bool = True,
) -> tuple[Path, bool]:
    if local_path.exists() and not overwrite:
        return local_path, False

    local_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, local_path)
    return local_path, True
