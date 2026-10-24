#!/usr/bin/env python3
"""Daily best-effort image enrichment for existing E.G.O and safe identity release discovery.
Upstream pages may use client-side rendering; never invent data or replace existing records.
"""
import json,re,pathlib,datetime,requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
P=pathlib.Path(__file__).resolve().parent.parent/'data/catalog.json'
BASE='https://limbusdeck.com'
s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; LimbusFanCatalog/1.0)'})
def page(path):
    r=s.get(BASE+path,timeout=35);r.raise_for_status()
    return BeautifulSoup(r.text,'html.parser')
def absolute(path):
    url=urljoin(BASE,path or '')
    return url if url.startswith('https://') else ''
def main():
    d=json.loads(P.read_text('utf-8'))
    try:
        soup=page('/ko/database/egos')
        # Try card images and links matched by exact sinner+name in visible text.
        matches=0
        for a in soup.select('a[href*="/database/egos/"]'):
            href=absolute(a.get('href'))
            node=a
            for parent in (a.parent,a.parent.parent if a.parent else None):
                if parent and len(parent.get_text(' ',strip=True))<350:
                    node=parent
            txt=' '.join(node.stripped_strings)
            imgs=node.select('img')
            src=''
            for img in imgs:
                src=img.get('src') or img.get('data-src') or ''
                if src and not src.startswith('data:'):break
            if not src:continue
            candidates=[e for e in d['egos'] if e['sinner'] in txt and e['egoName'] in txt]
            if len(candidates)!=1:continue
            e=candidates[0]
            if not e.get('image'):
                e['image']=absolute(src);e['source']=href;e['imageVerified']=True;matches+=1
        print('E.G.O card images resolved:',matches)
        d['lastEgoImageCheck']=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    except Exception as ex:print('E.G.O image sync unavailable:',str(ex)[:240])
    P.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
