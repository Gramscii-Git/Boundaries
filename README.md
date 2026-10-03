# Boundaries

Ready-to-draw administrative and statistical boundaries for Italy and
for Europe, as SVG paths in plain JSON. Every shape carries the
identifiers statistical providers use for that place. Tables keyed by
matching ISTAT, NUTS, licence-plate or ISO codes can be joined directly
after checking their territorial level and classification vintage.

Twelve files, 33,852 shapes, 9.6 MB in total. No runtime, no dependencies:
a file is a JSON document a browser can draw with one `<svg>` element.

| File | Shapes | Level | Identifiers on each shape | Source | Licence |
| --- | ---: | --- | --- | --- | --- |
| `italy-macro-areas.geo.json` | 5 | Italian macro-areas (ripartizioni, NUTS 1) | ripartizione number (`2`), the NUTS 1 code ISTAT publishes under (`ITD`) and the NUTS 2024 code (`ITH`) | ISTAT, 1 January 2026 | CC BY 4.0 |
| `italy-regions.geo.json` | 22 | Italian regions (NUTS 2), plus the autonomous provinces of Trento and Bolzano and Trentino-Alto Adige as a whole | ISTAT region code (`05`), NUTS 2 code in both vintages (`ITD3`, `ITH3`), name as written and in upper case (`Veneto`, `VENETO`) | ISTAT, 1 January 2026 | CC BY 4.0 |
| `italy-provinces.geo.json` | 110 | Italian provinces and metropolitan cities (NUTS 3) | ISTAT province code (`015`), NUTS 3 code (`ITC4C`), licence plate (`MI`) | ISTAT, 1 January 2026 | CC BY 4.0 |
| `italy-municipalities.geo.json` | 7,896 | Italian municipalities (LAU) | ISTAT municipality code (`015146`); 377 municipalities also carry the code they had under an earlier provincial layout | ISTAT, 1 January 2026 | CC BY 4.0 |
| `italy-municipalities-2018.geo.json` | 7,954 | Municipalities active at the end of 2018 | ISTAT municipality code | ISTAT SITUAS inventory; 2018 and 2019 boundary releases | CC BY 4.0 |
| `italy-municipalities-2019.geo.json` | 7,914 | Municipalities active at the end of 2019 | ISTAT municipality code | ISTAT SITUAS inventory; 2019 and 2020 boundary releases | CC BY 4.0 |
| `italy-municipalities-2021.geo.json` | 7,904 | Municipalities active at the end of 2021 | ISTAT municipality code | ISTAT SITUAS inventory; 31 December 2021 boundaries | CC BY 4.0 |
| `europe-nuts1.geo.json` | 111 | NUTS 1 regions of Europe | NUTS 2024 code (`DE2`) | Eurostat GISCO, NUTS 2024 | Non-commercial, © EuroGeographics |
| `europe-nuts2.geo.json` | 291 | NUTS 2 regions of Europe | NUTS 2024 code (`ES51`) | Eurostat GISCO, NUTS 2024 | Non-commercial, © EuroGeographics |
| `europe-nuts3.geo.json` | 1,330 | NUTS 3 regions of Europe | NUTS 2024 code (`FR101`) | Eurostat GISCO, NUTS 2024 | Non-commercial, © EuroGeographics |
| `europe.geo.json` | 68 | Countries and separately coded territories inside the European frame | ISO 3166-1 alpha-2 (`DE`), alpha-3 (`DEU`), and the Eurostat code where it differs (`EL`, `UK`) | Natural Earth Map Units 5.1.1, 1:50m | Public domain |
| `world.geo.json` | 247 | Countries and separately coded territories of the world | ISO 3166-1 alpha-2, alpha-3, and the Eurostat code where it differs | Natural Earth Map Units 5.1.1, 1:50m | Public domain |

The shapes carry no population, area, postal code or cadastral code.
They are simplified for drawing at screen resolution and are not
suitable for measuring areas, distances or legal boundaries.

## Preview

The current territorial levels drawn as they are, one colour per shape, from the `preview/`
directory.

| | |
| --- | --- |
| **italy-macro-areas** ![Italian macro-areas](preview/italy-macro-areas.png) | **italy-regions** ![Italian regions](preview/italy-regions.png) |
| **italy-provinces** ![Italian provinces](preview/italy-provinces.png) | **italy-municipalities** ![Italian municipalities](preview/italy-municipalities.png) |
| **europe-nuts1** ![NUTS 1 regions of Europe](preview/europe-nuts1.png) | **europe-nuts2** ![NUTS 2 regions of Europe](preview/europe-nuts2.png) |
| **europe-nuts3** ![NUTS 3 regions of Europe](preview/europe-nuts3.png) | **europe** ![Countries of Europe](preview/europe.png) |
| **world** ![Countries of the world](preview/world.png) | |

## Format

Each file is one JSON object:

```json
{
  "viewBox": "0 0 1000 1288.1",
  "source": "ISTAT, Confini delle unità amministrative a fini statistici, 1 gennaio 2026 (generalizzati), CC BY 4.0",
  "shapes": [
    { "name": "Veneto", "aliases": ["05", "Veneto", "VENETO", "ITD3", "ITH3"], "d": "M600.2,131.4L…Z" }
  ]
}
```

- `viewBox` is the SVG view box every path in the file is drawn into.
  The seven Italian files share one view box and one projection, and so
  do the three European NUTS files, so levels of one country drawn
  together line up.
- `source` names the upstream dataset and its licence, so a file copied
  on its own still says where it came from.
- `shapes[].name` is the official name of the place.
- `shapes[].aliases` are the identifiers the place is known by. Match a
  row of data against any of them within the selected boundary file.
  An alias is not a crosswalk between arbitrary territorial vintages.
- `shapes[].d` is the SVG path, already projected and simplified.
- Historical municipality files also carry `reference_date`, the date of the
  official active-municipality inventory, and `shapes[].boundary_date`, the
  boundary release used for that individual shape. These dates serve different
  purposes; a file does not claim a uniform boundary date when releases differ.
- The three European NUTS files also carry `outside`: the codes of the
  regions the file does not draw because they lie outside its frame
  (the Canaries, Madeira, the Azores, the French overseas regions,
  Svalbard).

To draw a file:

```html
<svg viewBox="0 0 1000 1288.1">
  <path d="…" fill="#dfe6ee" stroke="#fff" stroke-width="0.5" />
</svg>
```

## Numbers to draw on these shapes

The identifiers support joins with official statistics. The companion
repositories provide discovery metadata and its publishing code, not the
numeric observations:

| Where | What it holds | What it is for |
| --- | --- | --- |
| **This repository** | the shapes, each with its ISTAT, NUTS and ISO identifiers | drawing a table of numbers on a map |
| [**Gramscii-IT/european-open-data-catalogue**](https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue) on Hugging Face | discovery metadata from statistical, Italian public-finance and municipal providers; release counts and coverage belong to the snapshot manifest and quality report | finding datasets and inspecting their recorded structures, codes and documentation |
| [**Gramscii-IT/european-territory-boundaries**](https://huggingface.co/datasets/Gramscii-IT/european-territory-boundaries) on Hugging Face | the same versioned geometry assets and machine-readable boundary-set manifest | downloading map boundaries on their own |
| [**Gramscii-Git/open-data-catalogue**](https://github.com/Gramscii-Git/open-data-catalogue) on GitHub | catalogue release policy, validation and publication code | validating an export from Gramscii's harvester and publishing a verified immutable revision |

A dataset in the catalogue is cut by a territorial dimension whose codes
are aliases of the shapes here: ISTAT's `REF_AREA` code `ITE4` is Lazio
in `italy-regions.geo.json`, Eurostat's `geo` code `IT` is Italy in
`europe.geo.json`, OECD's and ILO's `REF_AREA` code `AFG` is Afghanistan
in `world.geo.json`, and the ISTAT municipality codes of the Italian
public-finance sources require the municipality file qualified for that dataset. A row of
that dataset can colour a matching shape. These examples do not establish
coverage of every dataset or territorial vintage.

### Selection and map joins

Searchable municipal catalogue entries describe individual distributions with
verified field schemas and acquisition paths. Other entries can remain as
metadata without admission to search. Search qualification does not establish a
territorial dimension or a compatible boundary set. A resource from Milano,
Napoli, Roma, Torino or Bologna may describe points, addresses, neighbourhoods
or non-geographic records. Its publisher's municipality does not identify the
territorial level of its observations, and a GeoJSON format does not certify an
administrative boundary. Qualify the actual identifiers, classification, vintage
and source licence before declaring a join or adding geometry here.

This repository contains geometry, not a list of available observations.
A shape does not prove that a provider has data for a particular date,
territory or filter. The shared joint-availability artifact belongs in
`european-open-data-catalogue`; its publisher documentation states which
stages are implemented. Do not infer that an index has been published from
the presence of these boundary files.

Before drawing observations:

- Verify the selected file's SHA-256 at a pinned repository revision.
- Check the territorial level and vintage against the source dataset.
  Historical aliases do not account for arbitrary mergers, splits or
  changes of area.
- Use one dataset, period, measure, unit and filter combination per map.
  Treat multiple rows or codes mapping to the same shape as an explicit
  ambiguity, not permission to overwrite a value or invent an aggregate.
- Keep missing or suppressed values distinct from numeric zero. Report
  unmatched codes and regions listed in `outside` separately from places
  with no observation.

Adding selection metadata or updating numeric observations does not
require regenerating geometry. A boundary update requires a qualified
source release and new checksums.

## How the files were made

### Italy

Source: ISTAT, *Confini delle unità amministrative a fini statistici al
1° gennaio 2026*, the generalised release `Limiti01012026_g.zip`
(SHA-256 `b011a590656c3a3ebc297fba80726a376aa843b6f164641cf6a4a990021a81d6`,
as served by ISTAT on 7 September 2026), read from the shapefiles
`RipGeo01012026_g`, `Reg01012026_g`, `ProvCM01012026_g` and
`Com01012026_g`. The coordinates in that release are UTM zone 32N
eastings and northings.

1. One transform is computed from Italy's own bounding box and applied to
   all four levels: the country is drawn 1,000 units wide, the height
   follows from its shape, nothing is stretched.
2. Each polygon is simplified with topology preserved, with a tolerance
   of 250 metres for macro-areas, regions and provinces and 500 metres
   for municipalities. At this width one unit is about one kilometre, so
   a boundary moves by less than a pixel.
3. Each polygon is written as an SVG path with one decimal of precision.
4. Identifiers are attached from ISTAT's own classification: ripartizione,
   region, province and municipality codes, NUTS codes, licence plates,
   and for municipalities the codes they carried under an earlier
   provincial layout, so data keyed by either vintage lands on the same
   shape. NUTS 2010 renamed Italy's `ITD` to `ITH` and `ITE` to `ITI`;
   ISTAT still publishes under the old letters and Eurostat under the
   new, so macro-areas and regions carry both.

### Historical municipalities

[`municipalities.build.json`](municipalities.build.json) pins every input URL,
SHA-256, shapefile member, projection and active-municipality inventory. The
inventories are the official [ISTAT SITUAS](https://situas.istat.it/) reports for
31 December 2018, 2019 and 2021. Names come from those inventories. Geometry
comes from ISTAT's [generalised boundary releases](https://www.istat.it/notizia/confini-delle-unita-amministrative-a-fini-statistici-al-1-gennaio-2018-2/).

The 2018 and 2019 base releases describe 1 January. Six municipalities formed
during 2018 are explicitly assigned their geometry from the 2019 release; nine
formed during 2019 use the 2020 release. Retired municipalities absent from the
year-end inventory are excluded. The 2021 boundary release describes 31 December
and needs no additional assignments. These are declared source assignments,
never automatic substitution of a missing municipality with its successor.
Every shape records its geometry's date. This proves identifier coverage, not
the absence of any boundary adjustment within a year.

For the verified OpenCivitas source captures, the 2018, 2019 and 2021 datasets
use their corresponding files. The dataset named `opencivitas_fabbisogni` reports
2022 values using newer merged municipality identifiers, so its qualified join
uses `italy-municipalities.geo.json`. An observation year alone is insufficient
to choose a file. [The coverage report](docs/municipality-coverage.md) records
the full source-code checks.

To reproduce the historical files, save each declared source under its configured
`sources.*.file` name in `build/istat/`, then run:

```sh
uv sync --locked --group build
.venv/bin/python scripts/municipalities.py --spec municipalities.build.json \
  --inputs build/istat --output build/generated
.venv/bin/python -m unittest discover -s tests -v
```

The generator verifies all input checksums and projections before publishing
outputs. An altered input, duplicate code, incomplete inventory join or undeclared
addition fails the build. Source downloads are an explicit operator action;
the generator never changes pinned inputs or chooses replacement releases.
Generated build intermediates and downloaded source archives stay outside version
control. Only reviewed distributable geometry belongs at the repository root.

### European NUTS regions

Source: Eurostat GISCO, *NUTS 2024*, region polygons at 1:3 million in
EPSG:3035, file `NUTS_RG_03M_2024_3035.geojson` (SHA-256
`b6c44e3ed6c1d8e33b98ba36fe8236f3c4b2bdc005049bb37320574be1601e33`).

1. One frame is fixed around the continent, from the Atlantic coast of
   Portugal to Cyprus and from Crete to the North Cape (EPSG:3035
   x 2,600–7,350 km, y 1,350–5,500 km), and applied to all three levels:
   the frame is drawn 1,000 units wide.
2. Each polygon is clipped to the frame. A region lying wholly outside
   it is not drawn and its code is listed under `outside`; Svalbard, off
   the top of Norway, is cut away.
3. Each polygon is simplified with topology preserved, with a tolerance
   of 1,500 metres for NUTS 1 and 2 and 1,000 metres for NUTS 3. At this
   width one unit is about 4.75 kilometres, so a boundary moves by less
   than a third of a pixel.
4. Each polygon is written as an SVG path with one decimal of precision,
   named by its Latin name and identified by its NUTS 2024 code.

### Europe and the world

Source: Natural Earth, *Admin 0 – Map Units*, version 5.1.1 at 1:50m
scale. Map Units preserves separately coded territories that statistical
providers can expose independently.

1. The map-unit polygons are projected to EPSG:3035 for
   `europe.geo.json`, using the same fixed frame as the NUTS files, and
   to Robinson for `world.geo.json`.
2. Each polygon is simplified for screen resolution and written as an
   SVG path in a 1,000-unit-wide view box.
3. ISO 3166-1 alpha-2 and alpha-3 codes are attached, plus the Eurostat
   country code where it differs from ISO (`EL` for Greece, `UK` for the
   United Kingdom), so Eurostat tables colour the map directly.

[`natural-earth.build.json`](natural-earth.build.json) pins the source URL,
version, SHA-256, source identity fields, explicit aliases, projections,
frames and simplification tolerances. The input archive is
`ne_50m_admin_0_map_units.zip`, SHA-256
`f449ec126985e5aab30aea4b439c2d9eb0c5d40bd722fc1036ad3b6477e25cdd`.
To reproduce the two files, save that archive locally and run:

```sh
uv sync --locked --group build
.venv/bin/python scripts/natural_earth.py --spec natural-earth.build.json \
  --archive ne_50m_admin_0_map_units.zip --output build/natural-earth
```

The generator verifies the archive before reading it and rejects missing,
invalid or ambiguous identities. It never downloads or substitutes a source.

## Integrity

The files distributed here are identified by these SHA-256 digests, also
listed in `SHA256SUMS`. They identify the adapted files in this
repository, not the upstream archives.

| File | SHA-256 |
| --- | --- |
| `italy-macro-areas.geo.json` | `7a7cd481b2860b8a7c232d192fdd55fa86ebb75b6a9552f568059bf49c7d4b9f` |
| `italy-regions.geo.json` | `7963e74dc142126cc2807bef0be26d4117031851a08622fae9dd04c267f8ef26` |
| `italy-provinces.geo.json` | `292b3a4bd42844846519e8271466d23e96cf207861cad858e1c238da416ca798` |
| `italy-municipalities.geo.json` | `c0759f670a54920772b2cafd1541717e34c17b2a44cb970d0a7f05a502673420` |
| `italy-municipalities-2018.geo.json` | `90ede3e5e6533edc5d58a8bf868f3654ee66607b6f8ff0b03a2030b19e73ff30` |
| `italy-municipalities-2019.geo.json` | `4a6ee6c0675da5a736426f217665fa9f85f2e8c8a7f1c0b37b2186f80d518bd6` |
| `italy-municipalities-2021.geo.json` | `030f54e34fcf7b583a9863b46bfd1601c072499be24db1e7f9becb2daf093366` |
| `europe-nuts1.geo.json` | `25ced35220f9d1dc5ef3573f6e9989b6de7859472d311fbac9b5e7bfa2a90539` |
| `europe-nuts2.geo.json` | `6cf445662590b8ca7c17ff3394c1d7f3ae3febb32fa28eea6cedec236fc45eac` |
| `europe-nuts3.geo.json` | `6f0c585c165fc4aa01651f51c3c20e1d86de1a042df240f81f9c6ff2226675da` |
| `europe.geo.json` | `70cd83aa4832c9d195108cc4e2990f128052e24acb4967cb7c6691b695401d09` |
| `world.geo.json` | `68b225b731701c87d9b6a1db334760ed89de092f1b8b87649bedb51ae8046132` |

```sh
shasum -a 256 -c SHA256SUMS
```

## Licences

Each file carries the terms of the dataset it was adapted from, and
those terms are not the same for every file. Read the row of the table
above for the file you use; the details are here.

**Gramscii's adaptation** (projection, simplification, SVG paths and the
identifiers attached to each shape) is released for every file under the
[Creative Commons Attribution 4.0 International](LICENSE) licence. That
licence covers what Gramscii added, never the source data beneath it:
where the source is more restrictive, the source's terms decide what you
may do with the file.

**ISTAT files** (`italy-macro-areas`, `italy-regions`, `italy-provinces`,
`italy-municipalities` and its historical files) are adapted from data ISTAT publishes under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). You may use
them for any purpose, including commercially, with this attribution:

> ISTAT, Confini delle unità amministrative a fini statistici,
> 1 gennaio 2026 (generalizzati), CC BY 4.0

ISTAT's open-data terms: <https://www.istat.it/dati/open-data/>.
For historical files, use the attribution in their own `source` field, which
identifies the SITUAS inventory date and the boundary releases used.

**Eurostat GISCO files** (`europe-nuts1`, `europe-nuts2`, `europe-nuts3`)
are adapted from data Eurostat distributes under its own
[terms](GISCO-NUTS.md): non-commercial use only, with this copyright
notice visible on any printed or electronic publication using the data:

> © EuroGeographics for the administrative boundaries

Commercial use of these three files needs a licence from
[EuroGeographics](https://eurogeographics.org/). Gramscii's CC BY 4.0 on
its adaptation does not lift that condition.

**Natural Earth files** (`europe`, `world`) are adapted from data its
authors place in the [public domain](NATURAL-EARTH.md). You may use them
for any purpose; no attribution is required by the source, and Natural
Earth welcomes it.

When you use a file, credit the file's source, as written in its
`source` field, and this repository:

> Boundaries by Gramscii, CC BY 4.0, https://github.com/Gramscii-Git/boundaries

## Origin

[`boundary-sets.json`](boundary-sets.json) is the machine-readable contract for
territorial level, classification, vintage, identifier families, source terms,
commercial-use status, shape count and artifact digest. A catalogue provider is
bound to one of these sets only after its exact territorial codelist and vintage
are qualified; a provider-wide wildcard is not evidence of compatibility.

These files are the map layer of Gramscii's deterministic answer engine,
and are published here on their own so that anyone drawing Italian or
European statistics can use them.
The copies inside that engine and the files here are byte-identical:
the digests above are the proof.
