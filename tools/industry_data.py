#!/usr/bin/env python3
"""A股行业数据工具 — 东方财富行业板块 API，零外部依赖。

为 moat-analysis 和 quality-screen 提供行业基准数据。

用法:
    python tools/industry_data.py 白酒 --json
    python tools/industry_data.py search 新能源 --json
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlencode

_TIMEOUT = 15

# Built-in industry → BK code mapping (stable, well-known eastmoney board codes)
_BOARD_MAP = {
    "白酒": "BK0477",
    "啤酒": "BK0478",
    "食品饮料": "BK0480",
    "食品": "BK0480",
    "饮料": "BK0480",
    "银行": "BK0484",
    "保险": "BK0485",
    "券商": "BK0486",
    "证券": "BK0486",
    "医药": "BK0473",
    "医疗": "BK0472",
    "医疗器械": "BK0472",
    "新能源": "BK0456",
    "新能源汽车": "BK0459",
    "光伏": "BK0431",
    "风电": "BK0432",
    "储能": "BK0457",
    "半导体": "BK0448",
    "芯片": "BK0447",
    "5g": "BK0438",
    "房地产": "BK0489",
    "军工": "BK0453",
    "人工智能": "BK0420",
    "ai": "BK0420",
    "汽车": "BK0434",
    "家电": "BK0487",
    "煤炭": "BK0476",
    "石油": "BK0475",
    "钢铁": "BK0481",
    "有色": "BK0482",
    "有色金属": "BK0482",
    "化工": "BK0474",
    "电力": "BK0490",
    "软件": "BK0440",
    "计算机": "BK0441",
    "通信": "BK0443",
    "传媒": "BK0435",
    "游戏": "BK0436",
    "旅游": "BK0488",
    "农业": "BK0470",
    "养殖": "BK0471",
    "建材": "BK0483",
    "水泥": "BK0483",
    "港口": "BK0492",
    "航运": "BK0491",
    "航空": "BK0494",
    "铁路": "BK0493",
    "物流": "BK0495",
    "环保": "BK0465",
    "电力设备": "BK0460",
    "机械": "BK0462",
    "机器人": "BK0463",
    "消费电子": "BK0445",
    "物联网": "BK0446",
    "云计算": "BK0439",
    "大数据": "BK0442",
    "区块链": "BK0437",
    "数字货币": "BK0444",
    "中药": "BK0479",
}


def _fetch(url):
    """urllib GET，返回文本。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"请求失败: {url} — {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    return json.loads(_fetch(url))


def _lookup_board(name: str) -> tuple:
    """Look up board code by name. Returns (code, display_name) or (None, None)."""
    key = name.strip()
    # Exact match
    if key in _BOARD_MAP:
        return _BOARD_MAP[key], key
    # Substring match
    for k, v in _BOARD_MAP.items():
        if key in k or k in key:
            return v, k
    return None, None


def _try_api_search(keyword: str) -> tuple:
    """Try the eastmoney search API as fallback. Returns (code, name) or (None, None)."""
    url = "https://searchadapter.eastmoney.com/api/suggest/get"
    params = {
        "input": keyword,
        "type": "15",
        "token": "D43BF722C8E33BDC906FB84D85E326E8",
        "count": "10",
    }
    try:
        data = _fetch_json(url, params)
        results = data.get("QuotationCodeTable", {}).get("Data", [])
        if results:
            return results[0].get("Code", ""), results[0].get("Name", "")
    except Exception:
        pass
    return None, None


def cmd_search(keyword: str) -> list:
    """搜索行业板块 — 优先查内置表，再试 API。"""
    items = []

    # Built-in table search
    for k, v in _BOARD_MAP.items():
        if keyword.strip().lower() in k.lower() or k.lower() in keyword.strip().lower():
            if {"code": v, "name": k} not in items:
                items.append({"code": v, "name": k})

    # API fallback
    code, name = _try_api_search(keyword)
    if code and {"code": code, "name": name} not in items:
        items.append({"code": code, "name": name})

    return items[:10]


def cmd_industry(name: str) -> dict:
    """获取行业板块数据。"""
    # Look up board code
    bk_code, bk_name = _lookup_board(name)
    if not bk_code:
        # Try API search as last resort
        bk_code_api, bk_name_api = _try_api_search(name)
        if bk_code_api:
            bk_code, bk_name = bk_code_api, bk_name_api
        else:
            return {"error": f"未找到行业: {name}。可用行业请用 search 子命令查询。"}

    # Fetch board member stocks
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "50",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f20",
        "fs": f"b:{bk_code}+f:!200",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f37,f38,f39,f40,f41,f45,f46",
    }

    try:
        data = _fetch_json(url, params)
        stocks = data.get("data", {})
        if stocks is None:
            return {"error": f"行业 {bk_name} 数据获取失败（可能被限流，请稍后重试）"}
        stocks = stocks.get("diff", [])
    except Exception as e:
        return {"error": f"行业数据获取失败: {e}"}

    if not stocks:
        return {"error": f"行业 {bk_name} 无成分股数据"}

    roes, gms, nms, pes, debt_ratios, rev_growths = [], [], [], [], [], []
    top_cap, top_roe = [], []

    for s in stocks:
        roe = s.get("f37")
        gm = s.get("f39")
        nm = s.get("f40")
        pe = s.get("f9")
        debt = s.get("f41")
        rev_g = s.get("f38")
        mcap = s.get("f20")
        name_s = s.get("f14", "")
        code_s = s.get("f12", "")

        for lst, val in [(roes, roe), (gms, gm), (nms, nm), (pes, pe),
                         (debt_ratios, debt), (rev_growths, rev_g)]:
            if val is not None and val != "-" and val != "":
                try:
                    lst.append(float(val))
                except (ValueError, TypeError):
                    pass

        if mcap and mcap != "-":
            try:
                top_cap.append((code_s, name_s, float(mcap) / 1e8))
            except (ValueError, TypeError):
                pass
        if roe and roe != "-":
            try:
                top_roe.append((code_s, name_s, float(roe)))
            except (ValueError, TypeError):
                pass

    def _avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else None

    top_cap.sort(key=lambda x: x[2], reverse=True)
    top_roe.sort(key=lambda x: x[2], reverse=True)

    return {
        "industry": bk_name,
        "board_code": bk_code,
        "company_count": len(stocks),
        "averages": {
            "roe": _avg(roes),
            "gross_margin": _avg(gms),
            "net_margin": _avg(nms),
            "pe": _avg(pes),
            "debt_ratio": _avg(debt_ratios),
            "revenue_growth_3y": _avg(rev_growths),
        },
        "top_by_market_cap": [
            {"code": c, "name": n, "market_cap_yi": round(m, 0)} for c, n, m in top_cap[:5]
        ],
        "top_by_roe": [
            {"code": c, "name": n, "roe": round(r, 2)} for c, n, r in top_roe[:5]
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="A股行业数据工具 — 内置50+行业板块映射",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_ind = sub.add_parser("industry", help="行业概况")
    p_ind.add_argument("name", help="行业名称，如 白酒")

    p_search = sub.add_parser("search", help="搜索行业")
    p_search.add_argument("keyword", help="关键词")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search":
        result = cmd_search(args.keyword)
    elif args.command == "industry":
        result = cmd_industry(args.name)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
