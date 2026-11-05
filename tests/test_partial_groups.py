import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from partial_groups import merge_verified_groups
from source_reader import SourceError

def group(ident,clock,points=0):
 return {'id':ident,'competition':{'label':'Genç Kız '+ident,'value':ident+'*official'},'checked_at':clock,'category':'Genç','gender':'Kız','title':'Grup '+ident,'standings':[{'team':'Kulüp','points':points}],'matches':[]}

class PartialGroups(unittest.TestCase):
 def setUp(self):
  self.old='2026-11-01T10:00:00+00:00';self.now='2026-11-05T09:00:00+00:00'
  self.previous={'last_success_at':self.old,'groups':[group('1',self.old),group('2',self.old)]}
 def test_failed_group_does_not_freeze_a_verified_group(self):
  current={'last_success_at':self.now,'groups':[group('1',self.now,6)],'unverified_competitions':[{'value':'2*official','label':'Genç Kız 2','reason':'Set count mismatch'}]}
  result=merge_verified_groups(self.previous,current)
  self.assertTrue(result['partial_update']);self.assertEqual(result['last_success_at'],self.old)
  fresh=next(g for g in result['groups']if g['id']=='1');kept=next(g for g in result['groups']if g['id']=='2')
  self.assertEqual(fresh['standings'][0]['points'],6);self.assertEqual(fresh['checked_at'],self.now)
  self.assertEqual(kept['checked_at'],self.old);self.assertEqual(kept['standings'],self.previous['groups'][1]['standings'])
  self.assertEqual(result['preserved_group_ids'],['2']);self.assertEqual(result['fresh_group_ids'],['1'])
  self.assertEqual(result['unverified_competitions'],[])
  self.assertNotIn('source_state',self.previous['groups'][1])
 def test_absent_source_group_is_retained_not_deleted(self):
  result=merge_verified_groups(self.previous,{'last_success_at':self.now,'groups':[group('1',self.now)]})
  self.assertEqual(result['group_errors'][0]['kind'],'source_missing')
  self.assertEqual(len(result['groups']),2)
 def test_new_invalid_group_is_visible_as_unverified_not_fabricated(self):
  current={'last_success_at':self.now,'groups':[group('1',self.now),group('2',self.now)],'unverified_competitions':[{'value':'3*official','label':'Genç Kız 3','reason':'Ambiguous standings'}]}
  result=merge_verified_groups(self.previous,current)
  self.assertEqual(result['preserved_group_ids'],[]);self.assertFalse(result['group_errors'][0]['retained'])
  self.assertEqual(len(result['groups']),2);self.assertEqual(len(result['unverified_competitions']),1)
 def test_all_successful_groups_recover_without_partial_markers(self):
  result=merge_verified_groups(self.previous,{'last_success_at':self.now,'groups':[group('1',self.now),group('2',self.now)]})
  self.assertNotIn('partial_update',result);self.assertEqual(result['last_success_at'],self.now)
 def test_reused_numeric_id_with_another_official_identity_is_rejected(self):
  bad=group('1',self.now);bad['competition']['value']='1*other'
  with self.assertRaises(SourceError):merge_verified_groups(self.previous,{'groups':[bad]})

if __name__=='__main__':unittest.main()
