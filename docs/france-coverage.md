# French administrative coverage

The three French renderer assets cover metropolitan France and its five DROM
in the geography of 1 January 2026. They join IGN's official ADMIN EXPRESS COG
CARTO PE 4.0 geometry to the independent INSEE Code officiel géographique 2026.

| Level | IGN source records | Admitted COG identities | Rendered shapes | Outside the renderer | Partly clipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| Regions | 18 | 18 | 18 | 0 | 0 |
| Departments | 101 | 101 | 101 | 0 | 0 |
| Municipalities | 34,877 | 34,875 | 34,875 | 0 | 0 |

The municipality layer contains two additional IGN geometries, `97501` and
`97502`, for Saint-Pierre-et-Miquelon. INSEE places them in the separate COMER
registry; IGN records no department or region for them. The build excludes them
explicitly from this metropolitan/DROM scope. It does not declare them missing
or silently attach them to a DROM. This release does not cover every French
overseas collectivity or territory.

The main INSEE municipality file has 37,496 rows. Only its 34,875 `TYPECOM=COM`
records identify the admitted municipalities. Its 2,105 delegated communes,
471 associated communes and 45 municipal arrondissements are separate types
and are not counted as additional municipalities.

## Identity and display

All admitted geometry identifiers match the independent registry exactly.
Municipality department/region assignments and department region assignments
match both sources. Names come from INSEE; the IGN name is retained separately.
Codes stay as text, including leading zeroes and Corsican `2A`/`2B` identifiers.
The renderer does not invent NUTS aliases for these administrative units.

The SVG assets share a `1000 × 1080` view box. The main panel uses Lambert-93.
Guadeloupe, Martinique, French Guiana, Réunion and Mayotte use separate projected
panels with independent scales, in that order along the bottom. Each shape
records its panel and native parent codes. No admitted polygon is clipped.
Panel positions and projections are explicit validated configuration in
[`france.build.json`](../france.build.json), not a geographic distance model.

Every admitted source, projected and exported polygon passes OGC validity
checks. The generator does not repair geometries. It exports the complete
selected source polygons as GeoParquet 1.1.0 in OGC:CRS84, alongside the SVGs.
These are IGN's already generalised CARTO PE polygons; they are not cadastral
boundaries or an unsimplified survey product. The generator applies no further
polygon simplification. SVG coordinate rounding remains a display operation.

## Sources and rights

- [IGN's official dataset record](https://www.data.gouv.fr/datasets/admin-express-admin-express-cog-admin-express-cog-carto-admin-express-cog-carto-pe-admin-express-cog-carto-plus-pe)
  declares Licence Ouverte / Open Licence 2.0. The selected edition is
  1 January 2026, delivery `2026-06-00527`.
- [INSEE's COG 2026 release](https://www.insee.fr/fr/information/8740222)
  supplies the dated independent inventories. Its
  [official dataset record](https://www.data.gouv.fr/datasets/code-officiel-geographique-1)
  declares Licence Ouverte / Open Licence.
- [Licence Ouverte 2.0](https://www.data.gouv.fr/pages/legal/licences/etalab-2.0)
  permits commercial reuse and adaptation with source attribution and the
  source update information, without implying official endorsement. Gramscii's
  SVG adaptation uses CC BY 4.0; it does not replace upstream rights.

Both downloads, the extracted GeoPackage, archive member, CSV members, fields,
filters, counts, licence and render panels are pinned in `france.build.json`.
The archive SHA-256 is
`30f8dced1409a4ef19ed78c5efa6612696524893916b332d0582c8a41fae1368`;
the GeoPackage SHA-256 is
`132803b59ae5ce8d91d5c93c322c3a30cabe86e22027e701fe9428898f1a407f`;
the INSEE archive SHA-256 is
`5c037e2977c9d476cfe2e7b7f923bbe09a87cbe448c59e492a71ef6a917aa53f`.

Save the two declared archives in `build/france/` and extract the declared
`archive_geometry_member` to the configured `geometry.file`. Then run:

```sh
uv sync --locked --group build
.venv/bin/python -m scripts.administrative --spec france.build.json \
  --inputs build/france --output build/france/generated --usage commercial
.venv/bin/python -m unittest discover -s tests -v
```

The output directory must be empty. Changed bytes, duplicate or missing codes,
unqualified additions, changed parent assignments, invalid polygons, incorrect
projections, incomplete frame assignments or non-commercial rights fail
explicitly. `france/coverage.json` retains the measured coverage and both SVG
and GeoParquet digests. Downloaded inputs and generated GeoParquet stay in the
ignored build directory. No Hugging Face upload is performed by this build.
