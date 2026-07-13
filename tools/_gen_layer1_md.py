"""Generate Layer 1 markdown: filter bank/insurance, add industry classification."""
import json, sys, time, urllib.request

# ── Financial keywords to exclude ──
FIN_KW = ("银行", "保险", "人寿", "太保", "人保", "平安")

def is_finance(name):
    return any(kw in (name or "") for kw in FIN_KW)

# ── Industry fetch ──
def get_industry(code):
    """Fetch industry from RPT_F10_ORG_BASICINFO (cached in memory)."""
    code_clean, mkt = (code, "SH") if code.startswith(("6","9")) else (code, "SZ")
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    qs = f"type=RPT_F10_ORG_BASICINFO&sty=ALL&p=1&ps=1&sr=-1&filter=(SECUCODE=%22{code_clean}.{mkt}%22)&source=HSF10&client=PC"
    req = urllib.request.Request(url + "?" + qs, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        records = (data.get("result") or {}).get("data") or []
        if records:
            r = records[0]
            # 优先用申万/同花顺行业，回退到证监会行业
            for f in ("BOARD_NAME_2LEVEL", "BOARD_NAME_1LEVEL", "INDUSTRY_NAME",
                       "CSRC_INDUSTRY_NAME", "BOARD_NAME_3LEVEL"):
                v = r.get(f)
                if v and str(v).strip() and str(v).strip() != "-":
                    return str(v).strip()
            return "未分类"
    except Exception as e:
        print(f"[WARN] {code}: {e}", file=sys.stderr)
    return "未分类"

# ── Load ──
with open("reports/layer1-2026-07-13.json", "r", encoding="utf-8") as f:
    data = json.load(f)

all_passed = data["passed"]
meta = data["meta"]

# ── Filter ──
removed = [s for s in all_passed if is_finance(s.get("name", ""))]
passed = [s for s in all_passed if not is_finance(s.get("name", ""))]

print(f"剔除金融股: {len(removed)} 只, 剩余: {len(passed)} 只", file=sys.stderr)
for s in removed:
    print(f"  [-]: {s['code']} {s['name']}", file=sys.stderr)

# ── Fetch industries (with progress) ──
print(f"获取行业分类 ({len(passed)} 只)...", file=sys.stderr)
for i, s in enumerate(passed):
    code = s.get("code", "")
    s["industry"] = get_industry(code)
    if (i + 1) % 50 == 0:
        print(f"  [{i+1}/{len(passed)}]", file=sys.stderr)
    time.sleep(0.3)  # light rate limit

# ── Group by industry for display ──
from collections import OrderedDict
groups = OrderedDict()
for s in sorted(passed, key=lambda x: x.get("market_cap_yi", 0) or 0, reverse=True):
    ind = s.get("industry", "未分类")
    if ind not in groups:
        groups[ind] = []
    groups[ind].append(s)

print(f"行业数: {len(groups)}", file=sys.stderr)

# ── Generate markdown ──
lines = []
lines.append("# A股第一层量化筛选 — 通过名单（剔除银行/保险）")
lines.append("")
lines.append(f"> 日期: {meta['date']}  |  原始通过: {len(all_passed)} 只"
             f"  |  剔除金融: {len(removed)} 只  |  最终: {len(passed)} 只")
lines.append("")
lines.append("## 筛选标准")
lines.append("")
for k, v in meta["criteria"].items():
    lines.append(f"- **{k}**: {v}")
lines.append("")
lines.append("## 剔除的银行/保险股")
lines.append("")
lines.append(f"共 {len(removed)} 只：")
for s in removed:
    lines.append(f"- {s['code']} {s['name']}")
lines.append("")

lines.append("## 通过名单（按行业分组，行业内按市值降序）")
lines.append("")
lines.append(f"共 **{len(passed)}** 只，{len(groups)} 个行业。")
lines.append("")

for ind, stocks in groups.items():
    lines.append(f"### {ind}（{len(stocks)} 只）")
    lines.append("")
    lines.append("| # | 代码 | 名称 | 市值(亿) | PE(TTM) | ROE(%) | CF/NP | AR/Rev(%) |")
    lines.append("|---|------|------|:---:|:---:|:---:|:---:|:---:|")
    for j, s in enumerate(stocks, 1):
        code = s.get('code', '')
        name = s.get('name', '')
        cap = s.get('market_cap_yi')
        cap_s = f'{cap:.0f}' if cap else '-'
        pe = s.get('pe_ttm') or s.get('pe') or ''
        pe_s = f'{pe:.1f}' if pe else '-'
        roe = s.get('roe')
        roe_s = f'{roe:.2f}' if roe else '-'
        cf = s.get('cash_ratio')
        cf_s = f'{cf:.2f}' if cf else '-'
        rc = s.get('receivable_ratio')
        rc_s = f'{rc:.1f}' if rc is not None else '-'
        lines.append(f'| {j} | {code} | {name} | {cap_s} | {pe_s} | {roe_s} | {cf_s} | {rc_s} |')
    lines.append("")

with open("reports/layer1-passed-2026-07-13.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Done -> reports/layer1-passed-2026-07-13.md", file=sys.stderr)
