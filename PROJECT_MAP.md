# Mapa projektu

Tento dokument popisuje aktualni strukturu projektu `MasterThesis-DorisAnalysis`, hlavni moduly a datove toky. Projekt je ted baleny pod Python package `doris` a pokryva nacitani DORIS dat, stanicni trendovou analyzu, pripravenou spectralni analyzu, praci s orbitami ve formatu SP3 a pomocne vystupy pro grafy/tabulky.

## Rychly prehled

```text
MasterThesis-DorisAnalysis/
+-- README.md
+-- requirements.txt
+-- LICENSE
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
|       +-- download_cddis.ipynb
|       +-- spectral_analysis.ipynb
|       +-- trend_detection.ipynb
+-- data/
|   +-- stcd/gop25wd04/
+-- LaTeX/
    +-- build/
```

## Hlavni casti projektu

### `src/doris/`

Hlavni Python balicek. Importy v projektu maji smerovat na `doris...`, napr.:

```python
from doris.input.cddis import download_from_cddis
from doris.analysis.stations.trend import fit_linear_trend
```

Aktualne obsahuje:

- vstupni workflow pro CDDIS, SSH a lokalni slozky,
- sdilene utility pro cesty a dekompresi,
- stanicni trendovou analyzu,
- placeholder moduly pro spectralni analyzu,
- orbitni loading/interpolaci/porovnani/transformace,
- pomocniky pro nastaveni os grafu.

### `src/doris/_utils/`

Sdilene utility pouzivane vice castmi projektu.

- `_paths.py`
  - `matches_filters()` kontroluje, zda nazev souboru odpovida filtru `solution` a `satellite`.
  - `build_local_path()` sklada vystupni cestu ve tvaru `local_dir/solution/satellite/filename`.
  - Pri filtrovani ignoruje kompresni koncovky `.gz` a `.Z`.

- `_decompress.py`
  - `decompress_file()` dekomprimuje jeden soubor.
  - `decompress_many()` dekomprimuje vice souboru.
  - Podporuje `.Z` pres `unlzw3` a `.gz` pres standardni `gzip`.
  - Pri neuspechu pouziva vlastni vyjimku `DecompressionError`.

## Vstupy

### `src/doris/input/cddis/`

Workflow pro NASA CDDIS archiv.

- `_config.py`
  - Definuje `AuthConfig`, `CddisRequest`, `DownloadOptions`, `DecompressOptions`, `LoadConfig`.
  - `CddisRequest` sklada relativni datasetovou cestu, napr. `stcd/gop25wd04`.

- `_authentication.py`
  - Resi Earthdata autentizaci.
  - Poradi zdroju prihlaseni: `token.txt`, `login.txt`, interaktivni prompt.
  - Pripravuje `requests.Session` a umi zapsat Windows-friendly `_netrc`.

- `_client.py`
  - Sklada CDDIS URL.
  - Stahuje `MD5SUMS`.
  - Parsuje seznam archivnich `.Z` souboru z `MD5SUMS`.
  - Stahuje soubory sekvencne nebo paralelne pres `ThreadPoolExecutor`.
  - Detekuje HTML/login odpoved misto datoveho souboru.

- `workflow.py`
  - Hlavni API: `run_cddis_workflow(cfg)`, `download_from_cddis(...)`.
  - Provede autentizaci, stazeni datasetu a volitelnou dekompresi.
  - Vraci `CddisWorkflowResult`.

### `src/doris/input/ssh/`

Workflow pro stahovani dat pres SSH/SFTP.

- `_config.py`
  - Definuje `SshConfig`, `SshAuthOptions`, `SshDownloadRequest`, `SshDecompressOptions`.

- `_authentication.py`
  - Resi SSH heslo z primo predaneho hesla, `login_ssh.txt`, nebo interaktivniho promptu.
  - Umi prihlasovaci udaje ulozit po uspesnem pouziti.

- `_client.py`
  - Obaluje `paramiko.SSHClient` a `SFTPClient`.
  - Umi se pripojit, vypsat adresar, filtrovat soubory a stahovat soubory.

- `workflow.py`
  - Hlavni API: `run_ssh_workflow(...)`, `download_from_ssh(...)`.
  - Filtruje podle patternu, `solution`, `satellite` a volitelne dekomprimuje.
  - Vraci `SshDownloadResult`.

### `src/doris/input/local/`

Workflow pro kopirovani souboru z lokalni slozky.

- `_config.py`
  - Definuje `LocalCopyRequest` a `LocalDecompressOptions`.

- `_client.py`
  - `list_files()` vypise soubory v lokalnim adresari.
  - `copy_file()` kopiruje soubor na cilovou cestu.

- `workflow.py`
  - Hlavni API: `run_local_workflow(...)`, `copy_from_local(...)`.
  - Filtruje soubory podle patternu, `solution`, `satellite`, kopiruje je a volitelne dekomprimuje.
  - Vraci `LocalCopyResult`.

## Analyza stanic

### `src/doris/analysis/stations/`

Moduly pro fitovani trendu stanicnich casovych rad.

- `_ls.py`
  - `fit_ols()` pro nevazeny linearni fit.
  - `fit_wls()` pro vazeny linearni fit s vahami `1 / sigma**2`.
  - Vysledek drzi `FitResult` se sklonem, interceptem, RSS/WRSS, `r2`, rozsahem `x` a poctem bodu.

- `_bic.py`
  - `bic_from_rss()` pocita BIC z RSS, poctu bodu a poctu parametru.

- `trend.py`
  - `fit_linear_trend()` pro jeden linearni trend.
  - `fit_piecewise_trend()` pro BIC-vybirany po castech linearni trend.
  - Podporuje OLS/WLS, breakpoints, residualy, fitted hodnoty, export do DataFrame a segmentove summary.
  - Hlavni vysledky jsou `TrendResult` a `SegmentResult`.

### `src/doris/analysis/spectral/`

Pripravena cast pro spectralni analyzu stanicnich casovych rad.

- `periodogram.py`
  - Aktualne prazdny placeholder pro periodogram / frekvencni analyzu.

- `peaks.py`
  - Aktualne prazdny placeholder pro detekci spektralnich spickek.

## Analyza orbit

### `src/doris/analysis/orbits/loading/`

Nacitani, cisteni a normalizace SP3 orbitnich souboru.

- `load_to_df.py`
  - `load_orbit_dataframe()` nacte casovy rozsah do jednoho DataFrame.
  - `load_orbit_day()` nacte jeden den.
  - `iter_orbit_days()` iteruje po dnech.

- `_filename_parsers.py`
  - Parsuje filename metadata pro CDDIS `bYYDDD/eYYDDD` a GOP `provider_satellite_YYMMDD_YYMMDD_Vxx.sp3`.
  - Vraci `FilenameInfo`.

- `_orbit_file_selection.py`
  - `select_orbit_files_for_period()` vybira soubory prekryvajici pozadovane obdobi.
  - `select_file_for_day()` vybira nejvhodnejsi soubor pro konkretni den.

- `_sp3_reader.py`
  - Cte SP3 pozicni a rychlostni zaznamy do pandas DataFrame.
  - Detekuje time scale, coordinate system a uklada metadata do `df.attrs`.

- `_convert_trajectory_units.py`
  - Prevadi pozice/rychlosti na `m` a `m/s`.
  - Prevadi casove skaly mezi `TAI`, `UTC`, `GPS` s pomoci `astropy`.

- `_deduplicate.py`
  - Odstranuje duplicitni epochy podle casoveho sloupce a pripadne satelitu.
  - Podporuje strategie `first`, `last`, `mean`.

- `_coverage.py`
  - Kontroluje navaznost pokryti sousednich orbitnich souboru podle nazvu.
  - Reportuje gaps/touching/overlaps.

- `_continuity.py`
  - Kontroluje casovou pravidelnost nactene trajektorie podle ocekavaneho kroku.
  - Reportuje duplicity, mezery a nepravidelne kroky.

### `src/doris/analysis/orbits/interpolate/`

Interpolace orbitnich trajektorii.

- `hermite.py`
  - `hermite_at_time()` provadi Hermitovu interpolaci polohy z casu, pozic a rychlosti.
  - Podporuje vstup `(t, r, v)`, sedm vektoru, nebo matici `(N, 7)`.

- `interpolate.py`
  - `interpolate_trajectory_to_reference()` interpoluje zdrojovou trajektorii na epochy referencniho DataFrame.
  - `interpolate_like()` je zpetne kompatibilni alias.

### `src/doris/analysis/orbits/track/`

Prace s lokalnim RTN ramcem.

- `_rtn_frame.py`
  - `build_rtn_frame()` sklada radial/tangential/normal jednotkove vektory.
  - `project_to_rtn()` projektuje XYZ rozdily do slozek `dR`, `dT`, `dN`.

### `src/doris/analysis/orbits/compare/`

Porovnani dvou orbitnich trajektorii.

- `compare.py`
  - `compare_trajectories()` interpoluje trajektorii A na epochy trajektorie B.
  - Vraci rozdily v XYZ, normu a volitelne RTN slozky.
  - Uklada zakladni statistiky do `df.attrs`.

- `stats.py`
  - `orbit_diff_stats()` pocita mean/RMS/RMS0 pro RTN slozky.
  - `orbit_diff_summary()` sklada denni summary tabulku.

### `src/doris/analysis/orbits/transform/`

Transformace souradnicovych systemu.

- `itrf_transform.py`
  - `transform_itrf_to_gcrs()` transformuje trajektorii z ITRF/ITRS/IGS do GCRS pomoci `astropy`.

- `ITRF2GCRF.ipynb`
  - Notebook pro praci/experimenty s transformaci ITRF -> GCRF/GCRS.

## Vystupy

### `src/doris/output/plots/`

Pomocne funkce pro jednotne osy grafu.

- `_scale.py`
  - `uniform_y_scale_policy()` sjednocuje rozsah a tick step pro vice subplotu.
  - `set_unit_ticks()` nastavuje jednotne X tick spacing.

- `plot_settings.py`
  - Verejny re-export plot scale helperu.
  - Poznamka: docstring stale ukazuje priklad `from app.output.plots ...`; pokud se bude cistit dokumentace, ma byt `from doris.output.plots ...`.

## Notebooky

### `notebooks/stations/download_cddis.ipynb`

Notebook pro stazeni DORIS STCD dat z CDDIS.

Aktualni logika:

1. Najde root projektu podle existence `src/doris`.
2. Prida `src` do `sys.path`.
3. Importuje `download_from_cddis` z `doris.input.cddis`.
4. Stahuje dataset `doris/products/stcd/gop25wd04`.
5. Pouziva paralelni download (`max_workers=16`) a dekompresi.
6. Vypisuje URL datasetu, `MD5SUMS`, pocet archivu, stazenych a dekomprimovanych souboru.

### `notebooks/stations/spectral_analysis.ipynb`

Notebook pro rozpracovanou spectralni analyzu stanicnich casovych rad. Navazuje na stanicni STCD data a zatim ma oporu v prazdnych modulech `src/doris/analysis/spectral/periodogram.py` a `peaks.py`.

### `notebooks/stations/trend_detection.ipynb`

Notebook pro stanicni trendovou analyzu nad STCD daty. Podle struktury vystupu v `data/stcd/gop25wd04/exports/licb/` pracuje s vybranou stanici `licb`, exportuje vyrezana data, detrendovane rady a trendove tabulky.

## Data a soukrome soubory

### `data/stcd/gop25wd04/`

Lokalni data stazena z CDDIS:

- `MD5SUMS`,
- mnoho souboru `gop25wd04.stcd.<station>`,
- `images/licb/` s PDF grafy pro stanici `licb`,
- `exports/licb/` s CSV a LaTeX tabulkami pro trendove varianty.

Poznamka: `data/` je v `.gitignore`, takze jde o lokalni pracovni data, ne nutne o verzovanou cast repozitare.

### Soukrome prihlasovaci soubory

V aktualnim stromu je `notebooks/stations/login.txt`. Pokud obsahuje realne prihlasovaci udaje, patri mimo verzovani nebo do ignorovane privatni slozky.

Pozor: `.gitignore` obsahuje `*/token.txt` a pravdepodobne preklep `*/login.tx`; pro login soubory ma byt nejspis `*/login.txt`.

## LaTeX

### `LaTeX/build/`

Adresar obsahuje build artefakty LaTeX dokumentu:

- `main.pdf`,
- `.aux`, `.bbl`, `.blg`, `.log`, `.toc`, `.lof`, `.lot`, `.out`,
- `main.synctex.gz`,
- pomocne soubory pro kapitoly/prilohy.

V aktualnim stromu jsou videt hlavne vygenerovane vystupy.

## Konfigurace a zavislosti

### `requirements.txt`

Projekt deklaruje:

- `requests` - HTTP komunikace s CDDIS,
- `pandas` - prace s tabulkami,
- `numpy` - numericke vypocty a vektorove operace,
- `tqdm` - progress bary,
- `unlzw3` - dekomprese UNIX `.Z`,
- `paramiko` - SSH/SFTP klient,
- `astropy` - casove skaly a souradnicove transformace.
- `scipy` - statisticke a numericke metody,
- `matplotlib` - grafy a vizualizace,
- `jupyter` - notebookove prostredi,
- `ipykernel` - Python kernel pro notebooky.

### `.gitignore`

Obsahuje standardni Python/Jupyter ignorovani vcetne virtualnich prostredi, cache, build vystupu a `.ipynb_checkpoints`.

Obsahuje take ignorovani `data/`, `*/token.txt` a pravidlo `*/login.tx`, ktere je pravdepodobne preklep misto `*/login.txt`.

## Datove toky

### CDDIS download

```text
LoadConfig
  -> AuthConfig + CddisRequest + DownloadOptions + DecompressOptions
  -> get_authenticated_session()
  -> fetch_dataset_index()
     -> build_dataset_url()
     -> download_md5sums()
     -> parse_md5sums_for_archives()
  -> download_dataset_archives()
     -> sequential or parallel download
  -> optional decompress_file()
  -> CddisWorkflowResult
```

### Local/SSH input

```text
download_from_ssh() or copy_from_local()
  -> list files
  -> filter by filename_pattern / solution / satellite
  -> download or copy selected files
  -> optional decompress_file()
  -> SshDownloadResult or LocalCopyResult
```

### STCD trend analysis

```text
station time series
  -> fit_linear_trend() or fit_piecewise_trend()
  -> OLS/WLS segment fits
  -> BIC model selection
  -> fitted values + residuals + segment summaries
  -> CSV / LaTeX / plot exports
```

### Spectral analysis

```text
station time series
  -> spectral_analysis.ipynb
  -> planned periodogram / peak detection helpers
  -> spectral diagnostics and plots
```

### Orbit analysis

```text
SP3 files
  -> select_orbit_files_for_period()
  -> read_sp3_files_to_dataframe()
  -> deduplicate_orbit_epochs()
  -> convert_trajectory_units()
  -> optional continuity / coverage checks
  -> optional transform_itrf_to_gcrs()
  -> interpolate_trajectory_to_reference()
  -> compare_trajectories()
  -> RTN statistics
```

## Verejna API

Nejdulezitejsi funkce pro pouziti z notebooku nebo skriptu:

- `doris.input.cddis.download_from_cddis(...)`
- `doris.input.ssh.download_from_ssh(...)`
- `doris.input.local.copy_from_local(...)`
- `doris._utils._decompress.decompress_file(...)`
- `doris.analysis.stations.trend.fit_linear_trend(...)`
- `doris.analysis.stations.trend.fit_piecewise_trend(...)`
- `doris.analysis.orbits.loading.load_orbit_dataframe(...)`
- `doris.analysis.orbits.loading.load_orbit_day(...)`
- `doris.analysis.orbits.interpolate.interpolate_trajectory_to_reference(...)`
- `doris.analysis.orbits.compare.compare_trajectories(...)`
- `doris.analysis.orbits.transform.itrf_transform.transform_itrf_to_gcrs(...)`
- `doris.output.plots.uniform_y_scale_policy(...)`
- `doris.output.plots.set_unit_ticks(...)`

## Co zkontrolovat jako dalsi

1. Opravit zbyly docstring v `src/doris/output/plots/plot_settings.py`, kde je stale priklad importu pres `app`.
2. Opravit `.gitignore` pravidlo `*/login.tx` na `*/login.txt` a zvazit ignorovani `private/`, `data/` a notebookovych login souboru.
3. Rozhodnout, zda maji byt `data/` a `LaTeX/build/` verzovane, nebo brane jako generovane artefakty.
4. Dopsat obsah do `src/doris/analysis/spectral/periodogram.py` a `peaks.py`, nebo je odstranit, pokud zatim nemaji byt soucasti API.
5. Dopsat minimalni `README.md`: instalace, nastaveni `PYTHONPATH=src`, autentizace a zakladni priklady.
6. Pridat testy pro:
   - filtrovani nazvu souboru,
   - skladani CDDIS URL,
   - parsovani `MD5SUMS`,
   - dekompresi `.Z`/`.gz`,
   - parsovani SP3,
   - vyber orbitnich souboru podle obdobi,
   - OLS/WLS trend fitting a BIC split.
