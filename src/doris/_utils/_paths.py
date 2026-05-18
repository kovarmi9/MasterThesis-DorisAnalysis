from __future__ import annotations

from pathlib import Path

__all__ = [
    "matches_filters",
    "build_local_path",
]


# Remove .Z/.gz suffix from filename
def _strip_compression_suffix(name: str) -> str:
    if name.endswith(".gz"):
        return name[:-3]
    if name.endswith(".Z"):
        return name[:-2]
    return name


# Check if filename matches solution/satellite
def matches_filters(
    filename: str,
    *,
    solution: str | None = None,
    satellite: str | None = None,
) -> bool:
    if solution is None and satellite is None:
        return True

    parts = _strip_compression_suffix(filename).split("_")
    if len(parts) < 2:
        return False

    file_solution = parts[0].strip().lower()
    file_satellite = parts[1].strip().lower()

    if solution is not None and file_solution != solution.strip().lower():
        return False

    if satellite is not None and file_satellite != satellite.strip().lower():
        return False

    return True


# Build local path: dir/solution/satellite/filename
def build_local_path(
    local_dir: Path,
    filename: str,
    *,
    solution: str | None = None,
    satellite: str | None = None,
) -> Path:
    target_dir = local_dir

    if solution is not None:
        target_dir = target_dir / solution.strip().lower()

    if satellite is not None:
        target_dir = target_dir / satellite.strip().lower()

    return target_dir / filename
