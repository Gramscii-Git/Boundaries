# Eurostat GISCO terms of use

`europe-nuts1.geo.json`, `europe-nuts2.geo.json` and
`europe-nuts3.geo.json` are adapted from Eurostat GISCO, *NUTS 2024*,
region polygons at 1:3 million in EPSG:3035. The dataset is derived from
EuroGeographics EuroBoundaryMap, UN-FAO GAUL and TurkStat data.

Eurostat distributes the NUTS boundaries under specific provisions, in
addition to the general copyright policy of its website. In summary, as
published on the
[statistical units terms](https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units):

1. The Commission grants a non-exclusive and non-transferable right to
   use and process the Eurostat/GISCO geographical data.
2. Permission is granted on condition that the data is not used for
   commercial purposes, and that the source is acknowledged: a copyright
   notice must be visible on any printed or electronic publication using
   the data, in the legend of the map and in the introductory page of
   the publication:

   > © EuroGeographics for the administrative boundaries

   For publications in languages other than English, French or German,
   the notice is translated into the language of the publication.

3. Commercial use requires a licence agreement with
   [EuroGeographics](https://eurogeographics.org/).

Read the page linked above for the terms in force; that page, not this
summary, is what binds you.

The adaptation in this repository (frame, clipping, simplification, SVG
paths) is released by Gramscii under CC BY 4.0, see `LICENSE`. That
licence covers the adaptation only and does not lift Eurostat's
conditions on the data beneath it.

The same source terms cover the complete geometry exported by `scripts.nuts`.
Its explicit `--usage commercial` request fails for this source; generating
GeoParquet or preserving the polygons outside the renderer frame does not
grant additional reuse rights.
