"""Build administrative maps from a pinned GeoPackage and independent official registry."""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path

import pyogrio
import shapely
from pyproj import CRS

from .administrative_render import projected, svg_path, write_parquet
from .administrative_spec import Layer, Source, Specification


def verified(source: Source, inputs: Path) -> Path:
    path = inputs / source.file
    if hashlib.sha256(path.read_bytes()).hexdigest() != source.sha256:
        raise ValueError(f"administrative source checksum differs: {source.file}")
    return path


def registry(
    archive: zipfile.ZipFile, layer: Layer, spec: Specification
) -> dict[str, dict]:
    reader = csv.DictReader(
        io.StringIO(archive.read(layer.registry_member).decode(spec.identity_encoding)),
        delimiter=spec.identity_delimiter,
    )
    columns = reader.fieldnames
    required = {
        layer.registry_code_field,
        layer.registry_name_field,
        layer.registry_frame_field,
        *layer.registry_filter,
        *(parent.registry_field for parent in layer.parents),
    }
    if (
        columns is None
        or len(set(columns)) != len(columns)
        or not required <= set(columns)
    ):
        raise ValueError(
            f"administrative registry requires unique declared columns: {layer.id}"
        )
    rows = list(reader)
    if len(rows) != layer.registry_rows or any(
        None in row or any(value is None for value in row.values()) for row in rows
    ):
        raise ValueError(
            f"administrative registry differs from the declared inventory: {layer.id}"
        )
    selected = {}
    for row in rows:
        if any(
            row[field] not in values for field, values in layer.registry_filter.items()
        ):
            continue
        code = row[layer.registry_code_field]
        if (
            re.fullmatch(layer.code_pattern, code) is None
            or code in selected
            or not row[layer.registry_name_field].strip()
        ):
            raise ValueError(
                f"administrative registry identity is invalid or repeated: {layer.id}/{code}"
            )
        selected[code] = row
    if len(selected) != layer.expected_units:
        raise ValueError(f"administrative registry selection is incomplete: {layer.id}")
    return selected


def records(
    path: Path, spec: Specification, inventories: dict[str, dict]
) -> dict[str, list[dict]]:
    products = {}
    frames = {
        code: frame for frame in spec.render.frames for code in frame.region_codes
    }
    used_frames = set()
    for layer in spec.layers:
        fields = [
            layer.geometry_code_field,
            layer.geometry_name_field,
            *(parent.geometry_field for parent in layer.parents),
        ]
        metadata, table = pyogrio.read_arrow(
            path, layer=layer.geometry_layer, columns=fields
        )
        if (
            metadata["crs"] is None
            or CRS.from_user_input(metadata["crs"])
            != CRS.from_user_input(spec.source_crs)
            or metadata["geometry_type"] not in {"Polygon", "MultiPolygon"}
            or not set(fields) <= set(metadata["fields"])
        ):
            raise ValueError(
                f"administrative geometry fields or coordinate system differ: {layer.id}"
            )
        rows = table.to_pylist()
        if len(rows) != layer.expected_source_units:
            raise ValueError(f"administrative geometry inventory differs: {layer.id}")
        selected, seen = [], set()
        for row in rows:
            code = row[layer.geometry_code_field]
            if (
                not isinstance(code, str)
                or re.fullmatch(layer.code_pattern, code) is None
                or code in seen
            ):
                raise ValueError(
                    f"administrative geometry identity is invalid or repeated: {layer.id}/{code}"
                )
            seen.add(code)
            if code in layer.excluded_source_codes:
                continue
            if code not in inventories[layer.id]:
                raise ValueError(
                    f"administrative geometry has no registry identity: {layer.id}/{code}"
                )
            identity = inventories[layer.id][code]
            source_name = row[layer.geometry_name_field]
            if not isinstance(source_name, str) or not source_name.strip():
                raise ValueError(
                    f"administrative geometry name is missing: {layer.id}/{code}"
                )
            parents = {}
            for parent in layer.parents:
                value = identity[parent.registry_field]
                if (
                    value not in inventories[parent.level]
                    or row[parent.geometry_field] != value
                ):
                    raise ValueError(
                        f"administrative parent identity differs: {layer.id}/{code}"
                    )
                parents[parent.level] = value
            region = identity[layer.registry_frame_field]
            if region not in frames:
                raise ValueError(
                    f"administrative identity has no declared map frame: {layer.id}/{code}"
                )
            used_frames.add(region)
            geometry = shapely.from_wkb(row[metadata["geometry_name"]])
            if (
                geometry is None
                or geometry.is_empty
                or geometry.geom_type not in {"Polygon", "MultiPolygon"}
            ):
                raise ValueError(
                    f"administrative geometry requires nonempty polygons: {layer.id}/{code}"
                )
            if not geometry.is_valid or not all(
                math.isfinite(coordinate) for coordinate in geometry.bounds
            ):
                raise ValueError(
                    f"administrative geometry coordinates are invalid: {layer.id}/{code}"
                )
            selected.append(
                {
                    "code": code,
                    "name": identity[layer.registry_name_field],
                    "source_name": source_name,
                    "parents": parents,
                    "frame": frames[region],
                    "geometry": geometry,
                }
            )
        if seen != set(inventories[layer.id]) | set(layer.excluded_source_codes):
            raise ValueError(
                f"administrative coverage or source geometry quality differs: {layer.id}"
            )
        products[layer.id] = sorted(selected, key=lambda row: row["code"])
    if used_frames != frames.keys():
        raise ValueError(
            "administrative map frames contain undeclared regional identities"
        )
    return products


def build(spec: Specification, inputs: Path, output: Path, usage: str) -> dict:
    if usage not in {"commercial", "non-commercial"}:
        raise ValueError("administrative build requires an explicit usage purpose")
    if usage == "commercial" and not spec.license.commercial_use:
        raise ValueError("administrative source does not permit commercial use")
    if output.exists() and any(output.iterdir()):
        raise ValueError("administrative output directory is not empty")
    verified(spec.archive, inputs)
    geometry = verified(spec.geometry, inputs)
    identities = verified(spec.identities, inputs)
    with zipfile.ZipFile(identities) as archive:
        inventories = {
            layer.id: registry(archive, layer, spec) for layer in spec.layers
        }
    products = records(geometry, spec, inventories)
    contexts = projected(products, spec)
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for layer in spec.layers:
        rows = products[layer.id]
        coverage = {
            "source_count": layer.expected_source_units,
            "registry_count": layer.expected_units,
            "rendered_count": len(rows),
            "excluded_source_codes": layer.excluded_source_codes,
            "outside": [],
            "partially_clipped": [],
        }
        body = {
            "viewBox": f"0 0 {spec.render.width:g} {spec.render.height:g}",
            "source": spec.source_attribution,
            "source_archive_sha256": spec.archive.sha256,
            "source_geometry_sha256": spec.geometry.sha256,
            "source_identity_sha256": spec.identities.sha256,
            "source_geometry_url": spec.archive.url,
            "source_identity_url": spec.identities.url,
            "source_observed_at": {
                "geometry": spec.geometry.observed_at,
                "identities": spec.identities.observed_at,
            },
            "reference_date": spec.reference_date,
            "classification": spec.classification,
            "scope": spec.scope,
            "license_id": spec.license_id,
            "license": spec.license.model_dump(),
            "source_invalid_geometry_codes": [],
            "coverage": coverage,
            "outside": [],
            "partially_clipped": [],
            "frames": [frame.model_dump() for frame in spec.render.frames],
            "shapes": [
                {
                    "aliases": [row["code"]],
                    "name": row["name"],
                    "source_name": row["source_name"],
                    "parents": row["parents"],
                    "frame": row["frame"].id,
                    "boundary_date": spec.reference_date,
                    "source_geometry_valid": row["geometry"].is_valid,
                    "d": svg_path(
                        row, contexts[row["frame"].id], spec.render.coordinate_decimals
                    ),
                }
                for row in rows
            ],
        }
        svg = output / layer.svg_file
        svg.write_bytes(
            (
                json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode()
        )
        parquet = output / layer.parquet_file
        write_parquet(rows, spec, layer, parquet)
        reports.append(
            {
                "level": layer.id,
                **coverage,
                "svg_file": layer.svg_file,
                "svg_sha256": hashlib.sha256(svg.read_bytes()).hexdigest(),
                "parquet_file": layer.parquet_file,
                "parquet_sha256": hashlib.sha256(parquet.read_bytes()).hexdigest(),
            }
        )
    report = {
        "schema_version": 1,
        "scope": spec.scope,
        "reference_date": spec.reference_date,
        "archive": spec.archive.model_dump(),
        "geometry": spec.geometry.model_dump(),
        "identities": spec.identities.model_dump(),
        "license": spec.license.model_dump(),
        "levels": reports,
    }
    target = output / spec.coverage_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--usage", choices=("commercial", "non-commercial"), required=True
    )
    args = parser.parse_args()
    result = build(
        Specification.model_validate(json.loads(args.spec.read_bytes())),
        args.inputs,
        args.output,
        args.usage,
    )
    print(json.dumps(result["levels"]))
