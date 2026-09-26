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
- config_name: gisco-nuts-non-commercial
  data_files:
  - split: train
    path: data/gisco-nuts-non-commercial.jsonl.gz
---

# European Territory Boundaries

Versioned, ready-to-draw administrative and statistical boundaries used by
Semantic Deterministic Graph. The release contains 12 boundary sets and 33,852
shapes. Every shape has provider-facing identifiers and an SVG path in the
declared view box.

The raw `*.geo.json` files are the canonical renderer assets. The three compressed
JSONL files expose the same shapes as rows for the Hugging Face dataset viewer.
`boundary-sets.json` records each set's territorial level, classification,
vintage, identifier families, source terms, commercial-use status, shape count
and SHA-256 digest.

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
- `natural-earth` contains country and separately coded territory map units.
  Natural Earth's source data is in the public domain; Gramscii's adaptation is
  CC BY 4.0.
- `gisco-nuts-non-commercial` contains NUTS 2024 levels 1–3. Eurostat GISCO's
  source terms limit these files to non-commercial use and require the stated
  attribution. Commercial use requires a licence from EuroGeographics.

The repository uses `license: other` because one licence label cannot represent
the mixed source terms. Gramscii's projection, simplification, SVG conversion
and identifier enrichment are CC BY 4.0; that licence does not replace a source
dataset's terms. See `LICENSE`, `NATURAL-EARTH.md`, `GISCO-NUTS.md` and
`boundary-sets.json` before reuse.

## Join contract

An alias identifies one shape only inside its declared boundary set. Select a
boundary set by exact territorial level, classification and vintage before
joining provider codes. A boundary set does not prove that a provider has an
observation for a given territory, period or filter combination.

The companion
[`Gramscii-IT/european-open-data-catalogue`](https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue)
qualifies provider codelists separately. SDG binds a provider dataset to a map
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
- shape name, aliases and SVG path;
- reference and boundary dates where the source provides them.

The geometry is simplified for screen rendering. It is not suitable for legal
boundaries, cadastral work, distance measurement or area measurement.

## Integrity and source

`SHA256SUMS` identifies every canonical geometry asset. Natural Earth inputs are
reproducible from the exact Map Units 5.1.1 archive pinned in
`natural-earth.build.json`. The source repository, build contracts and tests are
at [`Gramscii-Git/boundaries`](https://github.com/Gramscii-Git/boundaries).
