from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re

import pandas as pd

__all__ = [
    "read_sp3_to_dataframe",
    "read_sp3_files_to_dataframe",
]

# ============================================================
# Header helpers
# ============================================================

_TIME_SCALE_RE = re.compile(r"\b(GPS|UTC|TAI)\b", re.IGNORECASE)


def _split_header_and_body(lines: list[str]) -> tuple[list[str], list[str]]:
    """
    Split SP3 file into header lines and body lines.

    Header is assumed to end before the first epoch line starting with '*'.
    """
    for i, line in enumerate(lines):
        if line.lstrip().startswith("*"):
            return lines[:i], lines[i:]
    return lines, []


def _extract_time_scale_from_header(header_lines: list[str]) -> str:
    """
    Extract time scale from SP3 header.

    Strategy
    --------
    1. Look first at lines starting with '%c'
    2. Fallback to the rest of the header
    3. Return UNKNOWN if not found
    """
    for line in header_lines:
        if line.lstrip().startswith("%c"):
            match = _TIME_SCALE_RE.search(line)
            if match:
                return match.group(1).upper()

    for line in header_lines:
        match = _TIME_SCALE_RE.search(line)
        if match:
            return match.group(1).upper()

    return "UNKNOWN"


def _extract_coordinate_system_from_header(header_lines: list[str]) -> str:
    """
    Extract coordinate/reference system from SP3 header.
    """
    candidates = ("ITRF", "IGS", "GCRF", "ICRF", "WGS84", "WGS 84")

    for line in header_lines:
        upper_line = line.upper()
        for candidate in candidates:
            if candidate in upper_line:
                return candidate.replace(" ", "")

    return "UNKNOWN"


def _build_time_column_name(header_lines: list[str]) -> str:
    """
    Build time column name based on the SP3 header.
    """
    time_scale = _extract_time_scale_from_header(header_lines)
    return f"MJD_{time_scale}"


# ============================================================
# Time helpers
# ============================================================

def _parse_epoch_line(line: str) -> datetime:
    """
    Parse SP3 epoch line.

    Example
    -------
    *  2023  8 20  0  0  0.00000000
    """
    parts = line.split()

    if len(parts) < 7:
        raise ValueError(f"Invalid epoch line: {line!r}")

    year = int(parts[1])
    month = int(parts[2])
    day = int(parts[3])
    hour = int(parts[4])
    minute = int(parts[5])
    second_float = float(parts[6])

    second = int(second_float)
    microsecond = int(round((second_float - second) * 1_000_000))

    return datetime(year, month, day, hour, minute, second, microsecond)


def _datetime_to_mjd(dt: datetime) -> float:
    """
    Convert datetime to Modified Julian Date (MJD).

    Uses integer Julian Day Number formula to avoid
    precision loss from Unix timestamp conversion.
    Precision: ~8.6 nanoseconds (vs ~10 microseconds with timestamp()).
    """
    y = dt.year
    m = dt.month
    d = dt.day

    # Integer Julian Day Number (Meeus formula, exact)
    a = (14 - m) // 12
    y1 = y + 4800 - a
    m1 = m + 12 * a - 3
    jdn = d + (153 * m1 + 2) // 5 + 365 * y1 + y1 // 4 - y1 // 100 + y1 // 400 - 32045

    # Fractional day from time components
    frac = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond * 1e-6) / 86400.0

    # MJD = JD - 2400000.5; JD = JDN - 0.5 + frac
    return jdn - 2400001 + frac


def _safe_float(value: str) -> float | None:
    """
    Convert SP3 numeric field to float, handling blank or invalid values.
    """
    value = value.strip()
    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        return None


# ============================================================
# SP3 fixed-width parsing
# ============================================================

def _parse_sp3_position_line(line: str) -> tuple[str, float | None, float | None, float | None]:
    """
    Parse fixed-width SP3 position record.

    Standard SP3 position line layout starts like:
    Psss xxxxxxxxxxxxxx yyyyyyyyyyyyyy zzzzzzzzzzzzzz ...

    We only read satellite + X,Y,Z.
    """
    satellite = line[1:4].strip()
    x = _safe_float(line[4:18])
    y = _safe_float(line[18:32])
    z = _safe_float(line[32:46])
    return satellite, x, y, z


def _parse_sp3_velocity_line(line: str) -> tuple[str, float | None, float | None, float | None]:
    """
    Parse fixed-width SP3 velocity record.

    Standard SP3 velocity line layout starts like:
    Vsss vxxxxxxxxxxxxx vyyyyyyyyyyyyy vzzzzzzzzzzzz ...
    """
    satellite = line[1:4].strip()
    vx = _safe_float(line[4:18])
    vy = _safe_float(line[18:32])
    vz = _safe_float(line[32:46])
    return satellite, vx, vy, vz


# ============================================================
# DataFrame finalization helpers
# ============================================================

def _finalize_satellite_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    If the dataframe contains exactly one unique satellite, move it to metadata
    and remove the 'satellite' column. Otherwise keep the column.
    """
    if df.empty or "satellite" not in df.columns:
        return df

    satellites = sorted(df["satellite"].dropna().unique())

    if len(satellites) == 1:
        df.attrs["satellite"] = satellites[0]
        df = df.drop(columns=["satellite"])
    else:
        df.attrs["satellites"] = satellites

    return df


# ============================================================
# Debug helper
# ============================================================

def _count_body_record_types(body_lines: list[str]) -> dict[str, int]:
    counts = {"epoch": 0, "P": 0, "V": 0}

    for raw_line in body_lines:
        stripped = raw_line.lstrip()
        if not stripped:
            continue

        first = stripped[:1].upper()
        if first == "*":
            counts["epoch"] += 1
        elif first == "P":
            counts["P"] += 1
        elif first == "V":
            counts["V"] += 1

    return counts


# ============================================================
# Core reader
# ============================================================

def read_sp3_to_dataframe(path: Path) -> pd.DataFrame:
    """
    Read a single SP3 file and return its contents as a pandas DataFrame.

    Output columns
    --------------
    satellite (only if more than one satellite is present)
    x
    y
    z
    vx
    vy
    vz
    MJD_<TIME_SCALE>

    Notes
    -----
    - Positions are kept in original SP3 units (typically km)
    - Velocities are kept in original SP3 units (typically dm/s)
    - Time scale is read from SP3 header
    - If time scale cannot be found, the column is named MJD_UNKNOWN
    - Coordinate system is stored in df.attrs
    """
    if not path.exists():
        raise FileNotFoundError(f"SP3 file does not exist: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header_lines, body_lines = _split_header_and_body(lines)

    time_scale = _extract_time_scale_from_header(header_lines)
    coordinate_system = _extract_coordinate_system_from_header(header_lines)
    time_column = _build_time_column_name(header_lines)

    counts = _count_body_record_types(body_lines)

    current_epoch: datetime | None = None
    records: dict[tuple[datetime, str], dict] = {}

    for raw_line in body_lines:
        line = raw_line.rstrip("\n")
        stripped = line.lstrip()

        if not stripped:
            continue

        first = stripped[:1].upper()

        if first == "*":
            current_epoch = _parse_epoch_line(stripped)
            continue

        if first == "P":
            if current_epoch is None:
                continue

            try:
                satellite, x, y, z = _parse_sp3_position_line(stripped)
            except Exception:
                continue

            if not satellite:
                continue

            key = (current_epoch, satellite)

            if key not in records:
                records[key] = {
                    "satellite": satellite,
                    time_column: _datetime_to_mjd(current_epoch),
                    "x": None,
                    "y": None,
                    "z": None,
                    "vx": None,
                    "vy": None,
                    "vz": None,
                }

            records[key]["x"] = x
            records[key]["y"] = y
            records[key]["z"] = z
            continue

        if first == "V":
            if current_epoch is None:
                continue

            try:
                satellite, vx, vy, vz = _parse_sp3_velocity_line(stripped)
            except Exception:
                continue

            if not satellite:
                continue

            key = (current_epoch, satellite)

            if key not in records:
                records[key] = {
                    "satellite": satellite,
                    time_column: _datetime_to_mjd(current_epoch),
                    "x": None,
                    "y": None,
                    "z": None,
                    "vx": None,
                    "vy": None,
                    "vz": None,
                }

            records[key]["vx"] = vx
            records[key]["vy"] = vy
            records[key]["vz"] = vz
            continue

    df = pd.DataFrame(records.values())

    if df.empty:
        raise ValueError(
            f"No SP3 records parsed from file: {path}\n"
            f"Detected in body: epochs={counts['epoch']}, P={counts['P']}, V={counts['V']}"
        )

    df = df.sort_values(by=[time_column, "satellite"]).reset_index(drop=True)

    df.attrs["source_files"] = [str(path)]
    df.attrs["time_scale"] = time_scale
    df.attrs["time_column"] = time_column
    df.attrs["coordinate_system"] = coordinate_system
    df.attrs["position_unit"] = "km"
    df.attrs["velocity_unit"] = "dm/s"

    df = _finalize_satellite_column(df)
    return df


def read_sp3_files_to_dataframe(paths: list[Path]) -> pd.DataFrame:
    """
    Read multiple SP3 files and concatenate them into a single DataFrame.

    Metadata from the first file are preserved in df.attrs.
    If the final dataframe contains exactly one unique satellite, the
    'satellite' column is removed and stored in metadata.
    """
    if not paths:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    failed: list[tuple[str, str]] = []

    for path in paths:
        try:
            df = read_sp3_to_dataframe(path).copy()
        except Exception as exc:
            failed.append((str(path), str(exc)))
            continue

        # If a single-satellite file removed the column, restore it temporarily
        # so concatenation across files keeps satellite identity.
        if "satellite" not in df.columns and "satellite" in df.attrs:
            df["satellite"] = df.attrs["satellite"]

        df["source_file"] = path.name
        frames.append(df)

    if not frames:
        msg = "No SP3 files were parsed successfully.\n"
        if failed:
            msg += "\n".join([f"- {p}: {e}" for p, e in failed[:10]])
        raise ValueError(msg)

    result = pd.concat(frames, ignore_index=True)

    time_column = frames[0].attrs.get("time_column")
    sort_cols: list[str] = []

    if time_column in result.columns:
        sort_cols.append(time_column)
    if "satellite" in result.columns:
        sort_cols.append("satellite")

    if sort_cols:
        result = result.sort_values(by=sort_cols).reset_index(drop=True)

    base_attrs = dict(frames[0].attrs)
    base_attrs["source_files"] = [str(path) for path in paths]
    if failed:
        base_attrs["failed_source_files"] = failed

    result.attrs.update(base_attrs)

    result = _finalize_satellite_column(result)
    return result