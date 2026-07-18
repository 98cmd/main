"""cross_filter.py の結果（unmatched_leads.json）を見やすい HTML テーブルに変換する。

EXISTS / MISSING を強調表示し、MISSING（リード候補）を上位に並べる。
"""
from __future__ import annotations
import argparse
import datetime
import json
from html import escape
from pathlib import Path


HTML_TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>他媒体 → 求人ボックス未出稿リード</title>
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
    --hit: #dc2626;
    --miss: #059669;
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
    background: var(--header); color: #fff;
    font-weight: 600; text-align: left;
    padding: 10px 12px; font-size: 12px;
    white-space: nowrap;
  }}
  tbody td {{
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    vertical-align: top;
  }}
  tbody tr:hover {{ background: var(--row-hover); }}
  tbody tr.miss td.status {{ color: var(--miss); font-weight: 700; }}
  tbody tr.exists td.status {{ color: var(--hit); }}
  td.idx {{ width: 32px; color: var(--muted); text-align: right; }}
  td.name {{ font-weight: 600; min-width: 200px; }}
  td.title {{ min-width: 240px; max-width: 400px; color: #374151; }}
  td.matched {{ font-size: 11px; color: var(--muted); max-width: 280px; word-break: break-word; }}
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
  .stats {{ display: flex; gap: 16px; margin: 8px 0 24px; flex-wrap: wrap; }}
  .stat {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 8px 14px; }}
  .stat .v {{ font-size: 18px; font-weight: 700; }}
  .stat .v.miss {{ color: var(--miss); }}
  .stat .l {{ color: var(--muted); font-size: 11px; }}
  .filter {{ margin: 8px 0 14px; }}
  .filter label {{ margin-right: 12px; cursor: pointer; }}
</style>
</head>
<body>
<h1>他媒体 → 求人ボックス未出稿リード</h1>
<div class="meta">母集団 <strong>{source}</strong> / 取得日 <strong>{date}</strong> / 求人ボックス判定 <strong>AI 一致判定</strong></div>

<div class="stats">
  <div class="stat"><div class="v">{count}</div><div class="l">調査総数</div></div>
  <div class="stat"><div class="v">{n_exists}</div><div class="l">求人ボックス出稿あり</div></div>
  <div class="stat"><div class="v miss">{n_missing}</div><div class="l">未出稿（リード候補）</div></div>
  <div class="stat"><div class="v">{rate_missing}%</div><div class="l">未出稿率</div></div>
</div>

<div class="filter">
  <label><input type="checkbox" checked id="show_miss"> 未出稿（リード候補）</label>
  <label><input type="checkbox" checked id="show_exists"> 出稿あり</label>
</div>

<table>
<thead><tr>
<th>#</th>
<th>状態</th>
<th>会社名</th>
<th>{source} 求人タイトル</th>
<th>求人ボックス判定詳細</th>
<th>リンク</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>

<script>
  const cMiss = document.getElementById('show_miss');
  const cExists = document.getElementById('show_exists');
  function applyFilter() {{
    document.querySelectorAll('tbody tr').forEach(tr => {{
      const isMiss = tr.classList.contains('miss');
      tr.style.display = (isMiss ? cMiss.checked : cExists.checked) ? '' : 'none';
    }});
  }}
  cMiss.addEventListener('change', applyFilter);
  cExists.addEventListener('change', applyFilter);
</script>
</body>
</html>
"""


def render(json_path: Path, out_path: Path) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    n = len(data)
    n_missing = sum(1 for r in data if not r.get("kyujinbox_exists"))
    n_exists = n - n_missing
    rate_missing = (n_missing * 100 // n) if n else 0
    source = data[0].get("source", "?") if data else "?"

    # MISSING を上位に、EXISTS は下位に並べる
    sorted_data = sorted(data, key=lambda r: (r.get("kyujinbox_exists", True), r.get("company_name", "")))

    rows = []
    for i, r in enumerate(sorted_data, 1):
        exists = r.get("kyujinbox_exists", True)
        cls = "exists" if exists else "miss"
        status = "出稿あり" if exists else "未出稿"
        n_listings = r.get("kyujinbox_listing_count", 0)
        matched = r.get("kyujinbox_matched_names", [])
        if isinstance(matched, str):
            matched = [m for m in matched.split("|") if m.strip()]
        # 重複した matched 名は uniq + count
        from collections import Counter
        mc = Counter(matched)
        matched_summary = "<br>".join(
            f"{escape(name)} <span style='color:var(--muted)'>×{c}</span>" for name, c in mc.most_common()[:5]
        ) if matched else '<span style="color:var(--muted)">マッチなし</span>'
        detail = (
            f'検索結果 {n_listings} 件 / マッチ {sum(mc.values())} 件<br>'
            f'<div style="margin-top:4px">{matched_summary}</div>'
        )

        links = []
        if r.get("source_url"):
            links.append(f'<a class="pill" href="{escape(r["source_url"])}" target="_blank" rel="noopener">{escape(source)} 求人</a>')
        if r.get("kyujinbox_search_url"):
            links.append(f'<a class="pill muted" href="{escape(r["kyujinbox_search_url"])}" target="_blank" rel="noopener">求人ボックス検索</a>')
        rows.append(f"""<tr class="{cls}">
<td class="idx">{i}</td>
<td class="status">{status}</td>
<td class="name">{escape(r.get("company_name",""))}</td>
<td class="title">{escape(r.get("job_title",""))}</td>
<td class="matched">{detail}</td>
<td>{" ".join(links)}</td>
</tr>""")

    html = HTML_TEMPLATE.format(
        date=datetime.datetime.fromtimestamp(json_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M JST"),
        source=escape(source),
        count=n,
        n_exists=n_exists,
        n_missing=n_missing,
        rate_missing=rate_missing,
        rows="\n".join(rows),
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="output/unmatched_leads.json")
    p.add_argument("--output", default="output/leads.html")
    args = p.parse_args()
    out = render(Path(args.input), Path(args.output))
    print(f"wrote: {out.resolve()}")


if __name__ == "__main__":
    main()
