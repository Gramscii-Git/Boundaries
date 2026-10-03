"""Build the Italian civic-address dataset from ANNCSU's regional bulk files.

ANNCSU (Agenzia delle Entrate and ISTAT, CC BY 4.0) publishes one zipped CSV of
civic numbers per region. Each becomes one Parquet file holding every row as
published: codes stay text, coordinates and altitude become numbers, and the
manifest records each source's digest, rows and georeferenced share. The build
refuses a set whose civic identifiers repeat, whose coordinates fall outside
Italy, or whose total differs from the civic numbers the national street file
counts.

`update` does the whole cycle for a scheduler: it downloads the files, stops when
their snapshot is the one already published, and otherwise builds, uploads to
the Hugging Face dataset with the card filled from the manifest, and reads every
uploaded file back at the new revision.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from string import Template

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

SOURCE = "https://anncsu.open.agenziaentrate.gov.it/age-inspire/opendata/anncsu/getds.php?{name}"
REGIONS = {
    "ABRU": "Abruzzo", "BASI": "Basilicata", "CALA": "Calabria", "CAMP": "Campania",
    "EMIL": "Emilia-Romagna", "FRIU": "Friuli-Venezia Giulia", "LAZI": "Lazio", "LIGU": "Liguria",
    "LOMB": "Lombardia", "MARC": "Marche", "MOLI": "Molise", "PIEM": "Piemonte", "PUGL": "Puglia",
    "SARD": "Sardegna", "SICI": "Sicilia", "TOSC": "Toscana", "TREN": "Trentino-Alto Adige/Südtirol",
    "UMBR": "Umbria", "VALL": "Valle d'Aosta/Vallée d'Aoste", "VENE": "Veneto",
}
COLUMNS = [
    "CODICE_COMUNE", "CODICE_ISTAT", "PROGRESSIVO_NAZIONALE", "CODICE_COMUNALE", "ODONIMO", "LOCALITA'",
    "DIZIONE_LINGUA1", "DIZIONE_LINGUA2", "PROGRESSIVO_ACCESSO", "CODICE_COMUNALE_ACCESSO", "CIVICO",
    "ESPONENTE", "SPECIFICITA", "METRICO", "PROGRESSIVO_SNC", "COORD_X_COMUNE", "COORD_Y_COMUNE", "QUOTA", "METODO",
]
# Decimal comma in the source; the column names keep ANNCSU's own.
DECIMALS = {"COORD_X_COMUNE": "LONGITUDE", "COORD_Y_COMUNE": "LATITUDE", "QUOTA": "QUOTA"}
INTEGERS = ("PROGRESSIVO_NAZIONALE", "PROGRESSIVO_ACCESSO", "METODO")
# Italy's extent with a margin, in ETRF2000 degrees.
LONGITUDE, LATITUDE = (6.0, 19.0), (35.0, 47.5)
SNAPSHOT = re.compile(r"^INDIR_[A-Z]{4}_(\d{4})(\d{2})(\d{2})\.csv$")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def member(archive: zipfile.ZipFile, pattern: re.Pattern) -> zipfile.ZipInfo:
    members = archive.infolist()
    if len(members) != 1 or not pattern.match(members[0].filename):
        raise ValueError(f"expected one CSV matching {pattern.pattern}, found {[item.filename for item in members]}")
    return members[0]


def table(path: Path) -> tuple[pa.Table, str]:
    """One region's rows with numbers parsed, and the snapshot date its CSV names."""
    with zipfile.ZipFile(path) as archive:
        held = member(archive, SNAPSHOT)
        year, month, day = SNAPSHOT.match(held.filename).groups()
        with archive.open(held) as stream:
            raw = pacsv.read_csv(stream, parse_options=pacsv.ParseOptions(delimiter=";", quote_char=False),
                                 convert_options=pacsv.ConvertOptions(column_types={name: pa.string() for name in COLUMNS},
                                                                      strings_can_be_null=True))
    if raw.column_names != COLUMNS:
        raise ValueError(f"{path.name}: unexpected header {raw.column_names}")
    columns = {}
    for name in COLUMNS:
        values = raw[name]
        if name in DECIMALS:
            values = pc.cast(pc.replace_substring(values, ",", "."), pa.float64())
            name = DECIMALS[name]
        elif name in INTEGERS:
            values = pc.cast(values, pa.int64())
        columns[name] = values
    return pa.table(columns), f"{year}-{month}-{day}"


def street_total(path: Path) -> int:
    """The civic numbers the national street file counts."""
    with zipfile.ZipFile(path) as archive:
        held = member(archive, re.compile(r"^STRAD_ITA_\d{8}\.csv$"))
        with archive.open(held) as stream:
            rows = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8"), delimiter=";")
            return sum(int(row["TOTALE_ACCESSI"] or 0) for row in rows)


def fetch(url: str, target: Path, attempts: int = 3) -> None:
    """One file over HTTP/1.1 GET: the publisher's edge refuses HEAD and HTTP/2."""
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Gramscii-OpenData/1.0"}),
                                        timeout=600) as response, target.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            return
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(60 * attempt)


def download(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in [*(f"INDIR_{code}" for code in REGIONS), "STRAD_ITA"]:
        fetch(SOURCE.format(name=name), directory / f"{name}.zip")


def checked(rows: pa.Table, name: str) -> dict:
    located = pc.and_(pc.is_valid(rows["LONGITUDE"]), pc.is_valid(rows["LATITUDE"]))
    longitude, latitude = pc.filter(rows["LONGITUDE"], located), pc.filter(rows["LATITUDE"], located)
    outside = pc.sum(pc.or_(pc.or_(pc.less(longitude, LONGITUDE[0]), pc.greater(longitude, LONGITUDE[1])),
                            pc.or_(pc.less(latitude, LATITUDE[0]), pc.greater(latitude, LATITUDE[1])))).as_py() or 0
    if outside:
        raise ValueError(f"{name}: {outside} civic numbers lie outside Italy's extent")
    return {"rows": rows.num_rows, "located": pc.sum(located).as_py() or 0,
            "altitude_positive": pc.sum(pc.greater(rows["QUOTA"], 0)).as_py() or 0}


def build(downloads: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    regions, snapshots, identifiers = {}, set(), []
    for code, name in REGIONS.items():
        source = downloads / f"INDIR_{code}.zip"
        rows, snapshot = table(source)
        snapshots.add(snapshot)
        identifiers.append(rows["PROGRESSIVO_ACCESSO"])
        target = output / "data" / f"{code}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(rows, target, compression="zstd")
        regions[code] = {"region": name, "file": f"data/{code}.parquet", "sha256": digest(target),
                         "source": SOURCE.format(name=f"INDIR_{code}"), "source_sha256": digest(source),
                         **checked(rows, name)}
    if len(snapshots) != 1:
        raise ValueError(f"regional files come from different snapshots: {sorted(snapshots)}")
    every = pa.chunked_array([chunk for column in identifiers for chunk in column.chunks])
    if pc.count_distinct(every).as_py() != len(every):
        raise ValueError("civic identifiers (PROGRESSIVO_ACCESSO) repeat across the set")
    total, counted = sum(region["rows"] for region in regions.values()), street_total(downloads / "STRAD_ITA.zip")
    if total != counted:
        raise ValueError(f"the regional files hold {total} civic numbers, the street file counts {counted}")
    manifest = {"schema_version": 1, "snapshot": snapshots.pop(), "licence": "CC-BY-4.0",
                "publisher": "Agenzia delle Entrate and ISTAT (ANNCSU)", "rows": total,
                "located": sum(region["located"] for region in regions.values()),
                "altitude_positive": sum(region["altitude_positive"] for region in regions.values()),
                "street_file": {"source": SOURCE.format(name="STRAD_ITA"), "sha256": digest(downloads / "STRAD_ITA.zip"),
                                "civic_numbers": counted},
                "regions": regions}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def card(template: str, manifest: dict) -> str:
    """The dataset card with this snapshot's numbers."""
    shares = {region["region"]: region["located"] / region["rows"] for region in manifest["regions"].values()}
    lowest, highest = min(shares, key=shares.get), max(shares, key=shares.get)
    return Template(template).substitute(
        snapshot=manifest["snapshot"], rows=f"{manifest['rows']:,}", located=f"{manifest['located']:,}",
        located_share=f"{100 * manifest['located'] / manifest['rows']:.1f}", altitude_positive=f"{manifest['altitude_positive']:,}",
        lowest=lowest, lowest_share=f"{100 * shares[lowest]:.1f}", highest=highest, highest_share=f"{100 * shares[highest]:.1f}")


def published(repository: str) -> str | None:
    """The snapshot the dataset's main revision holds, or None when it holds none."""
    url = f"https://huggingface.co/datasets/{repository}/resolve/main/manifest.json"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.load(response)["snapshot"]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def publish(output: Path, repository: str, hf: str, message: str) -> str:
    """Upload the build and read every file back at the revision the upload made; that revision."""
    answer = subprocess.run([hf, "upload", repository, str(output), ".", "--repo-type", "dataset", "--commit-message", message],
                            check=True, capture_output=True, text=True).stdout
    found = re.search(r"/commit/([0-9a-f]{40})", answer)
    if found is None:
        raise RuntimeError(f"the upload named no commit: {answer[-400:]}")
    revision = found.group(1)
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        relative = path.relative_to(output).as_posix()
        url = f"https://huggingface.co/datasets/{repository}/resolve/{revision}/{relative}"
        with urllib.request.urlopen(url, timeout=600) as response:
            remote = hashlib.file_digest(response, "sha256").hexdigest()
        if remote != digest(path):
            raise RuntimeError(f"{relative} read back at {revision} differs from the upload")
    return revision


def update(work: Path, repository: str, hf: str, template: Path) -> dict:
    """Download, and when the snapshot is new, build, publish and verify it."""
    downloads, output = work / "downloads", work / "build"
    download(downloads)
    with zipfile.ZipFile(downloads / f"INDIR_{next(iter(REGIONS))}.zip") as archive:
        year, month, day = SNAPSHOT.match(member(archive, SNAPSHOT).filename).groups()
    snapshot = f"{year}-{month}-{day}"
    if published(repository) == snapshot:
        return {"snapshot": snapshot, "outcome": "already-published"}
    shutil.rmtree(output, ignore_errors=True)
    manifest = build(downloads, output)
    (output / "README.md").write_text(card(template.read_text(), manifest))
    revision = publish(output, repository, hf, f"ANNCSU snapshot {snapshot}: {manifest['rows']:,} civic numbers")
    return {"snapshot": snapshot, "outcome": "published", "revision": revision, "rows": manifest["rows"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    built = commands.add_parser("build", help="build the dataset from downloaded files")
    built.add_argument("--downloads", type=Path, required=True, help="directory holding INDIR_<REGION>.zip and STRAD_ITA.zip")
    built.add_argument("--output", type=Path, required=True)
    updated = commands.add_parser("update", help="download, and publish a new snapshot")
    updated.add_argument("--work", type=Path, required=True)
    updated.add_argument("--repository", default="Gramscii-IT/italian-civic-addresses")
    updated.add_argument("--hf", default="hf", help="the Hugging Face CLI")
    updated.add_argument("--card", type=Path, default=Path(__file__).resolve().parents[1] / "CIVIC_ADDRESSES_README.md")
    arguments = parser.parse_args()
    if arguments.command == "build":
        manifest = build(arguments.downloads, arguments.output)
        print(json.dumps({key: manifest[key] for key in ("snapshot", "rows", "located")}))
    else:
        print(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          **update(arguments.work, arguments.repository, arguments.hf, arguments.card)}))


if __name__ == "__main__":
    main()
