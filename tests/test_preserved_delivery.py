import copy,json,sys,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from download_release_data import download

class PreservedDelivery(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,25,18,tzinfo=timezone.utc)
  self.registry=[{'id':str(i),'name':str(i),'status':'source_empty','snapshot':None} for i in range(1,82)]
  self.registry[6].update(status='ready',snapshot='/data/provinces/7.json',last_error_at=self.now.isoformat())
  self.record={'schema_version':1,'province_id':'7','province':'7','last_success_at':(self.now-timedelta(hours=8)).isoformat(),'groups':[{'standings':[{'team':'A'}],'matches':[]}]}
 def verify(self,allow):
  with TemporaryDirectory() as tmp:
   root=Path(tmp)/'data';root.mkdir();(root/'provinces.json').write_text(json.dumps(self.registry))
   def fetch(path):return copy.deepcopy(self.registry if path.endswith('provinces.json') else self.record)
   count=download(root,fetch,self.now,allow_preserved=allow)
   self.assertEqual(count,1)
   self.assertEqual(json.loads((root/'provinces/7.json').read_text()),self.record)
 def test_source_outage_retains_exact_clock_without_blocking_other_provinces_delivery(self):
  self.verify(True)
 def test_release_defaults_and_unmarked_staleness_remain_strict(self):
  with self.assertRaises(ValueError):self.verify(False)
  self.registry[6].pop('last_error_at')
  with self.assertRaises(ValueError):self.verify(True)
 def test_future_or_older_than_retention_records_are_rejected(self):
  for timestamp in [self.now+timedelta(hours=1),self.now-timedelta(days=31)]:
   self.record['last_success_at']=timestamp.isoformat()
   with self.assertRaises(ValueError):self.verify(True)

if __name__=='__main__':unittest.main()
