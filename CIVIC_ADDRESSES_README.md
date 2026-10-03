---
license: cc-by-4.0
language:
- it
pretty_name: Italian civic addresses (ANNCSU)
tags:
- geospatial
- addresses
- italy
- high-value-dataset
configs:
- config_name: default
  data_files: data/*.parquet
---

# Italian civic addresses

Every civic number of Italy's national address archive, ANNCSU (Archivio
Nazionale dei Numeri Civici delle Strade Urbane), one Parquet file per region,
as Agenzia delle Entrate and ISTAT publish it in their regional bulk files.

Snapshot **2026-09-15**: **27,415,954** civic numbers, of which **20,731,065**
(75.6%) carry coordinates. [`manifest.json`](manifest.json) lists, per region,
the rows, the georeferenced rows, the source URL and the sha256 of both the
source archive and the Parquet file.

## Columns

The columns keep ANNCSU's own names and values; only numbers are parsed.

| Column | Meaning |
| --- | --- |
| `CODICE_COMUNE` | Cadastral (Belfiore) code of the municipality |
| `CODICE_ISTAT` | ISTAT municipality code, six digits as text |
| `PROGRESSIVO_NAZIONALE` | National identifier of the street |
| `CODICE_COMUNALE` | The municipality's own street code |
| `ODONIMO` | Street name |
| `LOCALITA'` | Locality |
| `DIZIONE_LINGUA1`, `DIZIONE_LINGUA2` | Street name in a second or third official language |
| `PROGRESSIVO_ACCESSO` | National identifier of the civic number, stable for its lifetime |
| `CODICE_COMUNALE_ACCESSO` | The municipality's own civic-number code |
| `CIVICO`, `ESPONENTE` | Civic number and its letter part, where present (for example 12 and A) |
| `SPECIFICITA` | A numbering scheme ISTAT validates, such as red and black numbers (`ROSSO`, `NERO`) |
| `METRICO` | The civic number in metres, where the municipality numbers by distance instead of in sequence |
| `PROGRESSIVO_SNC` | Set for an access without a standard civic number (SNC), placed after the civic or metric number given; with no preceding reference it lies at the start of the street |
| `LONGITUDE`, `LATITUDE` | Decimal degrees, ETRF2000 (ETRS89 realisation); `COORD_X_COMUNE` and `COORD_Y_COMUNE` in the source |
| `QUOTA` | Altitude in metres as published |
| `METODO` | Georeferencing method: 1 field survey under 5 m; 2 field survey 5 m or more; 3 from a territorial database under 5 m; 4 the same, 5 m or more; 5 assigned through the municipalities' portal |

## Coverage and caveats

- Georeferenced civic numbers range by region from 20.4% (Valle d'Aosta) to
  95.6% (Emilia-Romagna). A missing coordinate is published as null.
- `QUOTA` is mostly empty or `0`: only 2,405,171 civic numbers have a positive
  altitude, and `0` is often a placeholder rather than a measured height.
- `CODICE_ISTAT` is the code each municipality recorded: it includes
  pre-2026 Sardinian codes and `024129`, which the 2026 ISTAT boundaries do not
  list.
- ANNCSU has no census-section field; joining civic numbers to sections takes a
  point-in-polygon join.
- Coordinates are not kept historically by the source: a snapshot holds the
  current ones.

## Source and licence

Data: **Agenzia delle Entrate and ISTAT, ANNCSU**, released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) as an EU high-value
dataset (Regulation 2023/138, geospatial category). The regional bulk files are
downloaded from
`https://anncsu.open.agenziaentrate.gov.it/age-inspire/opendata/anncsu/getds.php`
and the national street file is used to check the total. The source refreshes
its bulk files monthly.

Assembled by Gramscii. The build script and its tests are in
[`Gramscii-Git/boundaries`](https://github.com/Gramscii-Git/boundaries)
(`scripts/civic_addresses.py`).
