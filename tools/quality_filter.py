#!/usr/bin/env python3
"""A股第一层量化筛选 — 财务质量过滤，零外部依赖（仅 stdlib）。

基于第零层通过名单（~840 只），逐只调用东方财富 datacenter API
获取近 5 年财务数据 + 资产负债表数据，用 2 条指标过滤。

用法:
    python tools/quality_filter.py run              # 全量筛选
    python tools/quality_filter.py run --top 50     # 仅筛前 50 只（测试用）
    python tools/quality_filter.py probe 600519     # 单只探测
    python tools/quality_filter.py run --json       # JSON 输出
    python tools/quality_filter.py run --output reports/layer1.json

筛选标准:
    --min-cash-ratio   经营现金流/净利润 下限，默认 0.7
    --max-receivable   应收/营收 上限（%），默认 30

数据源:
    API-1: RPT_F10_FINANCE_MAINFINADATA → 现金流、利润、营收 (不限流)
    API-2: RPT_DMSK_FN_BALANCE         → 应收账款余额 (不限流)
    商誉无法通过免费 API 获取，留给 LLM Gate 2。

"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

_TIMEOUT = 20
_DEFAULT_INPUT = "reports/screener-2026-07-13.json"

# ── 已确认字段 ──
_FIELD_OCF = "NETCASH_OPERATE_PK"    # 经营现金流 (API-1)
_FIELD_NP  = "PARENTNETPROFIT"       # 归母净利润 (API-1)
_FIELD_REV = "TOTALOPERATEREVE"      # 营业总收入 (API-1)
_FIELD_REC = "ACCOUNTS_RECE"         # 应收账款余额 (API-2)
_FIELD_EQ  = "TOTAL_EQUITY"          # 净资产 (API-2)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _fetch(url, timeout=_TIMEOUT):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"请求失败 — {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    text = _fetch(url)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON 解析失败: {text[:200]}")


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _try_float(val):
    if val is None or val == "-" or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _fmt_code(code):
    code = code.strip()
    return (code, "SH") if code.startswith(("6", "9")) else (code, "SZ")


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

def fetch_financials(code):
    """获取近 5 份年报现金流/利润/营收。"""
    code_clean, market = _fmt_code(code)
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA", "sty": "ALL",
        "p": "1", "ps": "10", "sr": "-1", "st": "REPORT_DATE",
        "filter": f'(SECUCODE="{code_clean}.{market}")(REPORT_TYPE="年报")',
        "source": "HSF10", "client": "PC",
    }
    try:
        data = _fetch_json(url, params)
        result = data.get("result") or {}
        reports = result.get("data") or []
        if not reports:
            params["filter"] = f'(SECUCODE="{code_clean}.{market}")'
            data = _fetch_json(url, params)
            result = data.get("result") or {}
            reports = result.get("data") or []
        return reports[:5]
    except Exception:
        return []


def fetch_balance_sheet(code):
    """获取最新资产负债表应收账款 + 净资产。"""
    code_clean, market = _fmt_code(code)
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_DMSK_FN_BALANCE", "sty": "ALL",
        "p": "1", "ps": "1", "sr": "-1",
        "filter": f'(SECUCODE="{code_clean}.{market}")',
        "source": "HSF10", "client": "PC",
    }
    try:
        data = _fetch_json(url, params)
        result = data.get("result") or {}
        records = result.get("data") or []
        if records:
            r = records[0]
            return (
                _try_float(r.get(_FIELD_REC)),
                _try_float(r.get(_FIELD_EQ)),
            )
    except Exception:
        pass
    return None, None


def compute_metrics(code):
    """计算现金流比率和应收比率。返回 dict。"""
    reports = fetch_financials(code)
    if not reports or len(reports) < 2:
        return {"error": "财务数据不足", "reports": len(reports)}

    # ── 现金流/净利润（多年累计） ──
    total_cf, total_np, cf_years = 0.0, 0.0, 0
    for r in reports:
        cf = _try_float(r.get(_FIELD_OCF))
        np_val = _try_float(r.get(_FIELD_NP))
        if cf is not None and np_val is not None and np_val > 0:
            total_cf += cf
            total_np += np_val
            cf_years += 1

    cash_ratio = round(total_cf / total_np, 2) if total_np > 0 else None

    # ── 应收/营收（最新年报） ──
    rec, eq = fetch_balance_sheet(code)
    rev = _try_float(reports[0].get(_FIELD_REV)) if reports else None
    rec_ratio = round(rec / rev * 100, 1) if (rec is not None and rev is not None and rev > 0) else None

    return {
        "cash_ratio": cash_ratio,
        "receivable_ratio": rec_ratio,
        "cf_years": cf_years,
    }


# ---------------------------------------------------------------------------
# 筛选
# ---------------------------------------------------------------------------

def _defaults():
    return {"min_cash_ratio": 0.7, "max_receivable": 30}


def screen_one(stock, criteria):
    """对单只股票执行第一层筛选。返回 (result|None, reason|None)。"""
    code = stock.get("code", "")
    m = compute_metrics(code)

    if "error" in m:
        return None, m["error"]

    cash = m["cash_ratio"]
    rec = m.get("receivable_ratio")

    # #3: 经营现金流 / 净利润 > 0.7
    if cash is None:
        return None, "现金流数据缺失"
    if cash < criteria["min_cash_ratio"]:
        return None, f"现金流不足 ({cash:.2f})"

    # #4: 应收 / 营收 < 30%
    if rec is not None and rec > criteria["max_receivable"]:
        return None, f"应收账款过高 ({rec:.1f}%)"

    return {**stock, **m}, None


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------

def cmd_probe(args):
    """单只探测。"""
    code = args.code
    m = compute_metrics(code)
    print(f"=== {code} ===")
    for k, v in m.items():
        print(f"  {k}: {v}")


def cmd_run(args):
    """全量筛选。"""
    criteria = _defaults()
    if args.min_cash_ratio is not None: criteria["min_cash_ratio"] = args.min_cash_ratio
    if args.max_receivable is not None: criteria["max_receivable"] = args.max_receivable

    with open(args.input, "r", encoding="utf-8") as f:
        stocks = json.load(f).get("passed", [])
    if args.top:
        stocks = stocks[:args.top]

    total = len(stocks)
    verbose = not args.json

    if verbose:
        print(f"[INFO] 加载 {total} 只", file=sys.stderr)
        print(f"[INFO] 现金流/净利润 > {criteria['min_cash_ratio']}", file=sys.stderr)
        print(f"[INFO] 应收/营收 < {criteria['max_receivable']}%", file=sys.stderr)
        t0 = time.time()

    passed, rejected = [], {"cash": [], "receivable": [], "no_data": []}

    for i, s in enumerate(stocks):
        result, reason = screen_one(s, criteria)
        if result:
            passed.append(result)
        elif reason:
            if "现金流" in reason:
                rejected["cash"].append({**s, "reason": reason})
            elif "应收" in reason:
                rejected["receivable"].append({**s, "reason": reason})
            else:
                rejected["no_data"].append({**s, "reason": reason})

        if verbose and (i + 1) % 50 == 0:
            pct = (i + 1) * 100 // total
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (total - i - 1)
            print(f"[INFO] [{pct}%] {i+1}/{total}  "
                  f"pass={len(passed)}  {elapsed:.0f}s  eta={eta:.0f}s",
                  file=sys.stderr)

    if verbose:
        print(f"[INFO] 完成: {total} -> {len(passed)} pass, {elapsed:.0f}s", file=sys.stderr)

    summary = {
        "现金流不足": len(rejected["cash"]),
        "应收账款过高": len(rejected["receivable"]),
        "数据不足": len(rejected["no_data"]),
    }

    if args.json:
        out = {
            "meta": {"date": time.strftime("%Y-%m-%d"),
                     "total_screened": total, "passed": len(passed),
                     "pass_rate_pct": round(len(passed)/max(total,1)*100, 2),
                     "criteria": criteria},
            "rejected_summary": summary,
            "passed": passed,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("=" * 72)
        print("  A股第一层量化筛选 — 财务质量过滤")
        print("=" * 72)
        print(f"  输入: {total} 只  |  通过: {len(passed)} ({len(passed)/max(total,1)*100:.1f}%)")
        print(f"  现金流/净利润 > {criteria['min_cash_ratio']}")
        print(f"  应收/营收     < {criteria['max_receivable']}%")
        print()
        for label, count in sorted(summary.items(), key=lambda x: -x[1]):
            if count:
                bar = "█" * min(30, count * 30 // max(summary.values()))
                print(f"  {label:10s}  {count:>5}  {bar}")
        print()

        if passed:
            print(f"  ── 通过 ({len(passed)}) ──")
            hdr = f"  {'代码':<8s} {'名称':<10s} {'市值(亿)':>7s} {'PE':>6s} {'ROE':>6s} {'现金流比':>8s} {'应收%':>6s}"
            print(hdr)
            print("  " + "-" * 64)
            for s in sorted(passed, key=lambda x: x.get('market_cap_yi', 0) or 0, reverse=True)[:80]:
                cap = f"{s['market_cap_yi']:.0f}亿" if s.get('market_cap_yi') else "  -"
                pe  = f"{s.get('pe_ttm') or s.get('pe') or 0:.1f}"
                roe = f"{s.get('roe') or 0:.1f}%" if s.get('roe') else "  -"
                cf  = f"{s.get('cash_ratio') or 0:.2f}"
                rc  = f"{s.get('receivable_ratio') or 0:.1f}%"
                print(f"  {s['code']:<8s} {s['name']:<10s} {cap:>7s} {pe:>6s} {roe:>6s} {cf:>8s} {rc:>6s}")

    if args.output:
        out = {
            "meta": {"date": time.strftime("%Y-%m-%d"),
                     "total_screened": total, "passed": len(passed),
                     "pass_rate_pct": round(len(passed)/max(total,1)*100, 2),
                     "criteria": criteria},
            "rejected_summary": summary,
            "passed": passed,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[INFO] -> {args.output}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description="A股第一层量化筛选")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run")
    r.add_argument("--input", default=_DEFAULT_INPUT)
    r.add_argument("--top", type=int, default=None, help="前 N 只测试")
    r.add_argument("--json", action="store_true")
    r.add_argument("--output", type=str, default=None)
    r.add_argument("--min-cash-ratio", type=float, default=None)
    r.add_argument("--max-receivable", type=float, default=None)

    pb = sub.add_parser("probe")
    pb.add_argument("code")

    args = p.parse_args()
    if args.cmd == "run": cmd_run(args)
    elif args.cmd == "probe": cmd_probe(args)
    else: p.print_help()


if __name__ == "__main__":
    main()
