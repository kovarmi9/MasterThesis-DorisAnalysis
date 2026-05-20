# Outputs

This module provides helpers for exporting tables and adjusting plot scales.

## Main features

- export of pandas DataFrames to LaTeX tables,
- custom column names and decimal formatting,
- automatic output paths under `LaTeX/tables`,
- preview of generated LaTeX code,
- shared axis scaling for Matplotlib plots.

## LaTeX table export

```python
from doris.output.tables import Col, save_latex_table

tex = save_latex_table(
    df,
    "results/stations/licb/trend",
    cols=[
        Col("axis", "Složka", None),
        Col("slope", "Směrnice [mm/rok]", 3),
        Col("r2", "$R^2$", 3),
        Col("bic", "BIC [-]", 1),
    ],
    caption="Lineární trend stanice LICB",
    label="tab:licb_trend",
)
```

## Preview LaTeX table

```python
from doris.output.tables import Col, print_latex_table

print_latex_table(
    df,
    cols=[
        Col("axis", "Složka", None),
        Col("slope", "Směrnice [mm/rok]", 3),
        Col("r2", "$R^2$", 3),
    ],
)
```

## Build table path

```python
from doris.output.tables import latex_table_path

path = latex_table_path(
    "results",
    "stations",
    "licb",
    filename="trend",
)
```

## Plot scale helpers

```python
from doris.output.plots import set_unit_ticks, uniform_y_scale_policy

set_unit_ticks(
    axes,
    step=1.0,
)

uniform_y_scale_policy(
    axes,
    df,
    components=["dE", "dN", "dU"],
)
```
