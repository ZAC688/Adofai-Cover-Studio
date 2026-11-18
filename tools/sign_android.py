"""Create a reusable local release identity without printing credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def initialize(directory: Path, keytool: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / 'release.json'
    keystore = directory / 'release.p12'
    if config.exists():
        settings = json.loads(config.read_text(encoding='utf-8'))
        if settings.get('storeFile') != keystore.name or not keystore.is_file():
            raise ValueError('Existing signing configuration is incomplete; preserve it and restore its matching key')
        verify(settings, keystore, keytool)
        return config
    if keystore.exists():
        raise ValueError('A key already exists without its configuration; refusing to replace it')
    password = secrets.token_urlsafe(40)
    environment = dict(os.environ, ADOFAI_KEY_PASSWORD=password)
    result = subprocess.run([
        str(keytool), '-genkeypair', '-keystore', str(keystore), '-storetype', 'PKCS12',
        '-storepass:env', 'ADOFAI_KEY_PASSWORD', '-keypass:env', 'ADOFAI_KEY_PASSWORD',
        '-alias', 'adofai-cover-studio', '-keyalg', 'RSA', '-keysize', '3072',
        '-validity', '10000', '-dname', 'CN=ZAC688, OU=ADOFAI Cover Studio', '-noprompt',
    ], env=environment, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Release key generation failed; no credentials are printed')
    settings = {'storeFile': keystore.name, 'keyAlias': 'adofai-cover-studio',
                'storePassword': password, 'keyPassword': password}
    verify(settings, keystore, keytool)
    # Exclusive creation protects a pre-existing local identity.
    with config.open('x', encoding='utf-8') as output:
        json.dump(settings, output)
    return config


def verify(settings: dict, keystore: Path, keytool: Path) -> None:
    environment = dict(os.environ, ADOFAI_KEY_PASSWORD=settings['storePassword'])
    result = subprocess.run([str(keytool), '-list', '-keystore', str(keystore),
                             '-storepass:env', 'ADOFAI_KEY_PASSWORD', '-alias', settings['keyAlias']],
                            env=environment, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('Existing release key could not be verified; refusing to replace it')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keytool', type=Path, required=True)
    args = parser.parse_args()
    initialize(ROOT / 'android/signing', args.keytool)
    print('Local release signing identity verified; credentials remain in the ignored signing directory')
