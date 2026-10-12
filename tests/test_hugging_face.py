"""Hugging Face publication contains every verified boundary exactly once."""

import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from datasets import load_dataset
from pydantic import ValidationError
from shapely.geometry import Polygon

from scripts.hugging_face import Publication, build, validate_rows


class HuggingFaceTests(unittest.TestCase):
    def test_build_rejects_stale_publication_files(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "stale.jsonl").write_bytes(b"stale")
            with self.assertRaisesRegex(ValueError, "not empty"):
                build(root, output)

    def test_build_has_deterministic_complete_licence_separated_rows(self):
        root = Path(__file__).parents[1]
        manifest = json.loads((root / "boundary-sets.json").read_bytes())
        publication = Publication.model_validate(manifest['publication'])
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            release = build(root, Path(first))
            repeated = build(root, Path(second))
            self.assertEqual(release, repeated)
            italian = load_dataset(
                first, name="istat", split="train", cache_dir=second,
            )
            nuts = italian.filter(lambda row: row["boundary_set_id"] == "italy-nuts3-2024")
            self.assertEqual(set(nuts["vintage"]), {"2024"})
            self.assertTrue(all(row["parent_codes"] is None for row in nuts))
            census = Path(first) / "census-sections-2021"
            census.mkdir()
            geometry = Polygon([(8, 45), (8.1, 45), (8, 45.1)]).wkb
            pq.write_table(
                pa.table({"section_id": ["000000001"], "geometry": [geometry]}),
                census / "R01.parquet",
            )
            sections = load_dataset(
                first, name="istat-census-sections-2021", split="train", cache_dir=second,
            )
            self.assertEqual(sections[0]["section_id"], "000000001")
            self.assertEqual(sections[0]["geometry"], geometry)
            self.assertEqual(
                {path.name for path in (Path(first) / "preview").glob("*.png")},
                {Path(name).name for name in publication.previews},
            )
            for name in publication.previews:
                self.assertEqual(
                    (Path(first) / name).read_bytes(),
                    (root / name).read_bytes(),
                )
                self.assertEqual(
                    (Path(second) / name).read_bytes(),
                    (root / name).read_bytes(),
                )
            self.assertEqual(
                sum(item["rows"] for item in release["data_files"].values()),
                68953,
            )
            manifest = json.loads((root / "boundary-sets.json").read_bytes())
            expected_commercial_use = {
                license_["viewer_config"]: license_["commercial_use"]
                for license_ in manifest["licenses"].values()
            }
            for group, metadata in release["data_files"].items():
                self.assertEqual(Path(metadata["file"]).suffix, ".parquet")
                rows = pq.read_table(Path(first) / metadata["file"]).to_pylist()
                self.assertEqual(len(rows), metadata["rows"])
                self.assertEqual(
                    {row["commercial_use"] for row in rows},
                    {expected_commercial_use[group]},
                )
                regional = [row for row in rows if row['license_id']=='gisco-nuts-non-commercial']
                if regional:
                    spec = json.loads((root / "nuts.build.json").read_bytes())
                    self.assertEqual({row["source_geometry_sha256"] for row in regional},
                                     {spec["source"]["sha256"]})
                    self.assertEqual({row["classification"] for row in regional},
                                     set(spec["source"]["classifications"].values()))
                    self.assertTrue(all(isinstance(row["partially_clipped_codes"], list)
                                        for row in regional))
                self.assertEqual(
                    {manifest["licenses"][row["license_id"]]["viewer_config"] for row in rows},
                    {group},
                )
                identities = {
                    (row["boundary_set_id"], alias)
                    for row in rows
                    for alias in row["aliases"]
                }
                self.assertEqual(
                    len(identities),
                    sum(len(row["aliases"]) for row in rows),
                )

    def test_publication_configuration_requires_explicit_safe_paths(self):
        good={'readme':'HUGGING_FACE_README.md','documents':['LICENSE'],
              'previews':[],'table_compression':'zstd'}
        for field in Publication.model_fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Publication.model_validate({name:value for name,value in good.items() if name!=field})
        for path in ['../private.json','/private.json','']:
            with self.subTest(path=path), self.assertRaises(ValidationError):
                Publication.model_validate({**good,'documents':[path]})

    def test_publication_rejects_missing_column_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "README.md").write_text("---\nlicense: other\n---\n# Boundaries\n")
            with self.assertRaisesRegex(ValueError, "column schema is missing: istat"):
                validate_rows(output, {"data_files": {
                    "istat": {"file": "data/istat.parquet", "rows": 1},
                }})


if __name__ == "__main__":
    unittest.main()
