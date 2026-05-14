import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'C:/Users/michal/Desktop/MasterThesis-DorisAnalysis'

def read_nb(rel):
    with open(os.path.join(BASE, rel), 'r', encoding='utf-8') as f:
        return json.load(f)

def write_nb(nb, rel):
    with open(os.path.join(BASE, rel), 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f'  OK: {os.path.basename(rel)}')

def get_src(c):
    return ''.join(c.get('source', []))

def set_src(c, src):
    c['source'] = [src]

def apply_line_map(src, line_map):
    lines = src.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped in line_map:
            indent = line[: len(line) - len(line.lstrip())]
            result.append(indent + line_map[stripped])
        else:
            result.append(line)
    return '\n'.join(result)

# ============================================================
# dynamic_parametrisation_accuracy.ipynb
# ============================================================

# Step 1: replace # ====\n# N) LABEL\n# ==== blocks
NUMBERED_MAP = {
    '# 1) IMPORTS':                                          '# --- Imports ---',
    '# 2) PARAMETERS':                                       '# --- Parameters ---',
    '# 3) SSH DOWNLOAD':                                     '# --- SSH download ---',
    '# 4) CONSOLIDATE LOCAL OUT FILES INTO DOWNLOAD_DIR':    '# --- Consolidate local OUT files ---',
    '# 5) FIND LOCAL OUT FILES':                             '# --- Find local OUT files ---',
    '# 6) CHECK DAY COVERAGE':                               '# --- Check day coverage ---',
    '# 7) PARSE ORBGEN FIT RMS FROM ZA/ZG OUT FILES':        '# --- Parse ORBGEN fit RMS ---',
    '# 8) DAILY AND GLOBAL SUMMARY':                         '# --- Daily and global summary ---',
    '# 9) PARSE EPOCH RESIDUALS':                            '# --- Parse epoch residuals ---',
    '# 10) RESIDUAL SUMMARY FROM EPOCHS':                    '# --- Residual summary from epochs ---',
    '# 11) PLOT — DAILY RMS FROM EPOCH RESIDUALS':     '# --- Plot: daily RMS from epoch residuals ---',
    '# 12) SETUP FOR SINGLE-DAY PLOTS (cells 13-17)':        '# --- Setup for single-day plots ---',
    '# 13) EXPORT — PARAMETRISATION ACCURACY SUMMARY TABLE': '# --- Export: parametrisation accuracy summary table ---',
    '# 14) RTN RESIDUALS FOR ONE DAY':                       '# --- RTN residuals for one day ---',
    '# 15) RTN RESIDUAL HISTOGRAMS FOR ONE DAY':             '# --- RTN residual histograms for one day ---',
    '# 16) RTN RESIDUAL PERIODOGRAMS FOR ONE DAY':           '# --- RTN residual periodograms for one day ---',
    '# 17) RTN RESIDUAL FFT PERIODOGRAMS FOR ONE DAY':       '# --- RTN residual FFT periodograms for one day ---',
    '# 18) PERIODOGRAM — SIGNIFICANT PEAKS':            '# --- Periodogram: significant peaks ---',
}

# Step 2: Czech inline comments
DYN_CZ_MAP = {
    '# Odstranění střední hodnoty':                          '# Remove mean value',
    '# Kontrola pravidelnosti vzorkování':                              '# Check sampling regularity',
    '# FFT amplitudové spektrum':                                            '# FFT amplitude spectrum',
    '# Vynechání nulové frekvence':                               '# Skip zero frequency',
    '# Omezení na stejný rozsah period jako u Lomb--Scargle':           '# Limit to same period range as Lomb-Scargle',
}

nb = read_nb('notebooks/tests/dynamic_parametrisation_accuracy.ipynb')
for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    src = get_src(cell)
    # Replace === / numbered / === blocks
    def repl(m):
        label = m.group(1).strip()
        return NUMBERED_MAP.get(label, label)
    src = re.sub(r'# =+\n(# \d+\) .+)\n# =+', repl, src)
    # Czech inline
    src = apply_line_map(src, DYN_CZ_MAP)
    set_src(cell, src)
write_nb(nb, 'notebooks/tests/dynamic_parametrisation_accuracy.ipynb')

# ============================================================
# hermite_interpolation_accuracy.ipynb
# ============================================================

HERM_MAP = {
    '# keep_every = 2 means vstupní interval 120 s':                                    '# keep_every = 2 means input interval 120 s',
    '# body, které si nechám':                                                     '# points to keep',
    '# body uprostřed mezi nimi':                                                        '# points in between',
    '# krajní body radši zahodím, aby interpolace nespadla':                  '# discard edge points to avoid interpolation failure',
    '# tady se uloží detailí bodové výsledky':                      '# store detailed point-wise results',
    '# převod na hodiny':                                                                '# convert to hours',
    '# velikost celé figury = nepřímo i velikost subplotů':              '# figure size = indirectly also subplot size',
    '# skutečný rozsah osy s malou rezervou':                                      '# actual axis range with small margin',
    '# čas':                                                                             '# time',
    '# ✔️ přepočet na amplitudu':                                        '# convert to amplitude',
    '# vykreslení':                                                                      '# plot',
    '# Převod na mm, protože compute_periodogram vrací amplitudu ve stejných jednotkách jako vstup.': '# Convert to mm — compute_periodogram returns amplitude in the same units as input.',
    '# den v měsíci':                                                               '# day of month',
    '# seřazení intervalů (aby legenda dávala smysl)':                  '# sort intervals so the legend makes sense',
    '# lepší osa x (nezahlcovat)':                                                  '# cleaner x axis (avoid clutter)',
    '# jemné zlepšení čitelnosti':                                       '# minor readability improvement',
    '# převod na mm':                                                                    '# convert to mm',
    '# nech jen to důležité':                                                 '# keep only relevant columns',
    '# přejmenuj sloupce (LaTeX-friendly)':                                              '# rename columns (LaTeX-friendly)',
    '# zaokrouhlení':                                                                    '# round values',
}

nb = read_nb('notebooks/tests/hermite_interpolation_accuracy.ipynb')
for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    src = apply_line_map(get_src(cell), HERM_MAP)
    set_src(cell, src)
write_nb(nb, 'notebooks/tests/hermite_interpolation_accuracy.ipynb')

# ============================================================
# periodograms_test.ipynb
# ============================================================

PERI_MAP = {
    '# --- Výstupní adresář pro tabulky ---':   '# --- Output directory for tables ---',
    '# --- Exportní tabulka s českými názvy ---': '# --- Export table ---',
    '# --- Šum: gaussovský + odlehlá měření ---': '# --- Noise: Gaussian + outliers ---',
}

nb = read_nb('notebooks/tests/periodograms_test.ipynb')
for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    src = apply_line_map(get_src(cell), PERI_MAP)
    set_src(cell, src)
write_nb(nb, 'notebooks/tests/periodograms_test.ipynb')

# ============================================================
# ITRF2GCRF.ipynb
# ============================================================

ITRF_MAP = {
    '# --- Dataset selection + sestavení cest (CSV v exports) ---':                        '# --- Dataset selection + path setup (CSV in exports) ---',
    '# název CSV, který jsme ukládali':                                          '# name of the CSV file saved earlier',
    '# načtení':                                                                       '# load',
    '# když chceš, rovnou převedeme epoch_UTC na datetime (pokud tam je)':       '# convert epoch_UTC to datetime if present',
    '# a taky epoch (TAI) pokud ji tam máš pořád jako text':               '# also convert epoch (TAI) if still stored as text',
    '# -------- nastavení --------':                                                        '# --- Settings ---',
    '# downsample (ať Pdf není zbytočně obrí)':                       '# downsample to keep PDF size manageable',
    '# -------- koule Země --------':                                                       '# --- Earth sphere ---',
    '# stejné měřítko os (equal scale)':                                   '# equal axis scale',
    '# krychlový box (když Matplotlib podporuje)':                                          '# cubic bounding box (when Matplotlib supports it)',
    '# krychlový box (když Matplolib podporuje)':                                           '# cubic bounding box (when Matplotlib supports it)',
    '# uložení do Pdf':                                                                '# save to PDF',
    '# (A) renderer pro zobrazení v notebooku:':                                            '# (A) renderer for notebook display:',
    '# - "notebook_connected" = nejčastěji funguje v klasickém Jupyter Notebooku': '# - "notebook_connected" = most reliable in classic Jupyter Notebook',
    '# - "jupyterlab" = pro JupyterLab (někdy)':                                           '# - "jupyterlab" = for JupyterLab (sometimes)',
    '# - "iframe" = funguje skoro vždy (zobrazí to jako vložené HTML)':     '# - "iframe" = works almost always (renders as embedded HTML)',
    '# -------- uložit + zobrazit spolehlivě --------':                               '# --- Save and display reliably ---',
    '# zobrazit přímo v notebooku jako iframe':                                        '# display directly in notebook as iframe',
    '# df v GCRS/GCRF (pozice + rychlost) – nový dataframe':                          '# df in GCRS/GCRF (position + velocity) — new dataframe',
    '# r_gcrs a v_gcrs jsou Nx3 (už máš z předchozí buňky)':    '# r_gcrs and v_gcrs are Nx3 (from the previous cell)',
    '# necháme původní epochy (MJD_TAI) – to je tvoje "pravda"':           '# keep original epochs (MJD_TAI) — ground truth',
    '# GCRF/GCRS souřadnice v metrech':                                                    '# GCRF/GCRS coordinates in metres',
    '# --- nový název: doplňme _GCRS před příponu ---':          '# --- new name: append _GCRS before the extension ---',
    '# když exporty neexistují, tak je vytvoř (bez breku)':                     '# create export directory if it does not exist',
    '# uložení DF':                                                                    '# save DataFrame',
}

nb = read_nb('src/doris/analysis/orbits/transform/ITRF2GCRF.ipynb')
for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    src = apply_line_map(get_src(cell), ITRF_MAP)
    set_src(cell, src)
write_nb(nb, 'src/doris/analysis/orbits/transform/ITRF2GCRF.ipynb')

print('Done.')
