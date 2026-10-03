import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import pyarrow.parquet as pq
import shapefile
import shapely

from scripts import census_sections

FIELDS = ["COD_REG", "COD_UTS", "PRO_COM", "SEZ21", "SEZ21_ID", "COD_TIPO_S", "TIPO_LOC", "LOC21_ID", "COD_ZIC",
          "COD_ISAM", "COD_ACQUE", "COD_ISOLE", "COD_MONT_D", "COD_AREA_S", "COM_ASC1", "COM_ASC2", "COM_ASC3",
          "POP21", "FAM21", "ABI21", "EDI21"]


def region(directory: Path, code: str, sections: list[int], listed: list[int] | None = None) -> None:
    """A regional zip with one 100 m square per section near Aosta, in UTM 32N."""
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON) as writer:
        for name in FIELDS:
            writer.field(name, "N", 13)
        writer.field("SHAPE_Leng", "F", 19, 11)
        writer.field("SHAPE_Area", "F", 19, 11)
        for index, section in enumerate(sections):
            x, y = 370000 + 200 * index, 5070000
            writer.poly([[[x, y], [x, y + 100], [x + 100, y + 100], [x + 100, y], [x, y]]])
            writer.record(2, 7, 7003, section, 7003 * 10**7 + section, 1, 1, 700310001, 0, 0, 0, 0, 0, 0,
                          7003002 if index else 0, 0, 0, 10, 4, 5, 2, 400.0, 10000.0)
    table = "\t".join(FIELDS) + "\n" + "".join(
        f"2\t7\t7003\t{section}\t{7003 * 10**7 + section}\n" for section in (listed if listed is not None else sections))
    with zipfile.ZipFile(directory / f"R{code}_21.zip", "w") as archive:
        for part, body in (("shp", shp), ("shx", shx), ("dbf", dbf)):
            archive.writestr(f"SHP/R{code}_21_WGS84.{part}", body.getvalue())
        archive.writestr(f"TAB/SEZ_R{code}_21.csv", table.encode("utf-16"))


class CensusSectionTests(unittest.TestCase):
    def setUp(self):
        self.held = tempfile.TemporaryDirectory()
        self.root = Path(self.held.name)
        self.addCleanup(self.held.cleanup)

    def build(self, regions: dict[str, str]):
        with mock.patch.object(census_sections, "REGIONS", regions):
            return census_sections.build(self.root, self.root / "build")

    def test_codes_keep_their_widths_and_geometry_is_in_degrees(self):
        region(self.root, "02", [1, 8888888])
        manifest = self.build({"02": "Valle d'Aosta"})
        self.assertEqual((manifest["sections"], manifest["pop21"]), (2, 20))
        rows = pq.read_table(self.root / "build/census-sections-2021/R02.parquet")
        first = rows.slice(0, 1).drop(["geometry"]).to_pylist()[0]
        self.assertEqual((first["PRO_COM"], first["SEZ21_ID"], first["LOC21_ID"]), ("007003", "0070030000001", "00700310001"))
        self.assertEqual((first["COM_ASC1"], rows["COM_ASC1"][1].as_py(), first["COD_ZIC"]), (None, "007003002", None))
        centre = shapely.from_wkb(rows["geometry"][0].as_py()).centroid
        self.assertTrue(7.3 < centre.x < 7.4 and 45.7 < centre.y < 45.8, centre)
        geo = json.loads(rows.schema.metadata[b"geo"])
        self.assertEqual((geo["primary_column"], geo["columns"]["geometry"]["encoding"]), ("geometry", "WKB"))

    def test_a_shapefile_that_differs_from_its_table_is_refused(self):
        region(self.root, "02", [1, 2], listed=[1])
        with self.assertRaisesRegex(ValueError, "the table lists 1"):
            self.build({"02": "Valle d'Aosta"})

    def test_a_section_repeated_across_regions_is_refused(self):
        region(self.root, "01", [1])
        region(self.root, "02", [1])
        with self.assertRaisesRegex(ValueError, "repeat"):
            self.build({"01": "Piemonte", "02": "Valle d'Aosta"})


if __name__ == "__main__":
    unittest.main()
