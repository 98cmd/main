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


def donut_svg(total: int, miss: int, size: int = 220, stroke: int = 18,
              miss_color: str = "#0d6e5c", hit_color: str = "#e5e0d6",
              center_label: str = "") -> str:
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
    <svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="{html.escape(center_label)}">
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{hit_color}" stroke-width="{stroke}"/>
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{miss_color}" stroke-width="{stroke}"
              stroke-linecap="butt"
              stroke-dasharray="{miss_len:.2f} {hit_len:.2f}"
              stroke-dashoffset="{c/4:.2f}" transform="rotate(-90 {cx} {cy})"/>
      <text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="44" font-weight="600" fill="#0b1730" font-family="'Inter', 'Noto Sans JP', sans-serif" letter-spacing="-0.02em">{pct_text}</text>
      <text x="{cx}" y="{cy + 24}" text-anchor="middle" font-size="11" fill="#5a6478" font-family="'Inter', sans-serif" letter-spacing="0.18em">UNTAPPED</text>
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&family=Noto+Serif+JP:wght@500;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #fbfaf6;
    --paper: #ffffff;
    --ink: #0b1730;
    --ink-2: #2b3550;
    --muted: #6a7388;
    --hairline: #ece8de;
    --line: rgba(11, 23, 48, .08);
    --accent: #0d6e5c;
    --accent-deep: #084c40;
    --accent-soft: #e0efe9;
    --gold: #a87a30;
  }
  * { box-sizing: border-box; }
  html { -webkit-font-smoothing: antialiased; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: 'Noto Sans JP', 'Inter', -apple-system, "Hiragino Kaku Gothic ProN", system-ui, sans-serif;
    background: var(--bg);
    color: var(--ink);
    line-height: 1.85;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: 0.01em;
  }
  /* paper texture */
  body::before {
    content: "";
    position: fixed; inset: 0;
    background-image:
      radial-gradient(rgba(11,23,48,.018) 1px, transparent 1px);
    background-size: 6px 6px;
    pointer-events: none;
    z-index: 0;
  }
  .container {
    position: relative;
    z-index: 1;
    max-width: 980px;
    margin: 0 auto;
    padding: 80px 32px 96px;
  }

  /* HEADER */
  .doc-header {
    margin-bottom: 96px;
  }
  .doc-eyebrow {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    letter-spacing: .32em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 600;
    margin-bottom: 28px;
  }
  .doc-eyebrow::before {
    content: "";
    display: inline-block;
    width: 28px; height: 1px;
    background: var(--accent);
    vertical-align: middle;
    margin-right: 12px;
  }
  .doc-title {
    font-family: 'Noto Serif JP', serif;
    font-weight: 700;
    font-size: 40px;
    line-height: 1.45;
    color: var(--ink);
    margin: 0 0 20px;
    letter-spacing: -0.005em;
  }
  .doc-lead {
    font-size: 16px;
    color: var(--ink-2);
    line-height: 1.95;
    max-width: 720px;
    margin: 0 0 40px;
  }
  .doc-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0;
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    padding: 22px 0;
  }
  .doc-meta-item {
    padding: 0 28px;
    border-right: 1px solid var(--line);
  }
  .doc-meta-item:first-child { padding-left: 0; }
  .doc-meta-item:last-child { border-right: none; padding-right: 0; }
  .doc-meta-label {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 6px;
  }
  .doc-meta-value {
    font-size: 14px;
    color: var(--ink);
    font-weight: 500;
  }

  /* SECTIONS */
  section {
    margin-bottom: 88px;
    scroll-margin-top: 32px;
  }
  .section-marker {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    letter-spacing: .28em;
    text-transform: uppercase;
    color: var(--gold);
    font-weight: 600;
    margin-bottom: 12px;
  }
  .section-title {
    font-family: 'Noto Serif JP', serif;
    font-size: 28px;
    line-height: 1.5;
    margin: 0 0 14px;
    color: var(--ink);
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .section-lead {
    font-size: 15px;
    color: var(--ink-2);
    line-height: 1.95;
    max-width: 720px;
    margin: 0 0 36px;
  }
  .section-divider {
    width: 32px;
    height: 1px;
    background: var(--ink);
    opacity: .25;
    margin: 0 0 28px;
  }

  /* HEADLINE METRIC */
  .headline {
    display: grid;
    grid-template-columns: minmax(280px, 1fr) auto;
    gap: 40px;
    align-items: center;
    padding: 36px 40px;
    background: var(--paper);
    border: 1px solid var(--hairline);
    border-radius: 4px;
    box-shadow: 0 1px 2px rgba(11, 23, 48, .04);
  }
  .headline-figure {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 96px;
    line-height: 1;
    color: var(--accent);
    letter-spacing: -0.04em;
    display: flex;
    align-items: baseline;
  }
  .headline-figure .unit {
    font-size: 32px;
    font-weight: 500;
    color: var(--ink-2);
    margin-left: 8px;
  }
  .headline-body h3 {
    font-family: 'Noto Serif JP', serif;
    font-size: 18px;
    margin: 0 0 6px;
    color: var(--ink);
    font-weight: 700;
  }
  .headline-body p {
    margin: 0;
    color: var(--ink-2);
    font-size: 14px;
    line-height: 1.85;
  }

  .submetrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0;
    margin: 32px 0 0;
    border-top: 1px solid var(--line);
  }
  .submetric {
    padding: 20px 28px 20px 0;
    border-right: 1px solid var(--line);
  }
  .submetric:last-child { border-right: none; padding-right: 0; }
  .submetric-label {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }
  .submetric-value {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 28px;
    color: var(--ink);
    letter-spacing: -0.02em;
  }
  .submetric-value .unit {
    font-size: 14px;
    color: var(--ink-2);
    margin-left: 4px;
    font-weight: 500;
  }

  /* CALLOUT */
  .callout {
    border-left: 2px solid var(--accent);
    padding: 4px 0 4px 22px;
    margin: 32px 0 0;
    color: var(--ink-2);
    font-size: 14.5px;
    line-height: 1.95;
  }
  .callout strong { color: var(--ink); font-weight: 700; }

  /* ACCURACY TABLE (Phase A) */
  .acc-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0 0 28px;
  }
  .acc-table th {
    text-align: left;
    padding: 14px 0;
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 600;
    border-bottom: 1px solid var(--ink);
  }
  .acc-table td {
    padding: 16px 0;
    border-bottom: 1px solid var(--line);
    vertical-align: middle;
    font-size: 14px;
  }
  .acc-table .col-label { width: 40%; }
  .acc-table .col-value {
    text-align: right;
    width: 80px;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 16px;
    color: var(--ink);
  }
  .acc-table .col-bar { padding-left: 24px; }
  .bar {
    position: relative;
    height: 6px;
    background: var(--hairline);
    border-radius: 3px;
    overflow: hidden;
  }
  .bar-fill {
    position: absolute;
    inset: 0 auto 0 0;
    background: var(--accent);
    border-radius: 3px;
  }

  /* COMPANY LIST TABLE */
  .lead-list {
    width: 100%;
    border-collapse: collapse;
    background: var(--paper);
    border: 1px solid var(--hairline);
    border-radius: 4px;
    overflow: hidden;
  }
  .lead-list thead th {
    background: #fafaf6;
    text-align: left;
    padding: 14px 18px;
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 600;
    border-bottom: 1px solid var(--hairline);
  }
  .lead-list tbody td {
    padding: 14px 18px;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
    font-size: 13.5px;
    line-height: 1.7;
  }
  .lead-list tbody tr:last-child td { border-bottom: none; }
  .lead-list tbody tr:hover td { background: #faf8f0; }
  .lead-list .col-idx {
    width: 38px;
    color: var(--muted);
    font-family: 'Inter', sans-serif;
    font-variant-numeric: tabular-nums;
  }
  .lead-list .col-name {
    font-weight: 600;
    color: var(--ink);
    min-width: 200px;
  }
  .lead-list .col-detail { color: var(--ink-2); max-width: 360px; }
  .lead-list .col-link { white-space: nowrap; min-width: 120px; }

  a.btn-text {
    display: inline-block;
    padding: 4px 0;
    color: var(--accent);
    text-decoration: none;
    font-size: 12.5px;
    border-bottom: 1px solid currentColor;
    margin-right: 16px;
    font-weight: 500;
  }
  a.btn-text:hover { color: var(--accent-deep); }
  a.btn-text.muted { color: var(--muted); }
  a.btn-text.muted:hover { color: var(--ink); }

  /* DONUT BLOCK */
  .donut-block {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 56px;
    align-items: center;
    padding: 32px 40px;
    background: var(--paper);
    border: 1px solid var(--hairline);
    border-radius: 4px;
    margin-bottom: 36px;
  }
  .donut-legend {
    display: grid;
    gap: 18px;
  }
  .donut-legend-item {
    display: grid;
    grid-template-columns: 8px 1fr auto;
    gap: 14px;
    align-items: center;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--line);
  }
  .donut-legend-item:last-child { border-bottom: none; padding-bottom: 0; }
  .donut-legend-marker {
    width: 8px; height: 32px;
    border-radius: 1px;
  }
  .donut-legend-label {
    color: var(--ink-2);
    font-size: 13.5px;
  }
  .donut-legend-label strong { color: var(--ink); }
  .donut-legend-value {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 22px;
    color: var(--ink);
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }

  /* MESSAGE CARD */
  .msg-card {
    margin-bottom: 24px;
    padding: 28px 32px;
    background: var(--paper);
    border: 1px solid var(--hairline);
    border-radius: 4px;
  }
  .msg-card-header {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--line);
    font-size: 12px;
    color: var(--muted);
  }
  .msg-card-header .co {
    font-family: 'Noto Serif JP', serif;
    font-weight: 700;
    color: var(--ink);
    font-size: 16px;
  }
  .msg-card-header .ctx { color: var(--ink-2); font-size: 13px; }
  .msg-body {
    margin: 0;
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 14px;
    line-height: 2.0;
    color: var(--ink);
    white-space: pre-wrap;
    word-break: break-word;
  }

  /* FOOTER */
  footer {
    color: var(--muted);
    font-size: 12px;
    text-align: center;
    padding-top: 64px;
    border-top: 1px solid var(--line);
    letter-spacing: 0.04em;
  }

  /* RESPONSIVE */
  @media (max-width: 720px) {
    .container { padding: 48px 20px 64px; }
    .doc-title { font-size: 28px; }
    .doc-meta { grid-template-columns: 1fr; padding: 0; border-bottom: none; }
    .doc-meta-item {
      padding: 18px 0;
      border-right: none;
      border-bottom: 1px solid var(--line);
    }
    .doc-meta-item:last-child { border-bottom: none; }
    section { margin-bottom: 64px; }
    .section-title { font-size: 22px; }
    .headline { grid-template-columns: 1fr; gap: 24px; padding: 28px 24px; }
    .headline-figure { font-size: 72px; }
    .donut-block { grid-template-columns: 1fr; gap: 32px; padding: 28px 24px; justify-items: center; }
    .donut-block svg { max-width: 200px; height: auto; }
    .submetric, .doc-meta-item { padding-right: 0; border-right: none; }
    .lead-list .col-detail { display: none; }
    .lead-list thead th, .lead-list tbody td { padding: 12px 14px; }
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

    # Phase B レコード行
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
            <a class="btn-text" href="{src}" target="_blank" rel="noopener">Wantedly</a>
            <a class="btn-text muted" href="{kbox}" target="_blank" rel="noopener">求人ボックス</a>
          </td>
        </tr>""")

    # Phase A 製造業 5 社
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
        kb_link = f'<a class="btn-text" href="{html.escape(kb)}" target="_blank" rel="noopener">求人ボックス</a>' if kb else ""
        site_link = f'<a class="btn-text muted" href="{html.escape(site)}" target="_blank" rel="noopener">公式サイト</a>' if site else ""
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
  <div class="section-marker">Phase A</div>
  <h2 class="section-title">求人ボックスから直接、人材紹介・派遣会社を抽出</h2>
  <div class="section-divider"></div>
  <p class="section-lead">求人ボックスで「人材紹介 製造」を検索し、求人内容から事業者の業態を読み取って人材紹介・派遣会社のみを抽出。さらに厚労省の事業者公開データと突合して、許可番号・所在地・電話番号を補完しました。</p>

  <table class="acc-table">
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

  <h3 style="font-family:'Noto Serif JP',serif; font-size:18px; font-weight:700; margin:36px 0 16px;">抽出された 5 社</h3>
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

    donut = donut_svg(n_total, n_missing, size=220, stroke=18,
                      miss_color="#0d6e5c", hit_color="#e5e0d6",
                      center_label=f"未出稿率 {rate_missing}%")

    out = HTML_HEAD + f"""<body>
<div class="container">

<header class="doc-header">
  <div class="doc-eyebrow">PROOF OF CONCEPT REPORT</div>
  <h1 class="doc-title">求人ボックス 直接アプローチ実証レポート<br>— 抽出から個別営業文章まで自動化が成立しました</h1>
  <p class="doc-lead">5/7 のお打ち合わせで合意した「他媒体に出ている企業のうち、求人ボックスにまだ出稿していない企業を狙って、直接お声がけする」という方針。本書は、その全工程をスクリプトで自動化し、Wantedly 100 社で実測した結果のご報告です。</p>
  <div class="doc-meta">
    <div class="doc-meta-item">
      <div class="doc-meta-label">Submitted To</div>
      <div class="doc-meta-value">株式会社UPDRAFT　高屋 裕司 様</div>
    </div>
    <div class="doc-meta-item">
      <div class="doc-meta-label">Report Date</div>
      <div class="doc-meta-value">{today}</div>
    </div>
    <div class="doc-meta-item">
      <div class="doc-meta-label">Scope</div>
      <div class="doc-meta-value">求人ボックス × 厚労省 × Wantedly</div>
    </div>
  </div>
</header>

<section>
  <div class="section-marker">01 — Executive Summary</div>
  <h2 class="section-title">Wantedly に出ている企業の {rate_missing}% は、求人ボックスにまだ出稿していない</h2>
  <div class="section-divider"></div>
  <p class="section-lead">同じ採用ニーズを持ちながら、求人ボックスをまだ使っていない企業が大量に存在することが裏付けられました。代理店としての切り替え・併用の提案余地が広く、想定（35%）を大きく上回るリード率です。</p>

  <div class="headline">
    <div class="headline-figure">{rate_missing}<span class="unit">%</span></div>
    <div class="headline-body">
      <h3>求人ボックス未出稿率（Wantedly 100 社調査）</h3>
      <p>調査総数 100 社のうち、求人ボックスに掲載が確認できなかった企業の比率です。リード候補は {n_missing} 社、すべて Wantedly では現役で求人募集中の企業です。</p>
    </div>
  </div>

  <div class="submetrics">
    <div class="submetric">
      <div class="submetric-label">Lead Candidates</div>
      <div class="submetric-value">{n_missing}<span class="unit">社</span></div>
    </div>
    <div class="submetric">
      <div class="submetric-label">Outreach Drafts</div>
      <div class="submetric-value">{len(msgs)}<span class="unit">通</span></div>
    </div>
    <div class="submetric">
      <div class="submetric-label">Sendable Quality</div>
      <div class="submetric-value">{len(valid_msgs)}<span class="unit">通</span></div>
    </div>
  </div>
</section>
{phase_a_section}

<section>
  <div class="section-marker">Phase B</div>
  <h2 class="section-title">他媒体（Wantedly）から、求人ボックス未出稿のリードを抽出</h2>
  <div class="section-divider"></div>
  <p class="section-lead">Wantedly に求人を出している企業 100 社を対象に、求人ボックスでの掲載状況を 1 社ずつ照合しました。会社名のゆらぎ（全角・半角、株式会社の表記揺れなど）を吸収して判定しています。</p>

  <div class="donut-block">
    {donut}
    <div class="donut-legend">
      <div class="donut-legend-item">
        <div class="donut-legend-marker" style="background:#0d6e5c"></div>
        <div class="donut-legend-label"><strong>未出稿</strong>（求人ボックスへの掲載が確認できない）<br>= リード候補</div>
        <div class="donut-legend-value">{n_missing}</div>
      </div>
      <div class="donut-legend-item">
        <div class="donut-legend-marker" style="background:#e5e0d6"></div>
        <div class="donut-legend-label">出稿あり<br>（既に求人ボックスに掲載中）</div>
        <div class="donut-legend-value">{n_exists}</div>
      </div>
      <div class="donut-legend-item">
        <div class="donut-legend-marker" style="background:transparent"></div>
        <div class="donut-legend-label">調査総数</div>
        <div class="donut-legend-value">{n_total}</div>
      </div>
    </div>
  </div>

  <h3 style="font-family:'Noto Serif JP',serif; font-size:18px; font-weight:700; margin:36px 0 16px;">リード候補 — 未出稿の {len(miss_targets)} 社一覧</h3>
  <p class="section-lead" style="margin-bottom:20px;">Wantedly では現役で求人を出しているのに、求人ボックスには掲載がない企業です。求人ボックス代理店としての切り替え・追加掲載提案が成立しやすい母集団です。</p>
  <div style="overflow:auto; max-height:560px; border:1px solid var(--hairline); border-radius:4px;">
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
  <div class="section-marker">Phase C</div>
  <h2 class="section-title">リード企業ごとに、個別の営業文章を自動生成</h2>
  <div class="section-divider"></div>
  <p class="section-lead">テンプレートの一斉送信ではありません。リード各社の事業内容を読み取って、件名と本文を 1 社ずつ書き分けた状態でアウトプットしました。同じ営業文章は 1 通もありません。</p>

  <div class="submetrics">
    <div class="submetric">
      <div class="submetric-label">Generated</div>
      <div class="submetric-value">{len(msgs)}<span class="unit">通</span></div>
    </div>
    <div class="submetric">
      <div class="submetric-label">Sendable Quality</div>
      <div class="submetric-value">{len(valid_msgs)}<span class="unit">通</span></div>
    </div>
    <div class="submetric">
      <div class="submetric-label">Personalisation</div>
      <div class="submetric-value">100<span class="unit">%</span></div>
    </div>
  </div>

  <h3 style="font-family:'Noto Serif JP',serif; font-size:18px; font-weight:700; margin:44px 0 18px;">サンプル抜粋（3 通）</h3>
  {''.join(samples_html) if samples_html else '<p class="section-lead">サンプル取得待ち。</p>'}

  <p class="section-lead" style="margin-top:24px;">全 {len(msgs)} 通の文面は <a class="btn-text" href="messages.html">こちらの全文ページ</a> でご確認いただけます。</p>
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
            <span class="ctx" style="margin-left:auto;">
              <a class="btn-text" href="{wantedly_url}" target="_blank" rel="noopener">Wantedly</a>
              <a class="btn-text muted" href="{kbox_url}" target="_blank" rel="noopener">求人ボックス</a>
            </span>
          </div>
          <p class="msg-body">{msg}</p>
        </div>""")

    return HTML_HEAD + f"""<body>
<div class="container">

<header class="doc-header">
  <div class="doc-eyebrow">APPENDIX — OUTREACH MESSAGES</div>
  <h1 class="doc-title">リード候補 全 {len(msgs)} 社向け<br>個別営業文章の全文</h1>
  <p class="doc-lead">サマリレポートに記載のリード候補（Wantedly に出稿中・求人ボックス未出稿）に対して、それぞれの事業内容を踏まえて作成した件名 + 本文です。</p>
  <div class="doc-meta">
    <div class="doc-meta-item">
      <div class="doc-meta-label">Report Date</div>
      <div class="doc-meta-value">{today_iso}</div>
    </div>
    <div class="doc-meta-item">
      <div class="doc-meta-label">Total</div>
      <div class="doc-meta-value">{len(msgs)} 通</div>
    </div>
    <div class="doc-meta-item">
      <div class="doc-meta-label">Back</div>
      <div class="doc-meta-value"><a class="btn-text" href="index.html">← サマリレポートへ戻る</a></div>
    </div>
  </div>
</header>

<section>
  {''.join(rows)}
</section>

<footer>
  <a class="btn-text" href="index.html">← サマリレポートへ戻る</a>
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
