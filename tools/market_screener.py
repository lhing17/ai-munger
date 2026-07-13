#!/usr/bin/env python3
"""A股全市场量化快筛工具 — 第零层漏斗，零外部依赖（仅 stdlib）。

按东方财富行业板块逐个拉取全市场 ~5500 只股票的基础数据，
用 3 条纯量化标准完成第一轮粗筛，排除 ~90% 无需考虑的标的。

核心思路：不翻页（会被反爬），而是按 43 个行业板块各自"第一页"拉取，
每个板块像正常用户浏览一个行业，最后去重合并。

用法:
    python tools/market_screener.py run              # 全市场快筛（约 10 分钟）
    python tools/market_screener.py run --top 500    # 仅筛市值前 500（单次请求，秒级）
    python tools/market_screener.py test             # 单板块连通性测试
    python tools/market_screener.py run --json       # JSON 格式输出
    python tools/market_screener.py run --json --output reports/screener.json

筛选标准（可命令行覆盖）:
    --min-cap      市值下限（亿），默认 50
    --min-roe      ROE 下限（%），默认 2.5（注：push2 API 返回的是季度/滚动 ROE，
                   年化 ≈ 季度×4，2.5% 对应年化 ~10%）
    --max-pe       PE 上限，默认 200（排除负值和极端高估）
    --include-bj   包含北交所（默认排除）

关键约束：
    - push2 clist API 的 f38-f41 字段返回原始货币值而非百分比，
      因此资产负债率、毛利率、营收增长率等高阶质量指标无法在此层使用。
      这些指标留给 LLM 驱动的 Gate 2（quality-screen）。
    - f37 返回的是季度/滚动 ROE（非年化），阈值已相应调低。

设计原则: 零 LLM 成本、纯量化、可复现、可调参。
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

_TIMEOUT = 25

# 东方财富行业板块代码（去重后的唯一 BK 码，来源 industry_data.py）
# 每个板块内股票数通常 30-200，单次请求即可全部获取。
_BOARD_CODES = [
    "BK0477",  # 白酒
    "BK0478",  # 啤酒
    "BK0480",  # 食品饮料
    "BK0484",  # 银行
    "BK0485",  # 保险
    "BK0486",  # 券商
    "BK0473",  # 医药
    "BK0472",  # 医疗器械
    "BK0456",  # 新能源
    "BK0459",  # 新能源汽车
    "BK0431",  # 光伏
    "BK0432",  # 风电
    "BK0457",  # 储能
    "BK0448",  # 半导体
    "BK0447",  # 芯片
    "BK0438",  # 5G
    "BK0489",  # 房地产
    "BK0453",  # 军工
    "BK0420",  # 人工智能
    "BK0434",  # 汽车
    "BK0487",  # 家电
    "BK0476",  # 煤炭
    "BK0475",  # 石油
    "BK0481",  # 钢铁
    "BK0482",  # 有色金属
    "BK0474",  # 化工
    "BK0490",  # 电力
    "BK0440",  # 软件
    "BK0441",  # 计算机
    "BK0443",  # 通信
    "BK0435",  # 传媒
    "BK0436",  # 游戏
    "BK0488",  # 旅游
    "BK0470",  # 农业
    "BK0471",  # 养殖
    "BK0483",  # 建材
    "BK0492",  # 港口
    "BK0491",  # 航运
    "BK0494",  # 航空
    "BK0493",  # 铁路
    "BK0495",  # 物流
    "BK0465",  # 环保
    "BK0460",  # 电力设备
    "BK0462",  # 机械
    "BK0463",  # 机器人
    "BK0445",  # 消费电子
    "BK0446",  # 物联网
    "BK0439",  # 云计算
    "BK0442",  # 大数据
    "BK0437",  # 区块链
    "BK0444",  # 数字货币
    "BK0479",  # 中药
]

# 用于 --top 模式的直接全市场查询（不翻页，单次取市值前 N）
_ALL_MARKETS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
_ALL_MARKETS_WITH_BJ = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81"

# 全体请求字段
_FIELDS = "f2,f3,f9,f12,f14,f20,f21,f23,f37,f115"

# JSON 输出保留的核心字段
_OUTPUT_KEYS = [
    "code", "name", "price", "pe", "pe_ttm", "pb",
    "market_cap_yi", "roe",
]


# ---------------------------------------------------------------------------
# HTTP 工具（urllib，零外部依赖，与 ashare_data.py 一致）
# ---------------------------------------------------------------------------

def _fetch(url, timeout=_TIMEOUT):
    """GET 请求，返回解码后的文本。自动处理 UTF-8/GBK。"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://data.eastmoney.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(f"请求失败: {url} — {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


class APIError(Exception):
    """API 返回非成功 rc 码。"""
    def __init__(self, rc, msg, url):
        self.rc = rc
        self.msg = msg
        self.url = url
        super().__init__(f"API rc={rc}: {msg} ({url})")


class JSONParseError(Exception):
    """API 返回非 JSON 响应（HTML 错误页/网关超时等）。"""
    def __init__(self, url, text_preview):
        self.url = url
        self.text_preview = text_preview
        super().__init__(f"JSON 解析失败: {url} — 响应预览: {text_preview[:200]}")


def _fetch_json(url, params=None, timeout=_TIMEOUT):
    """GET 并解析 JSON。"""
    if params:
        url = f"{url}?{urlencode(params)}"
    text = _fetch(url, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise JSONParseError(url, text[:500])


# ---------------------------------------------------------------------------
# 格式化工具（与 ashare_data.py 一致）
# ---------------------------------------------------------------------------

def _try_float(val):
    """安全地转为 float，失败返回 None。"""
    if val is None or val == "-" or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _fmt_yi(val):
    """数值 → 亿（1e8）格式化字符串。"""
    v = _try_float(val)
    if v is None:
        return "-"
    if abs(v) >= 1e8:
        return f"{v / 1e8:.0f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.0f}万"
    return f"{v:.2f}"


def _fmt_pct(val):
    """数值 → 百分比字符串。"""
    v = _try_float(val)
    if v is None:
        return "-"
    return f"{v:.1f}%"


# ---------------------------------------------------------------------------
# 行业判断
# ---------------------------------------------------------------------------

# 金融行业关键词（名称中包含即为金融股，享受负债率例外）
_FINANCIAL_KEYWORDS = (
    "银行", "保险", "证券", "信托", "金控",
    "租赁", "期货", "资产管理",
    "平安", "人寿", "太保", "人保",  # 保险系（名称中不含"保险"二字）
)

# 新股/次新股前缀（可选排除）
_NEW_STOCK_PREFIXES = ("N", "C")


def _is_financial(name):
    """判断是否为金融行业。"""
    return any(kw in (name or "") for kw in _FINANCIAL_KEYWORDS)


def _is_st(name):
    """判断是否 ST / *ST。"""
    n = (name or "").strip()
    return "ST" in n.split("*")[-1] if "*" in n else "ST" in n


def _is_new_stock(name):
    """判断是否新股（N/C 开头）。"""
    n = (name or "").strip()
    return any(n.startswith(p) for p in _NEW_STOCK_PREFIXES)


# ---------------------------------------------------------------------------
# 批量数据获取
# ---------------------------------------------------------------------------

def _parse_stock(raw):
    """将 clist API 返回的单条原始 dict 解析为标准格式。返回 dict 或 None。

    字段说明：
        f9  = 动态 PE, f115 = PE TTM, f37 = 季度/滚动 ROE (%),
        f20 = 总市值(元), f23 = PB

    注意：f38-f41 (clist API) 返回原始货币值，非百分比。
    """
    code = raw.get("f12", "")
    name = raw.get("f14", "")
    if not code or not name:
        return None

    mcap = _try_float(raw.get("f20"))
    return {
        "code": code,
        "name": name,
        "price": _try_float(raw.get("f2")),
        "change_pct": _try_float(raw.get("f3")),
        "pe": _try_float(raw.get("f9")),
        "pe_ttm": _try_float(raw.get("f115")),
        "pb": _try_float(raw.get("f23")),
        "market_cap": mcap,
        "market_cap_yi": round(mcap / 1e8, 1) if mcap is not None else None,
        "float_cap": _try_float(raw.get("f21")),
        "roe": _try_float(raw.get("f37")),
    }


def _fetch_one_page(page, pz, fs, fid="f20"):
    """获取单页数据。返回 (stocks: list, total: int)。"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": page,
        "pz": pz,
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": fid,
        "fs": fs,
        "fields": _FIELDS,
    }
    data = _fetch_json(url, params, timeout=30)

    # 检查 API 返回码（Critical: 忽略 rc 会导致限流/错误被当作"无数据"）
    rc = data.get("rc")
    if rc is not None and rc != 0:
        raise APIError(rc, data.get("msg", data.get("error", "未知错误")), url)

    result = data.get("data") or {}
    raw_stocks = result.get("diff") or []
    total = result.get("total", 0)

    stocks = []
    for raw in raw_stocks:
        s = _parse_stock(raw)
        if s:
            stocks.append(s)
    return stocks, total


def _fetch_board(board_code, pz=500):
    """获取单个行业板块的全部股票（单页，pz 设大以一次拉完）。

    注意：不使用 f:!200 过滤器。该过滤器在 industry_data.py 中用于
    排除退市/风险警示股，但实际上会大量误杀 A 股主板正常标的。
    ST/风险股由客户端 _is_st() 处理，无需在 API 层过滤。

    Returns: (stocks: list, board_name: str)
    """
    fs = f"b:{board_code}"
    stocks, total = _fetch_one_page(1, pz, fs)

    # 如果板块股票数超过 pz，再拉第二页（罕见，如医药 BK0473）
    if total > pz:
        page2_stocks, _ = _fetch_one_page(2, pz, fs)
        stocks.extend(page2_stocks)

    return stocks


def fetch_all_by_boards(verbose=False):
    """按行业板块逐个拉取，去重后返回全市场股票列表。

    核心策略：43 个板块各自"第一页"拉取，不像翻页那样触发反爬。
    每个板块间隔 15 秒，总耗时约 10 分钟。
    """
    seen_codes = set()
    all_stocks = []
    board_count = len(_BOARD_CODES)
    failed_boards = 0
    retry_boards = []

    if verbose:
        print(f"[INFO] 开始按 {board_count} 个行业板块拉取全市场数据", file=sys.stderr)

    for i, bk in enumerate(_BOARD_CODES):
        try:
            stocks = _fetch_board(bk)
        except (ConnectionError, urllib.error.URLError) as e:
            print(f"[WARN] 板块 {bk} 网络错误 ({e})，稍后重试", file=sys.stderr)
            retry_boards.append(bk)
            failed_boards += 1
        except (APIError, JSONParseError) as e:
            print(f"[WARN] 板块 {bk} 致命错误 ({e})，跳过", file=sys.stderr)
            failed_boards += 1
        else:
            new_count = 0
            for s in stocks:
                code = s.get("code")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    all_stocks.append(s)
                    new_count += 1

            if verbose:
                pct = (i + 1) * 100 // board_count
                print(
                    f"[INFO] [{pct:2d}%] {bk}: 板块{len(stocks)}只, "
                    f"新增{new_count}只, 累计{len(all_stocks)}只",
                    file=sys.stderr,
                )

        # 板块间延时，避免连续请求触发反爬
        if i < board_count - 1:
            time.sleep(15)

    # 重试失败的板块
    if retry_boards:
        if verbose:
            print(f"[INFO] 重试 {len(retry_boards)} 个失败板块...", file=sys.stderr)
        for bk in retry_boards:
            time.sleep(15)
            try:
                stocks = _fetch_board(bk)
            except Exception as e:
                print(f"[WARN] 板块 {bk} 重试仍失败 ({e})，放弃", file=sys.stderr)
                continue
            new_count = 0
            for s in stocks:
                code = s.get("code")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    all_stocks.append(s)
                    new_count += 1
            if verbose:
                print(f"[INFO] 重试 {bk}: 新增{new_count}只, 累计{len(all_stocks)}只", file=sys.stderr)

    if verbose:
        print(
            f"[INFO] 拉取完成: {len(all_stocks)} 只股票 "
            f"({failed_boards} 个板块失败)",
            file=sys.stderr,
        )

    return all_stocks


def fetch_top_stocks(fs, top_n, verbose=False):
    """单次请求获取市值前 N 只股票（用于 --top 快速模式）。"""
    if verbose:
        print(f"[INFO] 单次拉取市值前 {top_n} 只...", file=sys.stderr)
    stocks, total = _fetch_one_page(1, min(top_n, 100), fs)
    stocks = stocks[:top_n]
    if verbose:
        print(f"[INFO] 拉取到 {len(stocks)} 只 (全市场共 {total})", file=sys.stderr)
    return stocks


# ---------------------------------------------------------------------------
# 筛选逻辑
# ---------------------------------------------------------------------------

def _screening_defaults():
    """返回默认筛选参数。

    注意：ROE 阈值 2.5% 对应季度/滚动 ROE（≈ 年化 10%），
    因为 push2 clist API 的 f37 返回非年化数据。
    """
    return {
        "min_cap_yi": 50,        # 市值 ≥ 50 亿
        "min_roe": 2.5,          # 季度/滚动 ROE > 2.5%（≈ 年化 10%）
        "max_pe": 200,           # PE < 200 且 > 0
        "exclude_bj": True,      # 排除北交所
        "exclude_new": True,     # 排除新股 N/C
    }


def screen_stocks(all_stocks, criteria=None):
    """对股票列表执行 3 条件 + 硬排除筛选。

    仅使用 push2 clist API 中可靠的三项指标：
    1. 市值 ≥ 下限
    2. PE TTM（优先）或动态 PE 在合理区间（> 0 且 < 上限）
    3. 季度/滚动 ROE > 下限

    资产负债率、毛利率、营收增长率等指标依赖的 f38-f41 字段
    在 clist API 中返回原始货币值，不可用于百分比阈值筛选。

    Returns:
        passed: list[dict]  通过筛选的股票
        rejected: dict      按原因分组的淘汰统计
    """
    if criteria is None:
        criteria = _screening_defaults()

    passed = []
    rejected = {
        "st_stock": [],
        "bj_stock": [],
        "new_stock": [],
        "small_cap": [],
        "loss_making": [],
        "low_roe": [],
    }

    for s in all_stocks:
        name = s.get("name", "")

        # ── 硬排除（不可调） ──
        if _is_st(name):
            rejected["st_stock"].append(s)
            continue

        # ── 北交所排除 ──
        if criteria.get("exclude_bj") and s.get("code", "").startswith(("4", "8")):
            rejected["bj_stock"].append(s)
            continue

        if criteria.get("exclude_new") and _is_new_stock(name):
            rejected["new_stock"].append(s)
            continue

        mcap_yi = s.get("market_cap_yi")
        pe = s.get("pe")
        pe_ttm = s.get("pe_ttm")
        roe = s.get("roe")

        # ── 市值 ──
        if mcap_yi is None or mcap_yi < criteria["min_cap_yi"]:
            rejected["small_cap"].append(s)
            continue

        # ── 盈利（优先用 PE TTM，缺失时回退到 PE 动态） ──
        effective_pe = pe_ttm if pe_ttm is not None else pe
        if effective_pe is None or effective_pe <= 0 or effective_pe > criteria["max_pe"]:
            rejected["loss_making"].append(s)
            continue

        # ── ROE（季度/滚动，阈值已按年化/4 设） ──
        if roe is None or roe <= criteria["min_roe"]:
            rejected["low_roe"].append(s)
            continue

        passed.append(s)

    return passed, rejected


# ---------------------------------------------------------------------------
# 输出格式
# ---------------------------------------------------------------------------

def _rejected_summary(rejected):
    """生成淘汰统计。"""
    summary = {}
    labels = {
        "st_stock": "ST/*ST股",
        "bj_stock": "北交所",
        "new_stock": "新股(N/C开头)",
        "small_cap": "市值不达标",
        "loss_making": "亏损或PE异常",
        "low_roe": "ROE 过低",
    }
    for key, label in labels.items():
        count = len(rejected.get(key, []))
        if count > 0:
            summary[label] = count
    return summary


def _clean_passed(passed):
    """过滤通过列表，仅保留 _OUTPUT_KEYS 中的核心字段。"""
    return [{k: s.get(k) for k in _OUTPUT_KEYS} for s in passed]


def _print_text(passed, rejected, total, criteria):
    """文本表格输出。"""
    print("=" * 72)
    print("  A 股全市场量化快筛 — 第零层漏斗")
    print("=" * 72)
    print(f"  筛选总数: {total}")
    print(f"  通过数量: {len(passed)}  ({len(passed) / max(total, 1) * 100:.1f}%)")
    print()
    print("  筛选标准:")
    print(f"    市值 ≥ {criteria['min_cap_yi']} 亿")
    print(f"    ROE  > {criteria['min_roe']}%（季度/滚动，≈年化{criteria['min_roe']*4:.0f}%）")
    print(f"    PE   > 0 且 < {criteria['max_pe']}（优先 TTM，缺则动态）")
    print(f"    排除 ST / *ST / 北交所（{'含' if not criteria.get('exclude_bj') else '不含'}）")
    print()

    # ── 淘汰统计 ──
    summary = _rejected_summary(rejected)
    if summary:
        print("  ── 淘汰统计 ──")
        for label, count in sorted(summary.items(), key=lambda x: -x[1]):
            bar = "█" * min(30, count * 30 // max(summary.values()))
            print(f"  {label:12s}  {count:>5}  {bar}")
        print()

    # ── 通过列表 ──
    if not passed:
        print("  (无股票通过筛选)")
        return

    print(f"  ── 通过筛选 ({len(passed)} 只) ──")
    print(f"  {'代码':<8s} {'名称':<10s} {'市值(亿)':>8s} {'PE(TTM)':>8s} {'ROE':>6s} {'PB':>6s}")
    print("  " + "-" * 54)

    for s in passed[:200]:
        cap_str = f"{s['market_cap_yi']:.1f}亿" if s.get('market_cap_yi') is not None else "  -"
        pe_str = f"{s['pe_ttm']:.1f}" if s.get('pe_ttm') is not None else f"{s['pe']:.1f}" if s.get('pe') is not None else "  -"
        roe_str = _fmt_pct(s.get('roe'))
        pb_str = f"{s['pb']:.2f}" if s.get('pb') is not None else "  -"

        print(
            f"  {s['code']:<8s} {s['name']:<10s} "
            f"{cap_str:>8s} "
            f"{pe_str:>8s} "
            f"{roe_str:>6s} "
            f"{pb_str:>6s}"
        )

    if len(passed) > 200:
        print(f"  ... (还有 {len(passed) - 200} 只未显示)")

    print()


def _print_json(passed, rejected, total, criteria):
    """JSON 输出（stdout）。"""
    passed_clean = _clean_passed(passed)
    output = {
        "meta": {
            "date": time.strftime("%Y-%m-%d"),
            "total_screened": total,
            "passed": len(passed),
            "pass_rate_pct": round(len(passed) / max(total, 1) * 100, 2),
            "criteria": criteria,
        },
        "rejected_summary": _rejected_summary(rejected),
        "passed": passed_clean,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def cmd_run(args):
    """全市场快筛 / top N 快速筛选。"""
    criteria = _screening_defaults()

    # 命令行参数覆盖默认标准
    if args.min_cap is not None:
        criteria["min_cap_yi"] = args.min_cap
    if args.min_roe is not None:
        criteria["min_roe"] = args.min_roe
    if args.max_pe is not None:
        criteria["max_pe"] = args.max_pe
    if args.include_bj:
        criteria["exclude_bj"] = False

    # ── 拉取数据 ──
    if args.top:
        # 快速模式：单次请求取市值前 N
        fs = _ALL_MARKETS_WITH_BJ if args.include_bj else _ALL_MARKETS
        stocks = fetch_top_stocks(fs, args.top, verbose=not args.json)
    else:
        # 全市场模式：按行业板块逐个拉取 + 去重
        stocks = fetch_all_by_boards(verbose=not args.json)

    if not stocks:
        print("[ERROR] 未能获取任何股票数据", file=sys.stderr)
        sys.exit(1)

    # ── 筛选 ──
    passed, rejected = screen_stocks(stocks, criteria)

    # ── 输出 ──
    if args.json:
        _print_json(passed, rejected, len(stocks), criteria)
    else:
        _print_text(passed, rejected, len(stocks), criteria)

    # ── 保存到文件 ──
    if args.output:
        output = {
            "meta": {
                "date": time.strftime("%Y-%m-%d"),
                "total_screened": len(stocks),
                "passed": len(passed),
                "pass_rate_pct": round(len(passed) / max(len(stocks), 1) * 100, 2),
                "criteria": criteria,
            },
            "rejected_summary": _rejected_summary(rejected),
            "passed": _clean_passed(passed),
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 结果已保存到 {args.output}", file=sys.stderr)


def cmd_test(args):
    """单板块连通性测试 — 拉白酒板块验证 API 和数据质量。"""
    board = "BK0477"  # 白酒
    fs = f"b:{board}"
    pz = 100

    print(f"[TEST] 拉取板块 {board} (白酒) 数据...", file=sys.stderr)
    try:
        stocks, total = _fetch_one_page(1, pz, fs)
    except Exception as e:
        print(f"[ERROR] 第 1 页失败: {e}", file=sys.stderr)
        print("[HINT] API 可能限流，请等待 1-2 分钟后重试", file=sys.stderr)
        sys.exit(1)

    if not stocks:
        print("[ERROR] 测试拉取失败（0 条数据）", file=sys.stderr)
        sys.exit(1)

    print(f"[TEST] 板块有 {total} 只股票，本次获取 {len(stocks)} 只", file=sys.stderr)

    criteria = _screening_defaults()
    passed, rejected = screen_stocks(stocks, criteria)

    # 打印前 5 只原始数据
    print("\n── 原始数据抽样 (前 5 只) ──")
    for s in stocks[:5]:
        print(f"  {s['code']} {s['name']}: "
              f"市值={_fmt_yi(s.get('market_cap'))} "
              f"PE={s.get('pe')} PE_TTM={s.get('pe_ttm')} "
              f"ROE={_fmt_pct(s.get('roe'))} PB={s.get('pb')}")

    print(f"\n── 筛选结果 ──")
    print(f"  板块总数: {len(stocks)}")
    print(f"  通过: {len(passed)}")
    print(f"  淘汰: {len(stocks) - len(passed)}")
    for label, count in sorted(_rejected_summary(rejected).items(), key=lambda x: -x[1]):
        print(f"    {label}: {count}")

    if passed:
        print(f"\n  通过列表:")
        for s in passed:
            print(f"    {s['code']} {s['name']} "
                  f"市值={s['market_cap_yi']:.0f}亿 "
                  f"PE_TTM={s.get('pe_ttm', '-')} "
                  f"ROE={_fmt_pct(s.get('roe'))}")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A股全市场量化快筛 — 第零层漏斗",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # ── run ──
    p_run = sub.add_parser("run", help="全市场快筛")
    p_run.add_argument("--top", type=int, default=None,
                       help="仅筛选市值前 N 只")
    p_run.add_argument("--json", action="store_true",
                       help="JSON 格式输出")
    p_run.add_argument("--output", type=str, default=None,
                       help="保存 JSON 结果到文件")
    p_run.add_argument("--include-bj", action="store_true",
                       help="包含北交所")
    # 可调阈值
    p_run.add_argument("--min-cap", type=float, default=None,
                       help="市值下限（亿），默认 50")
    p_run.add_argument("--min-roe", type=float, default=None,
                       help="ROE 下限（%%），默认 2.5（季度/滚动 ≈ 年化 10%%）")
    p_run.add_argument("--max-pe", type=float, default=None,
                       help="PE 上限，默认 200")

    # ── test ──
    p_test = sub.add_parser("test", help="单板块连通性测试（白酒）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        cmd_run(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
