---
license: other
license_name: mixed-source-terms
pretty_name: European Territory Boundaries
language:
- en
tags:
- geospatial
- boundaries
- europe
configs:
- config_name: istat
  data_files:
  - split: train
    path: data/istat.jsonl.gz
- config_name: natural-earth
  data_files:
  - split: train
    path: data/natural-earth.jsonl.gz
- config_name: ign-insee
  data_files:
  - split: train
    path: data/ign-insee.jsonl.gz
- config_name: gisco-nuts-non-commercial
  data_files:
  - split: train
    path: data/gisco-nuts-non-commercial.jsonl.gz
- config_name: istat-census-sections-2021
  data_files:
  - split: train
    path: census-sections-2021/*.parquet
---

# European Territory Boundaries

Versioned, ready-to-draw administrative and statistical boundaries used by
Gramscii's maps. The source checkout contains 16 boundary sets and 68,953
shapes. Every shape has provider-facing identifiers and an SVG path in the
declared view box.

The raw `*.geo.json` files are the canonical renderer assets. The four compressed
JSONL files expose the same shapes as rows for the Hugging Face dataset viewer.
`boundary-sets.json` records each set's territorial level, classification,
vintage, identifier families, source terms, commercial-use status, shape count
and SHA-256 digest.

Source changes and local packaging do not update the live Hugging Face dataset.
Published snapshot coverage belongs to that snapshot's own manifest; uploading
a release is a separate explicit action.

## Preview

The current territorial levels are drawn directly from the canonical geometry
assets, one colour per shape.

| | |
| --- | --- |
| **italy-macro-areas** ![Italian macro-areas](preview/italy-macro-areas.png) | **italy-regions** ![Italian regions](preview/italy-regions.png) |
| **italy-provinces** ![Italian provinces](preview/italy-provinces.png) | **italy-municipalities** ![Italian municipalities](preview/italy-municipalities.png) |
| **europe-nuts1** ![NUTS 1 regions of Europe](preview/europe-nuts1.png) | **europe-nuts2** ![NUTS 2 regions of Europe](preview/europe-nuts2.png) |
| **europe-nuts3** ![NUTS 3 regions of Europe](preview/europe-nuts3.png) | **europe** ![Countries and territories of Europe](preview/europe.png) |
| **world** ![Countries and territories of the world](preview/world.png) | |

## Configurations

- `istat` contains the current and historical Italian administrative units.
  ISTAT permits commercial use under CC BY 4.0 with attribution.
  Its separate `italy-nuts3-2024` set contains 107 statistical units using
  the 2024 geometry. The 110 administrative provinces of 2026 carry source
  administrative identifiers and do not claim NUTS 2024 aliases.
- `natural-earth` contains country and separately coded territory map units.
  Natural Earth's source data is in the public domain; Gramscii's adaptation is
  CC BY 4.0.
- `ign-insee` contains the 18 regions, 101 departments and 34,875 municipalities
  of metropolitan France and its five DROM on 1 January 2026. IGN geometry joins
  the independent INSEE COG registry, preserving text identifiers and native
  parents. The sources permit commercial reuse under Licence Ouverte 2.0 with
  attribution. Other French overseas collectivities are outside this scope.
  DROM panels use independent scales and no admitted geometry is clipped.
- `istat-census-sections-2021` contains ISTAT's 2021 census sections as
  GeoParquet, described below. ISTAT permits commercial use under CC BY 4.0
  with attribution.
- `gisco-nuts-non-commercial` contains EU NUTS 2024 levels 1–3 and Eurostat's
  statistical regions for non-EU countries, classified separately per row. Eurostat GISCO's
  source terms limit these files to non-commercial use and require the stated
  attribution. Commercial use requires a licence from EuroGeographics.

This release does not contain municipality boundaries across Europe.
Italian and French administrative units are dated explicitly; NUTS levels are statistical
regions and do not prove coverage of every country's regions and provinces.
The European renderer frame contains 111, 291 and 1,330 units at levels 1, 2
and 3, while the complete source has 115, 299 and 1,345. The EU source counts
are 92, 244 and 1,165. Each renderer file records its `outside` and
`partially_clipped` codes and measured coverage. The complete, unclipped
GeoParquet export is reproducible locally with `nuts.build.json`; it is not
part of this published viewer configuration.

The repository uses `license: other` because one licence label cannot represent
the mixed source terms. Gramscii's projection, simplification, SVG conversion
and identifier enrichment are CC BY 4.0; that licence does not replace a source
dataset's terms. See `LICENSE`, `NATURAL-EARTH.md`, `GISCO-NUTS.md` and
`boundary-sets.json` and `docs/france-coverage.md` before reuse.

## Join contract

An alias identifies one shape only inside its declared boundary set. Select a
boundary set by exact territorial level, classification and vintage before
joining provider codes. A boundary set does not prove that a provider has an
observation for a given territory, period or filter combination.

The companion
[`Gramscii-IT/european-open-data-catalogue`](https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue)
qualifies provider codelists separately. Gramscii binds a provider dataset to a map
only when that exact codelist and vintage pass coverage checks. Unknown,
ambiguous and outside-frame codes remain explicit; there is no provider-wide
geometry fallback.

Searchable municipal distributions in the companion catalogue have verified
field schemas and acquisition contracts; other entries can remain metadata only.
A municipal publisher or a GeoJSON format does not establish a territorial
dimension or an administrative boundary.
Qualify each resource's actual identifiers, classification, vintage and licence
before joining its observations to one of these sets.

## Row schema

Each viewer row contains:

- boundary-set identity, scope, level, classification and vintage;
- identifier families, licence identity and commercial-use status;
- source, view box, source archive digest where applicable and outside codes;
- source geometry digest and partially clipped codes where measured;
- identity-source digest and source geometry validity where measured;
- shape name, aliases and SVG path;
- reference and boundary dates where the source provides them.
- renderer panel and native administrative parent codes where measured.

The geometry is simplified for screen rendering. It is not suitable for legal
boundaries, cadastral work, distance measurement or area measurement.
The Italian NUTS 2024 source polygon `ITG2D` (Sassari) is not OGC-valid.
Its quality flag and attribution identify that source limitation; the renderer
does not repair it or present it as a valid GIS polygon.

## Census sections 2021

`census-sections-2021/` holds ISTAT's
[Basi territoriali 2021](https://www.istat.it/notizia/basi-territoriali-e-variabili-censuarie/):
756,376 census sections, one GeoParquet file per region (`R01.parquet` for
Piemonte to `R20.parquet` for Sardegna, ISTAT's region codes). Unlike the sets
above, these are full-resolution polygons for GIS use, not simplified SVG paths.

- Geometry is WKB in longitude and latitude (OGC:CRS84), reprojected from
  ISTAT's WGS84 UTM zone 32N and rounded to 7 decimals (about 1 cm). ISTAT's
  polygons are kept as published: 1,637 of them are not valid OGC geometries.
- Codes are text at their fixed widths: `PRO_COM` 6 digits, `SEZ21_ID` 13
  (`PRO_COM` followed by the 7-digit `SEZ21`), `LOC21_ID` 11, `COM_ASC1`–`3`
  9. Optional codes that ISTAT writes as 0 (`COD_ZIC`, `COD_ISAM`, `COD_ACQUE`,
  `COD_ISOLE`, `COD_MONT_D`, `COD_AREA_S`, `COM_ASC1`–`3`) are null.
- `POP21`, `FAM21`, `ABI21` and `EDI21` are the 2021 census counts of
  residents, households, dwellings and buildings: 59,030,133 residents in all,
  and 305,076 sections with none.
- `COD_TIPO_S` is the section type; `SHAPE_Leng` and `SHAPE_Area` are ISTAT's
  perimeter and area in metres, measured in UTM.
- 7,911 sections are fictitious, as ISTAT defines them: 8888885–8888888 hold
  people with no fixed abode (type 100), drawn near the town hall;
  9999998–9999999 hold residents of a disputed zone assigned to another
  municipality.

`census-sections-2021/manifest.json` records each region's source archive and
SHA-256 digest, file digest, section count, bounding box and census totals.
Field definitions are ISTAT's own, in the source's
[description](https://www.istat.it/wp-content/uploads/2024/07/Descrizione-dei-dati-Basi-territoriali.pdf).
Attribution: ISTAT, Basi territoriali 2021, CC BY 4.0.

## Integrity and source

`SHA256SUMS` identifies every canonical geometry asset. Natural Earth inputs are
reproducible from the exact Map Units 5.1.1 archive pinned in
`natural-earth.build.json`. Regional geometry inputs, inventories, render
settings and non-commercial source terms are pinned in `nuts.build.json`.
The separate Italian NUTS 2024 geography, licensed for commercial use, is
reproducible from `istat-nuts.build.json` and its two pinned ISTAT inputs.
French geometry and parent assignments are reproducible from `france.build.json`.
The complete selected French polygons export locally as GeoParquet; those
ignored build outputs are not part of the SVG viewer configuration.
The source repository, build contracts and tests are
at [`Gramscii-Git/boundaries`](https://github.com/Gramscii-Git/boundaries).
