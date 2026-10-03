"""Build the Italian civic-address dataset from ANNCSU's regional bulk files.

ANNCSU (Agenzia delle Entrate and ISTAT, CC BY 4.0) publishes one zipped CSV of
civic numbers per region. Each becomes one Parquet file holding every row as
published: codes stay text, coordinates and altitude become numbers, and the
manifest records each source's digest, rows and georeferenced share. The build
refuses a set whose civic identifiers repeat, whose coordinates fall outside
Italy, or whose total differs from the civic numbers the national street file
counts.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

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


def checked(rows: pa.Table, name: str) -> dict:
    located = pc.and_(pc.is_valid(rows["LONGITUDE"]), pc.is_valid(rows["LATITUDE"]))
    longitude, latitude = pc.filter(rows["LONGITUDE"], located), pc.filter(rows["LATITUDE"], located)
    outside = pc.sum(pc.or_(pc.or_(pc.less(longitude, LONGITUDE[0]), pc.greater(longitude, LONGITUDE[1])),
                            pc.or_(pc.less(latitude, LATITUDE[0]), pc.greater(latitude, LATITUDE[1])))).as_py() or 0
    if outside:
        raise ValueError(f"{name}: {outside} civic numbers lie outside Italy's extent")
    return {"rows": rows.num_rows, "located": pc.sum(located).as_py() or 0}


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
                "street_file": {"source": SOURCE.format(name="STRAD_ITA"), "sha256": digest(downloads / "STRAD_ITA.zip"),
                                "civic_numbers": counted},
                "regions": regions}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--downloads", type=Path, required=True, help="directory holding INDIR_<REGION>.zip and STRAD_ITA.zip")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = build(arguments.downloads, arguments.output)
    print(json.dumps({key: manifest[key] for key in ("snapshot", "rows", "located")}))


if __name__ == "__main__":
    main()
