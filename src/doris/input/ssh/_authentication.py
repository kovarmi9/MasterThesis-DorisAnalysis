from __future__ import annotations

import logging
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Literal

from ._config import SshAuthOptions

log = logging.getLogger(__name__)


# SSH authentication input error
class SshAuthenticationInputError(RuntimeError):
    """Raised when SSH authentication input is missing or invalid."""


# Resolved SSH auth credentials
@dataclass(frozen=True, slots=True)
class ResolvedSshAuth:
    source: Literal["provided_password", "login_file", "interactive", "none"]
    username: str
    password: str | None = None


# Read credentials from login file
def read_login_file(path: Path) -> tuple[str, str] | None:
    if not path.exists():
        return None

    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not lines:
        return None

    if len(lines) >= 2 and "=" not in lines[0] and "=" not in lines[1]:
        username = lines[0].strip()
        password = lines[1].strip()
        if username and password:
            return username, password

    username: str | None = None
    password: str | None = None

    for line in lines:
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lower()
        value = value.strip()

        if key == "username":
            username = value
        elif key == "password":
            password = value

    if username and password:
        return username, password

    return None


# Save credentials to login file
def save_login_file(path: Path, username: str, password: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{username}\n{password}\n", encoding="utf-8")


# Prompt user for SSH password
def prompt_for_password(
    username: str,
    host: str,
) -> str:
    log.info("Authentication: waiting for interactive SSH password.")
    password = getpass(f"SSH password for {username}@{host}: ").strip()

    if not password:
        raise SshAuthenticationInputError("SSH password must not be empty.")

    log.info("Authentication: interactive SSH password entered.")
    return password


# Resolve SSH auth from available sources
def resolve_ssh_auth(
    *,
    host: str,
    username: str,
    password: str | None,
    auth_options: SshAuthOptions,
) -> ResolvedSshAuth:
    log.info("Authentication: resolving authentication source.")

    if password is not None:
        log.info("Authentication: using provided SSH password.")
        return ResolvedSshAuth(
            source="provided_password",
            username=username,
            password=password,
        )

    log.info("Authentication: checking SSH login file.")
    credentials = read_login_file(auth_options.login_file)
    if credentials is not None:
        stored_username, stored_password = credentials
        if stored_username == username:
            log.info("Authentication: using SSH login file %s.", auth_options.login_file)
            return ResolvedSshAuth(
                source="login_file",
                username=username,
                password=stored_password,
            )

        log.info(
            "Authentication: ignoring SSH login file %s for different user '%s'.",
            auth_options.login_file,
            stored_username,
        )

    if auth_options.allow_interactive:
        log.info("Authentication: no file-based SSH auth found, using interactive password prompt.")
        resolved_password = prompt_for_password(username, host)
        return ResolvedSshAuth(
            source="interactive",
            username=username,
            password=resolved_password,
        )

    return ResolvedSshAuth(
        source="none",
        username=username,
        password=None,
    )
