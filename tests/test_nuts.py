"""Regional builds retain complete geometry, qualified coverage and source rights."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import ValidationError
from shapely import from_wkb
from shapely.geometry import box, mapping

from scripts import nuts
from scripts.nuts_spec import Specification


class NutsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parents[1]
        self.specification = json.loads((self.root / "nuts.build.json").read_bytes())

    def source(self):
        fields = self.specification["source"]["fields"]
        rows = [
            ("AA1", 1, box(0, 0, 2, 2)),
            ("AA11", 2, box(0, 0, 2, 2)),
            ("AA111", 3, box(0, 0, 2, 2)),
            ("AA112", 3, box(12, 12, 14, 14)),
        ]
        return {"type": "FeatureCollection", "crs": {"properties": {"name": "EPSG:3035"}},
                "features": [{"type": "Feature", "properties": {fields["code"]: code,
                    fields["level"]: level, fields["country"]: "AA", fields["name"]: code,
                    fields["membership"]: self.specification["source"]["eu_membership"]},
                    "geometry": mapping(geometry)} for code, level, geometry in rows]}

    def held(self, directory: Path, value: dict):
        spec = copy.deepcopy(self.specification)
        spec["source"]["expected_counts"] = {"1": 1, "2": 1, "3": 2}
        spec["source"]["expected_eu_counts"] = {"1": 1, "2": 1, "3": 2}
        spec["render"]["frame"] = [1.0, 1.0, 10.0, 10.0]
        source = directory / spec["source"]["file"]
        source.write_text(json.dumps(value), encoding="utf-8")
        spec["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        return Specification.model_validate(spec), source

    def test_specification_requires_source_identity_rights_and_inventory(self):
        for path in (("source", "sha256"), ("source", "license"),
                     ("source", "expected_eu_counts"), ("render", "frame")):
            with self.subTest(path=path):
                value = copy.deepcopy(self.specification)
                del value[path[0]][path[1]]
                with self.assertRaises(ValidationError):
                    Specification.model_validate(value)

    def test_specification_refuses_undeclared_keys_and_invalid_geometry_configuration(self):
        for value in ("../outside.parquet", "file.parquet"):
            spec = copy.deepcopy(self.specification)
            spec["geoparquet"]["file"] = value
            with self.assertRaises(ValidationError):
                Specification.model_validate(spec)
        spec = copy.deepcopy(self.specification)
        spec["render"]["frame"] = [0.0, 0.0, 0.0, 1.0]
        with self.assertRaises(ValidationError):
            Specification.model_validate(spec)

    def test_source_changes_fail_before_creating_any_output(self):
        with tempfile.TemporaryDirectory() as held:
            directory = Path(held)
            spec, source = self.held(directory, self.source())
            source.write_bytes(source.read_bytes() + b" ")
            output = directory / "output"
            with self.assertRaisesRegex(ValueError, "checksum differs"):
                nuts.build(spec, source, output, "non-commercial")
            self.assertFalse(output.exists())

    def test_source_inventory_rejects_duplicate_missing_and_undeclared_regions(self):
        original = self.source()
        duplicate = copy.deepcopy(original)
        duplicate["features"].append(copy.deepcopy(duplicate["features"][0]))
        missing = copy.deepcopy(original)
        missing["features"].pop()
        undeclared = copy.deepcopy(original)
        undeclared["features"][0]["properties"][self.specification["source"]["fields"]["level"]] = 4
        for value, message in ((duplicate, "repeated"), (missing, "inventory differs"),
                               (undeclared, "level is not declared")):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as held:
                directory = Path(held)
                spec, source = self.held(directory, value)
                with self.assertRaisesRegex(ValueError, message):
                    nuts.records(source, spec)

    def test_commercial_usage_rejects_restricted_source_before_writing_files(self):
        with tempfile.TemporaryDirectory() as held:
            directory = Path(held)
            spec, source = self.held(directory, self.source())
            output = directory / "output"
            with self.assertRaisesRegex(ValueError, "does not permit commercial use"):
                nuts.build(spec, source, output, "commercial")
            self.assertFalse(output.exists())

    def test_full_geometry_retains_regions_outside_and_partly_inside_the_map(self):
        with tempfile.TemporaryDirectory() as held:
            directory = Path(held)
            spec, source = self.held(directory, self.source())
            output = directory / "output"
            report = nuts.build(spec, source, output, "non-commercial")
            level = next(item for item in report["levels"] if item["level"] == 3)
            self.assertEqual(level["outside"], ["AA112"])
            self.assertEqual(level["partially_clipped"], ["AA111"])
            table = pq.read_table(output / spec.geoparquet.file)
            self.assertEqual(table.num_rows, 4)
            self.assertEqual(set(table["code"].to_pylist()), {"AA1", "AA11", "AA111", "AA112"})
            metadata = json.loads(table.schema.metadata[b"geo"])
            self.assertEqual(metadata["primary_column"], "geometry")
            for row in table.to_pylist():
                self.assertTrue(from_wkb(row["geometry"]).is_valid)
                self.assertFalse(row["commercial_use"])
                self.assertEqual(row["source_geometry_sha256"], spec.source.sha256)
            body = json.loads((output / spec.render.outputs[-1].file).read_bytes())
            self.assertEqual(body["coverage"], level)
            self.assertEqual(body["source_geometry_sha256"], spec.source.sha256)
            self.assertFalse(body["license"]["commercial_use"])


if __name__ == "__main__":
    unittest.main()
