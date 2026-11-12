"""Development-only fetch of pinned, OFL-licensed font assets; never used by the app."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import subprocess
import re

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'frontend/public/fonts'
SPECS=[('noto-sans-sc','思源风格黑体 · Noto Sans SC','notosanssc','NotoSansSC[wght].ttf'),
       ('noto-serif-sc','宋体 · Noto Serif SC','notoserifsc','NotoSerifSC[wght].ttf'),
       ('inter','Inter · 英文无衬线','inter','Inter[opsz,wght].ttf'),
       ('noto-serif','Noto Serif · 英文衬线','notoserif','NotoSerif[wdth,wght].ttf')]


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    manifest=OUTPUT/'manifest.json'
    if manifest.is_file():revision=json.loads(manifest.read_text(encoding='utf-8'))['upstreamRevision']
    else:
        result=subprocess.run(['git','ls-remote','https://github.com/google/fonts.git','refs/heads/main'],capture_output=True,text=True,check=True,timeout=60)
        revision=result.stdout.split()[0]
        if not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('Invalid upstream revision')
    def fetch(spec):
        font_id,label,folder,filename=spec
        base=f'https://raw.githubusercontent.com/google/fonts/{revision}/ofl/{folder}/'
        url=base+urllib.parse.quote(filename)
        target=OUTPUT/(font_id+'.ttf')
        urllib.request.urlretrieve(url,target)
        license_path=OUTPUT/(font_id+'-OFL.txt')
        urllib.request.urlretrieve(base+'OFL.txt',license_path)
        # Preserve license wording; normalize trailing spaces for text tooling.
        license_path.write_text('\n'.join(line.rstrip() for line in license_path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
        return {'id':font_id,'label':label,'file':target.name,'source':url,'license':'SIL Open Font License 1.1',
                'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:entries=list(pool.map(fetch,SPECS))
    manifest.write_text(json.dumps({'upstreamRevision':revision,'fonts':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    for entry in entries:print(entry['id'],entry['bytes'],entry['sha256'])


if __name__=='__main__':main()
