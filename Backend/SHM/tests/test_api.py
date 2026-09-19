"""Shared API tests. Firebase/Firestore are explicitly simulated, never bypassed in production."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main as shared_main
from app.deps import get_current_user, CurrentUser
from app.firebase import get_db
from app.services import cache, datasets, runs
from app.subsystems.registry import get_runner
from app.subsystems.shm.runner import ShmRunner
from SHM.core.errors import ShmInputError, ShmModelError
from SHM.core.model import MODEL_PATH, ShmModel

HERE = Path(__file__).resolve().parents[1]
ARTIFACT_SHA = '4f5f84828fcb230b004a6721d82d9f9cc268298596404beab868a0f8f1da0a16'
RAW = b'0\n2\n' * (581120 // 2)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(shared_main, 'init_firebase', lambda _: None)
    stored = {}
    monkeypatch.setattr(cache, 'get', lambda db, key: stored.get(key))
    monkeypatch.setattr(cache, 'put', lambda db, key, **kw: stored.__setitem__(key, kw['payload']))
    monkeypatch.setattr(datasets, 'touch', Mock())
    monkeypatch.setattr(runs, 'record', Mock(return_value='test-run'))
    app = shared_main.create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser('test', None, None, None, False)
    app.dependency_overrides[get_db] = lambda: object()
    with TestClient(app) as value:
        yield value


def upload(client, raw=RAW, name='recording.csv', subsystem='shm'):
    return client.post(f'/api/{subsystem}/predict', files={'file': (name, raw, 'text/csv')})


def test_registration_prediction_and_cache_identifiers(client):
    runner = get_runner('shm')
    assert runner.available and runner.upload_mode == 'per-file'
    response = upload(client)
    assert response.status_code == 200, response.text
    result = response.json()
    log_scale = json.loads(MODEL_PATH.read_text())['model']['state']['log_scale']
    assert result['prediction'] == pytest.approx(np.exp(log_scale) * (581120 - 1) / 2)
    assert result['observations'] == 581120
    assert result['weighted_cycle_count'] == (581120 - 1) / 2
    assert result['model_id'] == ARTIFACT_SHA
    assert result['model_version'] == runner.model_version
    assert result['interval'] is None and result['warnings'] == []
    assert 'file_id' not in result and 'filename' not in result
    renamed = upload(client, name='renamed.csv')
    assert renamed.json() == result
    assert renamed.headers['X-Prediction-Cache'] == 'hit'
    assert runs.record.call_args.kwargs['filename'] == 'renamed.csv'


@pytest.mark.parametrize('raw', [b'', b'0\n2\n', b'stress\n' + b'1\n'*581119,
    b'NaN\n'+b'1\n'*581119, b'Inf\n'+b'1\n'*581119, b'0,2\n'*581120,
    b'1\n'*581120, b'\n'+b'1\n'*581119, b'1\n2,3\n', b'\xff'], ids=['empty', 'short', 'header', 'nan', 'inf', 'columns', 'flat', 'missing', 'ragged', 'encoding'])
def test_malformed_inputs_are_client_errors(client, raw):
    response = upload(client, raw)
    assert response.status_code == 400, response.text
    assert isinstance(response.json()['message'], str)
    assert 'detail' not in response.json()


def test_auth_required_and_invalid_token(client, monkeypatch):
    client.app.dependency_overrides.pop(get_current_user)
    assert upload(client).status_code == 401
    import app.deps as deps
    def invalid(_):
        raise ValueError('invalid test token')
    monkeypatch.setattr(deps, 'verify_token', invalid)
    response = client.post('/api/shm/predict', headers={'Authorization': 'Bearer test-only-invalid'}, files={'file': ('x.csv', RAW)})
    assert response.status_code == 401
    assert 'message' in response.json()


def test_missing_file_and_unavailable_model(client, monkeypatch):
    assert client.post('/api/shm/predict').status_code == 422
    monkeypatch.setattr(get_runner('shm'), 'available', False)
    assert upload(client).status_code == 503
    assert get_runner('door').available


@pytest.mark.parametrize('kind', ['missing', 'json', 'feature', 'family', 'scale', 'length', 'rainflow'])
def test_invalid_artifacts_do_not_disable_other_subsystems(tmp_path, kind):
    path = tmp_path/'model.json'
    artifact = json.loads(MODEL_PATH.read_text())
    if kind == 'feature': artifact['feature_version'] = 'incompatible'
    if kind == 'family': artifact['model']['candidate']['family'] = 'hybrid'
    if kind == 'scale': artifact['model']['state']['log_scale'] = float('nan')
    if kind == 'length': artifact['observations'] = 1
    if kind == 'rainflow': artifact['dependencies']['rainflow'] = '0.0'
    if kind != 'missing': path.write_text('not json' if kind == 'json' else json.dumps(artifact))
    with pytest.raises(ShmModelError): ShmModel.load(path)
    runner = ShmRunner(path)
    runner.load()
    assert not runner.available and runner.unavailable_reason


def test_domain_errors_single_batch_and_door_coexistence(client, monkeypatch):
    from core.errors import DoorInputError
    from core.data import __file__ as door_data
    assert 'Door' in door_data
    for subsystem, error, status in [('shm', ShmInputError('Fix recording'), 400),
                                     ('shm', ShmModelError('Model unavailable'), 503),
                                     ('door', DoorInputError('Fix door recording'), 400)]:
        def fail(*args): raise error
        monkeypatch.setattr(get_runner(subsystem), 'run', fail)
        assert upload(client, b'uncached', subsystem=subsystem).status_code == status
        batch = client.post(f'/api/{subsystem}/predict-batch', files=[('files', ('bad.csv', b'uncached'))])
        assert batch.status_code == 200
        assert batch.json()['results'][0] == {'filename': 'bad.csv', 'ok': False, 'result': None, 'message': str(error)}


def test_batch_keeps_current_names_and_partial_errors(client):
    response = client.post('/api/shm/predict-batch', files=[('files', ('a.csv', RAW)), ('files', ('b.csv', RAW)), ('files', ('bad.csv', b'1'))])
    rows = response.json()['results']
    assert [r['filename'] for r in rows] == ['a.csv', 'b.csv', 'bad.csv']
    assert [r['ok'] for r in rows] == [True, True, False]
    assert rows[0]['result'] == rows[1]['result']


def test_model_and_pipeline_cache_separation(client, tmp_path, monkeypatch):
    first = upload(client)
    runner = get_runner('shm')
    original = runner._model
    artifact = json.loads(MODEL_PATH.read_text())
    artifact['model']['state']['log_scale'] += .01
    path = tmp_path/'different.json'
    path.write_text(json.dumps(artifact))
    changed = ShmModel.load(path)
    monkeypatch.setattr(runner, '_model', changed)
    monkeypatch.setattr(runner, 'model_version', changed.model_version)
    second = upload(client)
    assert second.headers['X-Prediction-Cache'] == 'miss'
    assert second.json()['prediction'] != first.json()['prediction']
    import SHM.core.model as module
    monkeypatch.setattr(module, 'PIPELINE_REVISION', 'test-next-pipeline')
    revised = ShmModel.load()
    assert revised.model_id == original.model_id and revised.model_version != original.model_version
    monkeypatch.setattr(runner, '_model', revised)
    monkeypatch.setattr(runner, 'model_version', revised.model_version)
    assert upload(client).headers['X-Prediction-Cache'] == 'miss'


def test_inference_imports_without_training_or_sklearn():
    code = """
import sys
import importlib.abc
class RejectTraining(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.startswith(('sklearn', 'SHM.models', 'SHM.training', 'SHM.validation', 'SHM.splits')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, RejectTraining())
from app.subsystems.registry import load_all, get_runner
load_all()
assert get_runner('door').available and get_runner('shm').available
from SHM.core.model import ShmModel
from SHM.main import predict
assert ShmModel.load().model_id
"""
    subprocess.run([sys.executable, '-c', code], cwd=HERE.parent, check=True)


@pytest.mark.skipif(not (HERE/'dataset_shm/SHM/Test/test01.csv').exists()
    or not (HERE/'outputs/grouped/final/shm_predictions.csv').exists(),
    reason='Optional original dataset and saved predictions are not in Git')
def test_all_16_real_recordings_match_untouched_saved_predictions(client, tmp_path):
    before = MODEL_PATH.read_bytes()
    assert hashlib.sha256(before).hexdigest() == ARTIFACT_SHA
    expected = pd.read_csv(HERE/'outputs/grouped/final/shm_predictions.csv').set_index('file_id').prediction
    files = sorted((HERE/'dataset_shm/SHM/Test').glob('*.csv'))
    assert len(files) == len(expected) == 16 and expected.index.is_unique
    assert {p.name for p in files} == set(expected.index)
    output = tmp_path / 'shm_predictions.csv'
    subprocess.run([
        sys.executable, str(HERE / 'predict.py'),
        '--input', str(HERE / 'dataset_shm/SHM/Test'), '--output', str(output),
    ], check=True)
    cli_frame = pd.read_csv(output)
    assert list(cli_frame.columns) == ['file_id', 'prediction']
    assert len(cli_frame) == 16 and cli_frame.file_id.is_unique
    cli = cli_frame.set_index('file_id').prediction
    assert set(cli.index) == set(expected.index)
    for path in files:
        raw = path.read_bytes()
        response = upload(client, raw, path.name)
        assert response.status_code == 200, response.text
        target = expected[path.name]
        assert response.json()['prediction'] == pytest.approx(target, rel=1e-12, abs=0)
        assert cli[path.name] == pytest.approx(response.json()['prediction'], rel=1e-12, abs=0)
    assert MODEL_PATH.read_bytes() == before
