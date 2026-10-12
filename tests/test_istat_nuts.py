"""ISTAT geometry joins only exact, sourced identities and preserves source quality."""

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import shapefile

from scripts.istat_nuts import Specification, build


class IstatNutsTests(unittest.TestCase):
    def prepare(self, root: Path):
        spec = json.loads((Path(__file__).parents[1] / "istat-nuts.build.json").read_bytes())
        shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
        with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON) as writer:
            writer.field(spec["geometry_code_field"], "N")
            writer.field(spec["geometry_name_field"], "C")
            for code, ring in ((1, [[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]]),
                               (2, [[3, 0], [5, 3], [5, 0], [3, 2], [3, 0]])):
                writer.poly([ring])
                writer.record(code, str(code))
        projection = b"qualified test projection"
        archive = root / spec["geometry"]["file"]
        with zipfile.ZipFile(archive, "w") as held:
            for extension, content in (("shp", shp.getvalue()), ("shx", shx.getvalue()),
                                       ("dbf", dbf.getvalue()), ("prj", projection)):
                held.writestr(spec["member"] + "." + extension, content)
        identities = root / spec["identities"]["file"]
        identities.write_text(spec["identity_code_field"] + ";" + spec["identity_nuts_field"]
                              + "\n001;ITC11\n001;ITC11\n002;ITC12\n", encoding=spec["identity_encoding"])
        spec["geometry"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        spec["identities"]["sha256"] = hashlib.sha256(identities.read_bytes()).hexdigest()
        spec["projection_sha256"] = hashlib.sha256(projection).hexdigest()
        spec["expected_identity_rows"] = 3
        spec["expected_units"] = 2
        spec["expected_invalid_geometry_codes"] = ["ITC12"]
        spec["simplification_tolerance"] = 0.0
        return spec, identities

    def test_commercial_build_uses_official_identity_codes_and_records_invalid_source_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, _ = self.prepare(root)
            spec = Specification.model_validate(raw)
            body = build(spec, root, root / "output", "commercial")
            self.assertTrue(body["license"]["commercial_use"])
            self.assertEqual([row["aliases"] for row in body["shapes"]],
                             [["ITC11", "001"], ["ITC12", "002"]])
            self.assertEqual(body["source_invalid_geometry_codes"], ["ITC12"])
            self.assertFalse(body["shapes"][1]["source_geometry_valid"])
            self.assertEqual(body["source_identity_sha256"], spec.identities.sha256)

    def test_ambiguous_identity_and_unrecorded_source_quality_fail_before_output(self):
        for ambiguity in (False, True):
            with self.subTest(ambiguity=ambiguity), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                raw, identities = self.prepare(root)
                if ambiguity:
                    identities.write_text(identities.read_text(encoding=raw["identity_encoding"])
                                          .replace("001;ITC11", "001;ITC13", 1), encoding=raw["identity_encoding"])
                    raw["identities"]["sha256"] = hashlib.sha256(identities.read_bytes()).hexdigest()
                    message = "more than one NUTS"
                else:
                    raw["expected_invalid_geometry_codes"] = []
                    message = "source quality differs"
                with self.assertRaisesRegex(ValueError, message):
                    build(Specification.model_validate(raw), root, root / "output", "commercial")
                self.assertFalse((root / "output").exists())

    def test_changed_identity_source_is_refused_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, identities = self.prepare(root)
            identities.write_bytes(identities.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "checksum differs"):
                build(Specification.model_validate(raw), root, root / "output", "commercial")
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
