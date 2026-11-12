"""Collect matching Qt WebEngine third-party license texts from official Qt docs.

Cached at build time with source URLs and hashes; no runtime network access.
"""
import concurrent.futures
import hashlib
from html import escape,unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin

import httpx
from PySide6.QtWebEngineCore import qWebEngineVersion

OUTPUT=Path(__file__).resolve().parent/'dependency-notices/QtWebEngine'

class Text(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if not self.depth:
            if tag=='div' and 'descr' in dict(attrs).get('class','').split():self.depth=1
        elif tag not in {'br','hr','img','meta','link','input','wbr'}:
            self.depth+=1
        if self.depth and tag in {'p','div','pre','li','br','h1','h2','h3'}:self.parts.append('\n')
    def handle_endtag(self,tag):
        if self.depth and tag not in {'br','hr','img','meta','link','input','wbr'}:
            self.depth-=1
            if tag in {'p','div','pre','li'}:self.parts.append('\n')
    def handle_data(self,value):
        if self.depth:self.parts.append(value)


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    missing=[name for name in ['lgpl-3.0','gpl-3.0','lgpl-2.1','gpl-2.0'] if not (OUTPUT/(name.upper()+'.txt')).is_file()]
    if missing:
        with httpx.Client(trust_env=False,timeout=30,follow_redirects=True) as client:
            for name in missing:
                response=client.get('https://www.gnu.org/licenses/'+name+'.txt');response.raise_for_status()
                if 'GNU' not in response.text or len(response.content)<5000:raise RuntimeError('Invalid GNU license text')
                (OUTPUT/(name.upper()+'.txt')).write_bytes(response.content)
    version=qWebEngineVersion();target=OUTPUT/'Chromium-credits.html';manifest=OUTPUT/'credits-manifest.json'
    if target.is_file() and manifest.is_file():
        old=json.loads(manifest.read_text(encoding='utf-8'))
        if old['version']==version and hashlib.sha256(target.read_bytes()).hexdigest()==old['sha256']:
            print('Verified cached WebEngine attributions:',version);return
    with httpx.Client(trust_env=False,timeout=30,follow_redirects=True) as client:
        index=client.get('https://doc.qt.io/qt-6/qtwebengine-licensing.html');index.raise_for_status()
        if version not in index.text:raise RuntimeError('Official attribution index does not match bundled WebEngine '+version)
        urls=sorted(set(urljoin(str(index.url),unescape(href)) for href in re.findall(r'href="([^"]+)"',index.text) if 'qtwebengine-3rdparty-' in href))
        if len(urls)<50:raise RuntimeError('Incomplete WebEngine attribution index')
        def fetch(url):
            for attempt in range(3):
                try:
                    response=client.get(url);response.raise_for_status();parser=Text();parser.feed(response.text)
                    text=''.join(parser.parts).strip()
                    if not text:raise RuntimeError('Empty license body: '+url)
                    title=re.search(r'<h1[^>]*>(.*?)</h1>',response.text,re.S)
                    title=re.sub('<[^>]+>','',title.group(1)) if title else url.rsplit('/',1)[-1]
                    return {'url':url,'title':unescape(title),'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}
                except (httpx.HTTPError,RuntimeError):
                    if attempt==2:raise
        with concurrent.futures.ThreadPoolExecutor(8) as pool:documents=list(pool.map(fetch,urls))
    OUTPUT.mkdir(parents=True,exist_ok=True)
    html='<!doctype html><meta charset="utf-8"><title>Qt WebEngine '+version+' third-party licenses</title><style>body{max-width:1100px;margin:40px auto;font-family:system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:1px solid #aaa;margin:30px 0;padding:20px 0}</style><h1>Qt WebEngine '+version+' third-party licenses</h1><p>Source: '+escape(str(index.url))+'</p>'
    for doc in documents:html+='<section><h2>'+escape(doc['title'])+'</h2><p>'+escape(doc['url'])+'</p><pre>'+escape(doc['text'])+'</pre></section>'
    target.write_text(html,encoding='utf-8')
    manifest.write_text(json.dumps({'version':version,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'documents':[{k:v for k,v in doc.items() if k!='text'} for doc in documents]},indent=2),encoding='utf-8')
    print('Collected matching official WebEngine attributions:',len(documents),target.stat().st_size)

if __name__=='__main__':main()
