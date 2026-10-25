import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from source_reader import parse_results,SourceError

class Scores(unittest.TestCase):
 def rows(self,a='3',b='0',sets='(25-18)(25-8)(25-9)'):
  return [['No','Tarih','Saat','Salon Adı','Ev Sahibi (A)','A','B','Misafir (B)','Set Sonuçları'],['1','25.10.2026','10:00','Salon','Kulüp A',a,b,'Kulüp B',sets]]
 def test_published_three_nil_result_keeps_all_three_sets(self):
  result=parse_results(self.rows())[0]
  self.assertEqual(result['score'],[3,0]);self.assertEqual(result['sets'],[[25,18],[25,8],[25,9]])
 def test_impossible_scores_are_rejected(self):
  for a,b in [('9','2'),('4','0'),('3','3')]:
   with self.assertRaises(SourceError):parse_results(self.rows(a,b))
 def test_set_winners_must_match_match_score(self):
  with self.assertRaises(SourceError):parse_results(self.rows(sets='(18-25)(25-8)(25-9)'))
 def test_unplayed_match_has_no_fabricated_score(self):
  result=parse_results(self.rows('','',''))[0]
  self.assertIsNone(result['score']);self.assertEqual(result['sets'],[])

if __name__=='__main__':unittest.main()
