# Mapa projektu

Tento dokument popisuje aktualni strukturu projektu `MasterThesis-DorisAnalysis`.
Projekt je Python knihovna balena jako package `doris` ve slozce `src/`.
Hlavni cil je nacitani a analyza DORIS dat: stanicni casove rady, spektralni analyza
a prace s orbitami ve formatu SP3.

## Rychly prehled stromu

```text
MasterThesis-DorisAnalysis/
+-- README.md
+-- pyproject.toml
+-- requirements.txt
+-- PROJECT_MAP.md
+-- src/
|   +-- doris/
|       +-- _utils/
|       +-- input/
|       |   +-- cddis/
|       |   +-- local/
|       |   +-- ssh/
|       +-- analysis/
|       |   +-- stations/
|       |   +-- spectral/
|       |   +-- orbits/
|       |       +-- loading/
|       |       +-- interpolate/
|       |       +-- track/
|       |       +-- compare/
|       |       +-- transform/
|       +-- output/
|           +-- plots/
+-- notebooks/
|   +-- stations/
|   +-- satellites/
|   +-- tests/
+-- data/
+-- LaTeX/
```

## Jak cist `src`

Nejrychlejsi orientace:

1. `src/doris/input/` resi, odkud se data vezmou a kam se ulozi.
2. `src/doris/analysis/stations/` a `src/doris/analysis/spectral/` resi stanicni casove rady.
3. `src/doris/analysis/orbits/` resi SP3 orbity: vyber souboru, parsovani, jednotky, interpolaci, RTN a porovnani.
4. `src/doris/output/plots/` obsahuje male pomocniky pro jednotny vzhled grafu.
5. `src/doris/_utils/` obsahuje sdilene funkce pouzite napric vstupnimi workflow.

Importy maji smerovat na package `doris`, napr.:

```python
from doris.input.cddis import download_from_cddis
from doris.analysis.stations.trend import fit_piecewise_trend
from doris.analysis.orbits import load_orbit_dataframe, compare_trajectories
```

## `src/doris/_utils`

Sdilene utility, ktere nejsou vazane na konkretni zdroj dat.

### `_paths.py`

Resi jednotne filtrovani a vystupni cesty pro lokalni/SSH workflow.

- `matches_filters(name, solution=None, satellite=None)` kontroluje, zda nazev souboru odpovida zadanemu reseni a satelitu.
- Pri filtrovani ignoruje kompresni koncovky `.gz` a `.Z`, aby filtr pracoval se skutecnym datovym nazvem.
- `build_local_path(local_dir, filename, solution=None, satellite=None)` sklada cilovou cestu ve tvaru `local_dir/solution/satellite/filename`, pokud jsou tyto casti zadane.

### `_decompress.py`

Spolecna dekomprese komprimovanych vstupu.

- `decompress_file(path, keep_compressed=False, overwrite=True)` dekomprimuje jeden soubor.
- `decompress_many(paths, ...)` vola dekompresi pro vice souboru.
- Podporuje `.Z` pres `unlzw3` a `.gz` pres standardni `gzip`.
- Pokud vstup neni podporovany nebo dekomprese selze, pouziva `DecompressionError`.

## `src/doris/input`

Vstupni cast sjednocuje tri zpusoby ziskani dat: NASA CDDIS, SSH/SFTP a lokalni kopii.
Vsechny workflow maji podobny tvar: najit soubory, filtrovat, ulozit do lokalni struktury
a volitelne dekomprimovat.

### `input/cddis`

Workflow pro NASA CDDIS archiv a Earthdata autentizaci.

#### `_config.py`

Konfiguracni dataclassy:

- `AuthConfig` urcuje `token_file`, `login_file`, interaktivni prihlaseni a ukladani loginu.
- `CddisRequest` popisuje dataset: `technique`, `subtree`, `product`, `solution`, volitelny `satellite`, `archive_root` a `output_root`.
- `CddisRequest.relative_dataset_path` sklada cestu typu `stcd/gop25wd04` nebo `orbits/ssa/srl`.
- `DownloadOptions` ridi overwrite, vytvareni adresaru, timeouty, retry, `MD5SUMS`, paralelni download a `max_workers`.
- `DecompressOptions` ridi, zda dekomprimovat, ponechat komprimovany soubor a prepisovat vystup.
- `LoadConfig` spojuje request, autentizaci, download a dekompresi do jednoho objektu.

#### `_authentication.py`

Resi Earthdata prihlaseni.

- Hleda token v `token.txt`.
- Hleda username/password v `login.txt`.
- Pri povolene interakci umi vyzvat k prihlaseni.
- Vytvari `requests.Session`.
- Umi nastavit bearer token nebo username/password pres `.netrc`/`_netrc`.
- Verejne dulezite funkce: `get_authenticated_session()`, `resolve_auth()`, `describe_auth_source()`.

#### `_client.py`

Nizsi HTTP klient pro archiv.

- `build_dataset_url()` sklada URL z `CddisRequest`.
- `download_md5sums()` stahuje index `MD5SUMS`.
- `parse_md5sums_for_archives()` z indexu vybere archivni `.Z` soubory.
- `fetch_dataset_index()` vraci `DatasetIndex` s URL, cestou k MD5 a seznamem souboru.
- `download_dataset_archives()` stahuje archivni soubory sekvencne nebo paralelne.
- Stazeni kontroluje, jestli misto dat neprisla HTML/login odpoved.

#### `workflow.py`

Vysoka vrstva pro pouziti z notebooku.

- `run_cddis_workflow(cfg)` provede autentizaci, nacte index, stahne soubory a volitelne je dekomprimuje.
- `download_from_cddis(...)` je ploche pohodlne API bez nutnosti rucne skladat config objekty.
- `CddisWorkflowResult` obsahuje `dataset_index`, `downloaded_paths` a `decompressed_paths`.

#### `__init__.py`

Re-exportuje hlavni konfigurace a workflow, takze v notebooku staci:

```python
from doris.input.cddis import download_from_cddis
```

### `input/ssh`

Workflow pro stahovani souboru pres SSH/SFTP.

#### `_config.py`

- `SshConfig` drzi host, port, username, heslo nebo private key a nastaveni host keys.
- `SshAuthOptions` drzi `login_ssh.txt`, interaktivni prihlaseni a ukladani loginu.
- `SshDownloadRequest` popisuje remote/local adresare, `filename_pattern`, `solution`, `satellite` a overwrite.
- `SshDecompressOptions` ridi dekompresi stejne jako u ostatnich vstupu.

#### `_authentication.py`

- `resolve_ssh_auth()` vybere heslo z argumentu, `login_ssh.txt`, nebo promptu.
- `read_login_file()` a `save_login_file()` cte/uklada SSH prihlaseni.
- `ResolvedSshAuth` uklada username, password a zdroj prihlaseni.

#### `_client.py`

- Obaluje `paramiko.SSHClient` a `SFTPClient`.
- `SshClient` funguje jako context manager.
- `list_files()` vraci `RemoteEntry` pro soubory v remote adresari.
- `download_file()` stahuje remote soubor na lokalni cestu.
- Definuje vlastni chyby: `SshConnectionError`, `SshAuthenticationError`, `SshRemotePathError`.

#### `workflow.py`

- `download_from_ssh(...)` je hlavni notebookove API.
- `run_ssh_workflow(config, request, decompress_options)` je nizsi API nad config objekty.
- Soubor se ulozi pres `build_local_path()`, tedy volitelne do `local_dir/solution/satellite/`.
- Po stazeni muze workflow dekomprimovat `.Z`/`.gz`; chyby dekomprese u jednotlivych souboru jen zaloguje a pokracuje.
- `SshDownloadResult` poskytuje pocty `count`, `count_downloaded`, `count_skipped_existing`, `count_decompressed`.

### `input/local`

Workflow pro kopirovani souboru z lokalni slozky do projektove datove struktury.

#### `_config.py`

- `LocalCopyRequest` popisuje `source_dir`, `local_dir`, pattern, `solution`, `satellite` a overwrite.
- `LocalDecompressOptions` ridi dekompresi.

#### `_client.py`

- `list_files(source_dir, filename_pattern=None)` vraci soubory jako `LocalEntry`.
- `copy_file(source_path, local_path, overwrite=True)` kopiruje jeden soubor a vraci, zda se opravdu kopiroval.

#### `workflow.py`

- `copy_from_local(...)` je pohodlne API pro notebooky.
- `run_local_workflow(...)` vybere soubory, profiltuje je pres `matches_filters()`, zkopiruje a volitelne dekomprimuje.
- `LocalCopyResult` poskytuje pocty `count`, `count_copied`, `count_skipped_existing`, `count_decompressed`.

## `src/doris/analysis/stations`

Moduly pro trendovou analyzu stanicnich casovych rad.

### `_ls.py`

Nizsi linearni fit.

- `FitResult` uklada `slope`, `intercept`, RSS/WRSS, `r2`, pocet bodu a rozsah `x`.
- `fit_ols(x, y)` dela nevazeny linearni fit.
- `fit_wls(x, y, sigma)` dela vazeny fit s vahami `1 / sigma**2`.

### `_bic.py`

- `bic_from_rss(n, rss, k=2)` pocita Bayesovo informacni kriterium pro porovnani modelu.

### `trend.py`

Hlavni stanicni trendova logika.

- `fit_linear_trend(x, y, sigma=None, ...)` fituje jeden linearni trend.
- `fit_piecewise_trend(x, y, sigma=None, ...)` hleda po castech linearni trend a vybira split podle BIC.
- `SegmentResult` reprezentuje jeden segment trendu.
- `TrendResult` reprezentuje cely vysledek vcetne segmentu, breakpointu, fitted hodnot, residualu a BIC.
- Vysledek umi vyrabet tabulky a shrnuti segmentu pres metody objektu `TrendResult`.
- Interni pomocne funkce resi validni masku dat, kandidaty breakpointu, fit segmentu a skore modelu.

Typicky tok:

```text
station series
  -> fit_linear_trend() nebo fit_piecewise_trend()
  -> OLS/WLS segmenty
  -> BIC vyber breakpointu
  -> fitted hodnoty, residualy, segment summaries
```

## `src/doris/analysis/spectral`

Spektralni analyza casovych rad.

### `periodogram.py`

- `compute_periodogram(...)` je verejny wrapper.
- `compute_fft_periodogram(...)` pocita jednostranny FFT periodogram.
- Vystup obsahuje `frequency`, `period`, `amplitude`, `power`, `phase_rad`.
- Volitelne omezuje periody pomoci `min_period` a `max_period`.

### `peaks.py`

- `select_periodogram_peaks(periodogram_df, ...)` vybira lokalni peaky.
- Pouziva `scipy.signal.find_peaks`.
- Slouzi pro vytazeni dominantnich period z periodogramu.

### `__init__.py`

Re-exportuje:

- `compute_periodogram`
- `compute_fft_periodogram`
- `select_periodogram_peaks`

## `src/doris/analysis/orbits`

Nejvetsi cast projektu. Resi SP3 data od vyberu souboru az po porovnani dvou orbitnich trajektorii.

Hlavni datovy tok:

```text
SP3 files
  -> loading/select_orbit_files_for_period()
  -> loading/read_sp3_files_to_dataframe()
  -> loading/deduplicate_orbit_epochs()
  -> loading/convert_trajectory_units()
  -> optional coverage/continuity inspection
  -> optional transform_itrf_to_gcrs()
  -> interpolate/interpolate_trajectory_to_reference()
  -> compare/compare_trajectories()
  -> compare/orbit_diff_stats(), orbit_diff_summary()
```

### `orbits/loading`

Nacitani, vyber, cisteni a normalizace SP3 orbit.

#### `load_to_df.py`

Vysoka vrstva pro nacteni orbit do pandas DataFrame.

- `load_orbit_dataframe(source, start, end, ...)` nacte casovy rozsah.
- `load_orbit_day(source, day, window=0.0, ...)` nacte jeden den a oreze ho na denni okno.
- `iter_orbit_days(source, start, end, skip_missing=True, **kwargs)` iteruje po dnech.
- Pri nacitani vola vyber souboru, parsovani SP3, deduplikaci, volitelnou normalizaci jednotek a volitelne kontroly pokryti/casove pravidelnosti.
- Metadata o nacitani uklada do `df.attrs["load_to_df"]`.

#### `_filename_parsers.py`

Parsuje metadata z nazvu souboru.

- `FilenameInfo` drzi `path`, `start`, `end`, `provider`, `satellite`, `version`, `scheme`.
- `parse_cddis_filename()` zna CDDIS styl `.bYYDDD.eYYDDD.`.
- `parse_gop_filename()` zna styl `provider_satellite_YYMMDD_YYMMDD_Vxx.sp3`.
- `parse_filename_info()` zkusi vsechny zname parsery.

#### `_orbit_file_selection.py`

- `select_orbit_files_for_period(root, start, end, recursive=False)` vybere vsechny SP3 soubory, jejichz pokryti se prekryva s pozadovanym intervalem.
- `select_file_for_day(root, day, recursive=True)` vybere nejvhodnejsi soubor pro konkretni den, prednost ma soubor s lepsim okolnim pokrytim.

#### `_sp3_reader.py`

SP3 parser.

- `read_sp3_to_dataframe(path)` nacte jeden SP3 soubor.
- `read_sp3_files_to_dataframe(paths)` nacte vice souboru a spoji je.
- Parsuje epochy, `P` radky pozic a `V` radky rychlosti.
- Vystupni sloupce jsou typicky `x`, `y`, `z`, `vx`, `vy`, `vz`, `MJD_<TIME_SCALE>` a podle situace `satellite`/`source_file`.
- Metadata uklada do `df.attrs`: `source_files`, `time_scale`, `time_column`, `coordinate_system`, `position_unit`, `velocity_unit`.
- Pokud je v datech jen jeden satelit, sloupec `satellite` presune do metadat.

#### `_convert_trajectory_units.py`

Normalizace casu a jednotek.

- `convert_trajectory_units(df, target_time_scale="TAI", add_epoch=True)` prevadi pozice/rychlosti na `m` a `m/s`.
- Detekuje vstupni casovy sloupec a casovou skalu.
- Prevadi mezi `UTC`, `TAI` a `GPS` pomoci `astropy`.
- Uklada aktualni jednotky a casovy sloupec do `df.attrs`.

#### `_deduplicate.py`

- `deduplicate_orbit_epochs(df, keep="first", compute_statistics=False)` odstranuje duplicitni epochy.
- Klice odvozuje podle casoveho sloupce a pripadne satelitu.
- Podporuje strategie `first`, `last`, `mean`.

#### `_coverage.py`

- `inspect_orbit_file_coverage(paths)` kontroluje navaznost sousednich orbitnich souboru podle pokryti z nazvu.
- Vystup popisuje `gap`, `touching` nebo `overlap`.
- Souhrn uklada do `df.attrs["coverage_summary"]`.

#### `_continuity.py`

- `inspect_orbit_time_series(df, expected_step_seconds=60)` kontroluje casovou pravidelnost nactene trajektorie.
- Hleda duplicity, mezery a nepravidelne kroky.
- Souhrn uklada do `df.attrs["time_series_summary"]`.

#### `__init__.py`

Verejne z loading package exportuje:

- `load_orbit_dataframe`
- `load_orbit_day`
- `iter_orbit_days`
- `select_orbit_files_for_period`
- `select_file_for_day`

### `orbits/interpolate`

Interpolace trajektorii na referencni epochy.

#### `hermite.py`

Implementace Hermitovy interpolace polohy z casu, poloh a rychlosti.

- `hermite_at_time(data, t_query, degree=11, ...)` je hlavni funkce.
- Podporovane vstupy:
  - `(t, r, v)`
  - `(t, x, y, z, vx, vy, vz)`
  - matice `(N, 7)` jako `[t, x, y, z, vx, vy, vz]`
- Stupen musi byt lichy; pocet uzlu je `(degree + 1) // 2`.
- Funkce vraci jen interpolovanou polohu, ne rychlost.
- Interni `lagrange_basis()`, `lagrange_basis_deriv_at_nodes()` a `hermite_interpolate()` skladaji klasicky Hermituv polynom.

#### `interpolate.py`

Pandas wrapper nad Hermitovou interpolaci.

- `interpolate_trajectory_to_reference(df_source, df_reference, method="hermite", degree=11, time_col=None, ...)` interpoluje zdrojovou trajektorii na epochy referencniho DataFrame.
- Automaticky hleda spolecny casovy sloupec z `t_sec_round`, `t_sec`, `MJD_TAI`, `MJD_GPS`, pokud neni zadany.
- Vyzaduje ve zdroji `x`, `y`, `z`, `vx`, `vy`, `vz`.
- Vystup obsahuje interpolovane `x`, `y`, `z`; `vx`, `vy`, `vz` jsou zatim `NaN`, protoze backend vraci pouze polohu.
- `interpolate_like()` je zpetne kompatibilni alias.

### `orbits/track`

Prace s lokalnim RTN ramcem.

#### `_rtn_frame.py`

- `build_rtn_frame(position, velocity)` vytvori jednotkove vektory radial/tangential/normal.
- Radial je smer `r / ||r||`.
- Normal je smer orbitalniho momentu `r x v`.
- Tangential je `N x R`.
- `project_to_rtn(diff_xyz, position, velocity)` projektuje XYZ rozdily do `dR`, `dT`, `dN`.

### `orbits/compare`

Porovnani dvou orbit.

#### `compare.py`

- `compare_trajectories(df_a, df_b, time_col="t_sec", degree=11, edge_trim=10, rtn=True, unit="mm")`.
- Interpoluje trajektorii A na epochy trajektorie B.
- Oreze okraje referencni trajektorie podle `edge_trim`, aby se omezily okrajove efekty interpolace.
- Pocita rozdily `ref - interp`, normu rozdilu a volitelne RTN slozky.
- Podle `unit` vraci rozdily v metrech nebo milimetrech.
- Souhrnne statistiky uklada do `result.attrs`.

#### `stats.py`

- `orbit_diff_stats(diff_df)` pocita mean, RMS a RMS0 pro `dR_m`, `dT_m`, `dN_m`.
- `orbit_diff_summary(results)` sklada denni summary tabulku z dictionary `day -> diff_df`.

### `orbits/transform`

Transformace souradnic.

#### `itrf_transform.py`

- `transform_itrf_to_gcrs(df)` prevadi trajektorii z ITRF/ITRS/IGS do GCRS pomoci `astropy`.
- Detekuje casovy sloupec a casovou skalu z DataFrame.
- Vyzaduje pozicni sloupce `x`, `y`, `z`.
- Vystup ponechava DataFrame tvar a aktualizuje metadata souradnicoveho systemu.

#### `ITRF2GCRF.ipynb`

Experimentacni notebook pro transformaci ITRF -> GCRF/GCRS.

### `orbits/__init__.py`

Hlavni orbitni API exportuje napric podbalicky:

- `load_orbit_dataframe`, `load_orbit_day`, `iter_orbit_days`
- `hermite_at_time`, `interpolate_trajectory_to_reference`, `interpolate_like`
- `transform_itrf_to_gcrs`
- `build_rtn_frame`, `project_to_rtn`
- `compare_trajectories`, `orbit_diff_stats`, `orbit_diff_summary`

## `src/doris/output/plots`

Pomocne funkce pro konzistentni osy grafu.

### `_scale.py`

- `uniform_y_scale_policy(...)` sjednocuje y rozsah a tick step pro vice os/subplotu.
- `set_unit_ticks(...)` nastavuje jednotny spacing ticku na x ose.
- Interni `_nice_step()` vybira lidsky citelny krok ticku.

### `plot_settings.py` a `__init__.py`

Re-exportuji `set_unit_ticks` a `uniform_y_scale_policy`.

Poznamka: v `plot_settings.py` je stale docstring s prikladem importu pres `app.output.plots`; pri dalsim cisteni dokumentace by mel byt zmenen na `doris.output.plots`.

## Notebooky

Notebooky jsou prakticka vrstva nad `src`.

### `notebooks/stations/download_cddis.ipynb`

Stahuje DORIS STCD data z CDDIS pres `doris.input.cddis`.
Typicky pouziva dataset `doris/products/stcd/gop25wd04`, paralelni download a dekompresi.

### `notebooks/stations/spectral_analysis.ipynb`

Navazuje na stanicni STCD data a pouziva `doris.analysis.spectral` pro FFT periodogram a vyber period.

### `notebooks/stations/trend_detection.ipynb`

Trendova analyza stanicnich dat. Pracuje s vybranou stanici, vyrabi detrendovane rady, trendove tabulky a grafy.

### `notebooks/satellites/download_cddis.ipynb`

Stahovani satelitnich/orbitnich dat z CDDIS.

### `notebooks/satellites/download_local.ipynb`

Kopirovani orbitnich dat z lokalni slozky pres `doris.input.local`.

### `notebooks/satellites/download_ssh.ipynb`

Stahovani orbitnich dat pres SSH/SFTP pres `doris.input.ssh`.

### `notebooks/tests/hermite_interpolation_accuracy.ipynb`

Validacni notebook pro presnost Hermitovy interpolace orbit.

## Data a soukrome soubory

### `data/`

Lokalni pracovni data. Slozka je ignorovana pres `.gitignore`.

Typicke casti:

- `data/stcd/gop25wd04/` pro stanicni STCD data, exporty a grafy.
- `data/orbits/` pro orbitni data podle zdroju a satelitu.
- `data/amalie_sp3_2024/` pro SP3 data clenena podle poskytovatele/satelitu.

### Prihlasovaci soubory

Workflow umi cist:

- `token.txt` pro Earthdata token,
- `login.txt` pro Earthdata username/password,
- `login_ssh.txt` pro SSH username/password.

`.gitignore` obsahuje pravidla pro `**/token.txt`, `**/login.txt` a `**/login_ssh.txt`.

## LaTeX

### `LaTeX/images/`

Obrazove podklady a vysledky pro text prace:

- loga CVUT,
- zadani,
- validacni grafy pro testy Hermitovy interpolace.

### `LaTeX/build/`

Build artefakty LaTeX dokumentu, pokud jsou v lokalnim stromu vytvorene:

- `main.pdf`,
- `.aux`, `.bbl`, `.blg`, `.log`, `.toc`, `.lof`, `.lot`, `.out`,
- `main.synctex.gz`,
- pomocne soubory pro kapitoly/prilohy.

## Konfigurace a zavislosti

### `pyproject.toml`

Projekt je balen pres setuptools:

- package name: `doris-analysis`
- Python: `>=3.10`
- zdrojovy layout: `package-dir = {"" = "src"}`
- package discovery: `where = ["src"]`

### `requirements.txt`

Zavislosti projektu:

- `requests` pro HTTP komunikaci s CDDIS,
- `paramiko` pro SSH/SFTP,
- `unlzw3` pro `.Z` dekompresi,
- `pandas` a `numpy` pro tabulky a vypocty,
- `tqdm` pro progress bary,
- `astropy` pro casove skaly a transformace souradnic,
- `scipy` pro spektralni peaky a numeriku,
- `matplotlib` pro grafy,
- `jupyter` a `ipykernel` pro notebooky.

## Verejna API pro notebooky

Nejdulezitejsi importy:

```python
from doris.input.cddis import download_from_cddis
from doris.input.ssh import download_from_ssh
from doris.input.local import copy_from_local

from doris.analysis.stations.trend import fit_linear_trend, fit_piecewise_trend
from doris.analysis.spectral import (
    compute_periodogram,
    compute_fft_periodogram,
    select_periodogram_peaks,
)

from doris.analysis.orbits import (
    load_orbit_dataframe,
    load_orbit_day,
    iter_orbit_days,
    hermite_at_time,
    interpolate_trajectory_to_reference,
    compare_trajectories,
    orbit_diff_stats,
    orbit_diff_summary,
    transform_itrf_to_gcrs,
)

from doris.output.plots import uniform_y_scale_policy, set_unit_ticks
```

## Datove toky

### CDDIS download

```text
download_from_cddis()
  -> LoadConfig
  -> get_authenticated_session()
  -> fetch_dataset_index()
       -> build_dataset_url()
       -> download_md5sums()
       -> parse_md5sums_for_archives()
  -> download_dataset_archives()
  -> optional decompress_file()
  -> CddisWorkflowResult
```

### SSH/local vstup

```text
download_from_ssh() / copy_from_local()
  -> list remote/local files
  -> filename_pattern + solution/satellite filters
  -> build_local_path()
  -> download/copy
  -> optional decompress_file()
  -> SshDownloadResult / LocalCopyResult
```

### Stanicni trend

```text
station time series
  -> valid mask
  -> OLS/WLS fit
  -> optional BIC breakpoint search
  -> TrendResult
  -> residuals, fitted values, segment tables
```

### Spektralni analyza

```text
station time series
  -> compute_fft_periodogram()
  -> period/amplitude/power/phase table
  -> select_periodogram_peaks()
  -> dominant periods for plots/tables
```

### Orbitni porovnani

```text
SP3 directories
  -> load_orbit_dataframe()
  -> convert units/time scale
  -> optional transform_itrf_to_gcrs()
  -> compare_trajectories()
       -> interpolate A to B epochs
       -> XYZ differences
       -> optional RTN projection
  -> orbit_diff_stats()/orbit_diff_summary()
```

## Co zkontrolovat jako dalsi

1. Opravit docstring v `src/doris/output/plots/plot_settings.py`, kde zustal import pres `app`.
2. Rozhodnout, jestli maji byt vystupni PDF v `LaTeX/images/test/` verzovane, nebo brane jako generovane artefakty.
3. Zkontrolovat, ze prihlasovaci soubory nejsou trackovane ani staged.
4. Doplnit minimalni testy pro filtrovani nazvu, CDDIS URL, parsovani `MD5SUMS`, dekompresi, SP3 parser, vyber orbitnich souboru a trend fitting.
5. Zapsat do `README.md` kratky navod: instalace, `pip install -e .`, autentizace a zakladni priklady.
6. U spektralni casti zvazit Lomb-Scargle pro nerovnomerne vzorkovane casove rady.
