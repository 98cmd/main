"""client_report/ を Vercel にデプロイして共有 URL を取得する。

Vercel REST API（v13/deployments inline-files mode）を直接叩く。
`vercel deploy` CLI は使わない（CLAUDE.md ルール）。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


VERCEL_API = "https://api.vercel.com"


def _http_post_json(url: str, token: str, body: dict, timeout: float = 180.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} from {url}", file=sys.stderr)
        try:
            err_body = e.read().decode("utf-8")
            print(f"  body: {err_body}", file=sys.stderr)
        except Exception:
            pass
        raise


def deploy(name: str, report_dir: Path, prod: bool = True) -> dict:
    token = os.environ.get("VERCEL_API_KEY") or os.environ.get("VERCEL_TOKEN")
    if not token:
        raise RuntimeError("VERCEL_API_KEY env not set")

    files = []
    for p in sorted(report_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(report_dir).as_posix()
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        files.append({"file": rel, "data": data, "encoding": "base64"})

    if not files:
        raise RuntimeError(f"no files under {report_dir}")

    body = {
        "name": name,
        "target": "production" if prod else "preview",
        "files": files,
        "projectSettings": {"framework": None},
    }
    print(f"deploying {len(files)} file(s) to project {name!r}...")
    resp = _http_post_json(f"{VERCEL_API}/v13/deployments", token, body)
    return resp


def main() -> int:
    name = "kyujinbox-client-report"
    report_dir = Path(__file__).resolve().parent / "client_report"
    if not report_dir.exists():
        print(f"client_report/ not found at {report_dir}", file=sys.stderr)
        return 1

    resp = deploy(name, report_dir, prod=True)

    print()
    print("=== deployment ===")
    print(f"id          : {resp.get('id')}")
    print(f"url         : https://{resp.get('url')}")
    print(f"readyState  : {resp.get('readyState')}")
    aliases = resp.get("alias") or []
    if aliases:
        print(f"aliases     : {', '.join(f'https://{a}' for a in aliases)}")
    inspect = resp.get("inspectorUrl") or resp.get("inspector")
    if inspect:
        print(f"inspect     : {inspect}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
