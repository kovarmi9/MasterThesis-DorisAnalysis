# Orbit comparison

This module provides tools for loading, interpolating and comparing precise satellite orbits.

## Main features

- loading SP3 orbit products,
- Hermite interpolation,
- interpolation to common epochs,
- comparison of orbit solutions,
- RTN decomposition,
- RMS and RMS0 statistics.

## Loading SP3 orbit products

```python
from doris.analysis.orbits.loading import load_orbit_dataframe

df = load_orbit_dataframe("orbit.sp3")
```

## Hermite interpolation

```python
from doris.analysis.orbits.hermite import hermite_at_time

r_interp = hermite_at_time(
    data,
    t_query=12345.0,
    degree=11,
)
```

## Interpolation to common epochs

```python
from doris.analysis.orbits.interpolate import interpolate_like

df_interp = interpolate_like(
    df_source=df_ssa,
    df_reference=df_gop,
    degree=11,
    time_col="t_sec",
)
```

## Orbit comparison

```python
from doris.analysis.orbits.compare import compare_trajectories

diff_xyz = compare_trajectories(
    df_a=df_ssa,
    df_b=df_gop,
    degree=11,
    rtn=False,
    unit="mm",
)
```

## RTN decomposition

```python
diff_rtn = compare_trajectories(
    df_a=df_ssa,
    df_b=df_gop,
    degree=11,
    rtn=True,
    unit="mm",
)

diff_rtn[["dR_mm", "dT_mm", "dN_mm"]]
```

## Orbit statistics

```python
from doris.analysis.orbits.stats import orbit_diff_summary

summary = orbit_diff_summary(results)

print(summary)
```
