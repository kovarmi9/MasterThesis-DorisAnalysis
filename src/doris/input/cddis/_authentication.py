from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Literal

import requests
from requests.auth import HTTPBasicAuth

from ._config import AuthConfig

log = logging.getLogger(__name__)


# Exception for AuthenticationError
class AuthenticationError(RuntimeError):
    """Raised when authentication input is missing or invalid"""


# Helper data structure
@dataclass(frozen=True, slots=True)
class ResolvedAuth:
    """
    Stores resolved authentication information

    method:
        - "token"       -> Bearer token will be used
        - "credentials" -> username/password will be used
    """

    method: Literal["token", "credentials"]
    token: str | None = None
    username: str | None = None
    password: str | None = None


# File helpers
def read_token_file(path: Path) -> str | None:
    """
    Read a bearer token from a text file

    Expected format:
        Entire file contains the token as plain text

    Returns None if the file does not exist or is empty
    """
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8").strip()
    return content or None


# Read login from txt file
def read_login_file(path: Path) -> tuple[str, str] | None:
    """
    Read username/password from a login file.

    Supported formats
    -----------------
    Format A:
        line 1 = username
        line 2 = password

    Format B:
        username=my_username
        password=my_password
    """
    if not path.exists():
        return None

    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not lines:
        return None

    # Plain 2-line format
    if len(lines) >= 2 and "=" not in lines[0] and "=" not in lines[1]:
        username = lines[0].strip()
        password = lines[1].strip()
        if username and password:
            return username, password

    # key=value format
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


# Save login into txt file
def save_login_file(path: Path, username: str, password: str) -> None:
    """
    Save username/password to a login file.

    File format:
        line 1 = username
        line 2 = password
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{username}\n{password}\n", encoding="utf-8")


# Interactive helpers
def prompt_for_credentials() -> tuple[str, str]:
    """
    Prompt the user for username and password

    Password input is hidden using getpass()
    """
    log.info("Authentication: waiting for interactive credentials.")
    username = input("Earthdata username: ").strip()
    password = getpass("Earthdata password: ").strip()

    if not username:
        raise AuthenticationError("Username must not be empty.")
    if not password:
        raise AuthenticationError("Password must not be empty.")

    log.info("Authentication: interactive credentials entered.")
    return username, password


# NETRC helpers
def get_netrc_path() -> Path:
    """
    Return the Windows-friendly Earthdata netrc path

    On Windows, _netrc in the user's home directory is the usual choice
    """
    return Path.home() / "_netrc"


# Write credentials to netrc file
def write_netrc_file(
    path: Path,
    username: str,
    password: str,
) -> Path:
    """
    Write a minimal _netrc file for Earthdata
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    content = (
        "machine urs.earthdata.nasa.gov\n"
        f"login {username}\n"
        f"password {password}\n"
    )

    path.write_text(content, encoding="utf-8")
    log.info("Authentication: wrote netrc file to %s.", path)
    return path


# Session helpers
def create_session() -> requests.Session:
    """
    Create a fresh requests session with a simple default User-Agent
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "cddis-loader/0.1 (+python requests)",
        }
    )

    # Allow requests to use environment/netrc settings.
    session.trust_env = True
    log.info("Authentication: created HTTP session.")
    return session


# Attach bearer token to session
def configure_session_with_token(
    session: requests.Session,
    token: str,
) -> requests.Session:
    """
    Attach a bearer token to the session.
    """
    token = token.strip()
    if not token:
        raise AuthenticationError("Token must not be empty.")

    session.headers["Authorization"] = f"Bearer {token}"
    log.info("Authentication: configured session with bearer token.")
    return session


# Configure session with username/password
def configure_session_with_credentials(
    session: requests.Session,
    username: str,
    password: str,
) -> requests.Session:
    """
    Configure a session for Earthdata access

    What this does:
    - stores credentials in a Windows-friendly _netrc file
    - exposes that file through NETRC env var
    - also sets HTTP basic auth as a fallback

    This gives requests the best chance to follow the Earthdata flow correctly while still keeping the API simple for the caller
    """
    username = username.strip()
    password = password.strip()

    if not username:
        raise AuthenticationError("Username must not be empty.")
    if not password:
        raise AuthenticationError("Password must not be empty.")

    netrc_path = get_netrc_path()
    write_netrc_file(netrc_path, username, password)

    # Tell requests explicitly where the file is.
    os.environ["NETRC"] = str(netrc_path)

    # Keep both enabled:
    # - trust_env allows requests/netrc integration
    # - auth serves as an extra fallback
    session.trust_env = True
    session.auth = HTTPBasicAuth(username, password)

    log.info("Authentication: configured session with username/password.")
    return session


# Authentication resolution
def resolve_auth(
    config: AuthConfig,
) -> ResolvedAuth:
    """
    Resolve authentication material in this order:

    1. token_file
    2. login_file
    3. interactive prompt (if allowed)
    """
    log.info("Authentication: checking token file.")
    token = read_token_file(config.token_file)
    if token:
        log.info("Authentication: using token file %s.", config.token_file)
        return ResolvedAuth(method="token", token=token)

    log.info("Authentication: checking login file.")
    credentials = read_login_file(config.login_file)
    if credentials is not None:
        username, password = credentials
        log.info("Authentication: using login file %s.", config.login_file)
        return ResolvedAuth(
            method="credentials",
            username=username,
            password=password,
        )

    if config.allow_interactive:
        log.info("Authentication: no file-based auth found, using interactive prompt.")
        username, password = prompt_for_credentials()

        if config.save_login_on_success:
            save_login_file(config.login_file, username, password)
            log.info("Authentication: saved credentials to %s.", config.login_file)

        return ResolvedAuth(
            method="credentials",
            username=username,
            password=password,
        )

    raise AuthenticationError(
        "No usable authentication source found. "
        "Expected token.txt, login.txt, or interactive input."
    )


# Build authenticated session from config
def get_authenticated_session(
    config: AuthConfig,
) -> requests.Session:
    """
    Build a configured requests.Session from the available auth source

    Note:
        This only prepares the session. True server-side validation happens
        when the session accesses a protected CDDIS resource
    """
    log.info("Authentication: resolving authentication source.")
    resolved = resolve_auth(config)

    log.info("Authentication: creating session.")
    session = create_session()

    if resolved.method == "token":
        log.info("Authentication: applying token-based authentication.")
        return configure_session_with_token(
            session,
            resolved.token or "",
        )

    log.info("Authentication: applying credential-based authentication.")
    return configure_session_with_credentials(
        session,
        resolved.username or "",
        resolved.password or "",
    )


# Optional debug helpers
def describe_auth_source(config: AuthConfig) -> str:
    """
    Return a short readable description of which auth source will be used
    """
    token = read_token_file(config.token_file)
    if token:
        return f"token file: {config.token_file}"

    credentials = read_login_file(config.login_file)
    if credentials is not None:
        return f"login file: {config.login_file}"

    if config.allow_interactive:
        return "interactive prompt"

    return "no authentication source available"
