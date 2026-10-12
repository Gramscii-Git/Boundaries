"""Build licensed NUTS polygons from exact ISTAT geometry and identity sources."""

import argparse
import csv
import hashlib
import json
import math
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import shapefile
from pydantic import Field, model_validator
from shapely.geometry import shape

from .nuts_spec import License, Model


class Source(Model):
    file: str = Field(pattern=r"^[a-zA-Z0-9_.-]+\.(zip|csv)$")
    url: str = Field(pattern=r"^https://\S+$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: str

    @model_validator(mode="after")
    def qualified_observation(self):
        if datetime.fromisoformat(self.observed_at).utcoffset() is None:
            raise ValueError("ISTAT source observation time must have a timezone")
        return self


class Specification(Model):
    schema_version: Literal[1]
    geometry: Source
    identities: Source
    member: str = Field(min_length=1)
    projection_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    geometry_encoding: str = Field(min_length=1)
    identity_encoding: str = Field(min_length=1)
    identity_delimiter: str = Field(min_length=1, max_length=1)
    geometry_code_field: str = Field(min_length=1)
    geometry_name_field: str = Field(min_length=1)
    identity_code_field: str = Field(min_length=1)
    identity_nuts_field: str = Field(min_length=1)
    code_width: int = Field(gt=0)
    code_pattern: str = Field(min_length=1)
    nuts_pattern: str = Field(min_length=1)
    expected_identity_rows: int = Field(gt=0)
    expected_units: int = Field(gt=0)
    expected_invalid_geometry_codes: list[str]
    canvas_width: float = Field(gt=0, allow_inf_nan=False)
    coordinate_decimals: int = Field(ge=0)
    simplification_tolerance: float = Field(ge=0, allow_inf_nan=False)
    output_file: str = Field(pattern=r"^[a-z][a-z0-9-]*\.geo\.json$")
    classification: str = Field(min_length=1)
    classification_vintage: str = Field(min_length=1)
    reference_date: str
    attribution: str = Field(min_length=1)
    license_id: str = Field(min_length=1)
    license: License

    @model_validator(mode="after")
    def valid_contract(self):
        if ".." in Path(self.member).parts or self.member.startswith("/"):
            raise ValueError("geometry member must stay inside the source archive")
        for pattern in (self.code_pattern, self.nuts_pattern):
            re.compile(pattern)
        invalid = self.expected_invalid_geometry_codes
        if len(set(invalid)) != len(invalid) or any(re.fullmatch(self.nuts_pattern, code) is None for code in invalid):
            raise ValueError("source quality inventory requires distinct NUTS identifiers")
        date.fromisoformat(self.reference_date)
        return self


def verified(source: Source, inputs: Path) -> Path:
    path = inputs / source.file
    if hashlib.sha256(path.read_bytes()).hexdigest() != source.sha256:
        raise ValueError(f"ISTAT source checksum differs: {source.file}")
    return path


def identity_codes(path: Path, spec: Specification) -> dict[str, str]:
    with path.open(encoding=spec.identity_encoding, newline="") as stream:
        reader = csv.DictReader(stream, delimiter=spec.identity_delimiter)
        columns = reader.fieldnames
        if columns is None or len(set(columns)) != len(columns) or not {
            spec.identity_code_field, spec.identity_nuts_field
        } <= set(columns):
            raise ValueError("ISTAT identity source requires unique, declared columns")
        rows = list(reader)
    if len(rows) != spec.expected_identity_rows:
        raise ValueError("ISTAT identity inventory differs from its declared source")
    codes = {}
    for row in rows:
        province, nuts = row[spec.identity_code_field], row[spec.identity_nuts_field]
        if re.fullmatch(spec.code_pattern, province) is None or re.fullmatch(spec.nuts_pattern, nuts) is None:
            raise ValueError("ISTAT identity source contains an invalid regional code")
        if province in codes and codes[province] != nuts:
            raise ValueError(f"ISTAT province maps to more than one NUTS unit: {province}")
        codes[province] = nuts
    if len(codes) != spec.expected_units or len(set(codes.values())) != spec.expected_units:
        raise ValueError("ISTAT province and NUTS identities must form the declared exact inventory")
    return codes


def svg_path(geometry, spec: Specification, left: float, top: float, scale: float) -> str:
    simplified = geometry.simplify(spec.simplification_tolerance, preserve_topology=True)
    polygons = simplified.geoms if simplified.geom_type == "MultiPolygon" else [simplified]
    return "".join("M" + "L".join(
        f"{(x-left)*scale:.{spec.coordinate_decimals}f},{(top-y)*scale:.{spec.coordinate_decimals}f}"
        for x, y in ring.coords) + "Z" for polygon in polygons
        for ring in [polygon.exterior, *polygon.interiors])


def build(spec: Specification, inputs: Path, output: Path, usage: str) -> dict:
    if usage not in {"commercial", "non-commercial"}:
        raise ValueError("ISTAT build requires an explicit usage purpose")
    if usage == "commercial" and not spec.license.commercial_use:
        raise ValueError("ISTAT source does not permit commercial use")
    archive, identities = verified(spec.geometry, inputs), verified(spec.identities, inputs)
    codes = identity_codes(identities, spec)
    rendered, seen, invalid = [], set(), []
    with zipfile.ZipFile(archive) as held:
        if hashlib.sha256(held.read(spec.member + ".prj")).hexdigest() != spec.projection_sha256:
            raise ValueError("ISTAT geometry projection differs from its declared source")
        with held.open(spec.member + ".shp") as shp, held.open(spec.member + ".shx") as shx, \
                held.open(spec.member + ".dbf") as dbf, shapefile.Reader(
                    shp=shp, shx=shx, dbf=dbf, encoding=spec.geometry_encoding) as reader:
            left, bottom, right, top = reader.bbox
            if not all(math.isfinite(value) for value in (left, bottom, right, top)) or right <= left or top <= bottom:
                raise ValueError("ISTAT geometry requires a positive reference frame")
            scale = spec.canvas_width / (right-left)
            for item in reader.iterShapeRecords():
                number = item.record[spec.geometry_code_field]
                if type(number) is not int or number <= 0:
                    raise ValueError("ISTAT geometry province identity must be a positive integer")
                code = str(number).zfill(spec.code_width)
                if code not in codes or code in seen:
                    raise ValueError(f"ISTAT geometry identity is missing or repeated: {code}")
                seen.add(code)
                geometry = shape(item.shape.__geo_interface__)
                if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
                    raise ValueError(f"ISTAT geometry requires regional polygons: {code}")
                if not geometry.is_valid:
                    invalid.append(codes[code])
                name = item.record[spec.geometry_name_field]
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"ISTAT geometry requires a regional name: {code}")
                rendered.append({"aliases": [codes[code], code], "name": name,
                                 "classification": spec.classification,
                                 "source_geometry_valid": geometry.is_valid,
                                 "boundary_date": spec.reference_date,
                                 "d": svg_path(geometry, spec, left, top, scale)})
    if seen != codes.keys() or sorted(invalid) != sorted(spec.expected_invalid_geometry_codes):
        raise ValueError("ISTAT geometry inventory or declared source quality differs")
    width = str(int(spec.canvas_width)) if spec.canvas_width.is_integer() else str(spec.canvas_width)
    body = {"viewBox": f"0 0 {width} {(top-bottom)*scale:.{spec.coordinate_decimals}f}",
            "source": spec.attribution, "source_archive_sha256": spec.geometry.sha256,
            "source_identity_sha256": spec.identities.sha256,
            "source_geometry_url": spec.geometry.url, "source_identity_url": spec.identities.url,
            "source_observed_at": {"geometry": spec.geometry.observed_at, "identities": spec.identities.observed_at},
            "classification_vintage": spec.classification_vintage, "reference_date": spec.reference_date,
            "license_id": spec.license_id, "license": spec.license.model_dump(),
            "source_invalid_geometry_codes": sorted(invalid),
            "shapes": sorted(rendered, key=lambda row: row["aliases"][0])}
    output.mkdir(parents=True, exist_ok=True)
    (output / spec.output_file).write_bytes((json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
    return body


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--usage", required=True, choices=("commercial", "non-commercial"))
    args = parser.parse_args()
    contract = Specification.model_validate(json.loads(args.spec.read_bytes()))
    result = build(contract, args.inputs, args.output, args.usage)
    print(json.dumps({"file": contract.output_file, "shapes": len(result["shapes"]),
                      "source_invalid_geometry_codes": result["source_invalid_geometry_codes"]}))
