"""Build ISTAT's 2021 census sections as one GeoParquet file per region.

ISTAT's "Basi territoriali 2021" (CC BY 4.0) publish one zip per region with a
shapefile in WGS84 UTM zone 32N and the same sections as a table. Each region
becomes one GeoParquet file in longitude and latitude (OGC:CRS84, WKB): codes
become text at their fixed widths, the optional codes that ISTAT writes as 0
become null, and the census counts stay numbers. The build refuses a region whose
shapefile and table disagree on the sections, a set whose SEZ21_ID repeat, and
any coordinate outside Italy.

Run from the repository root with `uv run --group build --group civic python -m
scripts.census_sections`.
"""

import argparse
import csv
import io
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import shapefile
import shapely
from pyproj import Transformer

from scripts.civic_addresses import LATITUDE, LONGITUDE, digest, fetch, publish

SOURCE = "https://www.istat.it/storage/cartografia/basi_territoriali/2021/R{code}_21.zip"
REGIONS = {
    "01": "Piemonte", "02": "Valle d'Aosta/Vallée d'Aoste", "03": "Lombardia", "04": "Trentino-Alto Adige/Südtirol",
    "05": "Veneto", "06": "Friuli-Venezia Giulia", "07": "Liguria", "08": "Emilia-Romagna", "09": "Toscana",
    "10": "Umbria", "11": "Marche", "12": "Lazio", "13": "Abruzzo", "14": "Molise", "15": "Campania", "16": "Puglia",
    "17": "Basilicata", "18": "Calabria", "19": "Sicilia", "20": "Sardegna",
}
# Codes and their fixed widths; the optional ones are null where ISTAT writes 0.
CODES = {"COD_REG": 2, "COD_UTS": 3, "PRO_COM": 6, "SEZ21": 7, "SEZ21_ID": 13, "LOC21_ID": 11}
OPTIONAL = {"COD_ZIC": 5, "COD_ISAM": 5, "COD_ACQUE": 5, "COD_ISOLE": 5, "COD_MONT_D": 5, "COD_AREA_S": 5,
            "COM_ASC1": 9, "COM_ASC2": 9, "COM_ASC3": 9}
INTEGERS = ("COD_TIPO_S", "TIPO_LOC", "POP21", "FAM21", "ABI21", "EDI21")
DECIMALS = ("SHAPE_Leng", "SHAPE_Area")
COUNTS = ("POP21", "FAM21", "ABI21", "EDI21")
TYPES = {3: "Polygon", 6: "MultiPolygon"}
# About a centimetre.
DIGITS = 7
TO_DEGREES = Transformer.from_crs("EPSG:32632", "OGC:CRS84", always_xy=True)


def shapes(archive: zipfile.ZipFile, code: str) -> shapefile.Reader:
    stem = f"SHP/R{code}_21_WGS84"
    return shapefile.Reader(**{part: io.BytesIO(archive.read(f"{stem}.{part}")) for part in ("shp", "shx", "dbf")})


def listed(archive: zipfile.ZipFile, code: str) -> list[int]:
    """The SEZ21_ID the region's table lists."""
    text = archive.read(f"TAB/SEZ_R{code}_21.csv").decode("utf-16")
    return [int(row["SEZ21_ID"]) for row in csv.DictReader(io.StringIO(text), delimiter="\t")]


def degrees(points: np.ndarray) -> np.ndarray:
    longitude, latitude = TO_DEGREES.transform(points[:, 0], points[:, 1])
    return np.round(np.column_stack([longitude, latitude]), DIGITS)


def table(path: Path, code: str) -> pa.Table:
    """One region's sections, with codes as text and geometry in degrees."""
    with zipfile.ZipFile(path) as archive:
        reader, ids = shapes(archive, code), listed(archive, code)
        names = [field[0] for field in reader.fields[1:]]
        records = [dict(zip(names, record)) for record in reader.iterRecords()]
        geometries = shapely.transform([shapely.geometry.shape(shape.__geo_interface__) for shape in reader.iterShapes()],
                                     degrees)
    held = [record["SEZ21_ID"] for record in records]
    if sorted(held) != sorted(ids):
        raise ValueError(f"{path.name}: the shapefile holds {len(held)} sections, the table lists {len(ids)}, "
                         f"{len(set(held) ^ set(ids))} differ")
    columns = {name: pa.array([str(record[name]).zfill(width) for record in records]) for name, width in CODES.items()}
    columns.update({name: pa.array([str(record[name]).zfill(width) if record[name] else None for record in records],
                                   pa.string()) for name, width in OPTIONAL.items()})
    columns.update({name: pa.array([record[name] for record in records], pa.int64()) for name in INTEGERS})
    columns.update({name: pa.array([record[name] for record in records], pa.float64()) for name in DECIMALS})
    columns["geometry"] = pa.array(shapely.to_wkb(geometries), pa.binary())
    return pa.table(columns)


def checked(rows: pa.Table, name: str) -> dict:
    geometries = shapely.from_wkb(rows["geometry"].to_numpy(zero_copy_only=False))
    west, south, east, north = shapely.total_bounds(geometries)
    if west < LONGITUDE[0] or east > LONGITUDE[1] or south < LATITUDE[0] or north > LATITUDE[1]:
        raise ValueError(f"{name}: sections reach outside Italy's extent ({west}, {south}, {east}, {north})")
    types = sorted(set(shapely.get_type_id(geometries).tolist()))
    return {"sections": rows.num_rows, "bbox": [west, south, east, north],
            "geometry_types": [TYPES[kind] for kind in types],
            **{name.lower(): sum(rows[name].to_pylist()) for name in COUNTS}}


def geoparquet(rows: pa.Table, summary: dict, target: Path) -> None:
    geo = {"version": "1.1.0", "primary_column": "geometry",
           "columns": {"geometry": {"encoding": "WKB", "geometry_types": summary["geometry_types"],
                                    "bbox": summary["bbox"]}}}
    rows = rows.replace_schema_metadata({b"geo": json.dumps(geo).encode()})
    pq.write_table(rows, target, compression="zstd")


def download(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for code in REGIONS:
        target = directory / f"R{code}_21.zip"
        if not target.exists():
            fetch(SOURCE.format(code=code), target)


def build(downloads: Path, output: Path) -> dict:
    data = output / "census-sections-2021"
    data.mkdir(parents=True, exist_ok=True)
    regions, identifiers = {}, []
    for code, name in REGIONS.items():
        source = downloads / f"R{code}_21.zip"
        rows = table(source, code)
        identifiers.extend(rows["SEZ21_ID"].to_pylist())
        summary = checked(rows, name)
        target = data / f"R{code}.parquet"
        geoparquet(rows, summary, target)
        regions[code] = {"region": name, "file": target.relative_to(output).as_posix(), "sha256": digest(target),
                         "source": SOURCE.format(code=code), "source_sha256": digest(source), **summary}
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("SEZ21_ID repeat across the set")
    manifest = {"schema_version": 1, "vintage": "2021", "licence": "CC-BY-4.0",
                "publisher": "ISTAT, Basi territoriali 2021", "crs": "OGC:CRS84", "sections": len(identifiers),
                **{name.lower(): sum(region[name.lower()] for region in regions.values()) for name in COUNTS},
                "regions": regions}
    (data / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--downloads", type=Path, required=True, help="directory for R<NN>_21.zip")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish", metavar="REPOSITORY", help="upload the build to this Hugging Face dataset")
    parser.add_argument("--hf", default="hf", help="the Hugging Face CLI")
    arguments = parser.parse_args()
    download(arguments.downloads)
    manifest = build(arguments.downloads, arguments.output)
    outcome = {key: manifest[key] for key in ("sections", "pop21", "fam21", "abi21", "edi21")}
    if arguments.publish:
        shutil.copy2(Path(__file__).resolve().parents[1] / "HUGGING_FACE_README.md", arguments.output / "README.md")
        outcome["revision"] = publish(arguments.output, arguments.publish, arguments.hf,
                                      f"ISTAT 2021 census sections: {manifest['sections']:,} sections")
    print(json.dumps(outcome))


if __name__ == "__main__":
    main()
