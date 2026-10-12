"""Validate the source, rights and output contract for regional boundaries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class License(Model):
    name: str = Field(min_length=1)
    terms: str = Field(pattern=r"^https://\S+$")
    attribution: str = Field(min_length=1)
    commercial_use: bool


class Fields(Model):
    code: str = Field(min_length=1)
    level: str = Field(min_length=1)
    country: str = Field(min_length=1)
    name: str = Field(min_length=1)
    membership: str = Field(min_length=1)

    @model_validator(mode="after")
    def distinct_fields(self):
        names = list(self.model_dump().values())
        if len(set(names)) != len(names):
            raise ValueError("source identity fields must be distinct")
        return self


class Source(Model):
    file: str = Field(pattern=r"^[a-zA-Z0-9_.-]+\.geojson$")
    url: str = Field(pattern=r"^https://\S+$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    classification_vintage: str = Field(min_length=1)
    observed_at: str
    crs: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    license_id: str = Field(min_length=1)
    license: License
    fields: Fields
    classifications: dict[str, Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    eu_membership: str = Field(min_length=1)
    excluded_levels: list[Annotated[int, Field(ge=0)]]
    expected_counts: dict[str, Annotated[int, Field(gt=0)]]
    expected_eu_counts: dict[str, Annotated[int, Field(gt=0)]]

    @model_validator(mode="after")
    def valid_inventory(self):
        if self.eu_membership not in self.classifications:
            raise ValueError("EU membership must identify a declared classification")
        if self.expected_counts.keys() != self.expected_eu_counts.keys():
            raise ValueError("source and EU inventories must declare the same levels")
        if any(not level.isdecimal() for level in self.expected_counts):
            raise ValueError("source inventory levels must be nonnegative integer strings")
        if len(set(self.excluded_levels)) != len(self.excluded_levels):
            raise ValueError("excluded source levels must be distinct")
        if set(self.excluded_levels) & {int(level) for level in self.expected_counts}:
            raise ValueError("source inventory levels cannot also be excluded")
        if any(self.expected_eu_counts[level] > count for level, count in self.expected_counts.items()):
            raise ValueError("EU inventory cannot exceed source inventory")
        if datetime.fromisoformat(self.observed_at).utcoffset() is None:
            raise ValueError("source observation time must have a timezone")
        return self


class Output(Model):
    level: int = Field(ge=0)
    file: str = Field(pattern=r"^[a-z][a-z0-9-]*\.geo\.json$")
    simplification_tolerance: float = Field(ge=0, allow_inf_nan=False)


class Render(Model):
    frame: Annotated[list[Annotated[float, Field(allow_inf_nan=False)]], Field(min_length=4, max_length=4)]
    canvas_width: float = Field(gt=0, allow_inf_nan=False)
    coordinate_decimals: int = Field(ge=0)
    outputs: list[Output] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_frame(self):
        left, bottom, right, top = self.frame
        if left >= right or bottom >= top:
            raise ValueError("render frame must have positive width and height")
        if len({item.level for item in self.outputs}) != len(self.outputs):
            raise ValueError("render outputs must declare distinct levels")
        if len({item.file for item in self.outputs}) != len(self.outputs):
            raise ValueError("render output names must be distinct")
        return self


class GeoParquet(Model):
    file: str = Field(pattern=r"^[a-z][a-z0-9-]*/[a-z][a-z0-9-]*\.parquet$")
    crs: str = Field(min_length=1)
    version: str = Field(min_length=1)
    compression: str = Field(min_length=1)


class Specification(Model):
    schema_version: Literal[1]
    source: Source
    render: Render
    geoparquet: GeoParquet
    coverage_file: str = Field(pattern=r"^[a-z][a-z0-9-]*/[a-z][a-z0-9-]*\.json$")

    @model_validator(mode="after")
    def complete_levels(self):
        levels = {str(item.level) for item in self.render.outputs}
        if levels != self.source.expected_counts.keys():
            raise ValueError("render levels must match the declared source inventory")
        return self


def load(path: Path) -> Specification:
    return Specification.model_validate(json.loads(path.read_bytes()))
