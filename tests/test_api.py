import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
from scripts.build_dataset import fetch_snap, fetch_hrsa, record

class API(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'resources.json'
        self.rows=json.loads(app.PATH.read_text())
        self.path.write_text(json.dumps(self.rows))
        self.patch=patch.object(app,'PATH',self.path); self.patch.start()
    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()
    def test_filter(self):
        code,rows=app.dispatch('GET','/api/resources',{'category':'food','neighborhood':'Ensley'},None)
        self.assertEqual(code,200); self.assertTrue(rows)
        self.assertTrue(all(r['category']=='food' and r['neighborhood']=='Ensley' for r in rows))
    def test_today_closure_persists(self):
        code,r=app.dispatch('POST','/api/volunteer-update',{},dict(resource_id=self.rows[0]['id'],text='closed today, open tomorrow 9 to noon'))
        self.assertEqual(code,200); self.assertEqual(r['status'],'closed')
        self.assertEqual(app.load()[0]['status'],'closed')
        self.assertEqual(json.loads(self.path.read_text())[0]['hours_today'],'closed today, open tomorrow 9 to noon')
    def test_nearest_three_open_only(self):
        rows=[]
        for i in range(5):
            r=dict(self.rows[4],id=str(i),lat=33.4981+i*.01,status='open'); rows.append(r)
        rows.append(dict(rows[0],id='closed',status='closed'))
        with patch.object(app,'load',return_value=rows),patch.dict('os.environ',{},clear=True):
            result=app.ask('food tonight near Ensley')
        self.assertEqual([r['id'] for r in result['matches']],['0','1','2'])
    def test_no_open_does_not_invent(self):
        with patch.object(app,'load',return_value=[]): self.assertEqual(app.ask('food Ensley')['matches'],[])
    def test_invalid_json(self):
        status=[]
        output=app.application({'CONTENT_LENGTH':'1','wsgi.input':io.BytesIO(b'{'),'REQUEST_METHOD':'POST','PATH_INFO':'/api/ask'},lambda s,h:status.append(s))
        self.assertTrue(status[0].startswith('400'))
    def test_unknown_id(self):
        self.assertEqual(app.dispatch('POST','/api/volunteer-update',{},dict(resource_id='missing',text='open'))[0],404)
    def test_schema(self):
        fields='id name category subcategory neighborhood address zip lat lon phone hours_today status what_to_bring nearest_max_stop last_verified source'.split()
        for r in self.rows:
            self.assertTrue(set(fields)<=set(r)); self.assertTrue(30<r['lat']<35.1); self.assertTrue(-89<r['lon']<-84)
    def test_snap_pagination(self):
        feature={'properties':{'Store_Name':'Store','Address':'1 Main','Zip':'35203'},'geometry':{'coordinates':[-86.8,33.5]}}
        payloads=[{'features':[feature],'exceededTransferLimit':True},{'features':[feature]}]
        with patch('scripts.build_dataset.request',side_effect=[io.BytesIO(json.dumps(p).encode()) for p in payloads]):
            self.assertEqual(len(fetch_snap()),2)
    def test_hrsa_filter_and_mapping(self):
        csv='Site State Abbreviation,Site City,Site Name,Site Address,Site ZIP Code,X,Y\nAL,birmingham,Clinic,1 Main,35203,-86.8,33.5\nGA,Birmingham,Other,1 Main,35203,-86.8,33.5\n'
        with patch('scripts.build_dataset.request',return_value=io.BytesIO(csv.encode())):
            rows=fetch_hrsa()
        self.assertEqual(len(rows),1); self.assertEqual(rows[0]['name'],'Clinic')

if __name__=='__main__': unittest.main()
