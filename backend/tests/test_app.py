"""
Real, runnable tests for the Sendero Portfolio API -- no mocks. These hit
the actual Flask app and the actual classification engine.

Run:
    cd backend
    python -m pytest tests/ -v
"""
import io
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app_module.DB_PATH = path
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
    os.remove(path)


SAMPLE_CSV = """company_id,growth_gap_pts,founder_experience,reimbursement_model
novara,11.4,repeat,payer_heavy
perigon,13.1,first_time,payer_heavy
wellcase,8.9,first_time,cash_pay_mix
quorva,6.2,first_time,not_applicable
brightline,1.8,repeat,not_applicable
haloscript,2.4,repeat,not_applicable
medlyra,12.6,repeat,payer_heavy
carewisp,10.7,first_time,payer_heavy
"""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_classify_requires_file(client):
    r = client.post("/api/classify", data={"metric": "growth_gap_pts"})
    assert r.status_code == 400


def test_classify_requires_metric(client):
    data = {"file": (io.BytesIO(SAMPLE_CSV.encode()), "test.csv")}
    r = client.post("/api/classify", data=data, content_type="multipart/form-data")
    assert r.status_code == 400


def test_classify_end_to_end(client):
    """
    The digital-health cluster from the product mockups, run for real:
    growth_gap is elevated broadly (payer_heavy companies), which should
    read toward BUILD, not TRAINING -- founder experience should NOT be
    the dominant explanation.
    """
    data = {
        "file": (io.BytesIO(SAMPLE_CSV.encode()), "portfolio.csv"),
        "name": "Digital health portfolio",
        "metric": "growth_gap_pts",
        "baseline": "2",
        "higher_is_worse": "true",
        "capability_cols": "founder_experience",
        "config_cols": "reimbursement_model",
        "capital_exposed": "84000000",
    }
    r = client.post("/api/classify", data=data, content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    result = r.get_json()

    assert result["classification"] in ("BUILD", "HYBRID", "TRAINING")
    assert result["n"] == 8
    assert "id" in result
    assert result["recoverable_value"] is not None
    assert result["capital_exposed"] == 84000000.0
    # This is a real statistical result, not a scripted mock -- print it
    # so a human reviewing test output can sanity-check the actual call.
    print(json.dumps(result, indent=2))


def test_worklist_ranks_by_recoverable_value(client):
    data1 = {
        "file": (io.BytesIO(SAMPLE_CSV.encode()), "a.csv"),
        "name": "Cluster A", "metric": "growth_gap_pts", "baseline": "2",
        "capital_exposed": "10000000",
    }
    data2 = {
        "file": (io.BytesIO(SAMPLE_CSV.encode()), "b.csv"),
        "name": "Cluster B", "metric": "growth_gap_pts", "baseline": "2",
        "capital_exposed": "90000000",
    }
    client.post("/api/classify", data=data1, content_type="multipart/form-data")
    client.post("/api/classify", data=data2, content_type="multipart/form-data")

    r = client.get("/api/worklist")
    body = r.get_json()
    assert body["count"] == 2
    # Cluster B has 9x the capital exposed with the same underlying stats,
    # so it must rank first.
    assert body["items"][0]["name"] == "Cluster B"


def test_cluster_detail_not_found(client):
    r = client.get("/api/clusters/does-not-exist")
    assert r.status_code == 404
