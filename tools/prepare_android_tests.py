"""Prepare private fixtures for the emulator test APK only, never the user APK."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def prepare():
    import numpy as np
    import onnxruntime as ort
    target=ROOT/'android/app/build/generated/androidTestAssets'
    (target/'solid').mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'test-assets/solid/manifest.json').read_text(encoding='utf-8'))
    samples=[]
    for sample in manifest['samples']:
        if not sample['annotation_approved']:raise ValueError('Annotation not approved')
        source=(ROOT/sample['file']).resolve()
        truth=(ROOT/'test-assets/solid'/sample['ground_truth']).resolve()
        if not source.is_relative_to(ROOT) or not truth.is_relative_to(ROOT):raise ValueError('Fixture escaped workspace')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=sample['sha256']:raise ValueError('Approved source image changed')
        if hashlib.sha256(truth.read_bytes()).hexdigest()!=sample['annotation_sha256']:raise ValueError('Approved annotation changed')
        image_name=sample['id']+'-source.png'
        truth_name=sample['id']+'-truth.png'
        shutil.copyfile(source,target/'solid'/image_name)
        shutil.copyfile(truth,target/'solid'/truth_name)
        samples.append({'id':sample['id'],'image':image_name,'truth':truth_name,'truth_sha256':sample['annotation_sha256']})
    (target/'solid/manifest.json').write_text(json.dumps(samples),encoding='utf-8')
    session=ort.InferenceSession(str(ROOT/'models/u2netp.onnx'),providers=['CPUExecutionProvider'])
    values=(np.arange(3*320*320,dtype=np.int32)%251).astype(np.float32)/np.float32(251)
    result=session.run(None,{session.get_inputs()[0].name:values.reshape(1,3,320,320)})[0].reshape(-1)
    indices=[index*997%result.size for index in range(32)]
    (target/'model-reference.json').write_text(json.dumps({'mean':float(result.mean()),'indices':indices,'values':[float(result[index]) for index in indices]}),encoding='utf-8')
    print(f'Prepared {len(samples)} approved image/mask pairs for emulator test APK only')


if __name__=='__main__':prepare()
