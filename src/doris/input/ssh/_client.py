from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import fnmatch
import posixpath
import stat

import paramiko

from ._config import SshConfig


# Base SSH exception
class SshError(Exception):
    """Base exception for SSH operations."""


# SSH connection failure
class SshConnectionError(SshError):
    """Could not establish SSH connection."""


# SSH authentication failure
class SshAuthenticationError(SshError):
    """SSH authentication failed."""


# Remote path not found
class SshRemotePathError(SshError):
    """Remote path does not exist."""


# Remote file entry descriptor
@dataclass(slots=True)
class RemoteEntry:
    path: str
    name: str
    is_dir: bool
    size: int


# SSH/SFTP client wrapper over paramiko
class SshClient:
    def __init__(self, config: SshConfig) -> None:
        self._config = config
        self._ssh: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None

    def connect(self) -> None:
        if self._ssh is not None and self._sftp is not None:
            return

        ssh = paramiko.SSHClient()

        if self._config.allow_unknown_host_keys:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            ssh.load_system_host_keys()

        try:
            connect_kwargs: dict[str, object] = {
                "hostname": self._config.host,
                "port": self._config.port,
                "username": self._config.username,
                "timeout": self._config.timeout,
            }

            if self._config.private_key_path is not None:
                connect_kwargs["key_filename"] = str(self._config.private_key_path)
                if self._config.private_key_passphrase is not None:
                    connect_kwargs["passphrase"] = self._config.private_key_passphrase
            elif self._config.password is not None:
                connect_kwargs["password"] = self._config.password

            ssh.connect(**connect_kwargs)
            sftp = ssh.open_sftp()

        except paramiko.AuthenticationException as exc:
            ssh.close()
            raise SshAuthenticationError(
                f"SSH authentication failed for user '{self._config.username}'."
            ) from exc
        except Exception as exc:
            ssh.close()
            raise SshConnectionError(
                f"Could not connect to {self._config.host}:{self._config.port}."
            ) from exc

        self._ssh = ssh
        self._sftp = sftp

    def close(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None

        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    def __enter__(self) -> "SshClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            raise SshConnectionError("SFTP client is not connected.")
        return self._sftp

    def list_dir(self, remote_dir: str) -> list[RemoteEntry]:
        try:
            attrs = self.sftp.listdir_attr(remote_dir)
        except FileNotFoundError as exc:
            raise SshRemotePathError(
                f"Remote directory does not exist: {remote_dir}"
            ) from exc

        entries: list[RemoteEntry] = []
        for item in attrs:
            item_path = posixpath.join(remote_dir, item.filename)
            entries.append(
                RemoteEntry(
                    path=item_path,
                    name=item.filename,
                    is_dir=stat.S_ISDIR(item.st_mode),
                    size=item.st_size,
                )
            )

        return entries

    def list_files(
        self,
        remote_dir: str,
        *,
        filename_pattern: str | None = None,
    ) -> list[RemoteEntry]:
        files: list[RemoteEntry] = []

        for entry in self.list_dir(remote_dir):
            if entry.is_dir:
                continue

            if filename_pattern is not None and not fnmatch.fnmatch(
                entry.name, filename_pattern
            ):
                continue

            files.append(entry)

        return files

    def download_file(
        self,
        remote_path: str,
        local_path: Path,
        *,
        overwrite: bool = True,
    ) -> tuple[Path, bool]:
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if local_path.exists() and not overwrite:
            return local_path, False

        try:
            self.sftp.get(remote_path, str(local_path))
        except FileNotFoundError as exc:
            raise SshRemotePathError(
                f"Remote file does not exist: {remote_path}"
            ) from exc

        return local_path, True
