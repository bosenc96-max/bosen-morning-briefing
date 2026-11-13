import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from site_quality import inspect

RSS='''<?xml version="1.0"?><rss version="2.0"><channel><item><title>Day</title><link>https://example.org/#day</link></item></channel></rss>'''
SITEMAP='''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.org/</loc></url></urlset>'''
class TestSiteQuality(unittest.TestCase):
    def seed(self,path,html):
        (path/'index.html').write_text(html,encoding='utf-8')
        (path/'feed.xml').write_text(RSS,encoding='utf-8')
        (path/'sitemap.xml').write_text(SITEMAP,encoding='utf-8')
        (path/'robots.txt').write_text('User-agent: *\nAllow: /',encoding='utf-8')
    def test_valid_structure(self):
        with TemporaryDirectory() as d:
            p=Path(d);self.seed(p,'<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Test</title></head><body><a href="#ok">go</a><section id="ok"></section></body></html>')
            errors,warnings,_=inspect(p)
            self.assertFalse(errors);self.assertFalse(any(x['code']=='missing_internal_fragments' for x in warnings))
    def test_duplicate_ids_fail(self):
        with TemporaryDirectory() as d:
            p=Path(d);self.seed(p,'<html><title>X</title><div id="x"></div><div id="x"></div></html>')
            errors,_,_=inspect(p)
            self.assertTrue(any(x['code']=='duplicate_ids' for x in errors))
    def test_unresolved_fragment_warns(self):
        with TemporaryDirectory() as d:
            p=Path(d);self.seed(p,'<html><title>X</title><a href="#absent">go</a></html>')
            _,warnings,_=inspect(p)
            self.assertTrue(any(x['code']=='missing_internal_fragments' for x in warnings))
if __name__=='__main__': unittest.main()
