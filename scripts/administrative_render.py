"""Project complete administrative polygons and serialize SVG paths and GeoParquet."""

import json
import math
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from pyproj import CRS, Transformer
from shapely.ops import transform

from .administrative_spec import Layer, Specification


def projected(products: dict[str, list[dict]], spec: Specification) -> dict:
    contexts = {}
    for frame in spec.render.frames:
        selected = [
            row
            for rows in products.values()
            for row in rows
            if row["frame"].id == frame.id
        ]
        converter = Transformer.from_crs(spec.source_crs, frame.crs, always_xy=True)
        for row in selected:
            polygon = transform(converter.transform, row["geometry"])
            if polygon.is_empty or not polygon.is_valid:
                raise ValueError(
                    f"administrative projected geometry is invalid: {row['code']}"
                )
            row["projected"] = polygon
        left, bottom, right, top = shapely.total_bounds(
            [row["projected"] for row in selected]
        )
        if (
            not all(math.isfinite(value) for value in (left, bottom, right, top))
            or left >= right
            or bottom >= top
        ):
            raise ValueError(
                f"administrative map frame requires positive finite bounds: {frame.id}"
            )
        x, y, width, height = frame.rectangle
        scale = min(
            (width - 2 * frame.padding) / (right - left),
            (height - 2 * frame.padding) / (top - bottom),
        )
        contexts[frame.id] = {
            "left": left,
            "top": top,
            "scale": scale,
            "x": x + (width - (right - left) * scale) / 2,
            "y": y + (height - (top - bottom) * scale) / 2,
        }
    return contexts


def svg_path(row: dict, context: dict, decimals: int) -> str:
    geometry = row["projected"]
    polygons = geometry.geoms if geometry.geom_type == "MultiPolygon" else [geometry]
    paths = []
    for polygon in polygons:
        for ring in [polygon.exterior, *polygon.interiors]:
            points = [
                f"{context['x'] + (x - context['left']) * context['scale']:.{decimals}f},"
                f"{context['y'] + (context['top'] - y) * context['scale']:.{decimals}f}"
                for x, y in ring.coords
            ]
            paths.append("M" + "L".join(points) + "Z")
    return "".join(paths)


def write_parquet(
    rows: list[dict], spec: Specification, layer: Layer, path: Path
) -> None:
    converter = Transformer.from_crs(spec.source_crs, spec.export_crs, always_xy=True)
    exported = []
    for row in rows:
        geometry = transform(converter.transform, row["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(
                f"administrative exported geometry is invalid: {layer.id}/{row['code']}"
            )
        exported.append(
            {
                "code": row["code"],
                "name": row["name"],
                "source_name": row["source_name"],
                "parents_json": json.dumps(row["parents"], sort_keys=True),
                "level": layer.id,
                "classification": spec.classification,
                "reference_date": spec.reference_date,
                "license_id": spec.license_id,
                "geometry": geometry.wkb,
            }
        )
    table = pa.Table.from_pylist(exported)
    metadata = {
        "version": spec.geoparquet_version,
        "primary_column": "geometry",
        "columns": {
            "geometry": {
                "encoding": "WKB",
                "geometry_types": sorted({row["geometry"].geom_type for row in rows}),
                "crs": CRS.from_user_input(spec.export_crs).to_json_dict(),
            }
        },
    }
    table = table.replace_schema_metadata(
        {
            b"geo": json.dumps(metadata).encode(),
            b"source": json.dumps(
                {
                    "archive": spec.archive.model_dump(),
                    "geometry": spec.geometry.model_dump(),
                    "identities": spec.identities.model_dump(),
                    "license": spec.license.model_dump(),
                },
                ensure_ascii=False,
            ).encode(),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression=spec.compression)
