import contextlib,io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_all as collector

class LiveFeedTests(unittest.TestCase):
 def test_collection_uses_verified_public_json_client(self):
  registry=[{'id':'7','name':'Antalya'}]
  with patch.object(collector,'BASE',collector.ORIGIN),patch.object(collector,'fetch_live',return_value=registry) as fetch:
   self.assertEqual(collector.remote('data/provinces.json'),registry)
   fetch.assert_called_once_with('/data/provinces.json')

 def test_failed_public_read_reports_status_without_body_or_fallback(self):
  with patch.object(collector,'BASE',collector.ORIGIN),patch.object(collector,'fetch_live',side_effect=HTTPError('https://example.invalid',403,'denied',{},None)),contextlib.redirect_stdout(io.StringIO()) as out:
   self.assertIsNone(collector.remote('data/provinces.json'))
  self.assertEqual(json.loads(out.getvalue()),{'feed_path':'data/provinces.json','error':'HTTPError','status':403})

 def test_unexpected_service_is_not_contacted(self):
  with patch.object(collector,'BASE','https://example.invalid'),patch.object(collector,'fetch_live') as fetch,contextlib.redirect_stdout(io.StringIO()):
   self.assertIsNone(collector.remote('data/provinces.json'))
   fetch.assert_not_called()

if __name__=='__main__':unittest.main()
