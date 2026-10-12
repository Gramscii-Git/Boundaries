"""Build complete regional geometry and report the coverage of its map frame."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import CRS, Transformer
from shapely.geometry import box, shape
from shapely.ops import transform

from .nuts_spec import Specification, load


def records(path: Path, spec: Specification) -> list[dict]:
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != spec.source.sha256:
        raise ValueError(f"regional source checksum differs: {digest}")
    held = json.loads(content)
    if held["type"] != "FeatureCollection":
        raise ValueError("regional source must be a GeoJSON feature collection")
    if CRS.from_user_input(held["crs"]["properties"]["name"]) != CRS.from_user_input(spec.source.crs):
        raise ValueError("regional source coordinate system differs from its specification")
    fields = spec.source.fields
    rows = []
    codes = set()
    for feature in held["features"]:
        if feature["type"] != "Feature":
            raise ValueError("regional source entries must be GeoJSON features")
        props = feature["properties"]
        code, level = props[fields.code], props[fields.level]
        if not isinstance(code, str) or not code.strip() or code != code.strip() or code in codes:
            raise ValueError(f"regional source identity is blank or repeated: {code!r}")
        codes.add(code)
        if type(level) is not int or level < 0:
            raise ValueError(f"regional source level is invalid: {code}")
        if str(level) not in spec.source.expected_counts:
            if level in spec.source.excluded_levels:
                continue
            raise ValueError(f"regional source level is not declared: {code}")
        name, country, membership = props[fields.name], props[fields.country], props[fields.membership]
        if not isinstance(name, str) or not name.strip() or not isinstance(country, str) or not country.strip():
            raise ValueError(f"regional source name or country is missing: {code}")
        if membership not in spec.source.classifications:
            raise ValueError(f"regional source classification is not declared: {code}")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"regional source geometry is invalid: {code}")
        rows.append({"code": code, "level": level, "name": name, "country": country,
                     "membership": membership, "geometry": geometry, "properties": props})
    for label, selected, expected in (
        ("source", rows, spec.source.expected_counts),
        ("EU", [row for row in rows if row["membership"] == spec.source.eu_membership], spec.source.expected_eu_counts),
    ):
        counts = {str(level): count for level, count in Counter(row["level"] for row in selected).items()}
        if counts != expected:
            raise ValueError(f"regional {label} inventory differs: {counts}")
    return sorted(rows, key=lambda row: row["code"])


def path_of(geometry, spec: Specification, tolerance: float) -> str:
    left, _, right, top = spec.render.frame
    scale = spec.render.canvas_width / (right - left)
    simplified = geometry.simplify(tolerance, preserve_topology=True)
    polygons = simplified.geoms if simplified.geom_type == "MultiPolygon" else [simplified]
    parts = []
    decimals = spec.render.coordinate_decimals
    for polygon in polygons:
        if polygon.is_empty or polygon.geom_type != "Polygon":
            raise ValueError("rendered regional geometry must contain polygons")
        for ring in [polygon.exterior, *polygon.interiors]:
            points = [f"{(x - left) * scale:.{decimals}f},{(top - y) * scale:.{decimals}f}" for x, y in ring.coords]
            if len(points) < 4:
                raise ValueError("rendered regional ring requires four coordinates")
            parts.append("M" + "L".join(points) + "Z")
    if not parts:
        raise ValueError("regional geometry produces no SVG path")
    return "".join(parts)


def build_map(rows: list[dict], spec: Specification, output) -> tuple[dict, dict]:
    frame = box(*spec.render.frame)
    selected = [row for row in rows if row["level"] == output.level]
    rendered, outside, partial = [], [], []
    for row in selected:
        clipped = row["geometry"].intersection(frame)
        if clipped.is_empty:
            outside.append(row["code"])
            continue
        if not frame.covers(row["geometry"]):
            partial.append(row["code"])
        rendered.append({"aliases": [row["code"]], "name": row["name"],
                         "classification": spec.source.classifications[row["membership"]],
                         "d": path_of(clipped, spec, output.simplification_tolerance)})
    eu = {row["code"] for row in selected if row["membership"] == spec.source.eu_membership}
    drawn = {item["aliases"][0] for item in rendered}
    coverage = {"level": output.level, "source_count": len(selected), "rendered_count": len(rendered),
                "outside": outside, "partially_clipped": partial, "eu_source_count": len(eu),
                "eu_rendered_count": len(eu & drawn)}
    left, bottom, right, top = spec.render.frame
    width = spec.render.canvas_width
    width_label = str(int(width)) if width.is_integer() else str(width)
    body = {"viewBox": f"0 0 {width_label} {(top - bottom) * width / (right - left):.{spec.render.coordinate_decimals}f}",
            "source": spec.source.attribution, "source_geometry_sha256": spec.source.sha256,
            "classification_vintage": spec.source.classification_vintage,
            "license_id": spec.source.license_id, "license": spec.source.license.model_dump(),
            "outside": outside, "partially_clipped": partial, "coverage": coverage, "shapes": rendered}
    return body, coverage


def write_geoparquet(rows: list[dict], spec: Specification, target: Path) -> None:
    transformer = Transformer.from_crs(spec.source.crs, spec.geoparquet.crs, always_xy=True)
    exported = []
    geometry_types = set()
    for row in rows:
        geometry = transform(transformer.transform, row["geometry"])
        if not geometry.is_valid or geometry.is_empty:
            raise ValueError(f"regional reprojected geometry is invalid: {row['code']}")
        geometry_types.add(geometry.geom_type)
        exported.append({"code": row["code"], "level": row["level"], "name": row["name"],
                         "country_code": row["country"],
                         "classification": spec.source.classifications[row["membership"]],
                         "classification_vintage": spec.source.classification_vintage,
                         "license_id": spec.source.license_id,
                         "commercial_use": spec.source.license.commercial_use,
                         "source_geometry_sha256": spec.source.sha256,
                         "source_properties_json": json.dumps(row["properties"], ensure_ascii=False, sort_keys=True),
                         "geometry": geometry.wkb})
    table = pa.Table.from_pylist(exported)
    metadata = {"version": spec.geoparquet.version, "primary_column": "geometry",
                "columns": {"geometry": {"encoding": "WKB", "geometry_types": sorted(geometry_types),
                                           "crs": CRS.from_user_input(spec.geoparquet.crs).to_json_dict()}}}
    table = table.replace_schema_metadata({b"geo": json.dumps(metadata).encode(),
                                          b"source": json.dumps(spec.source.model_dump(), ensure_ascii=False).encode()})
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression=spec.geoparquet.compression)


def build(spec: Specification, source: Path, output: Path, usage: str) -> dict:
    if usage not in {"commercial", "non-commercial"}:
        raise ValueError("regional build requires an explicit usage purpose")
    if usage == "commercial" and not spec.source.license.commercial_use:
        raise ValueError(f"regional source does not permit commercial use: {spec.source.license.terms}")
    rows = records(source, spec)
    products = [build_map(rows, spec, item) for item in spec.render.outputs]
    output.mkdir(parents=True, exist_ok=True)
    write_geoparquet(rows, spec, output / spec.geoparquet.file)
    for item, (body, _) in zip(spec.render.outputs, products, strict=True):
        (output / item.file).write_bytes((json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
    coverage = {"source": spec.source.model_dump(), "geoparquet": {"file": spec.geoparquet.file,
                "rows": len(rows), "sha256": hashlib.sha256((output / spec.geoparquet.file).read_bytes()).hexdigest()},
                "levels": [measured for _, measured in products]}
    target = output / spec.coverage_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((json.dumps(coverage, ensure_ascii=False, indent=2) + "\n").encode())
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--usage", required=True, choices=("commercial", "non-commercial"))
    args = parser.parse_args()
    coverage = build(load(args.spec), args.source, args.output, args.usage)
    print(json.dumps({"geoparquet": coverage["geoparquet"], "levels": coverage["levels"]}))


if __name__ == "__main__":
    main()
