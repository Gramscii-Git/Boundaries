"""Hugging Face publication contains every verified boundary exactly once."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.hugging_face import PREVIEWS, build


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
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            release = build(root, Path(first))
            repeated = build(root, Path(second))
            self.assertEqual(release, repeated)
            self.assertEqual(
                {path.name for path in (Path(first) / "preview").glob("*.png")},
                set(PREVIEWS),
            )
            for name in PREVIEWS:
                self.assertEqual(
                    (Path(first) / "preview" / name).read_bytes(),
                    (root / "preview" / name).read_bytes(),
                )
                self.assertEqual(
                    (Path(second) / "preview" / name).read_bytes(),
                    (root / "preview" / name).read_bytes(),
                )
            self.assertEqual(
                sum(item["rows"] for item in release["data_files"].values()),
                33959,
            )
            manifest = json.loads((root / "boundary-sets.json").read_bytes())
            expected_commercial_use = {
                license_["viewer_config"]: license_["commercial_use"]
                for license_ in manifest["licenses"].values()
            }
            for group, metadata in release["data_files"].items():
                with gzip.open(Path(first) / metadata["file"], "rt", encoding="utf-8") as source:
                    rows = [json.loads(line) for line in source]
                self.assertEqual(len(rows), metadata["rows"])
                self.assertEqual(
                    {row["commercial_use"] for row in rows},
                    {expected_commercial_use[group]},
                )
                regional = [row for row in rows if row["source_geometry_sha256"] is not None]
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


if __name__ == "__main__":
    unittest.main()
