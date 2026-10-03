import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import pyarrow.parquet as pq

from scripts import civic_addresses

HEADER = ";".join(civic_addresses.COLUMNS)
ROWS = {
    "MOLI": ["A050;070001;740052;;CONTRADA BOSCO;;;;25539811;;1;;;;;14,8116502;41,8494625;0;4",
             "A050;070001;740046;;CONTRADA COLLE;;;;25539806;;2;A;;;;;;;"],
    "VALL": ["A205;007001;1;;VIA ROMA;;;;100;;3;;;;;7,3201;45,7372;583,5;1"],
}
STREETS = "CODICE_COMUNE;CODICE_ISTAT;PROGRESSIVO_NAZIONALE;CODICE_COMUNALE;ODONIMO;LOCALITA';TOTALE_ACCESSI;DIZIONE_LINGUA1;DIZIONE_LINGUA2;\n"


def downloads(directory: Path, rows=ROWS, total=3) -> Path:
    for code, lines in rows.items():
        with zipfile.ZipFile(directory / f"INDIR_{code}.zip", "w") as archive:
            archive.writestr(f"INDIR_{code}_20260915.csv", "\n".join([HEADER, *lines]) + "\n")
    with zipfile.ZipFile(directory / "STRAD_ITA.zip", "w") as archive:
        archive.writestr("STRAD_ITA_20260915.csv", STREETS + f"A050;070001;1;;VIA;;{total};;;\n")
    return directory


class CivicAddressTests(unittest.TestCase):
    def setUp(self):
        self.held = tempfile.TemporaryDirectory()
        self.root = Path(self.held.name)
        patcher = mock.patch.object(civic_addresses, "REGIONS", {"MOLI": "Molise", "VALL": "Valle d'Aosta"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.held.cleanup)

    def test_rows_keep_their_codes_and_get_numeric_coordinates(self):
        manifest = civic_addresses.build(downloads(self.root), self.root / "build")
        self.assertEqual((manifest["snapshot"], manifest["rows"], manifest["located"]), ("2026-09-15", 3, 2))
        molise = pq.read_table(self.root / "build/data/MOLI.parquet").to_pylist()
        self.assertEqual(molise[0]["CODICE_ISTAT"], "070001")
        self.assertEqual((molise[0]["LONGITUDE"], molise[0]["LATITUDE"], molise[0]["QUOTA"]), (14.8116502, 41.8494625, 0.0))
        self.assertEqual((molise[1]["LONGITUDE"], molise[1]["ESPONENTE"], molise[1]["METODO"]), (None, "A", None))
        written = json.loads((self.root / "build/manifest.json").read_text())
        self.assertEqual(written["regions"]["VALL"]["located"], 1)

    def test_a_total_that_differs_from_the_street_file_is_refused(self):
        with self.assertRaisesRegex(ValueError, "the street file counts 4"):
            civic_addresses.build(downloads(self.root, total=4), self.root / "build")

    def test_a_repeated_civic_identifier_is_refused(self):
        rows = {**ROWS, "VALL": ["A205;007001;1;;VIA ROMA;;;;25539811;;3;;;;;7,3201;45,7372;583,5;1"]}
        with self.assertRaisesRegex(ValueError, "repeat"):
            civic_addresses.build(downloads(self.root, rows), self.root / "build")

    def test_a_coordinate_outside_italy_is_refused(self):
        rows = {**ROWS, "VALL": ["A205;007001;1;;VIA ROMA;;;;100;;3;;;;;2,35;48,85;35;1"]}
        with self.assertRaisesRegex(ValueError, "outside Italy"):
            civic_addresses.build(downloads(self.root, rows), self.root / "build")


if __name__ == "__main__":
    unittest.main()
