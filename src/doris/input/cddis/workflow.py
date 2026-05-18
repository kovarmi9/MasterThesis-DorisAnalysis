from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from tqdm.auto import tqdm

from ._authentication import get_authenticated_session
from ._client import DatasetIndex, fetch_and_download_dataset
from ._config import (
    AuthConfig,
    CddisRequest,
    DecompressOptions,
    DownloadOptions,
    LoadConfig,
)
from doris._utils._decompress import DecompressionError, decompress_file

log = logging.getLogger(__name__)


__all__ = [
    "CddisWorkflowResult",
    "run_cddis_workflow",
    "download_from_cddis",
]


# Workflow result container
@dataclass(frozen=True, slots=True)
class CddisWorkflowResult:
    dataset_index: DatasetIndex
    downloaded_paths: list[Path]
    decompressed_paths: list[Path]


# Run full workflow from config
def run_cddis_workflow(
    cfg: LoadConfig,
) -> CddisWorkflowResult:
    log.info("Workflow: starting authentication.")
    session = get_authenticated_session(cfg.auth)

    log.info("Workflow: starting dataset fetch/download.")
    dataset_index, downloaded_paths = fetch_and_download_dataset(cfg, session)

    decompressed_paths: list[Path] = []
    if cfg.decompress.decompress:
        total = len(downloaded_paths)
        log.info("Workflow: starting decompression of %d files.", total)

        verbose = log.isEnabledFor(logging.DEBUG)
        for path in tqdm(downloaded_paths, desc="Decompressing", unit="file", disable=verbose):
            log.debug("Decompressing %s", path.name)

            try:
                out_path = decompress_file(
                    path,
                    keep_compressed=cfg.decompress.keep_compressed,
                    overwrite=cfg.decompress.overwrite_decompressed,
                )
            except DecompressionError as exc:
                log.warning("Skipping decompression for %s: %s", path.name, exc)
                out_path = path

            decompressed_paths.append(out_path)

        log.info("Workflow: decompression finished, %d files created.", len(decompressed_paths))

    log.info("Workflow: finished.")
    return CddisWorkflowResult(
        dataset_index=dataset_index,
        downloaded_paths=downloaded_paths,
        decompressed_paths=decompressed_paths,
    )


# Flat API convenience wrapper
def download_from_cddis(
    *,
    technique: str,
    product: str,
    solution: str,
    subtree: str = "products",
    satellite: str | None = None,
    archive_root: str = "https://cddis.nasa.gov/archive",
    output_root: Path | str = Path("data"),
    token_file: Path | str = Path("token.txt"),
    login_file: Path | str = Path("login.txt"),
    allow_interactive: bool = True,
    save_login_on_success: bool = True,
    overwrite: bool = True,
    create_dirs: bool = True,
    fail_on_missing: bool = False,
    keep_md5_file: bool = True,
    request_timeout: float = 60.0,
    retry_count: int = 3,
    retry_delay_seconds: float = 2.0,
    chunk_size: int = 1024 * 64,
    parallel_download: bool = False,
    max_workers: int = 4,
    decompress: bool = True,
    keep_compressed: bool = False,
    overwrite_decompressed: bool = True,
) -> CddisWorkflowResult:
    """
    Convenience wrapper for using the CDDIS workflow as a library.
    """
    cfg = LoadConfig(
        request=CddisRequest(
            technique=technique,
            subtree=subtree,
            product=product,
            solution=solution,
            satellite=satellite,
            archive_root=archive_root,
            output_root=output_root,
        ),
        auth=AuthConfig(
            token_file=token_file,
            login_file=login_file,
            allow_interactive=allow_interactive,
            save_login_on_success=save_login_on_success,
        ),
        download=DownloadOptions(
            overwrite=overwrite,
            create_dirs=create_dirs,
            fail_on_missing=fail_on_missing,
            keep_md5_file=keep_md5_file,
            request_timeout=request_timeout,
            retry_count=retry_count,
            retry_delay_seconds=retry_delay_seconds,
            chunk_size=chunk_size,
            parallel_download=parallel_download,
            max_workers=max_workers,
        ),
        decompress=DecompressOptions(
            decompress=decompress,
            keep_compressed=keep_compressed,
            overwrite_decompressed=overwrite_decompressed,
        ),
    )

    return run_cddis_workflow(cfg)


