"""Build the Hugging Face boundary dataset from verified distribution assets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Publication(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    readme: str = Field(min_length=1)
    documents: list[str] = Field(min_length=1)
    previews: list[str]

    @model_validator(mode="after")
    def paths(self):
        paths = [self.readme, *self.documents, *self.previews]
        if len(set(paths)) != len(paths):
            raise ValueError("publication source paths must be distinct")
        if any(not name.strip() or PurePosixPath(name).is_absolute()
               or '..' in PurePosixPath(name).parts for name in paths):
            raise ValueError("publication source paths must remain inside the repository")
        return self


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(asset: dict, license_: dict, body: dict, shape: dict) -> dict:
    return {
        "boundary_set_id": asset["id"],
        "source_file": asset["file"],
        "scope": asset["scope"],
        "level": asset["level"],
        "classification": (asset["classification"] if asset["classification_field"] is None
                           else shape[asset["classification_field"]]),
        "vintage": asset["vintage"],
        "identifiers": asset["identifiers"],
        "license_id": asset["license"],
        "commercial_use": license_["commercial_use"],
        "view_box": body["viewBox"],
        "source": body["source"],
        "source_archive_sha256": body.get("source_archive_sha256"),
        "source_geometry_sha256": body.get("source_geometry_sha256"),
        "source_identity_sha256": body.get("source_identity_sha256"),
        "source_geometry_valid": shape.get("source_geometry_valid"),
        "source_invalid_geometry_codes": body.get("source_invalid_geometry_codes"),
        "reference_date": body.get("reference_date"),
        "outside_codes": body.get("outside"),
        "partially_clipped_codes": body.get("partially_clipped"),
        "name": shape["name"],
        "aliases": shape["aliases"],
        "svg_path": shape["d"],
        "boundary_date": shape.get("boundary_date"),
        "frame_id": shape.get("frame"),
        "parent_codes": shape.get("parents"),
    }


def build(root: Path, output: Path) -> dict:
    manifest = json.loads((root / "boundary-sets.json").read_bytes())
    publication = Publication.model_validate(manifest["publication"])
    if output.exists() and any(output.iterdir()):
        raise ValueError("Hugging Face publication output directory is not empty")
    output.mkdir(parents=True, exist_ok=True)
    data = output / "data"
    data.mkdir(exist_ok=True)
    shutil.copy2(root / publication.readme, output / "README.md")
    for name in publication.documents:
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, output / name)
    for name in publication.previews:
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, output / name)

    grouped: dict[str, list[dict]] = {
        license_["viewer_config"]: [] for license_ in manifest["licenses"].values()
    }
    for asset in manifest["boundary_sets"]:
        source = root / asset["file"]
        if _digest(source) != asset["sha256"]:
            raise ValueError(f"boundary asset checksum differs: {asset['file']}")
        body = json.loads(source.read_bytes())
        if len(body["shapes"]) != asset["shapes"]:
            raise ValueError(f"boundary asset shape count differs: {asset['file']}")
        license_ = manifest["licenses"][asset["license"]]
        group = license_["viewer_config"]
        grouped[group].extend(_row(asset, license_, body, shape) for shape in body["shapes"])
        shutil.copy2(source, output / asset["file"])

    release = {"schema_version": 1, "dataset_id": manifest["dataset_id"], "data_files": {}}
    for group, rows in grouped.items():
        target = data / f"{group}.jsonl.gz"
        with (
            target.open("wb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        ):
            for row in rows:
                compressed.write(
                    (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
                )
        release["data_files"][group] = {
            "file": str(target.relative_to(output)),
            "rows": len(rows),
            "sha256": _digest(target),
        }
    (output / "publication.json").write_bytes(
        (json.dumps(release, ensure_ascii=False, indent=2) + "\n").encode()
    )
    return release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    release = build(args.root, args.output)
    print(json.dumps(release, indent=2))


if __name__ == "__main__":
    main()
