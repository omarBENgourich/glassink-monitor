"""Verify provisioned Grafana assets and execute every Flux dashboard query."""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "dashboards" / "definitions"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
    return values


ENV = {**load_env(), **os.environ}
BASE_URL = f"http://localhost:{ENV.get('GRAFANA_PORT', '3000')}"
USERNAME = ENV.get("GRAFANA_ADMIN_USER", "admin")
PASSWORD = ENV.get("GRAFANA_ADMIN_PASSWORD", "")
AUTH = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()


def request(path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": AUTH}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def main() -> int:
    health = request("/api/health")
    if health.get("database") != "ok":
        raise RuntimeError(f"Grafana unhealthy: {health}")

    files = sorted(DASHBOARD_DIR.glob("*.json"))
    expected_uids = {json.loads(path.read_text())["uid"] for path in files}
    provisioned = request("/api/search?type=dash-db")
    loaded_uids = {item["uid"] for item in provisioned}
    missing = expected_uids - loaded_uids
    if missing:
        raise RuntimeError(f"dashboards not provisioned: {sorted(missing)}")

    now = int(time.time() * 1000)
    start = now - 7 * 24 * 3600 * 1000
    checked = 0
    failures: list[str] = []

    for path in files:
        dashboard = json.loads(path.read_text())
        for panel in dashboard.get("panels", []):
            for target in panel.get("targets", []):
                if target.get("datasource", {}).get("uid") != "influxdb":
                    continue
                model = dict(target)
                model["datasource"] = {
                    "type": "influxdb",
                    "uid": "influxdb",
                }
                payload = request(
                    "/api/ds/query",
                    {"queries": [model], "from": str(start), "to": str(now)},
                )
                result = payload.get("results", {}).get(target["refId"], {})
                checked += 1
                if result.get("error") or result.get("status", 200) != 200:
                    failures.append(
                        f"{dashboard['title']} / {panel['title']}: "
                        f"{result.get('error') or result.get('status')}"
                    )

    rules = request("/api/v1/provisioning/alert-rules")
    if len(rules) != 7:
        failures.append(f"expected 7 alert rules, found {len(rules)}")

    checked_alerts = 0
    for rule in rules:
        queries = []
        seconds = 900
        for item in rule.get("data", []):
            model = dict(item["model"])
            if item.get("datasourceUid") == "influxdb":
                model["datasource"] = {"type": "influxdb", "uid": "influxdb"}
            seconds = max(
                seconds,
                int(item.get("relativeTimeRange", {}).get("from", 0)),
            )
            queries.append(model)
        payload = request(
            "/api/ds/query",
            {
                "queries": queries,
                "from": str(now - seconds * 1000),
                "to": str(now),
            },
        )
        checked_alerts += 1
        for model in queries:
            result = payload.get("results", {}).get(model["refId"], {})
            if result.get("error") or result.get("status", 200) != 200:
                failures.append(
                    f"alert {rule['title']} / {model['refId']}: "
                    f"{result.get('error') or result.get('status')}"
                )

    if failures:
        raise RuntimeError("\n".join(failures))

    print(
        f"Grafana/InfluxDB OK: {len(files)} dashboards, "
        f"{checked} panel queries, {checked_alerts} alert queries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
