from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from tqdm.auto import tqdm

from doris._utils._decompress import DecompressionError, decompress_file
from doris._utils._paths import matches_filters, build_local_path

from ._client import copy_file, list_files
from ._config import LocalCopyRequest, LocalDecompressOptions

__all__ = [
    "CopiedFile",
    "LocalCopyResult",
    "run_local_workflow",
    "copy_from_local",
]

log = logging.getLogger(__name__)



# Single copied file descriptor
@dataclass(slots=True)
class CopiedFile:
    source_path: Path
    local_path: Path
    size: int
    copied: bool


# Local workflow result container
@dataclass(slots=True)
class LocalCopyResult:
    files: list[CopiedFile]
    decompressed_paths: list[Path]
    decompression_performed: bool

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def count_copied(self) -> int:
        return sum(1 for file in self.files if file.copied)

    @property
    def count_skipped_existing(self) -> int:
        return sum(1 for file in self.files if not file.copied)

    @property
    def count_decompressed(self) -> int:
        if not self.decompression_performed:
            return 0
        return len(self.decompressed_paths)


# Flat API convenience wrapper
def copy_from_local(
    source_dir: Path,
    local_dir: Path,
    *,
    filename_pattern: str | None = None,
    solution: str | None = None,
    satellite: str | None = None,
    overwrite: bool = True,
    decompress: bool = True,
    keep_compressed: bool = False,
    overwrite_decompressed: bool = True,
) -> LocalCopyResult:
    request = LocalCopyRequest(
        source_dir=source_dir,
        local_dir=local_dir,
        filename_pattern=filename_pattern,
        solution=solution,
        satellite=satellite,
        overwrite=overwrite,
    )

    decompress_options = LocalDecompressOptions(
        decompress=decompress,
        keep_compressed=keep_compressed,
        overwrite_decompressed=overwrite_decompressed,
    )

    return run_local_workflow(request, decompress_options)


# Run full local copy workflow
def run_local_workflow(
    request: LocalCopyRequest,
    decompress_options: LocalDecompressOptions | None = None,
) -> LocalCopyResult:
    if decompress_options is None:
        decompress_options = LocalDecompressOptions()

    copied_files: list[CopiedFile] = []
    decompressed_paths: list[Path] = []

    log.info("Workflow: listing source files.")

    source_files = list_files(
        request.source_dir,
        filename_pattern=request.filename_pattern,
    )
    source_files = [
        entry
        for entry in source_files
        if matches_filters(
            entry.name,
            solution=request.solution,
            satellite=request.satellite,
        )
    ]

    total = len(source_files)
    log.info("Workflow: found %d files.", total)
    log.info("Workflow: starting local copy.")

    verbose = log.isEnabledFor(logging.DEBUG)
    for source_entry in tqdm(source_files, desc="Copying", unit="file", disable=verbose):
        local_path = build_local_path(
            request.local_dir,
            source_entry.name,
            solution=request.solution,
            satellite=request.satellite,
        )

        if local_path.exists() and not request.overwrite:
            log.debug("Skipping existing file: %s", source_entry.name)
        else:
            log.debug("Copying %s", source_entry.name)

        _, copied_now = copy_file(
            source_path=source_entry.path,
            local_path=local_path,
            overwrite=request.overwrite,
        )

        if copied_now:
            log.debug("Finished %s", source_entry.name)

        copied_files.append(
            CopiedFile(
                source_path=source_entry.path,
                local_path=local_path,
                size=source_entry.size,
                copied=copied_now,
            )
        )

    if decompress_options.decompress:
        total = len(copied_files)
        log.info("Workflow: starting decompression of %d files.", total)

        verbose = log.isEnabledFor(logging.DEBUG)
        for file in tqdm(copied_files, desc="Decompressing", unit="file", disable=verbose):
            log.debug("Decompressing %s", file.local_path.name)

            try:
                out_path = decompress_file(
                    file.local_path,
                    keep_compressed=decompress_options.keep_compressed,
                    overwrite=decompress_options.overwrite_decompressed,
                )
            except DecompressionError as exc:
                log.warning("Skipping decompression for %s: %s", file.local_path.name, exc)
                out_path = file.local_path

            decompressed_paths.append(out_path)

        log.info("Workflow: decompression finished, %d files processed.", len(decompressed_paths))

    log.info("Workflow: finished.")

    return LocalCopyResult(
        files=copied_files,
        decompressed_paths=decompressed_paths,
        decompression_performed=decompress_options.decompress,
    )
