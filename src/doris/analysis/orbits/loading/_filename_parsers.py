from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta, datetime
from pathlib import Path
import re


# ============================================================
# Public data model
# ============================================================

@dataclass(frozen=True, slots=True)
class FilenameInfo:
    """
    Parsed information derived only from the filename.

    Parameters
    ----------
    path : Path
        Original file path.

    start : date | None
        Start date inferred from the filename.

    end : date | None
        End date inferred from the filename.

    provider : str | None
        Data provider / solution family inferred from the filename.

    satellite : str | None
        Satellite identifier inferred from the filename.

    version : str | None
        Version inferred from the filename.

    scheme : str | None
        Name of the filename scheme that matched.
    """
    path: Path
    start: date | None
    end: date | None
    provider: str | None = None
    satellite: str | None = None
    version: str | None = None
    scheme: str | None = None


# ============================================================
# Regex patterns
# ============================================================

# Example:
# ssasrl20.b22002.e22010.D__.sp3.001
_CDDIS_YYDDD_RE = re.compile(r"\.b(?P<start>\d{5})\.e(?P<end>\d{5})\.", re.IGNORECASE)

# Example:
# GOP_cs2_240101_240101_V99.sp3
_GOP_YYMMDD_RE = re.compile(
    r"^(?P<provider>[A-Za-z0-9]+)_(?P<satellite>[A-Za-z0-9]+)_(?P<start>\d{6})_(?P<end>\d{6})_(?P<version>V\d+)\.sp3$",
    re.IGNORECASE,
)


# ============================================================
# Low-level date helpers
# ============================================================

def _yyddd_to_date(value: str) -> date:
    """
    Convert YYDDD (2-digit year + day-of-year) to Python date.

    Example
    -------
    22002 -> 2022-01-02
    """
    if len(value) != 5 or not value.isdigit():
        raise ValueError(f"Invalid YYDDD value: {value!r}")

    yy = int(value[:2])
    ddd = int(value[2:])

    year = 2000 + yy
    return date(year, 1, 1) + timedelta(days=ddd - 1)


def _yymmdd_to_date(value: str) -> date:
    """
    Convert YYMMDD to Python date.

    Example
    -------
    240101 -> 2024-01-01
    """
    if len(value) != 6 or not value.isdigit():
        raise ValueError(f"Invalid YYMMDD value: {value!r}")

    return datetime.strptime(value, "%y%m%d").date()


# ============================================================
# Individual filename parsers
# ============================================================

def parse_cddis_filename(path: Path) -> FilenameInfo | None:
    """
    Parse filenames carrying coverage in .bYYDDD.eYYDDD. style.

    Example
    -------
    ssasrl20.b22002.e22010.D__.sp3.001
    """
    match = _CDDIS_YYDDD_RE.search(path.name)
    if not match:
        return None

    start_raw = match.group("start")
    end_raw = match.group("end")

    return FilenameInfo(
        path=path,
        start=_yyddd_to_date(start_raw),
        end=_yyddd_to_date(end_raw),
        provider=None,
        satellite=None,
        version=None,
        scheme="cddis_yyddd",
    )


def parse_gop_filename(path: Path) -> FilenameInfo | None:
    """
    Parse GOP-like filenames in provider_satellite_YYMMDD_YYMMDD_Vxx.sp3 style.

    Example
    -------
    GOP_cs2_240101_240101_V99.sp3
    """
    match = _GOP_YYMMDD_RE.match(path.name)
    if not match:
        return None

    return FilenameInfo(
        path=path,
        start=_yymmdd_to_date(match.group("start")),
        end=_yymmdd_to_date(match.group("end")),
        provider=match.group("provider").upper(),
        satellite=match.group("satellite").lower(),
        version=match.group("version").upper(),
        scheme="gop_yymmdd",
    )


# ============================================================
# Central dispatch
# ============================================================

def get_filename_parsers():
    """
    Return parser callables in matching order.

    The order matters:
    more specific patterns should generally come first.
    """
    return (
        parse_gop_filename,
        parse_cddis_filename,
    )


def parse_filename_info(path: Path) -> FilenameInfo | None:
    """
    Try all known filename parsers and return the first successful match.

    Parameters
    ----------
    path : Path
        File path whose name should be parsed.

    Returns
    -------
    FilenameInfo | None
        Parsed filename info, or None if no known scheme matches.
    """
    for parser in get_filename_parsers():
        info = parser(path)
        if info is not None:
            return info
    return None