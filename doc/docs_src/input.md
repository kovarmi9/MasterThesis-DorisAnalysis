# Input data

The library supports loading and processing several types of DORIS-related products and auxiliary data.

Main supported inputs:

- DORIS station coordinate time series
- Precise satellite orbit products (SP3)
- Bernese GNSS Software outputs
- Local files
- Remote files via SSH/SFTP
- Remote products from NASA CDDIS

### Local files

Load precise orbit products from local SP3 files.

```python
from doris.input.local import load_orbit_dataframe

df = load_orbit_dataframe(
    "data/orbits/s3a2024001.sp3"
)

print(df.head())
```

### SSH / SFTP

Download products from remote servers using SSH/SFTP.

```python
from doris.input.ssh import download_file

download_file(
    host="example.server.cz",
    username="user",
    password="password",
    remote_path="/products/orbit.sp3",
    local_path="data/orbit.sp3"
)
```

### NASA CDDIS

Download DORIS products directly from NASA CDDIS.

```python
from doris.input.cddis import download_cddis_file

download_cddis_file(
    remote_path="/doris/products/sp3/example.sp3.Z",
    local_path="data/example.sp3.Z",
    token="YOUR_EARTHDATA_TOKEN"
)
```
