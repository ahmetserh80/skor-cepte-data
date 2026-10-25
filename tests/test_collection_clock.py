import contextlib,copy,io,json,os,sys,unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collect_all as collector

class CollectionClockTests(unittest.TestCase):
 def setUp(self):
  self.started='2026-10-25T15:45:12+00:00'
  self.province={'id':'7','name':'Antalya','status':'ready','url':'https://example.invalid','last_checked_at':'2026-10-25T15:23:55+00:00'}
  self.prior={'province_id':'7','province':'Antalya','last_success_at':'2026-10-25T15:22:53+00:00','groups':[{'id':'g1'}]}
  self.fresh={**self.prior,'last_success_at':'2026-10-25T15:46:05+00:00','collection_finished_at':'2026-10-25T15:47:11+00:00'}

 def test_success_displays_real_start_and_keeps_source_and_finish_times(self):
  with TemporaryDirectory() as tmp,patch.object(collector,'ROOT',Path(tmp)),patch.object(collector,'remote',return_value=copy.deepcopy(self.prior)),patch.object(collector,'collect',return_value=copy.deepcopy(self.fresh)):
   province,error,_=collector.one(dict(self.province),self.started)
   saved=json.loads((Path(tmp)/'provinces/7.json').read_text())
   self.assertIsNone(error)
   self.assertEqual(saved['last_success_at'],self.started)
   self.assertEqual(saved['collection_started_at'],self.started)
   self.assertEqual(saved['source_checked_at'],self.fresh['last_success_at'])
   self.assertEqual(saved['collection_finished_at'],self.fresh['collection_finished_at'])
   self.assertEqual(saved['groups'],self.fresh['groups'])
   self.assertNotIn('last_error_at',province)

 def test_failed_source_preserves_remote_snapshot_without_advancing_its_clock(self):
  with TemporaryDirectory() as tmp,patch.object(collector,'ROOT',Path(tmp)),patch.object(collector,'remote',return_value=copy.deepcopy(self.prior)),patch.object(collector,'collect',side_effect=ValueError('Source unavailable')):
   target=Path(tmp)/'provinces/7.json';target.parent.mkdir()
   target.write_text(json.dumps({**self.prior,'last_success_at':'2026-10-25T10:00:00+00:00'}))
   province,error,_=collector.one(dict(self.province),self.started)
   self.assertEqual(json.loads(target.read_text()),self.prior)
   self.assertEqual(error,'Source unavailable')
   self.assertIn('last_error_at',province)
   self.assertEqual(province['last_checked_at'],self.province['last_checked_at'])

 def test_new_runner_can_preserve_remote_data_without_a_bundled_snapshot(self):
  with TemporaryDirectory() as tmp,patch.object(collector,'ROOT',Path(tmp)),patch.object(collector,'remote',return_value=copy.deepcopy(self.prior)),patch.object(collector,'collect',side_effect=ValueError('Source unavailable')):
   _,error,_=collector.one(dict(self.province),self.started)
   self.assertEqual(error,'Source unavailable')
   self.assertEqual(json.loads((Path(tmp)/'provinces/7.json').read_text()),self.prior)

 def test_missing_verified_prior_requests_server_preservation_without_fabricating_data(self):
  with TemporaryDirectory() as tmp,patch.object(collector,'ROOT',Path(tmp)),patch.object(collector,'remote',return_value=None),patch.object(collector,'collect') as collect:
   province,error,_=collector.one(dict(self.province),self.started)
   self.assertIn('server preservation required',error)
   self.assertIn('last_error_at',province)
   self.assertEqual(json.loads((Path(tmp)/'provinces/7.json').read_text()),{'province_id':'7','province':'Antalya'})
   collect.assert_not_called()

 def test_unreachable_registry_does_not_publish_bootstrap_data(self):
  with patch.object(collector,'remote',return_value=None):
   with self.assertRaisesRegex(ValueError,'Live registry is unavailable'):collector.main()

 def test_all_81_provinces_share_the_batch_start_even_with_concurrent_reads(self):
  registry=[{'id':str(i),'name':str(i),'status':'source_empty'} for i in range(1,82)]
  previous_cwd=Path.cwd()
  with TemporaryDirectory() as tmp:
   try:
    os.chdir(tmp);Path('data').mkdir()
    with patch.object(collector,'ROOT',Path('data')),patch.object(collector,'remote',return_value=registry),patch.object(collector,'one',side_effect=lambda p,start:(p,None,0)) as one,contextlib.redirect_stdout(io.StringIO()):
     collector.main()
    report=json.loads(Path('collection-report.json').read_text())
    self.assertEqual(one.call_count,81)
    self.assertEqual({call.args[1] for call in one.call_args_list},{report['started_at']})
    self.assertLessEqual(datetime.fromisoformat(report['started_at']),datetime.fromisoformat(report['finished_at']))
    self.assertEqual(report['checked'],81)
   finally:os.chdir(previous_cwd)

if __name__=='__main__':unittest.main()
