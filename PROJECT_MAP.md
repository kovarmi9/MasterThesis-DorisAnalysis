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
|       |   |   +-- loading/
|       |   |   +-- discontinuities/
|       |   +-- spectral/
|       |   +-- orbits/
|       |       +-- loading/
|       |       +-- interpolate/
|       |       +-- track/
|       |       +-- compare/
|       |       +-- transform/
|       +-- output/
|           +-- tables/
|           |   +-- latex.py
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
2. `src/doris/analysis/stations/` resi stanicni STCD data: nacteni, trend a detekci skoku.
3. `src/doris/analysis/spectral/` resi FFT/Lomb-Scargle spektralni analyzu casovych rad.
4. `src/doris/analysis/orbits/` resi SP3 orbity: vyber souboru, parsovani, jednotky, interpolaci, RTN a porovnani.
5. `src/doris/output/tables/` a `src/doris/output/plots/` obsahuji pomocniky pro export tabulek a vzhled grafu.
6. `src/doris/_utils/` obsahuje sdilene funkce pouzite napric vstupnimi workflow.

Importy maji smerovat na package `doris`, napr.:

```python
from doris.input.cddis import download_from_cddis
from doris.analysis.stations.loading import load_station_dataframe
from doris.analysis.stations.discontinuities import detect_jumps_lowess
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

### `stations/loading`

Nacitani STCD stanicnich casovych rad do DataFrame pripraveneho pro analyzu.
Tahle cast vznikla proto, aby se opakovane notebookove kroky kolem STCD souboru
presunuly do knihovny a notebooky uz pracovaly s hotovou tabulkou se standardnimi
casovymi sloupci, vyplnenymi mezerami a konzistentnimi metadaty.

Verejny import:

```python
from doris.analysis.stations.loading import load_station_dataframe
```

#### `load_to_df.py`

`load_station_dataframe(path, start=None, end=None, fill_gaps=True, keep_xyz=False)`

Hlavni vstupni bod pro stanicni data. Sklada nizsi helpery do jedne pipeline:

```text
STCD file
  -> read_stcd_to_dataframe()
  -> add_time_columns()
  -> optional regularize_mjd_grid()
  -> optional date-window filter
  -> optional drop XYZ columns
```

Typicke pouziti v notebooku:

```python
from doris.analysis.stations.loading import load_station_dataframe

df = load_station_dataframe(
    "data/stcd/gop25wd04/gop25wd04.stcd.licb",
    start="2015-01-01",
    end="2025-12-31",
    fill_gaps=True,
    keep_xyz=False,
)
```

Co vraci:

- `MJD` jako puvodni casovy sloupec,
- `Date` jako datetime,
- `year` jako decimalni rok,
- ENU slozky `dE`, `dN`, `dU` a nejistoty `sE`, `sN`, `sU`,
- volitelne i karteske slozky `dX`, `dY`, `dZ`, `sX`, `sY`, `sZ`, pokud `keep_xyz=True`.

Vychozi `keep_xyz=False` je zamerne, protoze analyza v notebooku pracuje hlavne
s lokalnim ENU systemem. Karteske slozky jsou ale porad dostupne pro kontrolu nebo
specialni vypocty pres `keep_xyz=True`.

Metadata uklada do `df.attrs`, zejmena:

- `source_file`,
- `mjd_column`,
- `time_column`,
- `regularize`, pokud se doplnovaly mezery,
- `load_station` s parametry nacitani.

`df.attrs["load_station"]` je prakticke hlavne pri ladeni, protoze rika, z jakeho
souboru tabulka vznikla, jake casove okno bylo aplikovano, zda se vyplnovaly mezery,
zda zustaly XYZ sloupce a kolik radku vysledek obsahuje.

#### `_stcd_reader.py`

- `read_stcd_to_dataframe(path)` parsuje STCD soubor do pandas DataFrame.
- Najde zacatek datove casti, precte sloupce a ulozi metadata o zdrojovem souboru.
- STCD soubor je plain-text tabulka s promennou textovou hlavickou; reader proto
  nejdriv hleda prvni numericky radek a az od nej vola `pandas.read_csv()`.
- Ocekavany pevny sloupcovy format je:

```text
MJD, dX, dY, dZ, sX, sY, sZ, dE, dN, dU, sE, sN, sU
```

- Vsechny sloupce prevadi na cisla, seradi podle `MJD` a do `df.attrs` uklada
  `source_file` a `mjd_column`.
- Pokud soubor neexistuje, neni soubor, nema datove radky nebo se neprecte do
  ocekavaneho tvaru, vyhodi explicitni chybu.

#### `_time_convert.py`

- `add_time_columns(df)` prevadi `MJD` na `Date` a decimalni `year`.
- Interni `_mjd_to_datetime()` a `_decimal_year()` drzi samotne prevody.
- `Date` je vlozen hned za `MJD`.
- `year` je decimalni rok, ktery spravne bere v uvahu delku konkretniho roku
  vcetne prestupnych let.
- `df.attrs["time_column"]` se nastavi na `"Date"`.

#### `_regularize.py`

- `infer_mjd_step(df)` odhaduje typicky krok casove rady v MJD dnech.
- `regularize_mjd_grid(df, ...)` doplni chybejici epochy jako radky s `NaN`, aby navazujici analyza videla mezery explicitne.
- Krok se urcuje z rozdilu serazenych unikatnich hodnot `MJD`; rozdily se zaokrouhli
  na cele dny a vybere se nejcastejsi krok.
- Pri remapovani na pravidelnou mrizku se z prvni do posledni epochy vytvori nova
  osa a puvodni data se na ni reindexuji.
- Nove doplnene epochy maji v datovych sloupcich `NaN`, ale `Date` a `year` se
  znovu dopocitaji z `MJD`, aby byly grafy a filtry pouzitelne.
- Metadata `regularize` obsahuji `step_days`, `rows_added` a `inferred_step`.
- Smysl kroku je metodicky dulezity: detekce skoku a spektralni/rezidualni workflow
  pak neignoruje tiche mezery v pozorovanich.

### `stations/discontinuities`

Detekce skoku a diskontinuit ve stanicnich casovych radach.
Tahle cast vyjmula puvodni experimenty z notebooku do opakovatelneho API.
Notebook tak nemusi obsahovat vlastni implementaci metod a muze jen vybrat vstupni
rezidualni radu, zavolat detektory, vykreslit mezivysledky a exportovat tabulky.

Verejny import:

```python
from doris.analysis.stations.discontinuities import (
    detect_jumps_sliding_window,
    detect_jumps_lowess,
    JumpDetectionResult,
)
```

#### `detect.py`

- `detect_jumps_sliding_window(years, values, window_size=40, shift=40, ...)` porovnava dve sousedni klouzave okenni statistiky.
- `detect_jumps_lowess(years, values, frac=0.2, ...)` vyhladi radu pomoci LOWESS a hleda velke derivace.
- Oba detektory podporuji heuristicky prah a statisticky rezim (`t_test` nebo `z_test` podle metody).
- Vstupy jsou `numpy`-kompatibilni pole casu v decimalnich letech a hodnot rady, typicky aperiodicke residualy v mm.

Obecny vstupni tvar:

```python
years = df["year"].to_numpy()
values = df["aper_dU"].fillna(0).to_numpy()
```

`years` a `values` musi mit stejnou delku. Detektory samy nevyplnuji `NaN`;
notebook pred volanim explicitne pouziva napr. `fillna(0)`, aby bylo jasne, jak se
s chybejicimi hodnotami zachazi.

`detect_jumps_sliding_window(...)`

```python
result = detect_jumps_sliding_window(
    years,
    values,
    window_size=40,
    shift=40,
    threshold_mode="t_test",
    sigma_mult=1.0,
    alpha=0.05,
)
```

Logika:

- pro kazdou pozici vezme prvni okno `seg1` delky `window_size`,
- druhe okno `seg2` zacina o `shift` vzorku pozdeji,
- spocita prumer obou oken `mu1`, `mu2`,
- cas skoku reprezentuje stred mezi casovymi stredu obou oken,
- v rezimu `heuristic` oznaci skok, kdyz `abs(mu2 - mu1) > sigma_mult * sigma`,
- v rezimu `t_test` pouzije Welchuv dvouvyberovy t-test a oznaci skok, kdyz `p < alpha`.

Dulezite parametry:

- `window_size` urcuje, jak dlouhy usek se v kazdem kroku prumeruje.
- `shift` urcuje vzdalenost mezi porovnavanymi okny.
- `threshold_mode="heuristic"` reprodukuje jednodussi notebookovou logiku.
- `threshold_mode="t_test"` dava prahovani statisticky vyznamem pres `alpha`.
- `sigma_mult` se pouziva jen u heuristiky.
- `alpha` se pouziva u t-testu.

`detect_jumps_lowess(...)`

```python
result = detect_jumps_lowess(
    years,
    values,
    frac=0.2,
    threshold_mode="z_test",
    k_sigma=2.0,
    min_abs=3.0,
    alpha=0.05,
)
```

Logika:

- hodnoty se vyhladi metodou LOWESS ze `statsmodels`,
- z vyhlazene rady se spocte numericka derivace `slope = diff(smoothed) / diff(years)`,
- cas derivace lezi ve stredech sousednich epoch `t_mid`,
- robustni meritko rozptylu derivace se urci pomoci MAD,
- v rezimu `heuristic` je prah `max(min_abs, k_sigma * sigma_slope)`,
- v rezimu `z_test` je prah `max(min_abs, z_(alpha/2) * sigma_slope)`,
- skoky jsou epochy, kde `abs(slope)` prekroci prah.

Dulezite parametry:

- `frac` je sirka LOWESS vyhlazeni jako podil delky dat; mensi hodnota zachova vice detailu.
- `min_abs` brani prehnane citlive detekci u velmi hladkych rad.
- `k_sigma` se pouziva jen u heuristickeho rezimu.
- `alpha` se pouziva u `z_test`.

Vysledky obou detektoru se v notebooku ukladaji po komponentach:

```python
sw_results = {"dE": result_e, "dN": result_n, "dU": result_u}
lw_results = {"dE": result_e, "dN": result_n, "dU": result_u}
```

#### `_result.py`

- `JumpDetectionResult` uklada `jumps`, `method`, `threshold`, `threshold_mode`, `alpha` a `extras`.
- Je to spolecny vystup obou detekcnich metod.
- `len(result)` vraci pocet nalezenych skoku.
- `repr(result)` dava rychly ladici souhrn: metoda, pocet skoku, rezim prahu a hodnota prahu.
- `jumps` je `np.ndarray` decimalnich roku.
- `threshold` je ciselny prah pouzity v dane metode; u t-testu je to v implementaci stale
  heuristicka hodnota pro konzistenci vystupu, zatimco samotne rozhodnuti ridi `p < alpha`.
- `extras` je zamerne bohate, aby notebook mohl reprodukovat diagnosticke grafy bez
  prepoctu detekce.

`extras` pro sliding window:

- `mu1`, `mu2` - prumery prvniho a druheho okna,
- `years1`, `years2` - casove stredu oken,
- `sigma` - globalni smerodatna odchylka vstupu,
- `pvalues` - p-hodnoty Welchova testu nebo `None` pri heuristice,
- `window_size`, `shift` - parametry pouzite v behu.

`extras` pro LOWESS:

- `smoothed` - vyhlazena rada,
- `t_mid` - casy derivace,
- `slope` - odhad derivace,
- `sigma_slope` - robustni rozptyl derivace,
- `frac`, `min_abs` - parametry pouzite v behu.

#### `_sliding_window.py` a `_lowess_deriv.py`

- `_sliding_window()` obsahuje vlastni porovnani sousednich oken.
- `_lowess_derivative()` pocita LOWESS vyhlazeni, derivaci a prahovani.
- Tyto soubory jsou interni implementacni vrstva; z notebooku se ma sahat hlavne na funkce z `detect.py`.
- Oddeleni verejne vrstvy (`detect.py`) a numerickeho jadra (`_sliding_window.py`,
  `_lowess_deriv.py`) umoznuje jednoduse menit format vysledku, aniž by se musela
  menit samotna matematicka cast.

## `src/doris/analysis/spectral`

Spektralni analyza casovych rad.

### `periodogram.py`

- `compute_periodogram(...)` je verejny wrapper pro FFT i Lomb-Scargle periodogram.
- Podporuje vstup jako dvojici poli `(t, y)` i jako `pandas.DataFrame` se zadanym `time_col` a jednim nebo vice `value_cols`.
- `method="fft"` pocita jednostranny FFT periodogram pro pravidelne vzorkovane rady.
- `method="lomb_scargle"` pocita Lomb-Scargle periodogram pro nerovnomerne vzorkovane rady.
- Interni `_fft_periodogram_1d(...)` a `_lomb_scargle_periodogram_1d(...)` pracuji nad cistymi `numpy` poli bez pandas.
- `compute_fft_periodogram(...)` je kompatibilitni wrapper pro starsi notebooky/kod.
- Vystup obsahuje `frequency`, `period`, `amplitude`, `power`, `phase_rad`.
- Volitelne omezuje periody pomoci `min_period` a `max_period`.

### `peaks.py`

- `select_periodogram_peaks(periodogram_df, ...)` vybira lokalni peaky.
- Pouziva `scipy.signal.find_peaks`.
- Slouzi pro vytazeni dominantnich period z periodogramu.

### `significance.py`

- `estimate_periodogram_threshold(...)` odhaduje amplitudovy nebo vykonovy prah periodogramu pomoci permutacniho nuloveho modelu.
- Opakovane nahodne promicha hodnoty casove rady, spocita periodogram a ulozi maximum zvoleneho sloupce, typicky `amplitude`.
- Vraceny prah je kvantil urceny parametrem `false_alarm_level`, napr. `0.95`.
- `find_significant_peaks(periodogram, threshold, ...)` hleda lokalni vrcholy nad zadanym prahem.
- Funkce pracuji s vystupem `compute_periodogram()` a podporuji i periodogramy s vice komponentami pres sloupec `component`.

### `__init__.py`

Re-exportuje:

- `compute_periodogram`
- `compute_fft_periodogram`
- `select_periodogram_peaks`
- `estimate_periodogram_threshold`
- `find_significant_peaks`

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

Tahle cast je hlavni vstupni brana pro orbitni data. Umi najit spravne SP3 soubory podle data, precist jejich obsah do `pandas.DataFrame`, vyresit prekryvy/duplicity, prevest jednotky a casove skaly a ulozit diagnosticka metadata do `df.attrs`.

Nejdulezitejsi verejne importy:

```python
from datetime import date
from pathlib import Path

from doris.analysis.orbits.loading import (
    load_orbit_dataframe,
    load_orbit_day,
    iter_orbit_days,
    select_orbit_files_for_period,
    select_file_for_day,
)
```

Typicke pouziti:

```python
df = load_orbit_dataframe(
    Path("data/orbits/gop/srl"),
    start=date(2024, 1, 1),
    end=date(2024, 1, 7),
    target_time_scale="TAI",
    add_epoch=True,
)

print(df.columns)
print(df.attrs["load_to_df"])
```

Co typicky vraci DataFrame:

- polohove sloupce `x`, `y`, `z`,
- rychlostni sloupce `vx`, `vy`, `vz`,
- casovy sloupec typu `MJD_TAI`, `MJD_UTC` nebo `MJD_GPS`,
- volitelne `epoch_TAI` / `epoch_UTC` / `epoch_GPS`, pokud je `add_epoch=True`,
- `satellite`, pokud je v datech vice satelitu; pokud je jen jeden, satelit je presunut do `df.attrs["satellite"]`,
- `source_file`, pokud se sklada vice SP3 souboru.

Dulezita metadata v `df.attrs`:

- `source_files` - seznam souboru, ze kterych DataFrame vznikl,
- `time_scale` - aktualni casova skala,
- `time_column` - aktualni casovy sloupec,
- `coordinate_system` - souradnicovy system detekovany z hlavicky SP3,
- `position_unit` a `velocity_unit`,
- `deduplication` - informace o odstraneni duplicit,
- `load_to_df` - parametry celeho nacitani a souhrny kontrol.

#### `load_to_df.py`

Vysoka vrstva pro nacteni orbit do pandas DataFrame.

`load_orbit_dataframe(source, start, end, ...)`

Nacte cele obdobi od `start` do `end` vcetne. Je to nejpohodlnejsi funkce pro beznou praci s orbitami.

Pipeline uvnitr:

```text
source + start/end
  -> select_orbit_files_for_period()
  -> optional inspect_orbit_file_coverage()
  -> read_sp3_files_to_dataframe()
  -> deduplicate_orbit_epochs()
  -> optional convert_trajectory_units()
  -> optional inspect_orbit_time_series()
  -> df.attrs["load_to_df"]
```

Hlavni parametry:

- `source: Path` - slozka, kde jsou SP3 soubory.
- `start: date`, `end: date` - pozadovane datumove obdobi.
- `recursive=True` - hleda i v podslozkach; vhodne pro struktury typu `data/orbits/gop/srl`.
- `dedup_keep="first"` - jak resit duplicity stejne epochy: `first`, `last`, nebo `mean`.
- `compute_statistics=False` - zda pri deduplikaci pocitat statistiky prekryvu.
- `normalize=True` - zda prevest jednotky/cas na jednotny format.
- `target_time_scale="TAI"` - cilova casova skala po normalizaci.
- `add_epoch=True` - prida citelny datetime sloupec, napr. `epoch_TAI`.
- `inspect_coverage=True` - zkontroluje navaznost souboru podle nazvu.
- `inspect_continuity=True` - zkontroluje pravidelnost casove rady po nacteni.
- `expected_step_seconds=60` - ocekavany krok mezi epochami.

Pouziti:

```python
df = load_orbit_dataframe(
    Path("data/orbits/ssa/srl"),
    date(2024, 1, 1),
    date(2024, 1, 3),
    dedup_keep="mean",
    target_time_scale="TAI",
)
```

`load_orbit_day(source, day, window=0.0, ...)`

Nacte data pro jeden den. Pouziva stejne cteni, deduplikaci a volitelnou normalizaci jako `load_orbit_dataframe()`, ale po nacteni DataFrame jeste oreze na interval daneho dne.

- `day: date` - den, ktery chci nacist.
- `window: float` - rozsireni denniho okna v MJD dnech. Napr. `window=0.01` prida okraj okolo dne; uzitecne pro interpolaci.
- `add_epoch=False` ve vychozim stavu, protoze u dennich iteraci se casto chce mensi DataFrame.
- `inspect_coverage=False` a `inspect_continuity=False` ve vychozim stavu, aby denni smycky nebyly zbytecne drahe.

Pouziti:

```python
df_day = load_orbit_day(
    Path("data/orbits/gop/srl"),
    date(2024, 1, 1),
    window=0.01,
    target_time_scale="TAI",
)
```

`iter_orbit_days(source, start, end, skip_missing=True, **kwargs)`

Generator pro praci po jednotlivych dnech. Pro kazdy den vola `load_orbit_day()` a vraci dvojici `(day, df_day)`.

- `skip_missing=True` znamena, ze dny bez dat preskoci.
- `skip_missing=False` znamena, ze pri chybejicim dni vyhodi chybu.
- `**kwargs` se predavaji primo do `load_orbit_day()`.

Pouziti:

```python
for day, df_day in iter_orbit_days(
    Path("data/orbits/ssa/srl"),
    date(2024, 1, 1),
    date(2024, 1, 31),
    window=0.01,
):
    print(day, len(df_day))
```

#### `_filename_parsers.py`

Parsuje metadata z nazvu souboru.

`FilenameInfo`

Dataclass s informacemi odvozenymi pouze z nazvu souboru:

- `path` - puvodni cesta,
- `start`, `end` - datumove pokryti souboru,
- `provider` - zdroj/solution family, napr. `GOP`,
- `satellite` - satelit, napr. `srl`, `cs2`, `ja3`,
- `version` - verze, napr. `V99`,
- `scheme` - parser, ktery soubor rozpoznal.

`parse_cddis_filename(path)`

Rozpoznava CDDIS styl s rokem a dnem v roce:

```text
ssasrl20.b22002.e22010.D__.sp3.001
        ^^^^^  ^^^^^
        start  end
```

Tento parser hleda casti `.bYYDDD.eYYDDD.`. Napr. `22002` znamena rok 2022, druhy den roku.

`parse_gop_filename(path)`

Rozpoznava GOP-like styl:

```text
GOP_cs2_240101_240101_V99.sp3
 ^   ^   ^      ^      ^
 |   |   start  end    version
 provider satellite
```

`parse_filename_info(path)`

Centralni dispatch. Zkusi vsechny zname parsery v poradi:

1. `parse_gop_filename`,
2. `parse_cddis_filename`.

Kdyz zadny parser nesedi, vrati `None`. Na tom stoji vyber souboru podle data.

#### `_orbit_file_selection.py`

`select_orbit_files_for_period(root, start, end, recursive=False)`

Vybere vsechny soubory, jejichz datumove pokryti se prekryva s pozadovanym intervalem `[start, end]`.

Pouziva `parse_filename_info()`, takze bere jen soubory s rozpoznanym nazvem. Soubory bez rozpoznatelneho datumu ignoruje.

Pouziti:

```python
paths = select_orbit_files_for_period(
    Path("data/orbits/gop/srl"),
    start=date(2024, 1, 1),
    end=date(2024, 1, 7),
    recursive=True,
)
```

`select_file_for_day(root, day, recursive=True)`

Vybere jeden nejvhodnejsi soubor pokryvajici konkretni den. Pokud den pokryva vic souboru, preferuje soubor, ktery ma lepsi okoli kolem ciloveho dne. To je uzitecne u interpolace, kde okraje souboru byvaji citlivejsi.

Vraci `FilenameInfo | None`, tedy metadata vybraneho souboru nebo `None`, pokud nic nenasel.

#### `_sp3_reader.py`

SP3 parser.

`read_sp3_to_dataframe(path)`

Nacte jeden SP3 soubor do DataFrame. Je to nizsi vrstva; obvykle ji neni potreba volat primo, pokud staci `load_orbit_dataframe()`.

Co parser dela:

- rozdeli soubor na hlavicku a telo,
- z hlavicky detekuje casovou skalu (`GPS`, `UTC`, `TAI`) a souradnicovy system (`ITRF`, `IGS`, `GCRF`, ...),
- cte epochy z radku zacinajicich `*`,
- cte pozice z radku `P`,
- cte rychlosti z radku `V`,
- prevadi epochu na MJD,
- uklada pozice a rychlosti do radku DataFrame.

Vystupni sloupce:

- `MJD_<TIME_SCALE>`, napr. `MJD_GPS`,
- `x`, `y`, `z`,
- `vx`, `vy`, `vz`,
- `satellite`, pokud je v souboru vice satelitu.

Metadata:

- `df.attrs["source_files"]`,
- `df.attrs["time_scale"]`,
- `df.attrs["time_column"]`,
- `df.attrs["coordinate_system"]`,
- `df.attrs["position_unit"] = "km"`,
- `df.attrs["velocity_unit"] = "dm/s"`.

Pozor: po samotnem SP3 readeru jsou jednotky porad ve SP3 jednotkach, typicky `km` a `dm/s`. Na metry a `m/s` je prevadi az `convert_trajectory_units()`.

`read_sp3_files_to_dataframe(paths)`

Nacte vice SP3 souboru a spoji je do jednoho DataFrame.

- u kazdeho souboru vola `read_sp3_to_dataframe()`,
- neuspesne soubory nezastavi okamzite cele cteni; uklada je do `failed_source_files`,
- pridava sloupec `source_file`,
- vysledek seradi podle casu a pripadne podle satelitu,
- metadata bere z prvniho uspesne nacteneho souboru.

#### `_convert_trajectory_units.py`

Normalizace casu a jednotek.

`convert_trajectory_units(df, target_time_scale="TAI", add_epoch=False)`

Normalizuje DataFrame po nacteni SP3.

Co dela:

- detekuje zdrojovou casovou skalu z `df.attrs["time_scale"]` nebo ze sloupce `MJD_*`,
- prevede cas na cilovou skalu `TAI`, `UTC` nebo `GPS`,
- prejmenuje/cisti MJD sloupce tak, aby zustal jen aktualni `MJD_<target>`,
- prevede pozice:
  - `km -> m`,
  - `m -> m`,
- prevede rychlosti:
  - `dm/s -> m/s`,
  - `km/s -> m/s`,
  - `m/s -> m/s`,
- volitelne prida datetime sloupec `epoch_<target>`.

Po prevodu nastavuje:

- `df.attrs["source_time_scale"]`,
- `df.attrs["source_time_column"]`,
- `df.attrs["time_scale"]`,
- `df.attrs["time_column"]`,
- `df.attrs["position_unit"] = "m"`,
- `df.attrs["velocity_unit"] = "m/s"`,
- `df.attrs["normalized"] = True`.

Pouziti:

```python
raw = read_sp3_files_to_dataframe(paths)
df = convert_trajectory_units(raw, target_time_scale="TAI", add_epoch=True)
```

#### `_deduplicate.py`

`deduplicate_orbit_epochs(df, keep="mean", compute_statistics=True)`

Odstranuje duplicitni epochy po spojeni vice souboru.

Klic duplicity:

- vzdy `df.attrs["time_column"]`,
- plus `satellite`, pokud je sloupec v DataFrame.

Strategie:

- `keep="first"` - ponecha prvni radek v duplicitni skupine,
- `keep="last"` - ponecha posledni radek,
- `keep="mean"` - zprumeruje stavove sloupce `x`, `y`, `z`, `vx`, `vy`, `vz`.

Metadata uklada do `df.attrs["deduplication"]`:

- `strategy`,
- `overlap_count`,
- `column_std` pro stavove sloupce, pokud je `compute_statistics=True`.

Vysoka funkce `load_orbit_dataframe()` ma vychozi `dedup_keep="first"` a `compute_statistics=False`, aby nacitani bylo rychlejsi.

#### `_coverage.py`

`inspect_orbit_file_coverage(paths)`

Kontroluje navaznost souboru pred samotnym ctenim dat. Pouziva pouze datumove pokryti odvozene z nazvu souboru.

Pro kazdou sousedni dvojici urci:

- `gap` - mezi soubory chybi dny,
- `touching` - soubory na sebe presne navazuji,
- `overlap` - soubory se prekryvaji.

Vraci DataFrame s dvojicemi souboru a sloupci jako `left_file`, `right_file`, `relation`, `gap_days`, `overlap_days`.

Souhrn je v:

```python
coverage = inspect_orbit_file_coverage(paths)
coverage.attrs["coverage_summary"]
```

#### `_continuity.py`

`inspect_orbit_time_series(df, expected_step_seconds=60)`

Kontroluje pravidelnost uz nacteneho DataFrame podle aktualniho casoveho sloupce v `df.attrs["time_column"]`.

Hleda:

- `duplicate` - nulovy casovy krok,
- `gap` - krok vetsi nez ocekavany,
- `irregular` - krok mensi/jiny nez ocekavany, ale ne nulovy.

Vraci DataFrame problematickych kroku se sloupci:

- `time_prev`,
- `time_next`,
- `step_seconds`,
- `issue_type`.

Souhrn je v:

```python
issues = inspect_orbit_time_series(df, expected_step_seconds=60)
issues.attrs["time_series_summary"]
```

#### `__init__.py`

Verejne z loading package exportuje:

- `load_orbit_dataframe`
- `load_orbit_day`
- `iter_orbit_days`
- `select_orbit_files_for_period`
- `select_file_for_day`

To znamena, ze pro bezne pouziti neni potreba importovat z podmodulu:

```python
from doris.analysis.orbits.loading import load_orbit_dataframe
```

Interni/helper funkce typu `read_sp3_to_dataframe()`, `convert_trajectory_units()` nebo `inspect_orbit_time_series()` existuji v podmodulech a dava smysl je volat primo hlavne pri ladeni nebo kdyz chces pipeline rozebrat na jednotlive kroky.

#### Jak to popsat v textu prace

Presnejsi formulace pro kapitolu o nacitani dat:

```latex
\subsection{Nacteni dat}

Nacteni orbitnich dat druzic ze souboru ve formatu \texttt{SP3}
je v knihovne zajisteno modulem
\texttt{doris.analysis.orbits.loading}. Modul poskytuje vysoko-urovnove
funkce, ktere nejprve vyberou soubory pokryvajici pozadovane casove
obdobi, nasledne je nactou do struktury \texttt{pandas.DataFrame},
odstrani pripadne duplicitni epochy a volitelne sjednoti jednotky
a casovou skalu.

Funkce \texttt{load\_orbit\_dataframe} slouzi k nacteni orbitnich dat
pro zvoleny interval datumu. Na zaklade nazvu souboru vybere vsechny
soubory, jejichz casove pokryti se prekryva s pozadovanym intervalem,
tyto soubory nacte a spoji do jednoho objektu typu
\texttt{pandas.DataFrame}. Funkce \texttt{load\_orbit\_day} je urcena
pro nacteni dat pro jeden konkretni den. Nemusi jit nutne o jediny
vstupni soubor; funkce opet vybere vsechny soubory pokryvajici dany
den a vysledna data oreze na denni casove okno, pripadne rozsirene
o zadany okraj. Funkce \texttt{iter\_orbit\_days} poskytuje iterator,
ktery vola \texttt{load\_orbit\_day} postupne pro jednotlive dny
ve zvolenem intervalu.

Samotne cteni formatu \texttt{SP3} provadi nizsi vrstva modulu, zejmena
funkce \texttt{read\_sp3\_to\_dataframe} a
\texttt{read\_sp3\_files\_to\_dataframe}. Ty parsujou epochy, polohove
zaznamy a rychlostni zaznamy a ukladaji je do sloupcu
\texttt{x}, \texttt{y}, \texttt{z}, \texttt{vx}, \texttt{vy}, \texttt{vz}
a \texttt{MJD\_<TIME\_SCALE>}. Metadata, jako je casova skala,
casovy sloupec, souradnicovy system a zdrojove soubory, jsou ulozena
v atributu \texttt{DataFrame.attrs}.

Pro prevod jednotek a sjednoceni casove skaly slouzi funkce
\texttt{convert\_trajectory\_units}. Ta prevadi polohy typicky z kilometru
na metry, rychlosti typicky z decimetru za sekundu na metry za sekundu
a casovou reprezentaci na zvolenou skalu, napr. \texttt{TAI}. Pri pouziti
parametru \texttt{normalize=True} je tato normalizace provedena automaticky
v ramci funkci \texttt{load\_orbit\_dataframe} a \texttt{load\_orbit\_day}.
```

Obsahove dulezite opravy proti caste zjednodusene formulaci:

- `load_orbit_dataframe()` vybira soubory podle pokryti v nazvu a teprve potom je nacita/spojuje.
- `load_orbit_day()` neni "nacteni jednoho souboru"; je to nacteni jednoho dne. Muze pouzit vic souboru, pokud dany den pokryvaji nebo pokud je potreba okrajove okno.
- `iter_orbit_days()` neni samostatny parser; je to generator, ktery opakovane vola `load_orbit_day()`.
- `convert_trajectory_units()` je helper pro normalizaci, ale pri `normalize=True` se vola automaticky z vyssich loading funkci.
- Surovy SP3 reader nechava jednotky podle SP3 metadat (`km`, `dm/s`); sjednoceni na `m`, `m/s` dela az normalizacni krok.

### `orbits/interpolate`

Interpolace trajektorii na referencni epochy.

Tahle cast slouzi k tomu, aby bylo mozne porovnat dve orbitni trajektorie ve stejnem case. Typicky ma jedna trajektorie jine epochy nez druha, proto se jedna z nich interpoluje na casy referencni trajektorie. V projektu je implementovana Hermitova interpolace polohy z polohy a rychlosti.

Zjednoduseny tok:

```text
source trajectory: t, x, y, z, vx, vy, vz
reference trajectory: t_ref
  -> interpolate_trajectory_to_reference()
     -> prepare sorted source matrix [t, x, y, z, vx, vy, vz]
     -> call hermite_at_time(M, t_ref, degree=...)
     -> return DataFrame at reference epochs
```

#### Dokumentace modulu `doris.analysis.orbits.interpolate`

Modul je rozdeleny na dve vrstvy:

- `hermite.py` - cista numericka interpolace nad `numpy` poli.
- `interpolate.py` - pohodlny wrapper pro `pandas.DataFrame`.
- `__init__.py` - verejne exporty celeho podbalicku.

Verejne API:

```python
from doris.analysis.orbits.interpolate import (
    hermite_at_time,
    interpolate_trajectory_to_reference,
    interpolate_like,
)
```

Exporty podle `__init__.py`:

- `hermite_at_time` - nizkourovnova Hermitova interpolace polohy.
- `interpolate_trajectory_to_reference` - DataFrame wrapper pro interpolaci jedne trajektorie na epochy druhe.
- `interpolate_like` - zpetne kompatibilni alias pro `interpolate_trajectory_to_reference`.

Kdy pouzit kterou funkci:

- Chci rychle interpolovat raw `numpy` pole: pouzit `hermite_at_time()`.
- Mam dve orbitni tabulky/DataFrame a chci jednu prevest na casy druhe: pouzit `interpolate_trajectory_to_reference()`.
- Mam starsi notebook/kod, kde se volalo `interpolate_like()`: muze zustat, dela totiz to same jako `interpolate_trajectory_to_reference()`.

Minimalni vstupni predpoklady:

- casy musi byt ciselne,
- zdrojova trajektorie musi mit polohu i rychlost,
- casy zdroje po serazeni nesmi obsahovat duplicity,
- referencni casy musi lezet uvnitr casoveho rozsahu zdroje,
- dotazy nesmi byt tak blizko okraje, aby nebylo mozne vybrat dost uzlu pro dany `degree`.

#### `hermite.py`

Implementace Hermitovy interpolace polohy z casu, poloh a rychlosti.

`hermite.py` je nizkourovnova numericka implementace. Nepracuje s DataFrame, ale s poli `numpy`.

Hlavni verejna funkce:

```python
from doris.analysis.orbits.interpolate import hermite_at_time
```

`hermite_at_time(data, t_query, degree=11, drop_nan=True, assume_sorted=False, return_idx=False, atol=1e-12)`

Co dela:

- vezme casy `t`, polohy `r = (x, y, z)` a rychlosti `v = (vx, vy, vz)`,
- pro kazdy dotazovany cas `t_query` vybere okoli interpolacnich uzlu,
- z hodnot polohy a prvnich derivaci rychlosti sestavi klasicky Hermituv interpolacni polynom,
- vrati interpolovanou polohu v dotazovanem case.

Parametry:

- `data` - zdrojova trajektorie. Muze byt `(t, r, v)`, `(t, x, y, z, vx, vy, vz)`, nebo matice `(N, 7)`.
- `t_query` - jeden cas nebo pole casu, ve kterych chci ziskat interpolovanou polohu.
- `degree=11` - stupen Hermitova polynomu. Musi byt lichy.
- `drop_nan=True` - pred interpolaci odstrani radky, kde je `NaN` v case, poloze nebo rychlosti.
- `assume_sorted=False` - pokud `False`, funkce si data sama seradi podle casu. Pokud vis, ze jsou data uz serazena, `True` setri praci.
- `return_idx=False` - pokud `True`, vrati krom interpolovane polohy i indexy uzlu pouzitych pro kazdy dotaz.
- `atol=1e-12` - tolerance pro pripad, kdy je dotazovany cas prakticky totozny s existujicim uzlem.

Podporovane vstupy `data`:

```python
# 1) trojice casu, poloh a rychlosti
data = (t, r, v)

# 2) sedm samostatnych vektoru
data = (t, x, y, z, vx, vy, vz)

# 3) matice tvaru (N, 7)
data = M  # sloupce: [t, x, y, z, vx, vy, vz]
```

Vystup:

- pokud `t_query` je jedno cislo, vraci `np.ndarray` tvaru `(3,)`,
- pokud `t_query` je pole delky `Q`, vraci `np.ndarray` tvaru `(Q, 3)`,
- pokud `return_idx=True`, vrati navic indexy pouzitych uzlu.

Priklady vystupu:

```python
# Jeden cas -> jedna poloha [x, y, z]
r = hermite_at_time(M, 60310.5, degree=11)
# r.shape == (3,)

# Vice casu -> matice poloh
r = hermite_at_time(M, np.array([60310.1, 60310.2]), degree=11)
# r.shape == (2, 3)

# Vratit i pouzite uzly
r, idx = hermite_at_time(M, np.array([60310.1, 60310.2]), return_idx=True)
# idx.shape == (2, n_nodes)
```

Priklad:

```python
M = df[["MJD_TAI", "x", "y", "z", "vx", "vy", "vz"]].to_numpy()
t_query = reference_df["MJD_TAI"].to_numpy()

r_interp = hermite_at_time(
    M,
    t_query,
    degree=11,
    assume_sorted=True,
)
```

Stupen interpolace:

- `degree` musi byt lichy (`3`, `5`, `7`, `9`, `11`, ...),
- pocet pouzitych uzlu je `n_nodes = (degree + 1) // 2`,
- napr. `degree=11` pouziva 6 uzlu,
- cim vyssi stupen, tim vice okolnich bodu je potreba.

Vyber uzlu:

- funkce najde pozici dotazovaneho casu pomoci `np.searchsorted`,
- vybere `n_nodes` uzlu kolem interpolacni mezery,
- pro `degree=11` tedy 3 uzly vlevo a 3 uzly vpravo,
- pokud je dotaz moc blizko okraje a neni dost uzlu, vyhodi `ValueError`.

Specialni pripady a kontroly:

- pokud `drop_nan=True`, radky s `NaN` v case, poloze nebo rychlosti se vyhodi,
- pokud `assume_sorted=False`, data se seradi podle casu,
- po serazeni musi byt casy striktne rostouci; duplicity vyhodi chybu,
- pokud se `t_query` trefi primo do uzlu v toleranci `atol`, funkce vrati primo zadanou polohu bez interpolace.

Typicke chyby:

- `ValueError: degree must be odd` - `degree` je sudy.
- `ValueError: Not enough points for degree=...` - pro zvoleny stupen neni dost bodu.
- `ValueError: Times must be strictly increasing and without duplicates` - ve zdroji jsou duplicitni nebo nesezarazene casy po priprave.
- `ValueError: Query too close to edge...` - dotazovany cas je moc blizko zacatku nebo konci rady.

Interni funkce v `hermite.py`:

- `_coerce_inputs(data)` sjednoti ruzne vstupni formaty na trojici `t`, `r`, `v`.
- `_as_query_array(t_query)` prevede dotazovane casy na 1D pole a pamatuje si, zda vstup byl scalar.
- `_exact_node_index(t_sorted, q, atol)` resi pripad, kdy dotaz lezi primo v uzlu.
- `_select_nodes(t_sorted, t_query, n_nodes)` vybere uzly okolo dotazovaneho casu.
- `lagrange_basis(x_nodes, x)` pocita hodnoty Lagrangeovych bazi.
- `lagrange_basis_deriv_at_nodes(x_nodes)` pocita derivace bazi v uzlech.
- `hermite_interpolate(x_nodes, y_nodes, dy_nodes, x)` provede samotnou interpolaci pro jeden cas.

Jak je Hermituv polynom slozeny:

- `lagrange_basis(x_nodes, x)` pocita Lagrangeovy bazove polynomy `L_k(x)`,
- `lagrange_basis_deriv_at_nodes(x_nodes)` pocita derivace `L'_k(x_k)` v uzlech,
- `hermite_interpolate(x_nodes, y_nodes, dy_nodes, x)` slozi klasicky Hermituv tvar:

```text
H_k(x)    = (1 - 2 (x - x_k) L'_k(x_k)) L_k(x)^2
Hhat_k(x) = (x - x_k) L_k(x)^2

y(x) = sum_k H_k(x) y_k + Hhat_k(x) y'_k
```

V tomto projektu:

- `x_nodes` jsou casy,
- `y_nodes` jsou polohy `(x, y, z)`,
- `dy_nodes` jsou rychlosti `(vx, vy, vz)`,
- funkce interpoluje pouze polohu, ne rychlost.

#### `interpolate.py`

Pandas wrapper nad Hermitovou interpolaci.

`interpolate.py` je prakticka pandas vrstva nad `hermite_at_time()`. Tohle je funkce, kterou se vyplati pouzivat v analyzach a pri porovnani orbit.

```python
from doris.analysis.orbits.interpolate import interpolate_trajectory_to_reference
```

`interpolate_trajectory_to_reference(df_source, df_reference, method="hermite", degree=11, time_col=None, source_window_margin_points=None, preserve_reference_columns=True)`

Co dela:

- najde spolecny casovy sloupec,
- ze zdrojove trajektorie vybere `time_col`, `x`, `y`, `z`, `vx`, `vy`, `vz`,
- odstrani radky s neplatnymi hodnotami,
- seradi zdroj podle casu,
- overi, ze referencni casy lezi uvnitr casoveho intervalu zdroje,
- zavola `hermite_at_time()`,
- vrati DataFrame na epochach referencni trajektorie.

Parametry:

- `df_source` - zdrojova trajektorie, ktera se bude interpolovat.
- `df_reference` - referencni trajektorie; jeji casy urcuji vystupni epochy.
- `method="hermite"` - zatim je implementovana pouze hodnota `"hermite"`.
- `degree=11` - stupen Hermitovy interpolace predany do `hermite_at_time()`.
- `time_col=None` - spolecny casovy sloupec. Pokud neni zadany, funkce ho zkusi najit automaticky.
- `source_window_margin_points=None` - kompatibilitni parametr, aktualne se v implementaci nepouziva.
- `preserve_reference_columns=True` - pokud `True`, vystup ponecha sloupce z referencniho DataFrame a jen prepise/doplni interpolovane stavove slozky.

Casovy sloupec:

- pokud predas `time_col`, musi existovat v obou DataFrame,
- pokud `time_col=None`, funkce zkusi postupne:
  1. `t_sec_round`,
  2. `t_sec`,
  3. `MJD_TAI`,
  4. `MJD_GPS`.

Minimalni pozadovane sloupce ve zdroji:

```text
time_col, x, y, z, vx, vy, vz
```

Reference musi obsahovat alespon stejny casovy sloupec.

Interni kroky v `interpolate.py`:

- `_resolve_time_column()` najde nebo overi spolecny casovy sloupec.
- `_prepare_source_matrix()` vybere `time_col`, `x`, `y`, `z`, `vx`, `vy`, `vz`, vyhodi neplatne radky, seradi zdroj a vytvori matici `(N, 7)`.
- `_prepare_reference()` zkopiruje a seradi referencni DataFrame a vytahne dotazovane casy.
- `interpolate_trajectory_to_reference()` zkontroluje intervaly, zavola `hermite_at_time()` a slozi vysledny DataFrame.

Priklad pouziti:

```python
df_interp = interpolate_trajectory_to_reference(
    df_source=df_gop,
    df_reference=df_ssa,
    time_col="MJD_TAI",
    degree=11,
)
```

Priklad s automatickym vyberem casoveho sloupce:

```python
df_interp = interpolate_trajectory_to_reference(
    df_source=df_a,
    df_reference=df_b,
    degree=7,
)
```

To funguje jen pokud oba DataFrame sdileji jeden z podporovanych casovych sloupcu: `t_sec_round`, `t_sec`, `MJD_TAI`, nebo `MJD_GPS`.

Priklad bez zachovani referencnich sloupcu:

```python
df_interp = interpolate_trajectory_to_reference(
    df_source=df_a,
    df_reference=df_b,
    time_col="MJD_TAI",
    preserve_reference_columns=False,
)
```

Vystup pak obsahuje hlavne casovy sloupec a interpolovane `x`, `y`, `z`, `vx`, `vy`, `vz`.

Vysledek:

- pokud `preserve_reference_columns=True`, vystup zacina jako kopie `df_reference`,
- sloupce `x`, `y`, `z` jsou nahrazeny interpolovanou polohou zdroje,
- `vx`, `vy`, `vz` jsou nastaveny na `NaN`, protoze soucasny Hermite backend vraci pouze polohu,
- metadata obsahuji:
  - `interpolation_method = "hermite"`,
  - `interpolation_degree`,
  - `interpolation_time_column`,
  - `interpolation_source_rows`,
  - `interpolation_reference_rows`.

Omezeni:

- `method` muze byt zatim pouze `"hermite"`,
- `source_window_margin_points` je ponechany kvuli kompatibilite API, ale v implementaci se nepouziva,
- referencni casy nesmi byt mimo interval zdrojove trajektorie,
- kvuli vyberu uzlu nesmi byt dotazy prilis blizko okraje zdrojove rady; v praxi se to casto resi orezem okraju, napr. v `compare_trajectories(edge_trim=...)`.

Typicke chyby:

- `KeyError: No common time column found` - DataFrame nemaji spolecny casovy sloupec a `time_col` nebyl predan explicitne.
- `KeyError: df_source is missing required columns` - zdroj nema nektery ze sloupcu `x`, `y`, `z`, `vx`, `vy`, `vz`.
- `ValueError: Only method='hermite' is supported` - parametr `method` ma jinou hodnotu.
- `ValueError: Reference times are outside source interpolation interval` - referencni casy presahuji zdrojovou trajektorii.
- `ValueError: Query too close to edge...` - predany rozsah je sice uvnitr zdroje, ale pro zvoleny `degree` neni dost uzlu na okraji.

`interpolate_like(...)`

Zpetne kompatibilni alias pro `interpolate_trajectory_to_reference(...)`.

Podpis je stejny jako u hlavni funkce:

```python
interpolate_like(
    df_source,
    df_reference,
    method="hermite",
    degree=11,
    time_col=None,
    source_window_margin_points=None,
    preserve_reference_columns=True,
)
```

Pouziti:

```python
df_interp = interpolate_like(df_source=df_a, df_reference=df_b, time_col="MJD_TAI")
```

Typicky vztah k porovnani orbit:

```text
df_a, df_b
  -> compare_trajectories(df_a, df_b)
     -> oreze okraje df_b podle edge_trim
     -> interpolate_trajectory_to_reference(df_a, df_b_trimmed)
     -> spocita rozdily df_b_trimmed - df_a_interpolated
```

#### Jak popsat Hermitovu interpolaci v textu prace

Mozna formulace:

```latex
\subsection{Hermitova interpolace orbit}

Pro porovnani dvou orbitnich reseni je nutne vyjadrit obe trajektorie
ve stejnych epochach. V knihovne je tento krok realizovan modulem
\texttt{doris.analysis.orbits.interpolate}, ktery pouziva Hermitovu
interpolaci polohy. Interpolace vyuziva nejen polohove slozky
\texttt{x}, \texttt{y}, \texttt{z}, ale take rychlostni slozky
\texttt{vx}, \texttt{vy}, \texttt{vz}, ktere predstavuji prvni derivace
polohy podle casu.

Nizkourovnova funkce \texttt{hermite\_at\_time} pracuje s poli
obsahujicimi cas, polohu a rychlost. Pro kazdou pozadovanou epochu
vybere okoli interpolacnich uzlu a sestavi Hermituv interpolacni
polynom. Stupen polynomu je zadavan parametrem \texttt{degree} a musi
byt lichy; pocet pouzitych uzlu je roven
\texttt{(degree + 1) / 2}. Ve vychozim nastaveni \texttt{degree=11}
je tedy pouzito sest okolnich uzlu.

Pro praci s tabulkami \texttt{pandas.DataFrame} slouzi funkce
\texttt{interpolate\_trajectory\_to\_reference}. Ta interpoluje
zdrojovou trajektorii na epochy referencni trajektorie. Vstupni
trajektorie musi obsahovat casovy sloupec a stavove slozky
\texttt{x}, \texttt{y}, \texttt{z}, \texttt{vx}, \texttt{vy}, \texttt{vz}.
Vystupem je \texttt{DataFrame} na referencnich epochach, ve kterem jsou
sloupce \texttt{x}, \texttt{y}, \texttt{z} nahrazeny interpolovanou
polohou. Soucasna implementace vraci pouze interpolovanou polohu,
nikoli interpolovanou rychlost; rychlostni sloupce jsou proto ve vystupu
nastaveny na \texttt{NaN}.
```

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

## `src/doris/output/tables`

Export tabulek do ruznych vystupnich formatu. Aktualne je implementovany LaTeX export.
Tenhle modul vznikl kvuli workflow v notebooku: tabulku je potreba rychle vygenerovat
z `pandas.DataFrame`, zkontrolovat jeji LaTeX zdroj primo pres `print()` a teprve potom
ji ulozit do projektu bez rucniho otevirani `.tex` souboru.

Princip struktury:

```text
src/doris/output/
  tables/
    __init__.py
    latex.py
  plots/
```

`tables/` je hlavni domena: pracuje s tabulkami jako vystupnim artefaktem.
`latex.py` je konkretni format exportu. To je cistsi nez starsi struktura
`output/latex/tables.py`, protoze LaTeX neni hlavni domena, ale format tabulkoveho
vystupu.

Nove doporucene importy:

```python
from doris.output.tables import Col, save_latex_table
```

nebo explicitne podle formatu:

```python
from doris.output.tables.latex import save_latex_table
```

### `tables/latex.py`

- `Col(source, header, decimals)` popisuje jeden vystupni sloupec: zdrojovy nazev, LaTeX hlavicku a pocet desetinych mist.
- `make_latex_table(df, cols, ...)` vytvori LaTeX zdroj tabulky bez zapisu na disk.
- `print_latex_table(df, cols, ...)` vytvori LaTeX zdroj, vypise ho pres `print()` a vrati stejny string.
- `save_latex_table(df, path, cols, ...)` vytvori tabulku, zalozi cilove adresare a zapise `.tex` soubor.
- Relativni `path` se uklada pod projektove `LaTeX/tables`; pripona `.tex` se doplni automaticky.
- `latex_table_path(...)` sklada cesty pod `LaTeX/tables` nebo zrcadli cestu existujiciho grafu z `LaTeX/images`.
- Export pouziva `pandas.DataFrame.to_latex()` a podporuje `caption`, `label`, `escape`, `index` a `position`.

#### Cile API

Modul resi tri oddelene potreby:

1. vyrobit LaTeX string bez zapisu na disk,
2. jednoduse ho vypsat v notebooku pres `print`,
3. ulozit stejny text do `.tex` souboru v projektove strukture.

Diky tomu je format tabulek laditelny primo v kodu:

```python
tex = make_latex_table(df, cols=[...])
print(tex)
```

nebo jeste kratsi:

```python
print_latex_table(df, cols=[...])
```

Pri finalnim ulozeni se pouziva stejny generator, takze to, co se vytiskne do
notebooku, je presne to, co skonci v `.tex` souboru.

#### `Col`

`Col` je `NamedTuple`:

```python
Col(source, header, decimals)
```

Vyznamenani poli:

- `source` je nazev sloupce v puvodnim DataFrame.
- `header` je hlavicka v LaTeX tabulce. Muze obsahovat i LaTeX matematiku,
  napr. `$R^2$`.
- `decimals` urcuje pocet desetinych mist. Pokud je `None`, hodnota se neformatuje
  jako desetinne cislo a zustava vhodna pro text, integer nebo uz predformatovany
  string.

Priklad vyberu a poradi sloupcu:

```python
cols = [
    Col("comp", "Slozka", None),
    Col("jumps", "Epochy [rok]", None),
    Col("threshold", "Prah [mm]", 2),
]
```

To znamena:

- do tabulky se vezmou jen sloupce `comp`, `jumps`, `threshold`,
- poradi ve vystupu bude presne podle seznamu `cols`,
- v LaTeXu se prejmenuji na `Slozka`, `Epochy [rok]`, `Prah [mm]`,
- `threshold` se zaokrouhli/formatuje na dve desetinna mista.

#### `make_latex_table`

`make_latex_table(df, cols, caption="", label="", escape=False, index=False, position="htbp")`

Co dela:

- prevede polozky `cols` na objekty `Col`,
- overi, ze vsechny `source` sloupce existuji v DataFrame,
- vytvori kopii DataFrame jen s vybranymi sloupci,
- numericke sloupce s nastavenym `decimals` preformatuje na string s danym poctem mist,
- prejmenuje sloupce podle `header`,
- zavola `DataFrame.to_latex()`,
- vrati kompletni LaTeX zdroj jako `str`.

Pokud sloupec chybi, vyhodi `KeyError` se seznamem chybejicich a dostupnych sloupcu.
To je uzitecne v notebooku, protoze chyba hned rekne, jestli se preklepl nazev sloupce.

`escape=False` je vychozi, aby fungovaly hlavicky jako `$R^2$`. Pokud by se vkladaly
bezne textove hlavicky a bylo potreba automaticke escapovani LaTeX specialnich znaku,
da se prepnout na `escape=True`.

Zarovnani sloupcu se odvozuje automaticky:

- textove/neformatovane sloupce jsou vlevo,
- numericke sloupce s `decimals` jsou vpravo,
- pokud `index=True`, index se prida jako levy sloupec.

#### `print_latex_table`

`print_latex_table(...)` je mala ladici zkratka:

```python
tex = print_latex_table(df, cols, caption="...")
```

Interni tok:

```text
df + cols
  -> make_latex_table()
  -> print(latex)
  -> return latex
```

Je vhodna, kdyz se tabulka zatim nema zapisovat na disk a jde jen o doladeni hlavicek,
poradi sloupcu, popisku nebo zaokrouhleni.

#### `save_latex_table`

`save_latex_table(df, path, cols, ..., tables_root=None, print_preview=False)`

Interni tok:

```text
df + cols
  -> make_latex_table()
  -> resolve output path
  -> create parent directories
  -> write .tex
  -> optional print(latex)
  -> return latex
```

Dulezite chovani:

- Vraci LaTeX zdroj jako `str`, ne cestu. To umoznuje:

```python
tex = save_latex_table(...)
print(tex)
```

- Pokud `path` nema priponu, automaticky se doplni `.tex`.
- Pokud `path` je relativni, uklada se pod `DEFAULT_TABLES_ROOT`, tedy
  `PROJECT_ROOT/LaTeX/tables`.
- Pokud `path` je absolutni, pouzije se presne zadana cesta.
- Pokud `print_preview=True`, funkce rovnou vytiskne stejny LaTeX zdroj, ktery zapisuje.
- `tables_root` dovoluje zmenit koren pro relativni cesty, ale bezne neni potreba.

#### `latex_table_path`

`latex_table_path(...)` je pomocnik pro skladani cest pod `LaTeX/tables`.

Explicitni varianta:

```python
latex_table_path("results", "stations", "licb", filename="trend")
```

vrati:

```text
LaTeX/tables/results/stations/licb/trend.tex
```

Varianta zrcadleni podle grafu:

```python
latex_table_path(image_path="LaTeX/images/results/stations/licb/plot.pdf")
```

vrati:

```text
LaTeX/tables/results/stations/licb/plot.tex
```

Smysl je drzet tabulky ve stejne logicke strukture jako PDF grafy, jen pod
`LaTeX/tables` misto `LaTeX/images`.

Typicke pouziti:

```python
from doris.output.tables import Col, save_latex_table

tex = save_latex_table(
    trend_df,
    "results/stations/licb/licb_trend",
    cols=[
        Col("axis", "Slozka", None),
        Col("slope", "Smernice [mm/rok]", 3),
        Col("r2", "$R^2$", 3),
    ],
    caption="Linearni trend stanice LICB",
    label="tab:licb_trend",
    print_preview=True,
)
```

Typicky notebookovy ladici postup:

```python
cols = [
    Col("comp", "Slozka", None),
    Col("jumps", "Epochy [rok]", None),
    Col("threshold", "Prah [mm]", 2),
]

# 1) jen zobrazit v notebooku
tex = make_latex_table(df_sw, cols, caption="Skoky")
print(tex)

# 2) ulozit a zaroven zobrazit presne ulozeny zdroj
tex = save_latex_table(
    df_sw,
    "results/stations/licb/jumps_sliding_window",
    cols=cols,
    caption="Skoky",
    label="tab:licb_jumps_sw",
    print_preview=True,
)
```

### `__init__.py`

`src/doris/output/tables/__init__.py` re-exportuje hlavni tabulkove API:

- `Col`
- `DEFAULT_TABLES_ROOT`
- `latex_table_path`
- `make_latex_table`
- `print_latex_table`
- `save_latex_table`

### Proc tu neni `output/csv`

Samostatny CSV exportni modul se zatim nezavadi. Pokud by pouze obaloval
`pandas.DataFrame.to_csv()`, rozsiroval by API bez skutecne projektove logiky navic.

Doporuceny notebookovy zapis je explicitni pandas workflow:

```python
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
df.to_csv(EXPORT_DIR / "name.csv", index=False)
```

Wrapper pro CSV by mel smysl teprve ve chvili, kdy by opakovane resil neco
projektove specifickeho, napr.:

- jednotne skladani cest do `data/.../exports/...`,
- jednotny `float_format`,
- zapis metadat vedle CSV,
- validaci povinnych sloupcu,
- export vice souvisejicich CSV najednou,
- konzistentni nazvy souboru podle `solution`, `product`, `station` nebo `satellite`.

Do te doby zustava CSV export primo v noteboocich pres pandas a knihovni `output`
obsahuje jen veci, ktere pridavaji vlastni projektovou hodnotu: graficke helpery
a LaTeX tabulky.

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

### `notebooks/stations/trend_detection_load_with_doris.ipynb`

Varianta trendove analyzy, ktera vyuziva knihovni loader `doris.analysis.stations.loading.load_station_dataframe`.
Slouzi jako prechod od starsi notebookove logiky k workflow, kde nacteni STCD dat,
prevod casu a regularizaci resi knihovna. Notebook se tim zkracuje na analyzu a grafiku.

Hlavni myslenka:

```text
STCD file
  -> load_station_dataframe()
  -> trend detection / detrending
  -> residual exports
  -> figures
```

Prakticky prinos:

- mene kopirovaneho kodu mezi notebooky,
- jednotny format sloupcu `MJD`, `Date`, `year`, `dE`, `dN`, `dU`,
- jednotny zpusob vyplneni mezer v casove rade,
- jednodussi navazani na spektralni analyzu a detekci skoku.

### `notebooks/stations/Jump_detection.ipynb`

Notebook pro puvodni/experimentacni detekci skoku ve stanicnich radach.

### `notebooks/stations/Jump_detection_with_doris.ipynb`

Varianta detekce skoku postavena nad knihovnim API `doris.analysis.stations.discontinuities`.

Aktualni ukazkovy notebook pro nove veci kolem detekce diskontinuit a exportu
LaTeX tabulek. Je napsany tak, aby bylo jasne oddelene:

1. nastaveni datasetu a parametru,
2. nacteni rezidualni rady,
3. detekce skoku metodou klouzaveho okna,
4. detekce skoku pomoci LOWESS derivace,
5. porovnani s breakpointy z `fit_piecewise_trend`,
6. export prehledovych LaTeX tabulek s okamzitym preview v notebooku.

#### Importy

Notebook si nejdriv prida `src/` do `sys.path` a importuje:

```python
from doris.analysis.stations.trend import fit_piecewise_trend
from doris.analysis.stations.discontinuities import (
    detect_jumps_sliding_window,
    detect_jumps_lowess,
)
from doris.output.tables import Col, save_latex_table
```

Tzn. samotna detekce i export tabulek uz nejdou pres lokalni notebookove helpery,
ale pres knihovni API.

#### Nastaveni datasetu

Dulezite promenne:

- `PRODUCT = "stcd"` - typ produktu,
- `SOLUTION = "gop25wd04"` - zpracovani/reseni,
- `STATION = "LICB"` - analyzovana stanice,
- `TREND_VARIANT = "weighted_multiseg"` - varianta trendu pouzita pro predchozi detrending,
- `COMPONENTS = ["dE", "dN", "dU"]` - analyzovane ENU slozky,
- `INPUT_TYPE = "detr"` nebo `"aper"` - vyber vstupni rezidualni rady.

Vstupni typ:

- `"aper"` znamena aperiodicke residualy, tedy trend i periodicity uz jsou odectene,
- `"detr"` znamena detrendovane residualy, tedy odecteny je trend, ale periodicity zustavaji.

Notebook podle toho vybere prefix sloupcu:

```python
col = "aper" if INPUT_TYPE == "aper" else "res"
```

a pak pracuje se sloupci:

```text
aper_dE / aper_dN / aper_dU
nebo
res_dE / res_dN / res_dU
```

#### Cesty

Notebook pouziva tyto koreny:

```python
PROJECT_ROOT = Path("../..").resolve()
DATA_DIR     = PROJECT_ROOT / "data" / PRODUCT / SOLUTION
EXPORT_DIR   = DATA_DIR / "exports" / STATION.lower()
IMAGES_DIR   = PROJECT_ROOT / "LaTeX" / "images" / "results" / "stations" / STATION.lower()
```

Tabulky jsou zamerne zrcadlene pod `LaTeX/tables`:

```python
TABLES_REL_DIR = Path("results") / "stations" / STATION.lower()
TABLES_DIR = PROJECT_ROOT / "LaTeX" / "tables" / TABLES_REL_DIR
PRINT_TABLE_PREVIEW = True
```

Takze pro LICB se uklada do:

```text
LaTeX/tables/results/stations/licb/
```

To odpovida obrazkum v:

```text
LaTeX/images/results/stations/licb/
```

#### Vstupni CSV

Notebook ocekava export z predchozi trendove/spektralni casti:

```python
APER_CSV = EXPORT_DIR / f"{BASE_NAME}_aper_{TREND_VARIANT}.csv"
```

Pro aktualni nastaveni jde typicky o:

```text
data/stcd/gop25wd04/exports/licb/gop25wd04_stcd_licb_aper_weighted_multiseg.csv
```

Pokud soubor neexistuje, notebook vypise dostupne kandidaty `*_aper_*.csv`, aby bylo
rychle videt, jaky export je ve slozce k dispozici.

#### Metoda 1: sliding window

Pro kazdou slozku `dE`, `dN`, `dU`:

```python
y = df_aper[f"{col}_{comp}"].fillna(0).to_numpy()
sw_results[comp] = detect_jumps_sliding_window(...)
```

Pouzite parametry v konfiguracni bunce:

- `window_size`,
- `shift`,
- `sw_mode`,
- `sigma_mult`,
- `sw_alpha`.

Graf pro kazdou slozku zobrazuje:

- rezidualni radu,
- prumery prvniho okna `mu1`,
- prumery druheho okna `mu2`,
- svisle cary nalezenych skoku.

Data pro graf berou z `JumpDetectionResult.extras`, hlavne `years1`, `years2`,
`mu1`, `mu2`, `window_size` a `shift`.

#### Metoda 2: LOWESS + derivace

Pro kazdou slozku:

```python
y = df_aper[f"{col}_{comp}"].fillna(0).to_numpy()
lw_results[comp] = detect_jumps_lowess(...)
```

Pouzite parametry:

- `frac_lowess`,
- `lw_mode`,
- `k_sigma_slope`,
- `min_slope_abs`,
- `lw_alpha`.

Graf pro kazdou slozku zobrazuje:

- rezidualni radu,
- LOWESS vyhlazenou krivku,
- svisle cary nalezenych skoku,
- rezim prahu v titulku grafu.

Mezivysledky pro graf jsou v `extras`: `smoothed`, `t_mid`, `slope`, `sigma_slope`,
`frac` a `min_abs`.

#### Metoda 3: BIC piecewise trend

Treti cast neni samostatny jump detector, ale porovnavaci trendovy postup:

```python
result = fit_piecewise_trend(years, y, max_segments=None)
```

Pro kazdou slozku uklada:

- `result.breakpoints`,
- `result.n_segments`,
- `result.bic`,
- `result.fitted`.

Graf zobrazuje puvodni rezidualni radu, po castech linearni fit a svisle cary
breakpointu. V mapovani vysledku je ulozen jako `bic_results[comp]`.

#### Export tabulek v notebooku

Zaver notebooku vytvari tri souhrnne DataFrame:

- `df_sw` pro sliding-window detekci,
- `df_lw` pro LOWESS detekci,
- `df_bic` pro BIC breakpointy.

Kazdy DataFrame ma jasne minimalni sloupce:

```text
df_sw:  comp, jumps, n, threshold, mode
df_lw:  comp, jumps, n, threshold, mode
df_bic: comp, breakpoints, n_segments, bic
```

Pole skoku se pred exportem formatuje pomoci `_fmt_epochs(arr)` na string
s decimalnimi roky, napr.:

```text
2020.123, 2021.456
```

Pokud nejsou nalezeny zadne skoky, zapisuje se `"--"`.

Tabulky se definuji v seznamu `table_specs`. Kazda polozka obsahuje:

```text
(df_table, rel_path, cols, caption, label)
```

kde:

- `df_table` je zdrojovy DataFrame,
- `rel_path` je relativni cesta pod `LaTeX/tables`,
- `cols` je seznam `Col(...)`,
- `caption` je popisek tabulky,
- `label` je LaTeX label.

Priklad jedne definice:

```python
(
    df_sw,
    TABLES_REL_DIR / f"{IMAGE_NAME}_jumps_sliding_window",
    [
        Col("comp", "Slozka", None),
        Col("jumps", "Epochy [rok]", None),
        Col("n", "Pocet", None),
        Col("threshold", "Prah [mm]", 2),
        Col("mode", "Rezim", None),
    ],
    "... caption ...",
    f"tab:{IMAGE_NAME}_jumps_sw",
)
```

Samotny export:

```python
latex_tables = {}
for df_table, rel_path, cols, caption, label in table_specs:
    print(f"\n--- {rel_path.name}.tex ---")
    latex_tables[rel_path.name] = save_latex_table(
        df_table,
        rel_path,
        cols=cols,
        caption=caption,
        label=label,
        print_preview=PRINT_TABLE_PREVIEW,
    )
```

Diky `print_preview=True` se v outputu notebooku rovnou ukaze LaTeX zdroj, tedy
neni potreba otevirat `.tex` soubor jen kvuli kontrole formatu.

Vystupni soubory:

```text
LaTeX/tables/results/stations/licb/gop25wd04_stcd_licb_jumps_sliding_window.tex
LaTeX/tables/results/stations/licb/gop25wd04_stcd_licb_jumps_lowess.tex
LaTeX/tables/results/stations/licb/gop25wd04_stcd_licb_jumps_bic.tex
```

`latex_tables` drzi i texty tabulek jako Python stringy, takze je lze dale vypsat,
porovnat, vlozit do dalsi bunky nebo rychle zkontrolovat:

```python
print(latex_tables["gop25wd04_stcd_licb_jumps_bic"])
```

### `notebooks/satellites/download_cddis.ipynb`

Stahovani satelitnich/orbitnich dat z CDDIS.

### `notebooks/satellites/download_local.ipynb`

Kopirovani orbitnich dat z lokalni slozky pres `doris.input.local`.

### `notebooks/satellites/download_ssh.ipynb`

Stahovani orbitnich dat pres SSH/SFTP pres `doris.input.ssh`.

### `notebooks/satellites/compare_orbit_solutions_hermite.ipynb`

Porovnani orbitnich reseni pomoci knihovni Hermitovy interpolace a RTN rozdilu.

### `notebooks/satellites/compare_orbit_solutions_bernese.ipynb`

Porovnani orbitnich reseni ve stylu Bernese/dynamicke parametrizace.

### `notebooks/satellites/hermite_bernese_comparison.ipynb`

Primy porovnavaci notebook mezi Hermitovou interpolaci a Bernese/dynamickym postupem.

### `notebooks/tests/hermite_interpolation_accuracy.ipynb`

Validacni notebook pro presnost Hermitovy interpolace orbit.

### `notebooks/tests/dynamic_parametrisation_accuracy.ipynb`

Validacni notebook pro presnost dynamicke parametrizace/Bernese porovnani orbit.

### `notebooks/tests/periodograms_test.ipynb`

Validacni notebook pro spektralni analyzu na synteticke stanicni casove rade.

Notebook je rozdeleny do tri hlavnich bloku:

1. generovani fiktivni DORIS-like casove rady se znamymi periodicitami,
2. FFT analyza pravidelne vzorkovane rady,
3. Lomb-Scargle analyza stejne sedmidenni testovaci rady.

V metodickych blocich se vzdy:

- spocita kompletni periodogram a vypise se jako tabulka,
- odhadne 95% false-alarm prah pomoci permutacniho nuloveho modelu,
- vykresli periodogram s prahovou linii a vyznamnymi peaky,
- vypisou se generovane a nalezene periodicity,
- nalezene sinusove slozky se fituji v casove oblasti a odectou,
- porovna se rozptyl pred a po odecteni a vykresli se rezidualni rada.

Generovani dat je rozdelene na samostatne kroky: vytvoreni sedmidenni casove osy,
slozeni tri znamych periodickych slozek, vykresleni ciste periodicity, vytvoreni mirne
realistickeho sumu, vykresleni samotneho sumu a nakonec slozeni finalnich testovacich
dat jako periodicita plus sum.

Grafy v notebooku maji ceske popisy a ukladaji se jako PDF do `LaTeX/images/test/`.

## LaTeX vystupy

### `LaTeX/images/`

Slozka s obrazovymi vystupy pro text prace. Aktualni strom obsahuje hlavne:

- `logo_CVUT/` - loga CVUT ve formatu PDF/EPS,
- `zadani/` - PDF zadani,
- `Stations/LICB/` - starsi/vychozi grafy pro stanici LICB,
- `results/stations/licb/` - vysledkove grafy trendu, residualu, LOWESS/sliding-window a periodogramu stanice LICB,
- `results/satellites/hermite/` - vysledky orbitnich porovnani Hermitovou interpolaci,
- `results/satellites/bernese/` - vysledky Bernese/dynamickeho porovnani,
- `results/satellites/comparison/` - primy Hermite vs. Bernese comparison,
- `test/periodicities/` - grafy ze synteticke spektralni validace,
- `test/hermite_precision/ssa/srl/` - grafy presnosti Hermitovy interpolace,
- `test/dynamic_precision/` - grafy presnosti dynamicke parametrizace.

### `LaTeX/tables/`

Slozka pro samostatne `.tex` tabulky urcene k vlozeni do textu prace pres `\input{...}`.
Je analogicka ke slozce `LaTeX/images`, jen misto PDF obrazku obsahuje LaTeX zdroje
tabulek.

Aktualni konvence:

```text
LaTeX/
  images/
    results/
      stations/
        licb/
          *.pdf
  tables/
    results/
      stations/
        licb/
          *.tex
```

Tuhle konvenci podporuje `doris.output.tables.save_latex_table()`:

```python
save_latex_table(
    df,
    "results/stations/licb/table_name",
    cols=[...],
)
```

ulozi:

```text
LaTeX/tables/results/stations/licb/table_name.tex
```

V notebooku `Jump_detection_with_doris.ipynb` se sem ukladaji tri tabulky:

- `gop25wd04_stcd_licb_jumps_sliding_window.tex`,
- `gop25wd04_stcd_licb_jumps_lowess.tex`,
- `gop25wd04_stcd_licb_jumps_bic.tex`.

Prakticky rozdil proti grafum:

- grafy jsou binarni/finalni PDF vystupy,
- tabulky jsou textove `.tex` vystupy,
- tabulky je mozne okamzite kontrolovat v notebooku pres `print_preview=True`,
- stejny LaTeX string, ktery se tiskne, se uklada na disk.

Typicky workflow exportu tabulky:

```text
pandas DataFrame
  -> vybrat sloupce pres Col(...)
  -> make_latex_table()
  -> print preview v notebooku
  -> save_latex_table()
  -> \input{LaTeX/tables/.../table.tex} v textu prace
```

Pri psani prace je vhodne v LaTeXu odkazovat relativne podle struktury hlavniho
`.tex` dokumentu, napr.:

```latex
\input{tables/results/stations/licb/gop25wd04_stcd_licb_jumps_bic.tex}
```

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
  -> compute_periodogram(method="fft" nebo method="lomb_scargle")
  -> period/amplitude/power/phase table
  -> estimate_periodogram_threshold()
  -> find_significant_peaks()
  -> significant periods for plots/tables
```

Testovaci notebook `notebooks/tests/periodograms_test.ipynb` ukazuje FFT i Lomb-Scargle pres verejny
wrapper `compute_periodogram()` a jednoduchy odhad false-alarm prahu pomoci permutacniho nuloveho modelu.

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
