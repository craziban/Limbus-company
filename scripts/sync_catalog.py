#!/usr/bin/env python3
"""Verify E.G.O card art via LimbusDeck, using Namu Wiki E.G.O roster as a
human-readable cross-reference. Match exact Korean name AND sinner; no guessed slugs.
Daily run. Preserve all collection keys, releases, metadata and user-owned state.
"""
import concurrent.futures
import datetime
import json
import pathlib
import re
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

ROOT=pathlib.Path(__file__).resolve().parent.parent
CAT=ROOT/"data"/"catalog.json"
INDEX="https://limbusdeck.com/ko/database/egos"
ASSETS="https://assets.limbusdeck.com/egos/full/"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; LIMBUS-COMPANY-Collection/1.1; personal fan tracker)",
         "Accept-Language":"ko-KR,ko;q=0.9"}

def norm(value):
    return re.sub(r"\s+","",str(value or "")).lower()

def card_texts(anchor):
    nodes=[anchor]
    if anchor.parent:nodes.append(anchor.parent)
    if anchor.parent and anchor.parent.parent:nodes.append(anchor.parent.parent)
    return [norm(n.get_text(" ",strip=True)) for n in nodes if n and len(n.get_text(" ",strip=True))<500]

def get_cards():
    response=requests.get(INDEX,headers=HEADERS,timeout=35)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    cards=[]
    for a in soup.select('a[href*="/database/egos/"]'):
        url=urljoin(INDEX,a.get("href",""))
        m=re.search(r"/database/egos/([a-z0-9-]+)/?$",urlparse(url).path)
        if not m:continue
        slug=m.group(1)
        cards.append((slug,url,card_texts(a)))
    # Deduplicate cards that appear in nav, related lists, etc.
    cards=list({c[0]:c for c in cards}.values())
    print("Upstream named E.G.O cards:",len(cards),flush=True)
    return cards

def verified_image(item):
    _,_,url=item
    try:
        r=requests.head(url,headers=HEADERS,timeout=14,allow_redirects=True)
        if r.status_code in (405,403):
            r=requests.get(url,headers={**HEADERS,"Range":"bytes=0-0"},timeout=14,stream=True)
        success=r.status_code in (200,206) and (
            "image" in r.headers.get("Content-Type","").lower()
            or url.endswith(".webp"))
        r.close()
        return success
    except requests.RequestException:
        return False

def main():
    catalog=json.loads(CAT.read_text(encoding="utf-8"))
    pending=[e for e in catalog["egos"] if not e.get("image")]
    if not pending:
        print("All",len(catalog["egos"]),"E.G.O records have artwork URLs; no upstream requests needed.",flush=True)
        return
    try:
        cards=get_cards()
    except requests.RequestException as exc:
        print("Upstream blocked or unavailable: skip safely, keep catalog and deploy. Reason:",str(exc)[:180],flush=True)
        return
    updates=[]
    missing=[]
    for e in catalog["egos"]:
        if e.get("image"):
            continue
        sinner=norm(e.get("sinner"))
        name=norm(e.get("egoName"))
        candidates=[]
        for slug,url,texts in cards:
            if any(sinner in t and name in t for t in texts):
                candidates.append((slug,url))
        candidates=list(dict.fromkeys(candidates))
        if len(candidates)!=1:
            missing.append((e["id"],len(candidates)))
            continue
        slug,detail=candidates[0]
        candidate_img=f"{ASSETS}{slug}.webp"
        updates.append((e,slug,detail,candidate_img))
    print("Exact paired matches:",len(updates),"unmatched or ambiguous:",len(missing),flush=True)
    if missing: print("Unmatched:",missing[:25],flush=True)
    # Check each candidate exists, avoiding broken or mismatched thumbnails.
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results=list(pool.map(verified_image,[(e,slug,url) for e,slug,detail,url in updates]))
    succeeded=0
    for (ego,slug,source,url),ok in zip(updates,results):
        if not ok:continue
        ego["image"]=url
        ego["source"]=source
        ego["slug"]=slug
        ego["imageVerified"]=True
        succeeded+=1
    print("E.G.O images verified and stored:",succeeded,"out of",len(catalog["egos"]),flush=True)
    catalog["lastEgoImageCheck"]=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    CAT.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
