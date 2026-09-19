"""API contract, schema rejection, and parity with saved competition outputs."""
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import create_app
from inference import DEFAULT_MODEL, MAX_UPLOAD_BYTES, Predictor

HERE = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    with TestClient(create_app()) as value:
        yield value


def test_http_prediction_matches_hand_calculated_fatigue_law(client):
    # Alternating stress has N-1 reversals worth 0.5 cycles at amplitude 1.
    raw = b'0\n2\n' * (581120 // 2)
    response = client.post('/api/shm/predict', files={'file': ('recording.csv', raw, 'text/csv')})
    assert response.status_code == 200, response.text
    result = response.json()
    log_scale = json.loads(DEFAULT_MODEL.read_text())['model']['state']['log_scale']
    assert result['prediction'] == pytest.approx(np.exp(log_scale) * (581120 - 1) / 2)
    assert result['file_id'] == 'recording.csv'
    assert result['observations'] == 581120
    assert result['model_id'] == client.get('/api/shm/health').json()['model_id']


@pytest.mark.parametrize('name,raw', [
    ('wrong.txt', b'0\n2\n'), ('../unsafe.csv', b'0\n2\n'),
    ('empty.csv', b''), ('short.csv', b'0\n2\n'),
    ('header.csv', b'stress\n' + b'1\n' * 581119),
    ('nan.csv', b'NaN\n' + b'1\n' * 581119),
    ('inf.csv', b'Inf\n' + b'1\n' * 581119),
    ('columns.csv', b'0,2\n' * 581120),
    ('flat.csv', b'1\n' * 581120),
], ids=['extension', 'path', 'empty', 'length', 'header', 'nan', 'inf', 'columns', 'flat'])
def test_invalid_upload_has_actionable_error(client, name, raw):
    response = client.post('/api/shm/predict', files={'file': (name, raw, 'text/csv')})
    assert response.status_code == 422
    assert isinstance(response.json()['detail'], str)


def test_size_limit_and_missing_file(client):
    response = client.post('/api/shm/predict', files={'file': ('large.csv', b'0' * (MAX_UPLOAD_BYTES + 1))})
    assert response.status_code == 413
    assert client.post('/api/shm/predict').status_code == 422


def test_incompatible_artifact_fails_at_startup(tmp_path):
    artifact = json.loads(DEFAULT_MODEL.read_text())
    artifact['feature_version'] = 'different-extractor'
    path = tmp_path / 'model.json'
    path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError, match='version mismatch'):
        Predictor(path)


@pytest.mark.skipif(not (HERE/'dataset_shm/SHM/Test/test01.csv').exists()
                    or not (HERE/'outputs/grouped/final/shm_predictions.csv').exists(),
                    reason='Optional original dataset and saved validation artifacts are not in Git')
def test_all_real_test_files_http_predictions_match_saved_outputs(client):
    expected = pd.read_csv(HERE/'outputs/grouped/final/shm_predictions.csv').set_index('file_id').prediction
    results = []
    for name, target in expected.items():
        raw = (HERE/'dataset_shm/SHM/Test'/name).read_bytes()
        response = client.post('/api/shm/predict', files={'file': (name, raw, 'text/csv')})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['prediction'] == pytest.approx(target, rel=1e-12)
        results.append(result)
    # Official two-column export can be read without an extra index column.
    csv = pd.DataFrame(results)[['file_id', 'prediction']].to_csv(index=False)
    frame = pd.read_csv(io.StringIO(csv))
    assert list(frame.columns) == ['file_id', 'prediction']
    assert len(frame) == 16 and frame.file_id.is_unique
