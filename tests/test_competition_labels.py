import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from competition_labels import classify, is_youth
from import_province import convert_province

class CompetitionLabels(unittest.TestCase):
 def test_official_singular_plural_and_gender_variants(self):
  cases=[('Genç Kız Süper Lig A','Genç','Kız'),('Genç Kızlar Süper Ligi','Genç','Kız'),
         ('Samsun Genç Kadınlar İl Birinciliği A Grubu','Genç','Kız'),
         ('Genç Kadın','Genç','Kız'),('Yıldız Bayanlar','Yıldız','Kız'),
         ('Küçük Erkek İl Birinciliği','Küçük','Erkek'),('Küçük Erkekler','Küçük','Erkek'),
         ('GENÇ KIZLAR SÜPER LİG','Genç','Kız'),('Genc Kiz Il Birinciligi','Genç','Kız'),
         ('KÜÇÜK KADINLAR','Küçük','Kız'),('MİNİK ERKEKLER','Minik','Erkek'),
         ('YILDIZ KIZ','Yıldız','Kız')]
  for label,age,gender in cases:
   with self.subTest(label=label):
    value=classify(label);self.assertEqual((value['category'],value['gender']),(age,gender))

 def test_missing_gender_requires_verified_source_context(self):
  self.assertIsNone(classify('Midi A Grubu'))
  self.assertEqual(classify('Midi A Grubu','B')['gender'],'Kız')
  self.assertEqual(classify('Gençler İl Birinciliği','E')['gender'],'Erkek')
  with self.assertRaises(ValueError):classify('Genç Erkek','B')

 def test_display_does_not_repeat_province_and_keeps_the_group(self):
  result=classify('Samsun Genç Kadınlar İl Birinciliği A Grubu','B','Samsun')
  self.assertEqual(result['remaining'],'İl Birinciliği A Grubu')

 def test_scope_and_ambiguous_labels(self):
  for label in ['Okullar Arası Genç Kızlar İl Birinciliği','OKUL SPORLARI YILDIZ ERKEK','Liseler Arası Genç Bayan']:
   self.assertEqual(classify(label)['scope'],'school')
  self.assertEqual(classify('Samsun Genç Kadınlar İl Birinciliği')['scope'],'club')
  for label in ['Büyük Bayanlar','Genç Büyük Erkekler','Genç Yıldız Kız','Genç Kız Erkek','Deneme']:
   self.assertFalse(is_youth(label))

 def test_recognized_source_label_is_preserved_and_unplayed_fixture_stays_empty(self):
  table='<table id="icerik_GvTemplate_1"><tr>'+''.join('<th>'+x+'</th>'for x in ['Logo','Takım Adı','O','G','M','A','V','P'])+'</tr>'
  for name in ['Kulüp A','Kulüp B']:
   table+='<tr>'+''.join('<td>'+x+'</td>'for x in ['',name,'0','0','0','0','0','0'])+'</tr>'
  table+='</table>'
  for label in ['Genç Kız Süper Lig A','GENÇ KADINLAR İL BİRİNCİLİĞİ','Midi A Grubu']:
   raw={'province':'Samsun','province_id':'55','source':'https://samsun.voleyboliltemsilciligi.com/PuanDurumu','groups':[{'_sex':'B','competition':{'label':label,'value':'123*official-id'},'checked_at':'2026-11-05T08:00:00+00:00','tables':[{'html':table}]}]}
   g=convert_province(raw)['groups'][0]
   self.assertEqual(g['id'],'123');self.assertEqual(g['competition']['label'],label)
   self.assertEqual(g['competition_scope'],'club');self.assertEqual(len(g['standings']),2)
   self.assertEqual(g['matches'],[]);self.assertFalse(g['matches_published'])

if __name__=='__main__':unittest.main()
