"""Export pandas DataFrames to previewable standalone LaTeX table files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, NamedTuple

import pandas as pd

__all__ = [
    "Col",
    "DEFAULT_TABLES_ROOT",
    "latex_table_path",
    "make_latex_table",
    "print_latex_table",
    "save_latex_table",
]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TABLES_ROOT = PROJECT_ROOT / "LaTeX" / "tables"
DEFAULT_IMAGES_ROOT = PROJECT_ROOT / "LaTeX" / "images"


class Col(NamedTuple):
    """Column specification for :func:`save_latex_table`.

    Parameters
    ----------
    source : str
        Column name in the source DataFrame.
    header : str
        Display name used as the column header in the table.
        Supports LaTeX math, e.g. ``"$R^2$"``.
    decimals : int | None
        Number of decimal places.  ``None`` leaves the value as-is
        (useful for string or integer columns).

    Examples
    --------
    >>> Col("slope", "Směrnice [mm/rok]", 3)
    >>> Col("axis",  "Složka",            None)
    >>> Col("bic",   "BIC [-]",           1)
    """

    source: str
    header: str
    decimals: int | None


def _inject_preamble(latex: str, *, centering: bool, font_size: str) -> str:
    """Insert ``\\centering`` and/or a font-size command after ``\\begin{table}[...]``."""
    extras = []
    if centering:
        extras.append("\\centering")
    if font_size:
        extras.append(font_size)
    if not extras:
        return latex

    lines = latex.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(r"\begin{table}"):
            lines = lines[: i + 1] + extras + lines[i + 1 :]
            break
    return "\n".join(lines)


def _coerce_cols(cols: Iterable[Col | tuple]) -> list[Col]:
    return [c if isinstance(c, Col) else Col(*c) for c in cols]


def _validate_columns(df: pd.DataFrame, cols: list[Col]) -> None:
    missing = [c.source for c in cols if c.source not in df.columns]
    if missing:
        available = ", ".join(map(str, df.columns))
        wanted = ", ".join(missing)
        raise KeyError(
            f"DataFrame is missing column(s): {wanted}. "
            f"Available columns: {available}"
        )


def _resolve_output_path(
    path: Path | str,
    *,
    tables_root: Path | str | None,
) -> Path:
    path = Path(path)
    if path.suffix == "":
        path = path.with_suffix(".tex")
    if path.is_absolute():
        return path

    root = DEFAULT_TABLES_ROOT if tables_root is None else Path(tables_root)
    return root / path


def latex_table_path(
    *parts: str | Path,
    filename: str | Path | None = None,
    image_path: str | Path | None = None,
    tables_root: str | Path | None = None,
    images_root: str | Path | None = None,
) -> Path:
    """Build a path under ``LaTeX/tables``.

    Use ``parts`` for an explicit table subdirectory, or pass an existing
    figure path via ``image_path`` to mirror its location under
    ``LaTeX/images`` into ``LaTeX/tables``.

    Examples
    --------
    >>> latex_table_path("results", "stations", "licb", filename="trend")
    WindowsPath('.../LaTeX/tables/results/stations/licb/trend.tex')

    >>> latex_table_path(image_path="LaTeX/images/results/stations/licb/a.pdf")
    WindowsPath('.../LaTeX/tables/results/stations/licb/a.tex')
    """
    root = DEFAULT_TABLES_ROOT if tables_root is None else Path(tables_root)

    if image_path is not None:
        if parts or filename is not None:
            raise ValueError("Use either image_path or parts/filename, not both.")

        img = Path(image_path)
        img_root = DEFAULT_IMAGES_ROOT if images_root is None else Path(images_root)

        try:
            relative = img.resolve().relative_to(img_root.resolve())
        except ValueError:
            relative = img

        return (root / relative).with_suffix(".tex")

    if filename is not None:
        parts = (*parts, filename)
    if not parts:
        raise ValueError("Provide path parts, filename, or image_path.")

    return _resolve_output_path(Path(*map(str, parts)), tables_root=root)


def make_latex_table(
    df: pd.DataFrame,
    cols: list[Col | tuple],
    *,
    caption: str = "",
    label: str = "",
    escape: bool = False,
    index: bool = False,
    position: str = "H",
    centering: bool = True,
    font_size: str = "",
) -> str:
    """Build a booktabs LaTeX table string from *df* without writing any file.

    Useful for quick preview inside a notebook::

        print(make_latex_table(df, cols=[...], caption="..."))

    Parameters
    ----------
    df : pd.DataFrame
        Source data.
    cols : list of Col (or plain 3-tuples)
        Ordered column definitions.  Each entry is either a :class:`Col`
        or a plain tuple ``(source, header, decimals)``.
    caption : str
        Table caption.  Empty string omits the caption.
    label : str
        LaTeX label for ``\\ref{}`` cross-references.
        Empty string omits the label.
    escape : bool
        If ``False`` (default), column headers are not escaped so LaTeX
        math like ``$R^2$`` renders correctly.
    index : bool
        Whether to include the DataFrame index.  Default ``False``.
    position : str
        LaTeX placement specifier, e.g. ``"htbp"`` or ``"H"``.
    centering : bool
        If ``True`` (default), insert ``\\centering`` after
        ``\\begin{table}[...]``.
    font_size : str
        Optional LaTeX font-size command inserted after ``\\centering``,
        e.g. ``"\\small"`` or ``"\\footnotesize"``.
        Empty string (default) omits the command.

    Returns
    -------
    str
        Complete LaTeX table source.
    """
    cols = _coerce_cols(cols)
    _validate_columns(df, cols)

    out = df[[c.source for c in cols]].copy()

    align = ("l" if index else "") + "".join(
        "r" if (c.decimals is not None and pd.api.types.is_numeric_dtype(out[c.source]))
        else "l"
        for c in cols
    )

    for c in cols:
        if c.decimals is not None and c.source in out.columns:
            out[c.source] = (
                pd.to_numeric(out[c.source], errors="coerce")
                .apply(lambda x, d=c.decimals: f"{x:.{d}f}" if pd.notna(x) else "")
            )

    out = out.rename(columns={c.source: c.header for c in cols})

    latex = out.to_latex(
        index=index,
        caption=caption or None,
        label=label or None,
        escape=escape,
        position=position,
        column_format=align,
    )
    return _inject_preamble(latex, centering=centering, font_size=font_size)


def print_latex_table(
    df: pd.DataFrame,
    cols: list[Col | tuple],
    *,
    caption: str = "",
    label: str = "",
    escape: bool = False,
    index: bool = False,
    position: str = "H",
    centering: bool = True,
    font_size: str = "",
) -> str:
    """Print a LaTeX table for notebook debugging and return the same string."""
    latex = make_latex_table(
        df,
        cols,
        caption=caption,
        label=label,
        escape=escape,
        index=index,
        position=position,
        centering=centering,
        font_size=font_size,
    )
    print(latex)
    return latex


def save_latex_table(
    df: pd.DataFrame,
    path: Path | str,
    cols: list[Col | tuple],
    *,
    caption: str = "",
    label: str = "",
    escape: bool = False,
    index: bool = False,
    position: str = "H",
    centering: bool = True,
    font_size: str = "",
    tables_root: Path | str | None = None,
    print_preview: bool = False,
) -> str:
    """Export *df* as a booktabs LaTeX table, write it to *path*, and return the source.

    The generated file can be included in a LaTeX document with::

        \\input{path/to/file.tex}

    The LaTeX source is also returned so you can preview it immediately::

        tex = save_latex_table(df, "out.tex", cols=[...])
        print(tex)

    Relative paths are resolved under ``LaTeX/tables`` by default, so this::

        save_latex_table(df, "results/stations/licb/trend", cols=[...])

    writes ``LaTeX/tables/results/stations/licb/trend.tex``.

    Parameters
    ----------
    df : pd.DataFrame
        Source data.
    path : Path | str
        Output file path.  Parent directories are created automatically.
    cols : list of Col (or plain 3-tuples)
        Ordered column definitions.  Each entry is either a :class:`Col`
        or a plain tuple ``(source, header, decimals)``.  Controls which
        columns appear, in what order, under what header name, and with
        how many decimal places.
    caption : str
        Table caption.  Empty string omits the caption.
    label : str
        LaTeX label for ``\\ref{}`` cross-references, e.g.
        ``"tab:licb_trend"``.  Empty string omits the label.
    escape : bool
        If ``False`` (default), column headers are not escaped, so LaTeX
        math like ``$R^2$`` renders correctly.
    index : bool
        Whether to include the DataFrame index.  Default ``False``.
    position : str
        LaTeX placement specifier, e.g. ``"htbp"`` or ``"H"``.
    centering : bool
        If ``True`` (default), insert ``\\centering`` after
        ``\\begin{table}[...]``.
    font_size : str
        Optional LaTeX font-size command inserted after ``\\centering``,
        e.g. ``"\\small"`` or ``"\\footnotesize"``.
        Empty string (default) omits the command.
    tables_root : Path or str, optional
        Base directory used for relative output paths.  Defaults to the
        project-level ``LaTeX/tables`` directory.
    print_preview : bool
        If ``True``, print the generated LaTeX source before returning it.

    Returns
    -------
    str
        The LaTeX source that was written to *path*.

    Examples
    --------
    >>> from doris.output.tables import save_latex_table, Col
    >>> tex = save_latex_table(
    ...     trend_df,
    ...     "exports/licb_trend.tex",
    ...     cols=[
    ...         Col("axis",  "Složka",           None),
    ...         Col("slope", "Směrnice [mm/rok]", 3),
    ...         Col("r2",    "$R^2$",             3),
    ...         Col("bic",   "BIC [-]",           1),
    ...     ],
    ...     caption="Lineární trend stanice LICB",
    ...     label="tab:licb_trend",
    ... )
    >>> print(tex)
    """
    latex = make_latex_table(
        df, cols,
        caption=caption, label=label, escape=escape, index=index,
        position=position, centering=centering, font_size=font_size,
    )

    path = _resolve_output_path(path, tables_root=tables_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(latex, encoding="utf-8")
    if print_preview:
        print(latex)
    return latex
