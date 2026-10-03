# Municipality identifier coverage

Verified on 9 September 2026 against complete native DVNS OpenCivitas queries for
all 15 ordinary-statute regions and the official Cruscotto municipality inventory.
Every observed source code was checked against every alias in its assigned file.

| Source | Distinct source municipalities | Qualified file | Unmatched | Ambiguous |
| --- | ---: | --- | ---: | ---: |
| `opencivitas_fabbisogni_2018` | 6,606 | `italy-municipalities-2018.geo.json` | 0 | 0 |
| `opencivitas_fabbisogni_2019` | 6,567 | `italy-municipalities-2019.geo.json` | 0 | 0 |
| `opencivitas_fabbisogni_2021` | 6,565 | `italy-municipalities-2021.geo.json` | 0 | 0 |
| `opencivitas_fabbisogni` | 6,557 | `italy-municipalities.geo.json` | 0 | 0 |
| Cruscotto official municipality inventory | 7,896 | `italy-municipalities.geo.json` | 0 | 0 |

The Cruscotto check uses its complete
[official inventory](https://cruscotto-italia.dati.gov.it/data/lookup/comuni-index.json),
as recorded by the publisher's `inventories.json`. It proves geometry coverage
of that inventory; it does not assert that all domains have observations for
every municipality. OpenCivitas checks use returned observations from exhausted
source requests, retaining the distinct identifiers in each annual dataset.

The latest OpenCivitas dataset reports 2022 values but includes newer identifiers
such as `012144`, `013256`, `024128`, `025075` and `028108`. Assigning that dataset
to the January 2022 geometry would leave valid source codes unmatched. Its complete
current-source code set joins uniquely to the 2026 file. Historical datasets retain
their own municipality sets and use separate files; a merged successor is never
inserted as an alias for an extinct municipality.

The three historical files contain all municipalities in their corresponding
ISTAT SITUAS year-end inventories, including municipalities outside the
OpenCivitas source scope: 7,954 for 2018, 7,914 for 2019 and 7,904 for 2021.
The build specification pins input files, projections and every additional
geometry assignment. Names come from SITUAS; each polygon records its actual
boundary-release date. Code coverage does not certify unchanged physical borders
between the inventory date and the geometry release.

The distributor's checksum file and tests verify all published bytes. Native
shapefile tests cover removed municipalities, explicitly assigned new codes,
duplicate identities, altered input hashes, unknown projections and incomplete
joins. Rebuilding from the pinned official inputs reproduces the historical
files byte for byte. Consumer source bindings remain in the consuming engine's
validated geography catalogue; the boundary repository does not infer dataset
availability or choose a geometry from an observation year.
