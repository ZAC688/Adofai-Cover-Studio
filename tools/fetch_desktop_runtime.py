"""Fetch pinned Windows desktop wheels from PyPI with digest verification.

Small ranged requests tolerate connections that stall on large wheel downloads.
This is a build-time helper; the distributed program never downloads a runtime.
"""
import concurrent.futures
import hashlib
from pathlib import Path
import subprocess
import sys

import httpx

ROOT=Path(__file__).resolve().parents[1]
PACKAGES={'shiboken6':'6.12.0','PySide6_Essentials':'6.12.0','PySide6_Addons':'6.12.0',
          'PySide6_WebEngine':'6.12.0.140','PySide6_Pdf':'6.12.0.140','PySide6':'6.12.0'}


def main():
    folder=ROOT/'tools/desktop-wheels';folder.mkdir(exist_ok=True)
    with httpx.Client(trust_env=False,timeout=25,follow_redirects=True,
                      limits=httpx.Limits(max_connections=24,max_keepalive_connections=24)) as client:
        for package,version in PACKAGES.items():
            response=client.get(f'https://pypi.org/pypi/{package}/{version}/json');response.raise_for_status()
            wheels=[f for f in response.json()['urls'] if f['filename'].endswith('cp310-abi3-win_amd64.whl')]
            if len(wheels)!=1:raise RuntimeError('Unexpected wheel candidates: '+package)
            wheel=wheels[0];target=folder/wheel['filename'];sha=wheel['digests']['sha256']
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:
                part=target.with_suffix('.parts');size=wheel['size'];chunk=65536
                def piece(start):
                    end=min(size-1,start+chunk-1)
                    for attempt in range(4):
                        try:
                            r=client.get(wheel['url'],headers={'Range':f'bytes={start}-{end}'})
                            r.raise_for_status()
                            expected=f'bytes {start}-{end}/{size}'
                            if r.status_code!=206 or r.headers.get('content-range')!=expected or len(r.content)!=end-start+1:
                                raise RuntimeError('Invalid wheel range')
                            return start,r.content
                        except (httpx.HTTPError,RuntimeError):
                            if attempt==3:raise
                print('Fetching',target.name,size,flush=True)
                with part.open('wb') as stream,concurrent.futures.ThreadPoolExecutor(16) as pool:
                    for index,(start,raw) in enumerate(pool.map(piece,range(0,size,chunk))):
                        stream.seek(start);stream.write(raw)
                        if index%256==0:stream.flush();print('progress',round((start+len(raw))/size*100),'%',flush=True)
                if hashlib.sha256(part.read_bytes()).hexdigest()!=sha:raise RuntimeError('Wheel digest mismatch')
                part.replace(target)
            print('Verified',target.name,flush=True)
    return subprocess.call([sys.executable,'-m','pip','install','--no-index','--find-links',str(folder),'PySide6==6.12.0'])


if __name__=='__main__':raise SystemExit(main())
