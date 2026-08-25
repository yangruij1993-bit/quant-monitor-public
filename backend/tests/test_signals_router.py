"""Signals router: /nav /metrics auto-compute, /backtest window slicing."""
import importlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys_path = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(sys_path))

DEMO_DIR = Path(__file__).resolve().parents[2] / "strategies"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STRATEGY_DIR", str(DEMO_DIR))
    import app.services.generic_signal_parser as gsp
    importlib.reload(gsp)
    from app.routers import signals
    importlib.reload(signals)
    app = FastAPI()
    app.include_router(signals.router)
    return TestClient(app)


def test_nav_endpoint_returns_excess(client):
    r = client.get("/api/v1/signals/nav/_demo")
    assert r.status_code == 200
    body = r.json()
    assert body["benchmark_nav"] is not None
    assert body["excess_nav"] is not None
    assert len(body["excess_nav"]) == len(body["nav"])


def test_metrics_endpoint_autocomputes(client):
    r = client.get("/api/v1/signals/metrics/_demo")
    assert r.status_code == 200
    m = r.json()
    assert m["alpha"] is not None
    assert m["turnover"] is not None
    assert m["period_start"] == min(json.loads(
        (DEMO_DIR / "_demo" / "signal_latest.json").read_text(encoding="utf-8")
    )["nav"]["dates"])


def test_backtest_window_slices(client):
    full = client.get("/api/v1/signals/nav/_demo").json()
    start = full["dates"][30]
    end = full["dates"][89]
    r = client.get(f"/api/v1/signals/backtest/_demo?start_date={start}&end_date={end}")
    assert r.status_code == 200
    body = r.json()
    assert body["nav"]["dates"][0] == start
    assert body["nav"]["dates"][-1] == end
    assert body["metrics"]["period_start"] == start
    assert body["metrics"]["period_end"] == end
    assert len(body["nav"]["nav"]) == 60


def test_backtest_unknown_strategy_404(client):
    r = client.get("/api/v1/signals/backtest/nope?start_date=2026-01-01")
    assert r.status_code == 404


def test_backtest_too_narrow_400(client):
    full = client.get("/api/v1/signals/nav/_demo").json()
    d = full["dates"][10]
    r = client.get(f"/api/v1/signals/backtest/_demo?start_date={d}&end_date={d}")
    assert r.status_code == 400
