import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.sign_android import initialize


def keytool():
    candidates = [Path(os.environ.get('ADOFAI_JAVA_HOME', '')), Path(os.environ.get('JAVA_HOME', '')),
                  Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Java/jdk-17']
    return next(path / 'bin/keytool.exe' for path in candidates if (path / 'bin/keytool.exe').is_file())


def test_real_release_identity_is_reusable_and_never_silently_replaced(tmp_path, capsys):
    config = initialize(tmp_path, keytool())
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in tmp_path.iterdir()}
    assert initialize(tmp_path, keytool()) == config
    assert before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in tmp_path.iterdir()}
    settings = json.loads(config.read_text())
    assert len(settings['storePassword']) >= 40
    assert settings['storePassword'] not in capsys.readouterr().out
    settings['storePassword'] = 'incorrect-password'
    config.write_text(json.dumps(settings))
    with pytest.raises(ValueError, match='refusing to replace'):
        initialize(tmp_path, keytool())
    assert hashlib.sha256((tmp_path/'release.p12').read_bytes()).hexdigest() == before['release.p12']


def test_orphaned_key_is_preserved_instead_of_creating_a_new_identity(tmp_path):
    original = b'existing-key-do-not-replace'
    (tmp_path/'release.p12').write_bytes(original)
    with pytest.raises(ValueError, match='refusing to replace'):
        initialize(tmp_path, keytool())
    assert (tmp_path/'release.p12').read_bytes() == original
    assert not (tmp_path/'release.json').exists()
