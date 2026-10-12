"""Official geometry joins preserve registry scope, identities, parents and overseas coverage."""

import copy
import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pyogrio
from pydantic import ValidationError
from shapely.geometry import Polygon, box

from scripts.administrative import build
from scripts.administrative_spec import Specification


class AdministrativeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.inputs = Path(self.directory.name)
        root = Path(__file__).parents[1]
        self.raw = json.loads((root / 'france.build.json').read_bytes())
        main = box(4.0, 45.0, 5.0, 46.0)
        overseas = box(-62.0, 15.0, -61.0, 16.0)
        self.geometry_rows = {
            'region': [{'code_insee': '84', 'nom_officiel': 'Main', 'geometry': main.wkb},
                       {'code_insee': '01', 'nom_officiel': 'Overseas', 'geometry': overseas.wkb}],
            'department': [{'code_insee': '01', 'nom_officiel': 'Main department', 'code_insee_de_la_region': '84', 'geometry': main.wkb},
                           {'code_insee': '971', 'nom_officiel': 'Overseas department', 'code_insee_de_la_region': '01', 'geometry': overseas.wkb}],
            'municipality': [{'code_insee': '01001', 'nom_officiel': 'Main municipality', 'code_insee_de_la_region': '84', 'code_insee_du_departement': '01', 'geometry': main.wkb},
                             {'code_insee': '97101', 'nom_officiel': 'Overseas municipality', 'code_insee_de_la_region': '01', 'code_insee_du_departement': '971', 'geometry': overseas.wkb},
                             {'code_insee': '97501', 'nom_officiel': 'Separate registry', 'code_insee_de_la_region': 'NR', 'code_insee_du_departement': 'NR', 'geometry': overseas.wkb}]}
        registries = {
            'region': [{'REG':'84','LIBELLE':'Official main'}, {'REG':'01','LIBELLE':'Official overseas'}],
            'department': [{'DEP':'01','REG':'84','LIBELLE':'Main department'}, {'DEP':'971','REG':'01','LIBELLE':'Overseas department'}],
            'municipality': [{'TYPECOM':'COM','COM':'01001','REG':'84','DEP':'01','LIBELLE':'Main municipality'},
                             {'TYPECOM':'COM','COM':'97101','REG':'01','DEP':'971','LIBELLE':'Overseas municipality'},
                             {'TYPECOM':'COMD','COM':'01002','REG':'84','DEP':'01','LIBELLE':'Delegated unit'}]}
        self.raw['render']['frames'] = self.raw['render']['frames'][:2]
        self.raw['render']['frames'][0]['region_codes'] = ['84']
        with zipfile.ZipFile(self.inputs / self.raw['identities']['file'], 'w') as archive:
            for layer in self.raw['layers']:
                rows = registries[layer['id']]
                layer['registry_rows'] = len(rows)
                layer['expected_units'] = 2
                layer['expected_source_units'] = len(self.geometry_rows[layer['id']])
                layer['excluded_source_codes'] = {'97501':'Separate registry'} if layer['id']=='municipality' else {}
                stream = io.StringIO()
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
                archive.writestr(layer['registry_member'], stream.getvalue())
        self.raw['identities']['sha256'] = self.digest(self.raw['identities']['file'])
        self.write_geometry()

    def digest(self, filename):
        return hashlib.sha256((self.inputs/filename).read_bytes()).hexdigest()

    def write_geometry(self, crs='EPSG:4326'):
        path = self.inputs / self.raw['geometry']['file']
        if path.exists():
            path.unlink()
        for layer in self.raw['layers']:
            pyogrio.write_arrow(pa.Table.from_pylist(self.geometry_rows[layer['id']]), path,
                                layer=layer['geometry_layer'], driver='GPKG', geometry_name='geometry',
                                geometry_type='Polygon', crs=crs)
        self.raw['geometry']['sha256'] = self.digest(path.name)
        self.raw['archive']['file'] = 'geometry.zip'
        self.raw['archive_geometry_member'] = path.name
        with zipfile.ZipFile(self.inputs/'geometry.zip','w') as archive:
            archive.write(path,path.name)
        self.raw['archive']['sha256'] = self.digest('geometry.zip')

    def run_build(self, directory='output'):
        return build(Specification.model_validate(self.raw),self.inputs,self.inputs/directory,'commercial')

    def test_exact_inventory_draws_overseas_with_official_names_and_no_clipping(self):
        first = self.run_build('first')
        second = self.run_build('second')
        self.assertEqual(first,second)
        for layer in self.raw['layers']:
            body = json.loads((self.inputs/'first'/layer['svg_file']).read_bytes())
            self.assertEqual(len(body['shapes']),2)
            self.assertEqual(body['outside'],[])
            self.assertEqual(body['partially_clipped'],[])
            self.assertEqual({row['frame'] for row in body['shapes']},{'metropolitan','guadeloupe'})
            self.assertTrue(all(row['source_geometry_valid'] for row in body['shapes']))
            table = pq.read_table(self.inputs/'first'/layer['parquet_file'])
            metadata = json.loads(table.schema.metadata[b'geo'])
            self.assertEqual(table.num_rows,2)
            self.assertEqual(metadata['columns']['geometry']['crs']['id']['code'],'CRS84')
        regions = json.loads((self.inputs/'first'/self.raw['layers'][0]['svg_file']).read_bytes())
        self.assertEqual({r['name'] for r in regions['shapes']},{'Official main','Official overseas'})
        self.assertEqual(first['levels'][2]['excluded_source_codes'],{'97501':'Separate registry'})

    def test_changed_input_bytes_fail_before_writing(self):
        path = self.inputs/self.raw['geometry']['file']
        path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'checksum differs'):
            self.run_build()
        self.assertFalse((self.inputs/'output').exists())

    def test_duplicate_geometry_identity_is_an_error(self):
        self.geometry_rows['municipality'][1]['code_insee']='01001'
        self.write_geometry()
        with self.assertRaisesRegex(ValueError,'identity is invalid or repeated'):
            self.run_build()

    def test_missing_or_extra_geometry_is_not_an_implicit_exclusion(self):
        self.geometry_rows['municipality'][1]['code_insee']='97102'
        self.write_geometry()
        with self.assertRaisesRegex(ValueError,'no registry identity'):
            self.run_build()

    def test_wrong_parent_identity_is_an_error(self):
        self.geometry_rows['municipality'][0]['code_insee_du_departement']='971'
        self.write_geometry()
        with self.assertRaisesRegex(ValueError,'parent identity differs'):
            self.run_build()

    def test_wrong_projection_is_an_error(self):
        self.write_geometry(crs='EPSG:2154')
        with self.assertRaisesRegex(ValueError,'coordinate system differ'):
            self.run_build()

    def test_invalid_source_polygon_is_not_repaired(self):
        self.geometry_rows['municipality'][0]['geometry']=Polygon([(4,45),(5,46),(5,45),(4,46),(4,45)]).wkb
        self.write_geometry()
        with self.assertRaisesRegex(ValueError,'coordinates are invalid'):
            self.run_build()

    def test_noncommercial_rights_are_not_overridden_by_export(self):
        self.raw['license']['commercial_use']=False
        with self.assertRaisesRegex(ValueError,'does not permit commercial use'):
            self.run_build()

    def test_stale_outputs_are_refused(self):
        self.run_build()
        with self.assertRaisesRegex(ValueError,'not empty'):
            self.run_build()

    def test_missing_and_duplicate_frame_assignments_are_errors(self):
        missing=copy.deepcopy(self.raw)
        missing['render']['frames'][0]['region_codes']=['11']
        with self.assertRaisesRegex(ValueError,'no declared map frame'):
            build(Specification.model_validate(missing),self.inputs,self.inputs/'missing','commercial')
        self.raw['render']['frames'][0]['region_codes'].append('01')
        with self.assertRaises(ValidationError):
            Specification.model_validate(self.raw)

    def test_incomplete_configuration_has_no_default(self):
        for field in Specification.model_fields:
            incomplete={name:value for name,value in self.raw.items() if name!=field}
            with self.subTest(field=field),self.assertRaises(ValidationError):
                Specification.model_validate(incomplete)


if __name__=='__main__':
    unittest.main()
