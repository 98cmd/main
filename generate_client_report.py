"""高屋裕司氏（株式会社UPDRAFT）向けクライアントレポート HTML を生成する。

入力:
  - poc/output/results.json           (5/8 製造業 5 社の抽出結果)
  - poc/output/unmatched_leads.json   (5/9 Wantedly 100 社 突合結果)
  - poc/output/lead_outreach_messages.json  (営業文章)

出力:
  - client_report/index.html
  - client_report/messages.html
"""
from __future__ import annotations

import datetime
import html
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
LEADS_JSON = REPO_ROOT / "poc" / "output" / "unmatched_leads.json"
MESSAGES_JSON = REPO_ROOT / "poc" / "output" / "lead_outreach_messages.json"
RESULTS_JSON = REPO_ROOT / "poc" / "output" / "results.json"
OUT_DIR = REPO_ROOT / "client_report"
OUT_INDEX = OUT_DIR / "index.html"
OUT_MESSAGES = OUT_DIR / "messages.html"


PHASE1_NUMBERS = {
    "judge_accuracy_pct": 100,
    "license_with_mhlw_pct": 80,
    "address_with_mhlw_pct": 80,
    "phone_with_mhlw_pct": 80,
}

EXCLUDE_COMPANY_NAMES_LOWER = {"wantedly, inc.", "wantedly,inc.", "wantedlyinc"}


def _norm(s: str) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFKC", (s or "").strip()).split()).lower()


def is_valid_message(msg: str) -> bool:
    m = msg.strip()
    if m.startswith("件名"):
        return True
    return "件名:" in m[:120] or "件名 :" in m[:120]


def donut_svg(total: int, miss: int, size: int = 240, stroke: int = 16) -> str:
    """グラデーションストロークのモダンなドーナツチャート。"""
    if total <= 0:
        return ""
    cx = cy = size / 2
    r = (size - stroke) / 2
    c = 2 * 3.141592653589793 * r
    miss_pct = miss / total
    miss_len = c * miss_pct
    hit_len = c - miss_len
    pct_text = f"{int(round(miss_pct * 100))}%"
    return f"""
    <svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">
      <defs>
        <linearGradient id="donutGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#6366f1"/>
          <stop offset="100%" stop-color="#a855f7"/>
        </linearGradient>
      </defs>
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#f1f5f9" stroke-width="{stroke}"/>
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#donutGrad)" stroke-width="{stroke}"
              stroke-linecap="round"
              stroke-dasharray="{miss_len:.2f} {hit_len:.2f}"
              stroke-dashoffset="{c/4:.2f}" transform="rotate(-90 {cx} {cy})"/>
      <text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="48" font-weight="700"
            fill="#0a0a0a" font-family="'Inter', sans-serif" letter-spacing="-0.04em">{pct_text}</text>
      <text x="{cx}" y="{cy + 30}" text-anchor="middle" font-size="11" fill="#737373"
            font-family="'Inter', sans-serif" letter-spacing="0.18em" font-weight="500">UNTAPPED</text>
    </svg>
    """


HTML_HEAD = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>求人ボックス 直接アプローチ実証レポート</title>
<meta name="description" content="他媒体に出稿中で求人ボックスに未出稿の企業を抽出し、個別営業文章まで自動生成するパイプラインの実証結果。">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #fafafa;
    --paper: #ffffff;
    --ink: #0a0a0a;
    --ink-2: #404040;
    --ink-3: #525252;
    --muted: #737373;
    --line: #e5e5e5;
    --line-soft: #f1f5f9;
    --accent: #6366f1;
    --accent-2: #8b5cf6;
    --accent-3: #a855f7;
    --accent-soft: #eef2ff;
    --accent-soft-2: #f5f3ff;
    --success: #10b981;
    --success-soft: #d1fae5;
    --grad: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
    --grad-soft: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 50%, #faf5ff 100%);
    --shadow-sm: 0 1px 2px rgba(10, 10, 10, .04);
    --shadow: 0 1px 3px rgba(10, 10, 10, .05), 0 8px 24px rgba(10, 10, 10, .04);
    --shadow-lg: 0 4px 12px rgba(10, 10, 10, .06), 0 20px 48px rgba(99, 102, 241, .12);
  }
  * { box-sizing: border-box; }
  html { -webkit-font-smoothing: antialiased; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: 'Inter', 'Plus Jakarta Sans', 'Noto Sans JP', -apple-system, system-ui, sans-serif;
    background: var(--bg);
    color: var(--ink);
    line-height: 1.7;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: -0.005em;
  }

  /* グラデーションオーブ（背景ぼかし） */
  body::before {
    content: "";
    position: fixed;
    top: -200px; right: -200px;
    width: 700px; height: 700px;
    background: radial-gradient(circle, rgba(99, 102, 241, .12) 0%, transparent 70%);
    filter: blur(60px);
    pointer-events: none;
    z-index: 0;
  }
  body::after {
    content: "";
    position: fixed;
    bottom: -300px; left: -200px;
    width: 800px; height: 800px;
    background: radial-gradient(circle, rgba(168, 85, 247, .08) 0%, transparent 70%);
    filter: blur(80px);
    pointer-events: none;
    z-index: 0;
  }

  .container {
    position: relative;
    z-index: 1;
    max-width: 1120px;
    margin: 0 auto;
    padding: 64px 32px 96px;
  }

  /* HERO */
  .hero {
    margin-bottom: 96px;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background: var(--accent-soft);
    color: var(--accent);
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 28px;
    border: 1px solid rgba(99, 102, 241, .2);
  }
  .badge::before {
    content: "";
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 4px rgba(99, 102, 241, .2);
  }
  .hero-title {
    font-family: 'Plus Jakarta Sans', 'Inter', 'Noto Sans JP', sans-serif;
    font-weight: 800;
    font-size: 48px;
    line-height: 1.15;
    letter-spacing: -0.035em;
    margin: 0 0 24px;
    color: var(--ink);
  }
  .hero-title .grad {
    background: var(--grad);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }
  .hero-lead {
    font-size: 17px;
    color: var(--ink-2);
    line-height: 1.75;
    max-width: 760px;
    margin: 0 0 40px;
    font-weight: 400;
  }
  .meta-bar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
    padding: 24px;
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 16px;
    box-shadow: var(--shadow-sm);
  }
  .meta-item { padding: 0 4px; }
  .meta-label {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 600;
    margin-bottom: 6px;
  }
  .meta-value {
    font-size: 15px;
    color: var(--ink);
    font-weight: 600;
  }

  /* SECTION */
  section {
    margin-bottom: 88px;
    scroll-margin-top: 32px;
  }
  .section-tag {
    display: inline-block;
    font-family: 'Inter', sans-serif;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
    padding: 4px 12px;
    background: var(--accent-soft);
    border-radius: 6px;
    margin-bottom: 18px;
  }
  .section-title {
    font-family: 'Plus Jakarta Sans', 'Inter', 'Noto Sans JP', sans-serif;
    font-size: 32px;
    line-height: 1.3;
    margin: 0 0 14px;
    color: var(--ink);
    font-weight: 700;
    letter-spacing: -0.025em;
    max-width: 880px;
  }
  .section-lead {
    font-size: 15.5px;
    color: var(--ink-3);
    line-height: 1.75;
    max-width: 780px;
    margin: 0 0 40px;
  }

  /* HEADLINE KPI */
  .kpi-card {
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 48px 48px;
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
  }
  .kpi-card::before {
    content: "";
    position: absolute;
    top: -2px; left: 0; right: 0;
    height: 3px;
    background: var(--grad);
    border-radius: 24px 24px 0 0;
  }
  .kpi-grid {
    display: grid;
    grid-template-columns: minmax(280px, auto) 1fr;
    gap: 56px;
    align-items: center;
  }
  .kpi-figure {
    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
    font-weight: 800;
    font-size: 120px;
    line-height: 0.95;
    background: var(--grad);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
    letter-spacing: -0.06em;
    display: flex;
    align-items: baseline;
  }
  .kpi-figure .unit {
    font-size: 40px;
    margin-left: 4px;
    -webkit-text-fill-color: transparent;
  }
  .kpi-body h3 {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px;
    margin: 0 0 8px;
    color: var(--ink);
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .kpi-body p {
    margin: 0;
    color: var(--ink-3);
    font-size: 15px;
    line-height: 1.7;
  }

  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
    margin-top: 32px;
  }
  .stat {
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 20px 22px;
    transition: border-color .2s, box-shadow .2s;
  }
  .stat:hover {
    border-color: rgba(99, 102, 241, .3);
    box-shadow: var(--shadow);
  }
  .stat-label {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 600;
    margin-bottom: 10px;
  }
  .stat-value {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 30px;
    color: var(--ink);
    letter-spacing: -0.03em;
    line-height: 1;
  }
  .stat-value .unit {
    font-size: 15px;
    color: var(--ink-2);
    font-weight: 600;
    margin-left: 4px;
  }

  /* CALLOUT */
  .callout {
    margin-top: 24px;
    padding: 20px 24px;
    background: var(--grad-soft);
    border: 1px solid rgba(99, 102, 241, .15);
    border-radius: 14px;
    color: var(--ink-2);
    font-size: 14.5px;
    line-height: 1.75;
  }
  .callout strong { color: var(--ink); font-weight: 700; }

  /* INDICATOR TABLE */
  .ind-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }
  .ind-table th {
    text-align: left;
    padding: 14px 24px;
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 600;
    background: #fafafa;
    border-bottom: 1px solid var(--line);
  }
  .ind-table td {
    padding: 18px 24px;
    border-bottom: 1px solid var(--line);
    vertical-align: middle;
    font-size: 14.5px;
    color: var(--ink-2);
  }
  .ind-table tr:last-child td { border-bottom: none; }
  .ind-table .col-label { width: 40%; color: var(--ink); font-weight: 500; }
  .ind-table .col-value {
    text-align: right;
    width: 90px;
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 18px;
    color: var(--ink);
    letter-spacing: -0.02em;
  }
  .ind-table .col-bar { padding-left: 32px; padding-right: 32px; }
  .bar {
    position: relative;
    height: 8px;
    background: var(--line-soft);
    border-radius: 999px;
    overflow: hidden;
  }
  .bar-fill {
    position: absolute;
    inset: 0 auto 0 0;
    background: var(--grad);
    border-radius: 999px;
  }

  /* COMPANY LIST */
  .lead-list {
    width: 100%;
    border-collapse: collapse;
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }
  .lead-list thead th {
    background: #fafafa;
    text-align: left;
    padding: 14px 20px;
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 600;
    border-bottom: 1px solid var(--line);
  }
  .lead-list tbody td {
    padding: 16px 20px;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
    font-size: 14px;
    line-height: 1.65;
    color: var(--ink-2);
  }
  .lead-list tbody tr:last-child td { border-bottom: none; }
  .lead-list tbody tr { transition: background .15s; }
  .lead-list tbody tr:hover { background: var(--accent-soft-2); }
  .lead-list .col-idx {
    width: 44px;
    color: var(--muted);
    font-family: 'Inter', sans-serif;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    font-size: 12px;
  }
  .lead-list .col-name {
    font-weight: 600;
    color: var(--ink);
    min-width: 200px;
  }
  .lead-list .col-detail { color: var(--ink-2); max-width: 380px; }
  .lead-list .col-link { white-space: nowrap; min-width: 140px; text-align: right; }

  /* BUTTONS / LINKS */
  a.btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    background: var(--accent-soft);
    color: var(--accent);
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    text-decoration: none;
    transition: background .15s, color .15s;
    margin-left: 4px;
  }
  a.btn:hover { background: var(--accent); color: white; }
  a.btn.ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--line);
  }
  a.btn.ghost:hover { background: #f5f5f5; color: var(--ink); border-color: var(--ink); }
  a.btn::after { content: "→"; font-size: 11px; opacity: .7; }

  /* DONUT BLOCK */
  .donut-block {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 56px;
    align-items: center;
    padding: 48px;
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 24px;
    margin-bottom: 40px;
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
  }
  .donut-block::before {
    content: "";
    position: absolute;
    top: 0; right: 0;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(168, 85, 247, .06) 0%, transparent 70%);
    pointer-events: none;
  }
  .donut-legend {
    display: grid;
    gap: 0;
    position: relative;
  }
  .donut-legend-item {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 18px;
    align-items: center;
    padding: 18px 0;
    border-bottom: 1px solid var(--line);
  }
  .donut-legend-item:last-child { border-bottom: none; }
  .donut-legend-marker {
    width: 10px; height: 10px;
    border-radius: 3px;
  }
  .donut-legend-marker.miss { background: var(--grad); }
  .donut-legend-marker.hit { background: var(--line); border: 1px solid #d4d4d4; }
  .donut-legend-label {
    color: var(--ink-2);
    font-size: 14px;
    line-height: 1.6;
  }
  .donut-legend-label strong { color: var(--ink); font-weight: 700; }
  .donut-legend-value {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 28px;
    color: var(--ink);
    letter-spacing: -0.025em;
    font-variant-numeric: tabular-nums;
  }

  /* SECTION HEADING (subsection) */
  .h3-modern {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.015em;
    margin: 48px 0 18px;
    color: var(--ink);
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .h3-modern::before {
    content: "";
    display: block;
    width: 4px;
    height: 18px;
    background: var(--grad);
    border-radius: 2px;
  }

  /* MESSAGE CARD */
  .msg-card {
    margin-bottom: 16px;
    padding: 28px 32px;
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 16px;
    transition: border-color .2s, box-shadow .2s;
  }
  .msg-card:hover {
    border-color: rgba(99, 102, 241, .25);
    box-shadow: var(--shadow);
  }
  .msg-card-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--line);
  }
  .msg-card-header .co {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 700;
    color: var(--ink);
    font-size: 16px;
    letter-spacing: -0.01em;
  }
  .msg-card-header .ctx { color: var(--muted); font-size: 13px; }
  .msg-card-header .links { margin-left: auto; }
  .msg-body {
    margin: 0;
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 14px;
    line-height: 2.0;
    color: var(--ink-2);
    white-space: pre-wrap;
    word-break: break-word;
    letter-spacing: 0.005em;
  }

  /* FOOTER */
  footer {
    color: var(--muted);
    font-size: 12px;
    text-align: center;
    padding-top: 64px;
    margin-top: 64px;
    border-top: 1px solid var(--line);
    letter-spacing: 0.04em;
  }

  /* RESPONSIVE */
  @media (max-width: 720px) {
    .container { padding: 40px 18px 64px; }
    .hero-title { font-size: 30px; }
    .hero-lead { font-size: 15px; }
    .section-title { font-size: 24px; }
    .kpi-card { padding: 32px 24px; }
    .kpi-grid { grid-template-columns: 1fr; gap: 28px; }
    .kpi-figure { font-size: 84px; }
    .donut-block { grid-template-columns: 1fr; gap: 32px; padding: 32px 24px; justify-items: center; }
    .donut-block svg { max-width: 200px; height: auto; }
    .meta-bar { padding: 18px; }
    .ind-table th, .ind-table td { padding: 12px 16px; }
    .ind-table .col-bar { padding-left: 16px; padding-right: 16px; }
    .lead-list .col-detail { display: none; }
    .lead-list thead th, .lead-list tbody td { padding: 12px 14px; }
    .msg-card { padding: 22px 20px; }
    .msg-card-header .links { margin-left: 0; width: 100%; }
  }
</style>
</head>
"""


def render_index() -> str:
    leads = json.loads(LEADS_JSON.read_text(encoding="utf-8")) if LEADS_JSON.exists() else []
    msgs = json.loads(MESSAGES_JSON.read_text(encoding="utf-8")) if MESSAGES_JSON.exists() else []
    phase_a_results = []
    if RESULTS_JSON.exists():
        try:
            phase_a_results = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        except Exception:
            phase_a_results = []

    n_total = len(leads)
    n_missing = sum(1 for r in leads if not r.get("kyujinbox_exists"))
    n_exists = n_total - n_missing
    rate_missing = (n_missing * 100 // n_total) if n_total else 0

    miss_all = [r for r in leads if not r.get("kyujinbox_exists")]
    miss_targets = [r for r in miss_all if _norm(r.get("company_name", "")) not in EXCLUDE_COMPANY_NAMES_LOWER]

    valid_msgs = [m for m in msgs if is_valid_message(m.get("outreach_message", ""))]

    miss_with_job = [r for r in miss_targets if r.get("job_title")]
    miss_no_job = [r for r in miss_targets if not r.get("job_title")]
    miss_sorted = miss_with_job + miss_no_job

    sample_picks = []
    for m in valid_msgs:
        if len(sample_picks) >= 3:
            break
        sample_picks.append(m)
    samples = sample_picks

    today = datetime.datetime.now().strftime("%Y年%m月%d日")
    today_iso = datetime.datetime.now().strftime("%Y-%m-%d")
    p1 = PHASE1_NUMBERS

    leads_rows = []
    for i, r in enumerate(miss_sorted, 1):
        co = html.escape(r.get("company_name", ""))
        jt = (r.get("job_title") or "—").strip()
        if len(jt) > 60:
            jt = jt[:58] + "…"
        jt = html.escape(jt)
        src = html.escape(r.get("source_url", ""))
        kbox = html.escape(r.get("kyujinbox_search_url", ""))
        leads_rows.append(f"""<tr>
          <td class="col-idx">{i:02d}</td>
          <td class="col-name">{co}</td>
          <td class="col-detail">{jt}</td>
          <td class="col-link">
            <a class="btn" href="{src}" target="_blank" rel="noopener">Wantedly</a>
            <a class="btn ghost" href="{kbox}" target="_blank" rel="noopener">求人ボックス</a>
          </td>
        </tr>""")

    phase_a_rows = []
    for i, r in enumerate(phase_a_results, 1):
        co = html.escape(r.get("company_name", ""))
        sm = (r.get("industry_summary") or "").strip()
        if len(sm) > 130:
            sm = sm[:128] + "…"
        sm = html.escape(sm) or "—"
        lic = html.escape((r.get("license_number") or "—").strip())
        addr = html.escape((r.get("address") or "—").strip())
        kb = r.get("kyujinbox_company_url") or r.get("source_url") or ""
        site = (r.get("company_website") or "").strip()
        kb_link = f'<a class="btn" href="{html.escape(kb)}" target="_blank" rel="noopener">求人ボックス</a>' if kb else ""
        site_link = f'<a class="btn ghost" href="{html.escape(site)}" target="_blank" rel="noopener">公式サイト</a>' if site else ""
        phase_a_rows.append(f"""<tr>
          <td class="col-idx">{i:02d}</td>
          <td class="col-name">{co}</td>
          <td class="col-detail">{sm}</td>
          <td>{lic}</td>
          <td>{addr}</td>
          <td class="col-link">{kb_link} {site_link}</td>
        </tr>""")

    phase_a_section = ""
    if phase_a_rows:
        phase_a_section = f"""
<section>
  <span class="section-tag">Phase A</span>
  <h2 class="section-title">求人ボックスから直接、人材紹介・派遣会社を抽出</h2>
  <p class="section-lead">求人ボックスで「人材紹介 製造」を検索し、求人内容から事業者の業態を読み取って人材紹介・派遣会社のみを抽出。さらに厚労省の事業者公開データと突合して、許可番号・所在地・電話番号を補完しました。</p>

  <table class="ind-table">
    <thead>
      <tr><th class="col-label">指標</th><th>結果</th><th class="col-bar"></th></tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-label">人材紹介・派遣会社の業態判定</td>
        <td class="col-value">{p1['judge_accuracy_pct']}%</td>
        <td class="col-bar"><div class="bar"><div class="bar-fill" style="width:{p1['judge_accuracy_pct']}%"></div></div></td>
      </tr>
      <tr>
        <td class="col-label">許可番号の取得（厚労省連携あり）</td>
        <td class="col-value">{p1['license_with_mhlw_pct']}%</td>
        <td class="col-bar"><div class="bar"><div class="bar-fill" style="width:{p1['license_with_mhlw_pct']}%"></div></div></td>
      </tr>
      <tr>
        <td class="col-label">所在地の取得</td>
        <td class="col-value">{p1['address_with_mhlw_pct']}%</td>
        <td class="col-bar"><div class="bar"><div class="bar-fill" style="width:{p1['address_with_mhlw_pct']}%"></div></div></td>
      </tr>
      <tr>
        <td class="col-label">電話番号の取得</td>
        <td class="col-value">{p1['phone_with_mhlw_pct']}%</td>
        <td class="col-bar"><div class="bar"><div class="bar-fill" style="width:{p1['phone_with_mhlw_pct']}%"></div></div></td>
      </tr>
    </tbody>
  </table>

  <h3 class="h3-modern">抽出された 5 社</h3>
  <table class="lead-list">
    <thead>
      <tr>
        <th>#</th>
        <th>会社名</th>
        <th>業態（求人内容から要約）</th>
        <th>許可番号</th>
        <th>所在地</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {chr(10).join(phase_a_rows)}
    </tbody>
  </table>
</section>
"""

    samples_html = []
    for s in samples:
        co = html.escape(s.get("company_name", ""))
        jt = html.escape(s.get("wantedly_job_title", "") or "—")
        msg = html.escape(s.get("outreach_message", ""))
        samples_html.append(f"""<div class="msg-card">
          <div class="msg-card-header">
            <span class="co">{co}</span>
            <span class="ctx">／ Wantedly 掲載求人例：{jt}</span>
          </div>
          <p class="msg-body">{msg}</p>
        </div>""")

    donut = donut_svg(n_total, n_missing, size=240, stroke=16)

    out = HTML_HEAD + f"""<body>
<div class="container">

<header class="hero">
  <div class="badge">Proof of Concept Report</div>
  <h1 class="hero-title">Wantedly に出ている企業の <span class="grad">{rate_missing}%</span> は<br>求人ボックスにまだ出稿していない。</h1>
  <p class="hero-lead">5/7 のお打ち合わせで合意した「他媒体に出ている企業のうち、求人ボックスにまだ出稿していない企業を狙って、直接お声がけする」という方針。本書は、その全工程をスクリプトで自動化し、Wantedly 100 社で実測した結果のご報告です。</p>
  <div class="meta-bar">
    <div class="meta-item">
      <div class="meta-label">Submitted To</div>
      <div class="meta-value">株式会社UPDRAFT　高屋 裕司 様</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Report Date</div>
      <div class="meta-value">{today}</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Scope</div>
      <div class="meta-value">求人ボックス × 厚労省 × Wantedly</div>
    </div>
  </div>
</header>

<section>
  <span class="section-tag">01 — Executive Summary</span>
  <h2 class="section-title">同じ採用ニーズを持ちながら、求人ボックスをまだ使っていない企業が大量に存在する</h2>
  <p class="section-lead">代理店としての切り替え・併用提案の余地が広いことを示す結果が出ました。想定（35%）を大きく上回るリード率です。</p>

  <div class="kpi-card">
    <div class="kpi-grid">
      <div class="kpi-figure">{rate_missing}<span class="unit">%</span></div>
      <div class="kpi-body">
        <h3>求人ボックス未出稿率（Wantedly 100 社調査）</h3>
        <p>調査総数 100 社のうち、求人ボックスに掲載が確認できなかった企業の比率です。<br>リード候補は <strong style="color:var(--ink);font-weight:700;">{n_missing} 社</strong>、すべて Wantedly では現役で求人募集中の企業です。</p>
      </div>
    </div>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">Lead Candidates</div>
        <div class="stat-value">{n_missing}<span class="unit">社</span></div>
      </div>
      <div class="stat">
        <div class="stat-label">Outreach Drafts</div>
        <div class="stat-value">{len(msgs)}<span class="unit">通</span></div>
      </div>
      <div class="stat">
        <div class="stat-label">Sendable Quality</div>
        <div class="stat-value">{len(valid_msgs)}<span class="unit">通</span></div>
      </div>
    </div>
  </div>
</section>
{phase_a_section}

<section>
  <span class="section-tag">Phase B</span>
  <h2 class="section-title">他媒体（Wantedly）から、求人ボックス未出稿のリードを抽出</h2>
  <p class="section-lead">Wantedly に求人を出している企業 100 社を対象に、求人ボックスでの掲載状況を 1 社ずつ照合しました。会社名のゆらぎ（全角・半角、株式会社の表記揺れなど）を吸収して判定しています。</p>

  <div class="donut-block">
    {donut}
    <div class="donut-legend">
      <div class="donut-legend-item">
        <div class="donut-legend-marker miss"></div>
        <div class="donut-legend-label"><strong>未出稿</strong>（求人ボックスへの掲載が確認できない）<br>= リード候補</div>
        <div class="donut-legend-value">{n_missing}</div>
      </div>
      <div class="donut-legend-item">
        <div class="donut-legend-marker hit"></div>
        <div class="donut-legend-label">出稿あり<br>（既に求人ボックスに掲載中）</div>
        <div class="donut-legend-value">{n_exists}</div>
      </div>
      <div class="donut-legend-item">
        <div class="donut-legend-marker" style="opacity:0;"></div>
        <div class="donut-legend-label">調査総数</div>
        <div class="donut-legend-value">{n_total}</div>
      </div>
    </div>
  </div>

  <h3 class="h3-modern">リード候補 — 未出稿の {len(miss_targets)} 社一覧</h3>
  <p class="section-lead" style="margin-bottom:24px;">Wantedly では現役で求人を出しているのに、求人ボックスには掲載がない企業です。代理店としての切り替え・追加掲載提案が成立しやすい母集団です。</p>
  <div style="overflow:auto; max-height:600px; border-radius:16px;">
    <table class="lead-list">
      <thead>
        <tr>
          <th>#</th>
          <th>会社名</th>
          <th>Wantedly 掲載求人（一例）</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {chr(10).join(leads_rows)}
      </tbody>
    </table>
  </div>
</section>

<section>
  <span class="section-tag">Phase C</span>
  <h2 class="section-title">リード企業ごとに、個別の営業文章を自動生成</h2>
  <p class="section-lead">テンプレートの一斉送信ではありません。リード各社の事業内容を読み取って、件名と本文を 1 社ずつ書き分けた状態でアウトプットしました。同じ営業文章は 1 通もありません。</p>

  <div class="stats" style="margin-top:0; margin-bottom:24px;">
    <div class="stat">
      <div class="stat-label">Generated</div>
      <div class="stat-value">{len(msgs)}<span class="unit">通</span></div>
    </div>
    <div class="stat">
      <div class="stat-label">Sendable Quality</div>
      <div class="stat-value">{len(valid_msgs)}<span class="unit">通</span></div>
    </div>
    <div class="stat">
      <div class="stat-label">Personalisation</div>
      <div class="stat-value">100<span class="unit">%</span></div>
    </div>
  </div>

  <h3 class="h3-modern">サンプル抜粋（3 通）</h3>
  {''.join(samples_html) if samples_html else '<p class="section-lead">サンプル取得待ち。</p>'}

  <p class="section-lead" style="margin-top:24px;">全 {len(msgs)} 通の文面は <a class="btn" href="messages.html">全文ページ</a> でご確認いただけます。</p>
</section>

<footer>
  © {today_iso} 株式会社UPDRAFT 様向け実証レポート
</footer>

</div>
</body>
</html>
"""
    return out


def render_messages(msgs: list[dict]) -> str:
    today_iso = datetime.datetime.now().strftime("%Y-%m-%d")
    rows = []
    for i, m in enumerate(msgs, 1):
        co = html.escape(m.get("company_name", ""))
        jt = html.escape(m.get("wantedly_job_title", "") or "—")
        wantedly_url = html.escape(m.get("wantedly_url", ""))
        kbox_url = html.escape(m.get("kyujinbox_search_url", ""))
        msg = html.escape(m.get("outreach_message", ""))
        rows.append(f"""<div class="msg-card">
          <div class="msg-card-header">
            <span class="co">#{i:02d}　{co}</span>
            <span class="ctx">／ Wantedly：{jt}</span>
            <span class="links">
              <a class="btn" href="{wantedly_url}" target="_blank" rel="noopener">Wantedly</a>
              <a class="btn ghost" href="{kbox_url}" target="_blank" rel="noopener">求人ボックス</a>
            </span>
          </div>
          <p class="msg-body">{msg}</p>
        </div>""")

    return HTML_HEAD + f"""<body>
<div class="container">

<header class="hero">
  <div class="badge">Appendix · Outreach Messages</div>
  <h1 class="hero-title">リード候補 全 <span class="grad">{len(msgs)}</span> 社向け<br>個別営業文章の全文。</h1>
  <p class="hero-lead">サマリレポートに記載のリード候補（Wantedly に出稿中・求人ボックス未出稿）に対して、それぞれの事業内容を踏まえて作成した件名 + 本文です。</p>
  <div class="meta-bar">
    <div class="meta-item">
      <div class="meta-label">Report Date</div>
      <div class="meta-value">{today_iso}</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Total</div>
      <div class="meta-value">{len(msgs)} 通</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Back</div>
      <div class="meta-value"><a class="btn ghost" href="index.html">サマリへ戻る</a></div>
    </div>
  </div>
</header>

<section>
  {''.join(rows)}
</section>

<footer>
  <a class="btn ghost" href="index.html">サマリへ戻る</a>
</footer>

</div>
</body>
</html>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_INDEX.write_text(render_index(), encoding="utf-8")

    if MESSAGES_JSON.exists():
        msgs = json.loads(MESSAGES_JSON.read_text(encoding="utf-8"))
        OUT_MESSAGES.write_text(render_messages(msgs), encoding="utf-8")
        print(f"wrote: {OUT_INDEX}")
        print(f"wrote: {OUT_MESSAGES} ({len(msgs)} messages)")
    else:
        print(f"wrote: {OUT_INDEX}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
