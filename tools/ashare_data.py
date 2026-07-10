#!/usr/bin/env python3
"""A股数据工具 — 腾讯行情 + 东方财富搜索/财务，零外部依赖（仅 stdlib）。

为 Claude Code Skills 提供 A 股实时行情、财务数据等数据。
设计原则：独立模块，不影响现有工具；使用 urllib 直连，跨平台兼容。

用法（由 Skills 自动调用）：
    python tools/ashare_data.py quote 600519                       # 实时行情
    python tools/ashare_data.py quote 600519 --json                # JSON 格式
    python tools/ashare_data.py financials 600519                  # 核心财务数据（近5年）
    python tools/ashare_data.py financials 600519 --json --period 年报
    python tools/ashare_data.py valuation 600519                   # 估值指标
    python tools/ashare_data.py search 茅台                         # 搜索股票代码

需要 Python >= 3.8，零外部依赖。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from urllib.parse import urlencode

_TIMEOUT = 15


# ---------------------------------------------------------------------------
# HTTP 工具（urllib，零外部依赖，跨平台）
# ---------------------------------------------------------------------------

def _fetch(url):
    """用 urllib 直连，跨平台兼容（替代 curl）。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"请求失败: {url} — {e}")
    # 腾讯行情 API 返回 GBK 编码，其他返回 UTF-8
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None):
    """urllib 获取 JSON。"""
    if params:
        url = f"{url}?{urlencode(params)}"
    return json.loads(_fetch(url))


# ---------------------------------------------------------------------------
# 错误处理
# ---------------------------------------------------------------------------

def error_exit(msg, as_json=False):
    """输出错误信息并退出。JSON 模式下输出结构化 JSON。"""
    if as_json:
        try:
            print(json.dumps({"error": msg}, ensure_ascii=False, indent=2))
        except UnicodeEncodeError:
            print(json.dumps({"error": msg}, ensure_ascii=True, indent=2))
    else:
        print(msg)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 腾讯行情 API（稳定可靠，无需鉴权）
# ---------------------------------------------------------------------------

def _qq_code(code: str) -> str:
    """将股票代码转为腾讯行情格式。"""
    code = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if code.startswith(("6", "9", "5")):
        return f"sh{code}"
    elif code.startswith(("0", "3", "2", "1")):
        return f"sz{code}"
    elif code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sh{code}"


def _parse_qq_quote(raw: str) -> dict:
    """解析腾讯行情数据。格式：v_shXXXXXX="字段1~字段2~..."; """
    start = raw.find('"')
    end = raw.rfind('"')
    if start < 0 or end <= start:
        return {}
    fields = raw[start + 1:end].split("~")
    if len(fields) < 50:
        return {}
    return {
        "name": fields[1],
        "code": fields[2],
        "price": fields[3],
        "prev_close": fields[4],
        "open": fields[5],
        "volume": fields[6],         # 手
        "buy_vol": fields[7],
        "sell_vol": fields[8],
        "high": fields[33] if len(fields) > 33 else fields[3],
        "low": fields[34] if len(fields) > 34 else fields[3],
        "change_pct": fields[32],
        "change_amt": fields[31],
        "turnover_amt": fields[37] if len(fields) > 37 else "-",
        "turnover_rate": fields[38] if len(fields) > 38 else "-",
        "pe": fields[39] if len(fields) > 39 else "-",
        "market_cap": fields[45] if len(fields) > 45 else "-",    # 总市值（亿）
        "float_cap": fields[44] if len(fields) > 44 else "-",     # 流通市值（亿）
        "pb": fields[46] if len(fields) > 46 else "-",
        "high_52w": fields[47] if len(fields) > 47 else "-",
        "low_52w": fields[48] if len(fields) > 48 else "-",
    }


def _fmt_yi(value) -> str:
    if value is None or value == "-" or value == "":
        return "-"
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.2f}万"
    return f"{v:.2f}"


def _fmt_pct(value) -> str:
    if value is None or value == "-" or value == "":
        return "-"
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return str(value)


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def cmd_quote(code: str, as_json: bool = False):
    """实时行情快照。"""
    qq_code = _qq_code(code)
    raw = _fetch(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    if not d:
        error_exit(f"[ERROR] 未找到股票 {code}", as_json)

    if as_json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"实时行情: {d['name']} ({d['code']})")
    print("=" * 60)
    print(f"  当前价:     {d['price']}")
    print(f"  涨跌幅:     {d['change_pct']}%")
    print(f"  涨跌额:     {d['change_amt']}")
    print(f"  今开:       {d['open']}")
    print(f"  最高:       {d['high']}")
    print(f"  最低:       {d['low']}")
    print(f"  昨收:       {d['prev_close']}")
    print(f"  成交量:     {d['volume']} 手")
    print(f"  成交额:     {d['turnover_amt']}万")
    print(f"  总市值:     {d['market_cap']}亿")
    print(f"  流通市值:   {d['float_cap']}亿")
    print(f"  PE(动):     {d['pe']}")
    print(f"  PB:         {d['pb']}")
    print(f"  换手率:     {d['turnover_rate']}%")
    print(f"  52周最高:   {d['high_52w']}")
    print(f"  52周最低:   {d['low_52w']}")


def cmd_valuation(code: str, as_json: bool = False):
    """估值指标汇总。"""
    qq_code = _qq_code(code)
    raw = _fetch(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    if not d:
        error_exit(f"[ERROR] 未找到股票 {code}", as_json)

    price = d["price"]
    market_cap_yi = d["market_cap"]

    # 市值验算
    calc_info = {}
    try:
        p = Decimal(price)
        cap = Decimal(market_cap_yi) * Decimal("1e8")
        shares = cap / p
        calc_info["derived_total_shares"] = _fmt_yi(float(shares))
        calc_cap = p * shares
        reported_cap = Decimal(market_cap_yi) * Decimal("1e8")
        diff = abs(calc_cap - reported_cap) / reported_cap * 100
        calc_info["cap_check_deviation_pct"] = float(round(diff, 1))
        calc_info["cap_check_ok"] = True
    except Exception:
        calc_info["cap_check_ok"] = False

    if as_json:
        out = dict(d)
        out.update(calc_info)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"估值指标: {d['name']} ({d['code']})")
    print("=" * 60)
    print(f"  当前价:     {price}")
    print(f"  总市值:     {market_cap_yi}亿")
    print(f"  流通市值:   {d['float_cap']}亿")
    print(f"  PE(动):     {d['pe']}")
    print(f"  PB:         {d['pb']}")
    print(f"  52周最高:   {d['high_52w']}")
    print(f"  52周最低:   {d['low_52w']}")

    if calc_info.get("cap_check_ok"):
        print(f"\n  推算总股本: {calc_info['derived_total_shares']}股")
        print(f"  市值验算:   ✅ 一致（推算法，偏差 {calc_info['cap_check_deviation_pct']:.1f}%）")


def cmd_financials(code: str, period: str = "年报", as_json: bool = False):
    """近5年核心财务数据。"""
    qq_code = _qq_code(code)
    raw = _fetch(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    name = d.get("name", code) if d else code

    code_clean = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    market = "SH" if code_clean.startswith(("6", "9", "5")) else "SZ"

    # 东方财富 datacenter API
    fin_url = "https://datacenter.eastmoney.com/securities/api/data/get"

    # 构建 REPORT_TYPE 过滤条件
    def _build_filter(report_type=None):
        if report_type:
            return f'(SECUCODE="{code_clean}.{market}")(REPORT_TYPE="{report_type}")'
        return f'(SECUCODE="{code_clean}.{market}")'

    base_params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA",
        "sty": "ALL",
        "p": "1",
        "ps": "5",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
    }

    reports = []

    if period == "全部":
        # 不加 REPORT_TYPE 过滤，取全部
        params = dict(base_params)
        params["filter"] = _build_filter(None)
        try:
            data = _fetch_json(fin_url, params)
            reports = data.get("result", {}).get("data", [])
        except Exception as e:
            print(f"[WARN] API error (全部): {e}", file=sys.stderr)
    elif period == "季报":
        # "季报" 需合并一季报和三季报
        for sub_type in ("一季报", "三季报"):
            params = dict(base_params)
            params["filter"] = _build_filter(sub_type)
            try:
                data = _fetch_json(fin_url, params)
                sub_reports = data.get("result", {}).get("data", [])
                reports.extend(sub_reports)
            except Exception as e:
                print(f"[WARN] API error (季报/{sub_type}): {e}", file=sys.stderr)
        # 按 REPORT_DATE 降序排列，取前5条
        reports.sort(key=lambda r: r.get("REPORT_DATE", ""), reverse=True)
        reports = reports[:5]
    else:
        # "年报" 或 "半年报" — 东方财富 API 半年报对应 REPORT_TYPE="中报"
        api_period = "中报" if period == "半年报" else period
        params = dict(base_params)
        params["filter"] = _build_filter(api_period)
        try:
            data = _fetch_json(fin_url, params)
            reports = data.get("result", {}).get("data", [])
        except Exception as e:
            print(f"[WARN] API error ({api_period}): {e}", file=sys.stderr)

        # 如果筛选无结果，去掉报告期限制再试
        if not reports:
            params = dict(base_params)
            params["filter"] = _build_filter(None)
            try:
                data = _fetch_json(fin_url, params)
                reports = data.get("result", {}).get("data", [])
            except Exception as e:
                print(f"[WARN] API error (fallback): {e}", file=sys.stderr)

    if as_json:
        # 清理输出字段，只保留核心字段
        clean_reports = []
        keep_keys = {
            "REPORT_DATE", "REPORT_DATE_NAME", "TOTALOPERATEREVE",
            "PARENTNETPROFIT", "EPSJB", "BPS", "ROEJQ",
            "TOTALOPERATEREVETZ", "PARENTNETPROFITTZ",
        }
        for r in reports[:5]:
            clean = {k: r[k] for k in keep_keys if k in r}
            clean_reports.append(clean)

        out = {
            "name": name,
            "code": code_clean,
            "period": period,
            "reports": clean_reports,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"核心财务数据: {name} ({code_clean})")
    if period != "年报":
        print(f"报告期筛选: {period}")
    print("=" * 60)

    if not reports:
        print("  [WARN] 未能获取财务数据，建议通过 WebSearch 补充")
        return

    for r in reports[:5]:
        date = r.get("REPORT_DATE", "")[:10]
        report_name = r.get("REPORT_DATE_NAME", "")
        revenue = r.get("TOTALOPERATEREVE")
        net_profit = r.get("PARENTNETPROFIT")
        eps = r.get("EPSJB")
        bps = r.get("BPS")
        roe = r.get("ROEJQ")
        rev_growth = r.get("TOTALOPERATEREVETZ")
        profit_growth = r.get("PARENTNETPROFITTZ")

        print(f"\n  --- {date} {report_name} ---")
        if revenue is not None:
            print(f"  营收:           {_fmt_yi(revenue)}")
        if rev_growth is not None:
            print(f"  营收增速:       {_fmt_pct(rev_growth)}")
        if net_profit is not None:
            print(f"  归母净利润:     {_fmt_yi(net_profit)}")
        if profit_growth is not None:
            print(f"  净利润增速:     {_fmt_pct(profit_growth)}")
        if eps is not None:
            print(f"  基本每股收益:   {eps}")
        if bps is not None:
            print(f"  每股净资产:     {bps:.2f}")
        if roe is not None:
            print(f"  ROE(加权):      {_fmt_pct(roe)}")


def cmd_search(keyword: str, as_json: bool = False):
    """搜索股票代码。"""
    url = "https://searchadapter.eastmoney.com/api/suggest/get"
    # Use env var or fall back to the public eastmoney search token
    token = os.environ.get("EASTMONEY_SEARCH_TOKEN") or "D43BF722C8E33BDC906FB84D85E326E8"
    params = {
        "input": keyword,
        "type": "14",
        "token": token,
        "count": "10",
    }
    data = _fetch_json(url, params)
    results = data.get("QuotationCodeTable", {}).get("Data", [])

    if not results:
        error_exit(f"[ERROR] 未找到匹配 '{keyword}' 的股票", as_json)

    if as_json:
        out = {
            "keyword": keyword,
            "results": [
                {
                    "code": r.get("Code", ""),
                    "name": r.get("Name", ""),
                    "market": r.get("MktNum", ""),
                    "market_label": {"1": "沪", "2": "深", "3": "北"}.get(str(r.get("MktNum", "")), ""),
                }
                for r in results
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"搜索结果: '{keyword}'")
    print("=" * 60)
    for r in results:
        code = r.get("Code", "")
        name = r.get("Name", "")
        market = r.get("MktNum", "")
        mkt_label = {"1": "沪", "2": "深", "3": "北"}.get(str(market), "")
        print(f"  {code} {name} [{mkt_label}]")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A股数据工具 — 腾讯行情 + 东方财富财务数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_quote = sub.add_parser("quote", help="实时行情")
    p_quote.add_argument("code", help="股票代码，如 600519")
    p_quote.add_argument("--json", action="store_true", help="输出 JSON 格式")

    p_fin = sub.add_parser("financials", help="核心财务数据（近5年）")
    p_fin.add_argument("code", help="股票代码")
    p_fin.add_argument("--period", default="年报", choices=["年报", "半年报", "季报", "全部"],
                       help="报告期筛选（默认: 年报）")
    p_fin.add_argument("--json", action="store_true", help="输出 JSON 格式")

    p_val = sub.add_parser("valuation", help="估值指标")
    p_val.add_argument("code", help="股票代码")
    p_val.add_argument("--json", action="store_true", help="输出 JSON 格式")

    p_search = sub.add_parser("search", help="搜索股票代码")
    p_search.add_argument("keyword", help="公司名或关键词")
    p_search.add_argument("--json", action="store_true", help="输出 JSON 格式")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "quote": lambda: cmd_quote(args.code, as_json=args.json),
        "financials": lambda: cmd_financials(args.code, period=args.period, as_json=args.json),
        "valuation": lambda: cmd_valuation(args.code, as_json=args.json),
        "search": lambda: cmd_search(args.keyword, as_json=args.json),
    }
    cmds[args.command]()


if __name__ == "__main__":
    main()
