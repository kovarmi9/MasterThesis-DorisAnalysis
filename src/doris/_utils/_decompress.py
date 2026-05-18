from __future__ import annotations

import gzip
import logging
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "DecompressionError",
    "decompress_file",
    "decompress_many",
]

import unlzw3

log = logging.getLogger(__name__)


# Decompression failure exception
class DecompressionError(RuntimeError):
    """Raised when a compressed file cannot be decompressed."""


# Trim decompressed output file path
def _trim_output_path(
    input_path: Path,
    output_dir: Path | None = None,
) -> Path:
    """
    Trim the output path for a decompressed file.

    Supported suffixes:
    - .Z
    - .gz
    """

    name = input_path.name

    if name.endswith(".Z"):
        output_name = name[:-2]
    elif name.endswith(".gz"):
        output_name = name[:-3]
    else:
        raise DecompressionError(
            f"Unsupported compressed file extension: {input_path.name}"
        )

    target_dir = output_dir if output_dir is not None else input_path.parent
    return target_dir / output_name


# Read file as raw bytes
def _read_binary_file(path: Path) -> bytes:
    """Read a file as bytes."""
    try:
        return path.read_bytes()
    except OSError as exc:
        raise DecompressionError(f"Could not read file: {path}") from exc


# Write raw bytes to file
def _write_binary_file(path: Path, data: bytes) -> Path:
    """Write bytes to a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as exc:
        raise DecompressionError(f"Could not write file: {path}") from exc

    return path


# Decompress raw bytes (.Z or .gz)
def _decompress_bytes(data: bytes) -> bytes:
    """
    Decompress raw bytes.

    Strategy
    --------
    1. Try classic UNIX .Z via unlzw3
    2. Fall back to gzip
    """

    try:
        return unlzw3.unlzw(data)
    except Exception:
        pass

    try:
        return gzip.decompress(data)
    except Exception as exc:
        raise DecompressionError(
            "Could not decompress data using unlzw3 or gzip."
        ) from exc


# Decompress single file to disk
def decompress_file(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    keep_compressed: bool = False,
    overwrite: bool = False,
) -> Path:
    """
    Decompress a single file and return the decompressed file path.
    """

    input_path = Path(input_path)
    output_dir = None if output_dir is None else Path(output_dir)

    if not input_path.exists():
        raise DecompressionError(f"Input file does not exist: {input_path}")

    output_path = _trim_output_path(input_path, output_dir)

    if output_path.exists() and not overwrite:
        return output_path

    raw_data = _read_binary_file(input_path)
    decompressed_data = _decompress_bytes(raw_data)

    _write_binary_file(output_path, decompressed_data)

    if not keep_compressed:
        try:
            input_path.unlink()
        except OSError as exc:
            raise DecompressionError(
                f"Decompression succeeded but could not remove {input_path}"
            ) from exc

    return output_path

# Decompress multiple files at once
def decompress_many(
    paths: Iterable[Path],
    *,
    keep_compressed: bool = True,
    overwrite: bool = False,
) -> list[Path]:
    """
    Decompress multiple files.

    Files with unsupported extensions are skipped with a warning.
    """

    results: list[Path] = []

    for path in paths:

        try:
            out = decompress_file(
                path,
                keep_compressed=keep_compressed,
                overwrite=overwrite,
            )
            results.append(out)

        except DecompressionError as exc:
            # file is not compressed, skip it
            log.warning("Skipping decompression for %s: %s", path.name, exc)

            results.append(path)

    return results