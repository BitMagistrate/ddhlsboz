"""Ops console — basic FastAPI app with a few HTMX endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="RoadPulse Ops Console", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <!doctype html>
    <html lang='en'>
      <head><meta charset='utf-8'><title>RoadPulse Ops</title></head>
      <body style='font-family: system-ui, sans-serif; max-width: 720px; margin: 4rem auto'>
        <h1>RoadPulse Ops Console</h1>
        <p>Internal-only dashboard. Use the menu to replay flood triggers,
        inspect k-anonymity violations and force-rebuild the OSRM contraction.</p>
        <ul>
          <li><a href='/healthz'>health</a></li>
          <li><a href='/violations'>k-anon violations</a></li>
        </ul>
      </body>
    </html>
    """


@app.get("/violations")
def violations() -> dict[str, list[dict[str, str]]]:
    # The MVP backend is in-memory; real instance pulls from `audit.kanon.violations` Kafka topic.
    return {"violations": []}
