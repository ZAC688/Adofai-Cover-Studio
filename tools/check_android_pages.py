"""Audit every ELF in an APK, including Chaquopy's nested .imy archives.

ZIP alignment alone does not validate libraries extracted at runtime. This checks
LOAD alignment/congruence and writable data following RELRO, then invokes the
Android SDK's zipalign for the outer installable APK.
"""
from __future__ import annotations

import argparse
from collections import Counter
import io
import json
from pathlib import Path
import struct
import subprocess
import zipfile

PAGE = 16384
ROOT = Path(__file__).resolve().parents[1]


def inspect_elf(data: bytes, name: str) -> dict:
    if data[:6] != b'\x7fELF\x02\x01' or len(data) < 64:
        raise ValueError(f'Not a supported little-endian ELF64: {name}')
    machine = struct.unpack_from('<H', data, 18)[0]
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    if size < 56 or count == 0 or offset + size * count > len(data):
        raise ValueError(f'Invalid ELF program header table: {name}')
    segments = [struct.unpack_from('<IIQQQQQQ', data, offset + size * i) for i in range(count)]
    loads = [p for p in segments if p[0] == 1]
    issues = []
    if machine not in (62, 183):
        issues.append(f'unsupported machine {machine}')
    if not loads:
        issues.append('no LOAD segments')
    for p in loads:
        if p[7] < PAGE or p[7] & (p[7] - 1):
            issues.append(f'LOAD alignment {p[7]}')
        if (p[3] - p[2]) % PAGE:
            issues.append('LOAD offset/address not congruent at 16KB')
    for relro in (p for p in segments if p[0] == 0x6474e552):
        end = relro[3] + relro[6]
        for load in loads:
            if load[1] & 2 and load[3] <= relro[3] < load[3] + load[6]:
                if end % PAGE and end < load[3] + load[6]:
                    issues.append('writable data shares the trailing RELRO page')
    return {'path': name, 'abi': {62: 'x86_64', 183: 'arm64-v8a'}.get(machine, str(machine)),
            'loadAlignments': [p[7] for p in loads], 'issues': sorted(set(issues))}


def inspect_archive(bundle: zipfile.ZipFile, prefix: str = '', depth: int = 0) -> list[dict]:
    if depth > 4:
        raise ValueError('Unexpected archive nesting depth')
    records = []
    for info in bundle.infolist():
        if info.is_dir():
            continue
        with bundle.open(info) as stream:
            magic = stream.read(4)
        name = prefix + info.filename
        if magic == b'\x7fELF':
            records.append(inspect_elf(bundle.read(info), name))
        elif magic == b'PK\x03\x04':
            # Inspect by content, not just .so suffix or the outer lib/ directory.
            with zipfile.ZipFile(io.BytesIO(bundle.read(info))) as nested:
                records.extend(inspect_archive(nested, name + '!', depth + 1))
    return records


def audit(path: Path, zipalign: Path | None = None) -> dict:
    with zipfile.ZipFile(path) as bundle:
        records = inspect_archive(bundle)
    if not records:
        raise ValueError('No ELF libraries found; an empty scan is not a pass')
    counts = Counter(item['abi'] for item in records)
    result = {'file': path.name, 'pageSize': PAGE, 'libraries': records,
              'counts': dict(counts), 'elfPassed': all(not item['issues'] for item in records)}
    if zipalign is not None:
        command = subprocess.run([str(zipalign), '-c', '-P', '16', '4', str(path)],
                                 capture_output=True, text=True, timeout=60)
        result['zipPassed'] = command.returncode == 0
        result['zipOutput'] = (command.stdout + command.stderr).strip()
    result['passed'] = result['elfPassed'] and result.get('zipPassed', True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--zipalign', type=Path, default=ROOT/'tools/android-sdk/build-tools/35.0.0/zipalign.exe')
    args = parser.parse_args()
    result = audit(args.apk, args.zipalign)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('file', 'counts', 'elfPassed', 'zipPassed', 'passed')}))
    for record in result['libraries']:
        if record['issues']:
            print(record['path'] + ': ' + ', '.join(record['issues']))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
