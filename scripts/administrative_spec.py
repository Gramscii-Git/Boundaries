"""Validate official administrative geometry, identity inventories and map frames."""

import re
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, model_validator
from pyproj import CRS

from .nuts_spec import License, Model

Text = Annotated[str, Field(min_length=1)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class Source(Model):
    file: str = Field(pattern=r"^[a-zA-Z0-9_.-]+\.(7z|zip|gpkg)$")
    url: str = Field(pattern=r"^https://\S+$")
    sha256: Digest
    observed_at: str

    @model_validator(mode="after")
    def observation(self):
        if datetime.fromisoformat(self.observed_at).utcoffset() is None:
            raise ValueError("administrative source observation requires a timezone")
        return self


class Parent(Model):
    level: Text
    geometry_field: Text
    registry_field: Text


class Layer(Model):
    id: str = Field(pattern=r"^[a-z][a-z-]*$")
    geometry_layer: Text
    geometry_code_field: Text
    geometry_name_field: Text
    registry_member: Text
    registry_code_field: Text
    registry_name_field: Text
    registry_filter: dict[Text, list[Text]]
    registry_frame_field: Text
    registry_rows: int = Field(gt=0)
    expected_units: int = Field(gt=0)
    expected_source_units: int = Field(gt=0)
    excluded_source_codes: dict[Text, Text]
    code_pattern: Text
    parents: list[Parent]
    svg_file: str = Field(pattern=r"^[a-z][a-z0-9-]*\.geo\.json$")
    parquet_file: str = Field(pattern=r"^[a-z][a-z0-9-]*/[a-z][a-z0-9-]*\.parquet$")

    @model_validator(mode="after")
    def identities(self):
        member = PurePosixPath(self.registry_member)
        if member.is_absolute() or ".." in member.parts:
            raise ValueError("identity member must remain inside the registry archive")
        re.compile(self.code_pattern)
        for codes in [list(self.excluded_source_codes), *self.registry_filter.values()]:
            if len(codes) != len(set(codes)):
                raise ValueError("declared source selections must not repeat values")
        if self.expected_source_units != self.expected_units + len(
            self.excluded_source_codes
        ):
            raise ValueError(
                "source inventory must equal admitted and explicitly excluded units"
            )
        if self.expected_units > self.registry_rows:
            raise ValueError("admitted units cannot exceed the registry inventory")
        if len({parent.level for parent in self.parents}) != len(self.parents):
            raise ValueError("administrative parent levels must be distinct")
        return self


class Frame(Model):
    id: str = Field(pattern=r"^[a-z][a-z-]*$")
    label: Text
    region_codes: list[Text] = Field(min_length=1)
    crs: Text
    rectangle: Annotated[list[Finite], Field(min_length=4, max_length=4)]
    padding: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def layout(self):
        CRS.from_user_input(self.crs)
        x, y, width, height = self.rectangle
        if x < 0 or y < 0 or min(width, height) <= 2 * self.padding:
            raise ValueError(
                "map frame requires a positive drawing area inside the canvas"
            )
        if len(set(self.region_codes)) != len(self.region_codes):
            raise ValueError("map frame must select distinct regional identities")
        return self


class Render(Model):
    width: float = Field(gt=0, allow_inf_nan=False)
    height: float = Field(gt=0, allow_inf_nan=False)
    coordinate_decimals: int = Field(ge=0)
    frames: list[Frame] = Field(min_length=1)

    @model_validator(mode="after")
    def frames_are_distinct(self):
        codes = [code for frame in self.frames for code in frame.region_codes]
        if len(set(codes)) != len(codes) or len(
            {frame.id for frame in self.frames}
        ) != len(self.frames):
            raise ValueError("each regional identity requires one distinct map frame")
        for index, frame in enumerate(self.frames):
            x, y, width, height = frame.rectangle
            if x + width > self.width or y + height > self.height:
                raise ValueError("map frames must remain inside the canvas")
            for other in self.frames[:index]:
                ox, oy, ow, oh = other.rectangle
                if x < ox + ow and ox < x + width and y < oy + oh and oy < y + height:
                    raise ValueError("map frames must not overlap")
        return self


class Specification(Model):
    schema_version: Literal[1]
    archive: Source
    geometry: Source
    archive_geometry_member: Text
    identities: Source
    identity_encoding: Text
    identity_delimiter: str = Field(min_length=1, max_length=1)
    source_crs: Text
    export_crs: Text
    geoparquet_version: Text
    compression: Text
    reference_date: str
    classification: Text
    scope: Text
    source_attribution: Text
    license_id: Text
    license: License
    layers: list[Layer] = Field(min_length=1)
    render: Render
    coverage_file: str = Field(pattern=r"^[a-z][a-z0-9-]*/[a-z][a-z0-9-]*\.json$")

    @model_validator(mode="after")
    def contract(self):
        date.fromisoformat(self.reference_date)
        CRS.from_user_input(self.source_crs)
        CRS.from_user_input(self.export_crs)
        member = PurePosixPath(self.archive_geometry_member)
        if member.is_absolute() or ".." in member.parts:
            raise ValueError("geometry member must remain inside its archive")
        ids = {layer.id for layer in self.layers}
        if len(ids) != len(self.layers):
            raise ValueError("administrative levels must be distinct")
        names = [
            value
            for layer in self.layers
            for value in (layer.svg_file, layer.parquet_file)
        ]
        if len(set(names)) != len(names) or self.coverage_file in names:
            raise ValueError("administrative output paths must be distinct")
        if any(
            parent.level not in ids or parent.level == layer.id
            for layer in self.layers
            for parent in layer.parents
        ):
            raise ValueError("administrative parents require another declared level")
        return self
