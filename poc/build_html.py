"""results.json を見やすい HTML テーブルに変換する。"""
from __future__ import annotations
import argparse
import json
from html import escape
from pathlib import Path


HTML_TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>求人ボックス PoC 抽出リスト</title>
<style>
  :root {{
    --bg: #fafafa;
    --card: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --border: #e5e7eb;
    --accent: #2563eb;
    --header: #111827;
    --row-hover: #f3f4f6;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, "Segoe UI", "Yu Gothic UI", "Hiragino Sans", "Meiryo", sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    font-size: 13px;
    line-height: 1.55;
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; }}
  .meta {{ color: var(--muted); margin-bottom: 16px; }}
  .meta strong {{ color: var(--text); }}
  table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }}
  thead th {{
    position: sticky; top: 0;
    background: var(--header);
    color: #fff;
    font-weight: 600;
    text-align: left;
    padding: 10px 12px;
    font-size: 12px;
    white-space: nowrap;
  }}
  tbody td {{
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    vertical-align: top;
  }}
  tbody tr:hover {{ background: var(--row-hover); }}
  td.idx {{ width: 32px; color: var(--muted); text-align: right; }}
  td.name {{ font-weight: 600; min-width: 160px; }}
  td.summary {{ min-width: 280px; max-width: 380px; }}
  td.lic, td.phone {{ font-family: ui-monospace, "SFMono-Regular", Menlo, monospace; white-space: nowrap; font-size: 12px; color: #374151; }}
  td.addr {{ min-width: 200px; max-width: 280px; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .pill {{
    display: inline-block;
    background: #eff6ff; color: #1d4ed8;
    border: 1px solid #dbeafe;
    padding: 2px 8px; border-radius: 999px;
    font-size: 11px; font-weight: 500;
    margin-right: 4px;
    text-decoration: none;
  }}
  .pill.muted {{ background: #f3f4f6; color: var(--muted); border-color: var(--border); }}
  details summary {{ cursor: pointer; color: var(--muted); font-size: 12px; }}
  details[open] summary {{ margin-bottom: 6px; }}
  details .body {{ background: #f9fafb; padding: 10px 12px; border-radius: 6px; font-size: 12px; max-width: 480px; white-space: pre-wrap; }}
  .stats {{ display: flex; gap: 16px; margin: 8px 0 24px; flex-wrap: wrap; }}
  .stat {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 8px 14px; }}
  .stat .v {{ font-size: 18px; font-weight: 700; }}
  .stat .l {{ color: var(--muted); font-size: 11px; }}
  .empty {{ color: var(--muted); font-style: italic; font-size: 11px; }}
</style>
</head>
<body>
<h1>求人ボックス × 厚労省 抽出リスト</h1>
<div class="meta">クエリ <strong>「人材紹介 製造」</strong> / 取得日 <strong>{date}</strong> / モデル <strong>claude-sonnet-4-6</strong></div>

<div class="stats">
  <div class="stat"><div class="v">{count}</div><div class="l">件数</div></div>
  <div class="stat"><div class="v">{rate_lic}%</div><div class="l">許可番号</div></div>
  <div class="stat"><div class="v">{rate_addr}%</div><div class="l">住所</div></div>
  <div class="stat"><div class="v">{rate_phone}%</div><div class="l">電話</div></div>
  <div class="stat"><div class="v">{rate_web}%</div><div class="l">自社サイト</div></div>
  <div class="stat"><div class="v">{rate_co}%</div><div class="l">求人ボックス会社ページ</div></div>
</div>

<table>
<thead><tr>
<th>#</th>
<th>会社名</th>
<th>業種要約</th>
<th>許可番号</th>
<th>住所</th>
<th>電話</th>
<th>リンク</th>
<th>営業文案</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""


def percent(num: int, denom: int) -> int:
    return num * 100 // denom if denom else 0


def render(json_path: Path, out_path: Path) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    n = len(data)
    rate_lic = percent(sum(1 for r in data if r.get("license_number")), n)
    rate_addr = percent(sum(1 for r in data if r.get("address")), n)
    rate_phone = percent(sum(1 for r in data if r.get("phone")), n)
    rate_web = percent(sum(1 for r in data if r.get("company_website")), n)
    rate_co = percent(sum(1 for r in data if r.get("kyujinbox_company_url")), n)

    rows = []
    for i, r in enumerate(data, 1):
        # リンクピル
        links = []
        if r.get("source_url"):
            links.append(f'<a class="pill" href="{escape(r["source_url"])}" target="_blank" rel="noopener">求人ページ</a>')
        if r.get("kyujinbox_company_url"):
            links.append(f'<a class="pill" href="{escape(r["kyujinbox_company_url"])}" target="_blank" rel="noopener">会社ページ</a>')
        if r.get("company_website"):
            links.append(f'<a class="pill" href="{escape(r["company_website"])}" target="_blank" rel="noopener">公式サイト</a>')
        if not links:
            links.append('<span class="empty">なし</span>')

        msg = r.get("outreach_message", "") or ""
        msg_block = (
            f'<details><summary>本文を表示</summary><div class="body">{escape(msg)}</div></details>'
            if msg else '<span class="empty">未生成</span>'
        )

        rows.append(f"""<tr>
<td class="idx">{i}</td>
<td class="name">{escape(r.get("company_name",""))}</td>
<td class="summary">{escape(r.get("industry_summary",""))}</td>
<td class="lic">{escape(r.get("license_number","") or "")}</td>
<td class="addr">{escape(r.get("address","") or "")}</td>
<td class="phone">{escape(r.get("phone","") or "")}</td>
<td>{" ".join(links)}</td>
<td>{msg_block}</td>
</tr>""")

    html = HTML_TEMPLATE.format(
        date=Path(json_path).stat().st_mtime,  # placeholder
        count=n,
        rate_lic=rate_lic, rate_addr=rate_addr, rate_phone=rate_phone,
        rate_web=rate_web, rate_co=rate_co,
        rows="\n".join(rows),
    )
    # date を ISO 形式に置換
    import datetime
    html = html.replace(
        str(Path(json_path).stat().st_mtime),
        datetime.datetime.fromtimestamp(Path(json_path).stat().st_mtime).strftime("%Y-%m-%d %H:%M JST"),
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="output/results_20_companies.json")
    p.add_argument("--output", default="output/results.html")
    args = p.parse_args()
    out = render(Path(args.input), Path(args.output))
    print(f"wrote: {out.resolve()}")


if __name__ == "__main__":
    main()
