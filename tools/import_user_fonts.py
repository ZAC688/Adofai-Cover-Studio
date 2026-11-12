"""Import only the three explicitly approved families from the supplied archive."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from fontTools.ttLib import TTFont
import io

ROOT=Path(__file__).resolve().parents[1]
FACES=[('bebas-neue','Bebas Neue · 常规','Bebas_Neue/BebasNeue-Regular.ttf',400,'normal'),
       ('russo-one','Russo One · 常规','Russo_One/RussoOne-Regular.ttf',400,'normal'),
       ('space-mono','Space Mono · 常规','Space_Mono/SpaceMono-Regular.ttf',400,'normal'),
       ('space-mono-italic','Space Mono · 斜体','Space_Mono/SpaceMono-Italic.ttf',400,'italic'),
       ('space-mono-bold','Space Mono · 粗体','Space_Mono/SpaceMono-Bold.ttf',700,'normal'),
       ('space-mono-bold-italic','Space Mono · 粗斜体','Space_Mono/SpaceMono-BoldItalic.ttf',700,'italic')]

def main():
    output=ROOT/'frontend/public/fonts';path=output/'manifest.json'
    manifest=json.loads(path.read_text(encoding='utf-8'));ids={row[0] for row in FACES}
    manifest['fonts']=[row for row in manifest['fonts'] if row['id'] not in ids]
    hashes=set()
    with ZipFile(ROOT/'fonts/Bebas_Neue,Russo_One,Space_Mono.zip') as archive:
        for font_id,label,member,weight,style in FACES:
            raw=archive.read(member);digest=hashlib.sha256(raw).hexdigest()
            if digest in hashes:raise ValueError('Duplicate face')
            hashes.add(digest)
            with TTFont(io.BytesIO(raw)) as font:
                assert font.getBestCmap() and font['OS/2'].usWeightClass==weight
                assert bool(font['head'].macStyle & 2)==(style=='italic')
            (output/f'{font_id}.ttf').write_bytes(raw)
            license_name=member.split('/')[0]+'/OFL.txt'
            (output/f"{member.split('/')[0]}-OFL.txt").write_bytes(archive.read(license_name))
            manifest['fonts'].append({'id':font_id,'label':label,'file':f'{font_id}.ttf','source':f'User-supplied archive / {member}',
                'license':'SIL Open Font License 1.1','sha256':digest,'bytes':len(raw),'weight':weight,'style':style})
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
