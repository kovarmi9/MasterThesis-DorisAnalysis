# Input data

The library supports loading and processing several types of DORIS-related products and auxiliary data.

Supported input sources include:

- DORIS station coordinate time series,
- precise satellite orbit products in SP3 format,
- Bernese GNSS Software outputs,
- local files,
- remote files via SSH/SFTP,
- remote products from NASA CDDIS.

---

## Local files

Products already available on a local disk can be copied into the project structure using the local workflow.

```python
from pathlib import Path

from doris.input.local import copy_from_local

result = copy_from_local(
    source_dir=Path("external_products"),
    local_dir=Path("data/orbits"),
    filename_pattern="*.sp3*",
    solution="gop",
    satellite="srl",
    decompress=True,
    keep_compressed=False,
)

print(f"Files processed: {result.count}")
print(f"Files decompressed: {result.count_decompressed}")
```

The workflow supports:

- optional filename filtering,
- automatic decompression,
- overwrite control,
- filtering by solution and satellite identifier.

---

## SSH / SFTP

Remote products can be downloaded from SSH/SFTP servers.

```python
from pathlib import Path

from doris.input.ssh import download_from_ssh

result = download_from_ssh(
    host="example.server.cz",
    username="user",
    remote_dir="/products/orbits",
    local_dir=Path("data/orbits"),
    filename_pattern="*.sp3.Z",
    solution="gop",
    satellite="srl",
    decompress=True,
)

print(f"Downloaded files: {result.count_downloaded}")
```

The SSH workflow supports:

- password authentication,
- private key authentication,
- interactive password prompt,
- stored login credentials,
- optional filename filtering,
- automatic decompression,
- overwrite control,
- filtering by solution and satellite identifier.

---

## NASA CDDIS

DORIS products can be downloaded directly from the NASA CDDIS archive.

```python
from pathlib import Path

from doris.input.cddis import download_from_cddis

result = download_from_cddis(
    technique="doris",
    product="orbits",
    solution="ssa",
    satellite="srl",
    output_root=Path("data"),
    parallel_download=True,
    max_workers=4,
    decompress=True,
)

print(f"Downloaded files: {len(result.downloaded_paths)}")
print(f"Decompressed files: {len(result.decompressed_paths)}")
```

The CDDIS workflow supports:

- Earthdata authentication,
- parallel download,
- retry handling,
- MD5SUMS index parsing,
- automatic archive decompression,
- overwrite control,
- filtering by product, solution and satellite identifier.
