from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import requests
from tqdm.auto import tqdm

from ._config import CddisRequest, LoadConfig

log = logging.getLogger(__name__)


# Exceptions
class CddisError(RuntimeError):
    """Base exception for CDDIS-related operations."""


# Download failure exception
class CddisDownloadError(CddisError):
    """Raised when a required file cannot be downloaded."""



# Result containers
@dataclass(frozen=True, slots=True)
class DatasetIndex:
    dataset_url: str
    output_dir: Path
    md5_path: Path
    archive_names: list[str]



# Path / URL builders
def build_dataset_url(request: CddisRequest) -> str:
    root = request.archive_root.rstrip("/")
    technique = request.normalized_technique
    subtree = request.normalized_subtree
    rel_path = request.relative_dataset_path
    return f"{root}/{technique}/{subtree}/{rel_path}/"


# Build local output directory path
def build_output_dir(request: CddisRequest) -> Path:
    base = request.output_root.expanduser().resolve()
    return base / request.relative_dataset_path


# Build and create output directory
def ensure_output_dir(request: CddisRequest, create_dirs: bool = True) -> Path:
    out_dir = build_output_dir(request)

    if create_dirs:
        out_dir.mkdir(parents=True, exist_ok=True)

    return out_dir



# Download helpers
def _looks_like_html(content_start: bytes) -> bool:
    """
    Detect the common case where CDDIS returned an HTML login page
    instead of the requested file.
    """
    head = content_start.lstrip().lower()

    return (
        head.startswith(b"<!doctype html")
        or head.startswith(b"<html")
        or b"<title>earthdata" in head
        or b"oauth/authorize" in head
        or b"urs.earthdata.nasa.gov" in head
    )


# Remove partial file silently
def _safe_remove_file(path: Path) -> None:
    """
    Best-effort removal of a partially downloaded file.
    """
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


# Download single file with retries
def _download_to_path(
    session: requests.Session,
    url: str,
    destination: Path,
    *,
    timeout: float,
    overwrite: bool,
    retry_count: int,
    retry_delay_seconds: float,
    chunk_size: int,
) -> Path:
    """
    Download a single file to a specific local path.

    This function explicitly rejects:
    - redirects to Earthdata login
    - HTML pages returned instead of data files

    It also retries transient network failures and removes incomplete files.
    """
    if destination.exists() and not overwrite:
        log.debug("Skipping existing file: %s", destination.name)
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)

    last_error: Exception | None = None

    log.debug("Starting download: %s", destination.name)

    for attempt in range(1, retry_count + 1):
        _safe_remove_file(destination)

        try:
            if retry_count > 1:
                log.debug("Attempt %d/%d: %s", attempt, retry_count, destination.name)

            response = session.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            response.raise_for_status()

            final_url = str(response.url).lower()
            if "urs.earthdata.nasa.gov" in final_url:
                raise CddisDownloadError(
                    f"Authentication redirect detected while downloading {url}. "
                    f"Final URL: {response.url}"
                )

            iterator = response.iter_content(chunk_size=chunk_size)

            try:
                first_chunk = next(iterator)
            except StopIteration:
                first_chunk = b""

            if _looks_like_html(first_chunk):
                raise CddisDownloadError(
                    f"Downloaded HTML instead of data for {url}. "
                    f"Final URL: {response.url}"
                )

            with open(destination, "wb") as f:
                if first_chunk:
                    f.write(first_chunk)

                for chunk in iterator:
                    if chunk:
                        f.write(chunk)

            log.debug("Finished download: %s", destination.name)
            return destination

        except (requests.RequestException, CddisDownloadError) as exc:
            last_error = exc
            _safe_remove_file(destination)

            if attempt < retry_count:
                log.warning("Retrying download (%d/%d failed): %s", attempt, retry_count, destination.name)
                time.sleep(retry_delay_seconds)
            else:
                log.warning("Download failed: %s", destination.name)
                raise CddisDownloadError(
                    f"Failed to download {url} after {retry_count} attempts: {exc}"
                ) from exc

    raise CddisDownloadError(f"Failed to download {url}: {last_error}")


# Download MD5SUMS index file
def download_md5sums(
    cfg: LoadConfig,
    session: requests.Session,
) -> Path:
    dataset_url = build_dataset_url(cfg.request)
    out_dir = ensure_output_dir(cfg.request, create_dirs=cfg.download.create_dirs)

    md5_url = dataset_url + "MD5SUMS"
    md5_path = out_dir / "MD5SUMS"

    log.info("Downloading MD5SUMS index.")

    return _download_to_path(
        session=session,
        url=md5_url,
        destination=md5_path,
        timeout=cfg.download.request_timeout,
        overwrite=cfg.download.overwrite,
        retry_count=cfg.download.retry_count,
        retry_delay_seconds=cfg.download.retry_delay_seconds,
        chunk_size=cfg.download.chunk_size,
    )


# Extract archive filenames from MD5SUMS
def parse_md5sums_for_archives(md5_path: Path) -> list[str]:
    if not md5_path.exists():
        raise CddisDownloadError(f"MD5SUMS file does not exist: {md5_path}")

    archive_names: list[str] = []

    with open(md5_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue

            candidate = parts[-1]
            if candidate.endswith(".Z"):
                archive_names.append(candidate)

    return archive_names


# Download and parse dataset index
def fetch_dataset_index(
    cfg: LoadConfig,
    session: requests.Session,
) -> DatasetIndex:
    dataset_url = build_dataset_url(cfg.request)
    output_dir = ensure_output_dir(cfg.request, create_dirs=cfg.download.create_dirs)
    md5_path = download_md5sums(cfg, session)
    archive_names = parse_md5sums_for_archives(md5_path)

    log.info("Archive index loaded: %d files found.", len(archive_names))

    return DatasetIndex(
        dataset_url=dataset_url,
        output_dir=output_dir,
        md5_path=md5_path,
        archive_names=archive_names,
    )


# Download single archive file
def download_archive_file(
    session: requests.Session,
    file_url: str,
    output_dir: Path,
    *,
    timeout: float,
    overwrite: bool,
    retry_count: int,
    retry_delay_seconds: float,
    chunk_size: int,
) -> Path:
    filename = file_url.rstrip("/").split("/")[-1]
    destination = output_dir / filename

    return _download_to_path(
        session=session,
        url=file_url,
        destination=destination,
        timeout=timeout,
        overwrite=overwrite,
        retry_count=retry_count,
        retry_delay_seconds=retry_delay_seconds,
        chunk_size=chunk_size,
    )


# Clone session for thread safety
def _clone_session(session: requests.Session) -> requests.Session:
    """
    Create a fresh worker session from an already authenticated template session.

    Important:
    - we do NOT share one Session across multiple threads
    - each worker gets its own independent Session
    - auth headers, cookies and basic session settings are copied
    """
    new_session = requests.Session()

    new_session.headers.update(session.headers)
    new_session.cookies.update(session.cookies)
    new_session.auth = session.auth
    new_session.verify = session.verify
    new_session.proxies = session.proxies.copy() if session.proxies else {}
    new_session.cert = session.cert
    new_session.trust_env = session.trust_env

    return new_session


# Download archives one by one
def _download_dataset_archives_sequential(
    cfg: LoadConfig,
    session: requests.Session,
    archive_names: list[str],
    dataset_url: str,
    output_dir: Path,
) -> list[Path]:
    """
    Original sequential implementation.

    This remains the default behaviour unless parallel_download=True
    is explicitly enabled in DownloadOptions.
    """
    downloaded_paths: list[Path] = []

    verbose = log.isEnabledFor(logging.DEBUG)
    for archive_name in tqdm(archive_names, desc="Downloading", unit="file", disable=verbose):
        file_url = dataset_url + archive_name

        log.debug("Processing %s", archive_name)

        try:
            local_path = download_archive_file(
                session=session,
                file_url=file_url,
                output_dir=output_dir,
                timeout=cfg.download.request_timeout,
                overwrite=cfg.download.overwrite,
                retry_count=cfg.download.retry_count,
                retry_delay_seconds=cfg.download.retry_delay_seconds,
                chunk_size=cfg.download.chunk_size,
            )
            downloaded_paths.append(local_path)

        except CddisDownloadError:
            if cfg.download.fail_on_missing:
                raise

            log.warning("Missing or inaccessible file: %s", archive_name)

    return downloaded_paths


# Download archives using thread pool
def _download_dataset_archives_parallel(
    cfg: LoadConfig,
    session: requests.Session,
    archive_names: list[str],
    dataset_url: str,
    output_dir: Path,
) -> list[Path]:
    """
    Parallel implementation using one independent requests.Session per worker.

    HTML/login-page detection still happens inside _download_to_path(),
    so this mode rejects accidental Earthdata HTML responses in exactly
    the same way as the sequential mode.
    """
    downloaded_paths: list[Path] = []
    total = len(archive_names)
    max_workers = min(cfg.download.max_workers, total)

    log.info("Starting parallel download with %d workers.", max_workers)

    def worker(archive_name: str) -> tuple[str, Path | None, Exception | None]:
        worker_session = _clone_session(session)
        file_url = dataset_url + archive_name

        try:
            local_path = download_archive_file(
                session=worker_session,
                file_url=file_url,
                output_dir=output_dir,
                timeout=cfg.download.request_timeout,
                overwrite=cfg.download.overwrite,
                retry_count=cfg.download.retry_count,
                retry_delay_seconds=cfg.download.retry_delay_seconds,
                chunk_size=cfg.download.chunk_size,
            )
            return archive_name, local_path, None

        except Exception as exc:
            return archive_name, None, exc

        finally:
            worker_session.close()

    verbose = log.isEnabledFor(logging.DEBUG)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(worker, archive_name): archive_name
            for archive_name in archive_names
        }

        for future in tqdm(as_completed(futures), total=total, desc="Downloading", unit="file", disable=verbose):
            archive_name = futures[future]
            _, path, error = future.result()

            log.debug("Finished %s", archive_name)

            if error is not None:
                if cfg.download.fail_on_missing:
                    raise CddisDownloadError(
                        f"Failed to download {archive_name}: {error}"
                    ) from error

                log.warning("Missing or inaccessible file: %s", archive_name)
                continue

            if path is not None:
                downloaded_paths.append(path)

    return downloaded_paths


# Download all dataset archives
def download_dataset_archives(
    cfg: LoadConfig,
    session: requests.Session,
    archive_names: list[str],
) -> list[Path]:
    """
    Download all archives listed in archive_names.

    Behaviour:
    - default: sequential download (original behaviour)
    - optional: parallel download when cfg.download.parallel_download=True

    Important:
    This function only downloads archives.
    Decompression still happens later in the workflow exactly as before.
    """
    dataset_url = build_dataset_url(cfg.request)
    output_dir = ensure_output_dir(cfg.request, create_dirs=cfg.download.create_dirs)

    if not archive_names:
        return []

    if cfg.download.parallel_download:
        return _download_dataset_archives_parallel(
            cfg=cfg,
            session=session,
            archive_names=archive_names,
            dataset_url=dataset_url,
            output_dir=output_dir,
        )

    return _download_dataset_archives_sequential(
        cfg=cfg,
        session=session,
        archive_names=archive_names,
        dataset_url=dataset_url,
        output_dir=output_dir,
    )


# Fetch index and download all files
def fetch_and_download_dataset(
    cfg: LoadConfig,
    session: requests.Session,
) -> tuple[DatasetIndex, list[Path]]:
    dataset_index = fetch_dataset_index(cfg, session)
    downloaded_paths = download_dataset_archives(
        cfg,
        session,
        dataset_index.archive_names,
    )
    return dataset_index, downloaded_paths
