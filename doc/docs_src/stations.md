# Station analysis

This module provides tools for loading and analysing DORIS station coordinate time series.

## Main features

- loading STCD station files,
- trend estimation,
- discontinuity detection,
- spectral analysis,
- FFT and Lomb–Scargle periodograms.

## Loading station data

```python
from doris.analysis.stations.loading import load_station_dataframe

df = load_station_dataframe(
    "station.stcd",
    start="2015-01-01",
    end="2025-12-31",
)
```

## Linear trend estimation

```python
from doris.analysis.stations.trend import fit_linear_trend

result = fit_linear_trend(
    df["year"],
    df["dU"],
    sigma=df["sU"],
)

print(result.slope)
print(result.r2)
```

## Piecewise trend estimation

```python
from doris.analysis.stations.trend import fit_piecewise_trend

result = fit_piecewise_trend(
    df["year"],
    df["dU"],
    sigma=df["sU"],
    max_segments=2,
)

print(result.breakpoints)
```

## FFT periodogram

```python
from doris.analysis.spectral.periodogram import compute_periodogram

fft = compute_periodogram(
    df["year"],
    df["dU"],
    method="fft",
)
```

## Lomb–Scargle periodogram

```python
from doris.analysis.spectral.periodogram import compute_periodogram

lsp = compute_periodogram(
    df["year"],
    df["dU"],
    method="lomb_scargle",
)
```

## Significant peak detection

```python
from doris.analysis.spectral.significance import (
    estimate_periodogram_threshold,
    find_significant_peaks,
)

threshold = estimate_periodogram_threshold(
    df["year"],
    df["dU"],
    method="lomb_scargle",
)

peaks = find_significant_peaks(
    lsp,
    threshold=threshold,
)

print(peaks)
```
