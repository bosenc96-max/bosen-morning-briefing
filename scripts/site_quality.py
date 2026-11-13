#!/usr/bin/env python3
"""Read-only, offline structural checks for the Yu Meng GitHub Pages website.

No network access, no source changes and no external packages.
"""
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

class SiteParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=[]
        self.anchors=[]
        self.titles=[]
        self.in_title=False
        self.lang=False
        self.charset=False
        self.viewport=False
        self.masthead=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='html' and attrs.get('lang'): self.lang=True
        if tag=='meta':
            if attrs.get('charset'): self.charset=True
            if attrs.get('name','').lower()=='viewport': self.viewport=True
        if tag=='title': self.in_title=True
        if tag=='h1': self.masthead=True
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag=='a' and 'href' in attrs: self.anchors.append(attrs['href'])
    def handle_endtag(self,tag):
        if tag=='title': self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.titles.append(data)

def inspect(root):
    failures=[];warnings=[];stats={}
    def fail(code,msg): failures.append({'code':code,'message':msg})
    def warn(code,msg): warnings.append({'code':code,'message':msg})
    index=root/'index.html'
    if not index.is_file(): fail('missing_html','index.html missing');return failures,warnings,stats
    page=SiteParser()
    try: page.feed(index.read_text(encoding='utf-8-sig'))
    except (OSError,UnicodeError,ValueError) as e:fail('html_read_error',str(e));return failures,warnings,stats
    stats['html_size_bytes']=index.stat().st_size
    stats['id_count']=len(page.ids)
    stats['anchor_count']=len(page.anchors)
    if not ''.join(page.titles).strip():fail('missing_title','Missing HTML <title>')
    if not page.lang:warn('missing_lang','HTML lang attribute missing')
    if not page.charset:warn('missing_charset','HTML meta charset missing')
    if not page.viewport:warn('missing_viewport','Mobile viewport meta missing')
    ids=set(page.ids)
    duplicate=[(x,n) for x,n in Counter(page.ids).items() if n>1]
    if duplicate: fail('duplicate_ids',f'{len(duplicate)} repeated IDs; examples: '+', '.join(f'{x}({n})' for x,n in duplicate[:8]))
    missing=[]
    for href in page.anchors:
        # Only same-page fragment hrefs. A JS-generated anchor or cross-page links cannot be inferred.
        if href.startswith('#') and href!='#':
            frag=unquote(href[1:])
            if frag and frag not in ids: missing.append(frag)
    if missing:warn('missing_internal_fragments',f'{len(missing)} links point to fragment IDs absent in static HTML; examples: '+', '.join(sorted(set(missing))[:10]))
    stats['broken_static_fragment_links']=len(missing)
    for name in ('feed.xml','sitemap.xml','robots.txt'):
        if not (root/name).is_file():fail('missing_file',name+' missing')
    feed=root/'feed.xml'
    if feed.is_file():
        try:
            tree=ET.parse(feed);channel=tree.getroot().find('channel')
            if channel is None:fail('rss_structure','RSS channel missing')
            else:
                items=channel.findall('item');stats['rss_items']=len(items)
                if not items:warn('rss_empty','RSS contains no items')
                links=[]
                for item in items:
                    link=(item.findtext('link') or '').strip();title=(item.findtext('title') or '').strip()
                    if not link or not title:fail('rss_missing_fields','An RSS item lacks title or link')
                    if link:links.append(link)
                if len(links)!=len(set(links)):warn('rss_duplicate_links','Duplicate RSS item links')
        except ET.ParseError as e:fail('rss_invalid_xml',str(e))
    sitemap=root/'sitemap.xml'
    if sitemap.is_file():
        try:
            tree=ET.parse(sitemap)
            ns='{http://www.sitemaps.org/schemas/sitemap/0.9}'
            locs=[(x.text or '').strip() for x in tree.findall('.//'+ns+'loc')]
            stats['sitemap_entries']=len(locs)
            if not locs:fail('sitemap_empty','No sitemap URLs')
            for loc in locs:
                if urlsplit(loc).scheme not in ('http','https'):fail('sitemap_bad_url','Invalid sitemap URL: '+loc[:100])
        except ET.ParseError as e:fail('sitemap_invalid_xml',str(e))
    data_root=root/'data'/'v1'
    if not data_root.exists():warn('structured_data_not_present','No data/v1; future MVP data layer not yet installed')
    else:
        for jsonfile in sorted(data_root.rglob('*.json')):
            try:json.loads(jsonfile.read_text(encoding='utf-8'))
            except (OSError,UnicodeError,json.JSONDecodeError) as e:fail('invalid_json',str(jsonfile.relative_to(root))+': '+str(e))
        stats['json_files']=len(list(data_root.rglob('*.json')))
    return failures,warnings,stats

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='.');ap.add_argument('--report',default='quality-report.json');ap.add_argument('--strict',action='store_true',help='Also fail on warnings; not recommended for initial rollout')
    args=ap.parse_args()
    failures,warnings,stats=inspect(Path(args.root))
    payload={'result':'fail' if failures or (args.strict and warnings) else 'pass_with_warnings' if warnings else 'pass','failures':failures,'warnings':warnings,'stats':stats,'scope':'offline structural checks only; not news fact-check or browser QA'}
    Path(args.report).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return int(bool(failures or (args.strict and warnings)))
if __name__=='__main__': sys.exit(main())
