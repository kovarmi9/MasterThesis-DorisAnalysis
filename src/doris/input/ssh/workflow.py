from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from tqdm.auto import tqdm

from doris._utils._decompress import DecompressionError, decompress_file
from doris._utils._paths import matches_filters, build_local_path

from ._authentication import (
    ResolvedSshAuth,
    SshAuthenticationInputError,
    resolve_ssh_auth,
    save_login_file,
)
from ._client import SshAuthenticationError, SshClient
from ._config import (
    SshAuthOptions,
    SshConfig,
    SshDecompressOptions,
    SshDownloadRequest,
)

__all__ = [
    "DownloadedFile",
    "SshDownloadResult",
    "run_ssh_workflow",
    "download_from_ssh",
]

log = logging.getLogger(__name__)



# Single downloaded file descriptor
@dataclass(slots=True)
class DownloadedFile:
    remote_path: str
    local_path: Path
    size: int
    downloaded: bool


# SSH workflow result container
@dataclass(slots=True)
class SshDownloadResult:
    files: list[DownloadedFile]
    decompressed_paths: list[Path]
    decompression_performed: bool

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def count_downloaded(self) -> int:
        return sum(1 for file in self.files if file.downloaded)

    @property
    def count_skipped_existing(self) -> int:
        return sum(1 for file in self.files if not file.downloaded)

    @property
    def count_decompressed(self) -> int:
        if not self.decompression_performed:
            return 0
        return len(self.decompressed_paths)


# Flat API convenience wrapper
def download_from_ssh(
    host: str,
    username: str,
    remote_dir: str,
    local_dir: Path,
    *,
    port: int = 22,
    password: str | None = None,
    private_key_path: Path | None = None,
    private_key_passphrase: str | None = None,
    filename_pattern: str | None = None,
    solution: str | None = None,
    satellite: str | None = None,
    login_file: Path = Path("login_ssh.txt"),
    allow_interactive: bool = True,
    save_login_on_success: bool = True,
    overwrite: bool = True,
    timeout: float = 30.0,
    allow_unknown_host_keys: bool = False,
    decompress: bool = True,
    keep_compressed: bool = False,
    overwrite_decompressed: bool = True,
) -> SshDownloadResult:
    log.info("Workflow: starting authentication.")

    auth_options = SshAuthOptions(
        login_file=login_file,
        allow_interactive=allow_interactive,
        save_login_on_success=save_login_on_success,
    )

    resolved_auth: ResolvedSshAuth | None = None
    if private_key_path is None:
        resolved_auth = resolve_ssh_auth(
            host=host,
            username=username,
            password=password,
            auth_options=auth_options,
        )
        if resolved_auth.source == "none":
            raise SshAuthenticationInputError(
                "No usable SSH authentication source found. "
                "Provide password, login_file, or allow interactive input."
            )

    config = SshConfig(
        host=host,
        username=username,
        port=port,
        password=resolved_auth.password if resolved_auth is not None else password,
        private_key_path=private_key_path,
        private_key_passphrase=private_key_passphrase,
        timeout=timeout,
        allow_unknown_host_keys=allow_unknown_host_keys,
    )

    request = SshDownloadRequest(
        remote_dir=remote_dir,
        local_dir=local_dir,
        filename_pattern=filename_pattern,
        solution=solution,
        satellite=satellite,
        overwrite=overwrite,
    )

    decompress_options = SshDecompressOptions(
        decompress=decompress,
        keep_compressed=keep_compressed,
        overwrite_decompressed=overwrite_decompressed,
    )

    def save_resolved_login(auth: ResolvedSshAuth | None) -> None:
        if auth is None:
            return
        if auth.source not in {"interactive", "provided_password"}:
            return
        if not auth_options.save_login_on_success:
            return
        if auth.password is None:
            return

        save_login_file(
            auth_options.login_file,
            auth.username,
            auth.password,
        )
        log.info("Authentication: saved SSH credentials to %s.", auth_options.login_file)

    try:
        result = run_ssh_workflow(config, request, decompress_options)
    except SshAuthenticationError:
        should_retry_interactively = (
            private_key_path is None
            and resolved_auth is not None
            and resolved_auth.source == "login_file"
            and auth_options.allow_interactive
            and password is None
        )
        if not should_retry_interactively:
            raise

        log.info("Authentication: stored SSH login failed, retrying with interactive password.")

        resolved_auth = resolve_ssh_auth(
            host=host,
            username=username,
            password=None,
            auth_options=SshAuthOptions(
                login_file=auth_options.login_file,
                allow_interactive=True,
                save_login_on_success=auth_options.save_login_on_success,
            ),
        )
        config.password = resolved_auth.password

        result = run_ssh_workflow(config, request, decompress_options)
        save_resolved_login(resolved_auth)
        return result

    save_resolved_login(resolved_auth)
    return result


# Run full SSH workflow from config
def run_ssh_workflow(
    config: SshConfig,
    request: SshDownloadRequest,
    decompress_options: SshDecompressOptions | None = None,
) -> SshDownloadResult:
    if decompress_options is None:
        decompress_options = SshDecompressOptions()

    downloaded: list[DownloadedFile] = []
    decompressed_paths: list[Path] = []

    log.info("Workflow: connecting to SSH server.")

    with SshClient(config) as client:
        log.info("Workflow: listing remote files.")

        remote_files = client.list_files(
            request.remote_dir,
            filename_pattern=request.filename_pattern,
        )
        remote_files = [
            entry
            for entry in remote_files
            if matches_filters(
                entry.name,
                solution=request.solution,
                satellite=request.satellite,
            )
        ]

        total = len(remote_files)
        log.info("Workflow: found %d files.", total)
        log.info("Workflow: starting file download.")

        verbose = log.isEnabledFor(logging.DEBUG)
        for remote_entry in tqdm(remote_files, desc="Downloading", unit="file", disable=verbose):
            local_path = build_local_path(
                request.local_dir,
                remote_entry.name,
                solution=request.solution,
                satellite=request.satellite,
            )

            if local_path.exists() and not request.overwrite:
                log.debug("Skipping existing file: %s", remote_entry.name)
            else:
                log.debug("Downloading %s", remote_entry.name)

            _, downloaded_now = client.download_file(
                remote_path=remote_entry.path,
                local_path=local_path,
                overwrite=request.overwrite,
            )

            if downloaded_now:
                log.debug("Finished %s", remote_entry.name)

            downloaded_file = DownloadedFile(
                remote_path=remote_entry.path,
                local_path=local_path,
                size=remote_entry.size,
                downloaded=downloaded_now,
            )

            downloaded.append(downloaded_file)

    # ---------------------------------------------------------
    # Optional decompression AFTER all downloads are finished
    # ---------------------------------------------------------

    if decompress_options.decompress:
        total = len(downloaded)
        log.info("Workflow: starting decompression of %d files.", total)

        verbose = log.isEnabledFor(logging.DEBUG)
        for file in tqdm(downloaded, desc="Decompressing", unit="file", disable=verbose):
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

    else:
        decompressed_paths = []

    log.info("Workflow: finished.")

    return SshDownloadResult(
        files=downloaded,
        decompressed_paths=decompressed_paths,
        decompression_performed=decompress_options.decompress,
    )
