#!/usr/bin/env python3
"""A股全市场量化快筛工具 — 第零层漏斗。

基于 AKShare 获取完整股票代码表（沪/深/京三市 ~5530 只），
再通过东方财富 ulist.np/get 批量 API 每 50 只一批拉取财务数据，
用 3 条纯量化标准完成第一轮粗筛。

用法:
    python tools/market_screener.py run              # 全市场快筛（约 3 分钟）
    python tools/market_screener.py run --top 500    # 仅筛市值前 500
    python tools/market_screener.py test             # 连通性 + 小批量测试
    python tools/market_screener.py run --json       # JSON 格式输出
    python tools/market_screener.py run --json --output reports/screener.json

筛选标准:
    --min-cap      市值下限（亿），默认 50
    --min-roe      ROE 下限（%），默认 2.5（季度/滚动 ≈ 年化 10%）
    --max-pe       PE 上限，默认 200
    --include-bj   包含北交所（默认排除）

依赖:
    pip install akshare  # 仅获取代码表时使用（首次/定期刷新）
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

_TIMEOUT = 25
_BATCH_SIZE = 50           # 每批查询股票数
_BATCH_INTERVAL = 3.0      # 批次间隔（秒），ulist.np/get 反爬远弱于 clist
_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           ".stock_codes_cache.json")

# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class APIError(Exception):
    def __init__(self, rc, msg, ctx=""):
        self.rc = rc
        self.msg = msg
        super().__init__(f"API rc={rc}: {msg}" + (f" ({ctx})" if ctx else ""))


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------

def _fetch(url, timeout=_TIMEOUT):
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
        raise ConnectionError(f"请求失败 — {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None, timeout=_TIMEOUT):
    if params:
        url = f"{url}?{urlencode(params)}"
    text = _fetch(url, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON 解析失败: {text[:200]}")


# ---------------------------------------------------------------------------
# 格式化
# ---------------------------------------------------------------------------

def _try_float(val):
    if val is None or val == "-" or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _fmt_yi(val):
    v = _try_float(val)
    if v is None:
        return "-"
    if abs(v) >= 1e8:
        return f"{v / 1e8:.0f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.0f}万"
    return f"{v:.2f}"


def _fmt_pct(val):
    v = _try_float(val)
    if v is None:
        return "-"
    return f"{v:.1f}%"


# ---------------------------------------------------------------------------
# 股票代码表 (AKShare → secid 列表)
# ---------------------------------------------------------------------------

def _fetch_codes_from_akshare():
    """通过 AKShare 获取沪深京三市完整股票代码表。返回 list[dict]。
    结果缓存在 _CACHE_FILE 中，一天内有效。
    """
    # 检查缓存
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cache_date = cached.get("date", "")
            if cache_date == time.strftime("%Y-%m-%d"):
                codes = cached.get("codes", [])
                if codes:
                    return codes
        except Exception:
            pass

    try:
        import akshare as ak
    except ImportError:
        raise RuntimeError(
            "需要 akshare 获取股票代码表。请运行: pip install akshare"
        )

    codes = []

    # 沪市主板
    try:
        sh_main = ak.stock_info_sh_name_code(symbol="主板A股")
        for _, row in sh_main.iterrows():
            codes.append({"code": str(row["证券代码"]), "name": str(row["证券简称"]),
                          "market": "sh", "board": "主板"})
    except Exception as e:
        print(f"[WARN] 沪市主板获取失败: {e}", file=sys.stderr)

    # 科创板
    try:
        sh_star = ak.stock_info_sh_name_code(symbol="科创板")
        for _, row in sh_star.iterrows():
            codes.append({"code": str(row["证券代码"]), "name": str(row["证券简称"]),
                          "market": "sh", "board": "科创板"})
    except Exception as e:
        print(f"[WARN] 科创板获取失败: {e}", file=sys.stderr)

    # 深市（主板+创业板）
    try:
        sz = ak.stock_info_sz_name_code(symbol="A股列表")
        for _, row in sz.iterrows():
            codes.append({"code": str(row["A股代码"]), "name": str(row["A股简称"]),
                          "market": "sz", "board": "深市"})
    except Exception as e:
        print(f"[WARN] 深市获取失败: {e}", file=sys.stderr)

    # 北交所
    try:
        bj = ak.stock_info_bj_name_code()
        for _, row in bj.iterrows():
            codes.append({"code": str(row["证券代码"]), "name": str(row["证券简称"]),
                          "market": "bj", "board": "北交所"})
    except Exception as e:
        print(f"[WARN] 北交所获取失败: {e}", file=sys.stderr)

    # 缓存
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": time.strftime("%Y-%m-%d"), "codes": codes}, f,
                      ensure_ascii=False)
    except Exception:
        pass

    return codes


def _codes_to_secid(code, market):
    """将 600519 + sh → 1.600519, 000858 + sz → 0.000858"""
    if market == "sh":
        return f"1.{code}"
    elif market == "sz":
        return f"0.{code}"
    elif market == "bj":
        return f"0.{code}"  # 北交所也走 0 市场
    return code


# ---------------------------------------------------------------------------
# 批量数据获取 (ulist.np/get)
# ---------------------------------------------------------------------------

def _fetch_batch(secids, fields):
    """批量查询一批股票。返回 list[dict]（原始 API dict）。"""
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    params = {
        "fltt": "2",
        "invt": "2",
        "secids": ",".join(secids),
        "fields": fields,
    }
    data = _fetch_json(url, params, timeout=30)

    rc = data.get("rc")
    if rc is not None and rc != 0:
        raise APIError(rc, data.get("msg", data.get("error", "")),
                       f"batch {len(secids)} stocks")

    return data.get("data", {}).get("diff") or []


def _fetch_all_stocks(codes, fields, verbose=False):
    """分批拉取全部股票数据。失败批次自动拆分重试。"""
    all_raw = []
    total = len(codes)
    # 生成 secid 列表
    code_entries = [(c["code"], _codes_to_secid(c["code"], c["market"]))
                    for c in codes]

    batches = [code_entries[i:i + _BATCH_SIZE]
               for i in range(0, len(code_entries), _BATCH_SIZE)]

    if verbose:
        print(f"[INFO] 共 {len(batches)} 批次, 每批 {_BATCH_SIZE} 只", file=sys.stderr)

    failed_batches = []

    for bi, batch in enumerate(batches):
        secids = [s for _, s in batch]
        try:
            raw_stocks = _fetch_batch(secids, fields)
            all_raw.extend(raw_stocks)
            if verbose and (bi + 1) % 20 == 0:
                pct = (bi + 1) * 100 // len(batches)
                print(f"[INFO] [{pct}%] {bi+1}/{len(batches)} 批, "
                      f"累计 {len(all_raw)} 只", file=sys.stderr)
        except Exception as e:
            if verbose:
                print(f"[WARN] 第 {bi+1} 批失败 ({e})，降级重试", file=sys.stderr)
            failed_batches.append((bi, batch, str(e)))

        # 批次间隔
        if bi < len(batches) - 1:
            time.sleep(_BATCH_INTERVAL)

    # 重试失败批次：拆半重试
    if failed_batches:
        if verbose:
            print(f"[INFO] 重试 {len(failed_batches)} 个失败批次 (拆分后)...",
                  file=sys.stderr)
        for bi, batch, reason in failed_batches:
            time.sleep(5)
            half = len(batch) // 2
            for sub_batch in [batch[:half], batch[half:]]:
                if not sub_batch:
                    continue
                try:
                    secids = [s for _, s in sub_batch]
                    raw = _fetch_batch(secids, fields)
                    all_raw.extend(raw)
                except Exception:
                    # 拆成更小的 6 只一批
                    time.sleep(3)
                    for i in range(0, len(sub_batch), 6):
                        tiny = sub_batch[i:i + 6]
                        try:
                            secids = [s for _, s in tiny]
                            raw = _fetch_batch(secids, fields)
                            all_raw.extend(raw)
                        except Exception as e2:
                            if verbose:
                                codes_fail = [c for c, _ in tiny]
                                print(f"[WARN] 无法获取: {codes_fail} ({e2})",
                                      file=sys.stderr)

    if verbose:
        print(f"[INFO] 拉取完成: {len(all_raw)} / {total} 只", file=sys.stderr)

    return all_raw


# ---------------------------------------------------------------------------
# 数据解析
# ---------------------------------------------------------------------------

def _parse_stock(raw):
    """将 ulist API 返回的单条原始 dict 解析为标准格式。"""
    code = raw.get("f12", "")
    name = raw.get("f14", "")
    if not code or not name:
        return None

    mcap = _try_float(raw.get("f20"))
    return {
        "code": code,
        "name": name,
        "price": _try_float(raw.get("f2")),
        "pe": _try_float(raw.get("f9")),
        "pe_ttm": _try_float(raw.get("f115")),
        "pb": _try_float(raw.get("f23")),
        "market_cap": mcap,
        "market_cap_yi": round(mcap / 1e8, 1) if mcap is not None else None,
        "roe": _try_float(raw.get("f37")),
    }


# ---------------------------------------------------------------------------
# 筛选逻辑
# ---------------------------------------------------------------------------

def _screening_defaults():
    return {
        "min_cap_yi": 50,
        "min_roe": 2.5,
        "max_pe": 200,
        "exclude_bj": True,
        "exclude_new": True,
    }


def _is_st(name):
    n = (name or "").strip()
    return "ST" in n.split("*")[-1] if "*" in n else "ST" in n


def _is_new_stock(name):
    n = (name or "").strip()
    return n.startswith("N") or n.startswith("C")


def screen_stocks(all_stocks, criteria=None):
    if criteria is None:
        criteria = _screening_defaults()

    passed = []
    rejected = {
        "st_stock": [], "bj_stock": [], "new_stock": [],
        "small_cap": [], "loss_making": [], "low_roe": [],
    }

    for s in all_stocks:
        name = s.get("name", "")
        code = s.get("code", "")

        if _is_st(name):
            rejected["st_stock"].append(s); continue
        if criteria.get("exclude_bj") and code.startswith(("4", "8", "9")):
            rejected["bj_stock"].append(s); continue
        if criteria.get("exclude_new") and _is_new_stock(name):
            rejected["new_stock"].append(s); continue

        mcap_yi = s.get("market_cap_yi")
        pe = s.get("pe")
        pe_ttm = s.get("pe_ttm")
        roe = s.get("roe")

        if mcap_yi is None or mcap_yi < criteria["min_cap_yi"]:
            rejected["small_cap"].append(s); continue

        effective_pe = pe_ttm if pe_ttm is not None else pe
        if effective_pe is None or effective_pe <= 0 or effective_pe > criteria["max_pe"]:
            rejected["loss_making"].append(s); continue

        if roe is None or roe <= criteria["min_roe"]:
            rejected["low_roe"].append(s); continue

        passed.append(s)

    return passed, rejected


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

_OUTPUT_KEYS = ["code", "name", "price", "pe", "pe_ttm", "pb",
                "market_cap_yi", "roe"]


def _rejected_summary(rejected):
    labels = {
        "st_stock": "ST/*ST股", "bj_stock": "北交所",
        "new_stock": "新股(N/C)", "small_cap": "市值不达标",
        "loss_making": "亏损或PE异常", "low_roe": "ROE 过低",
    }
    return {label: len(rejected.get(k, []))
            for k, label in labels.items() if len(rejected.get(k, [])) > 0}


def _clean_passed(passed):
    return [{k: s.get(k) for k in _OUTPUT_KEYS} for s in passed]


def _print_text(passed, rejected, total, criteria):
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

    summary = _rejected_summary(rejected)
    if summary:
        print("  ── 淘汰统计 ──")
        mx = max(summary.values())
        for label, count in sorted(summary.items(), key=lambda x: -x[1]):
            bar = "█" * min(30, count * 30 // mx)
            print(f"  {label:12s}  {count:>5}  {bar}")
        print()

    if not passed:
        print("  (无股票通过筛选)")
        return

    print(f"  ── 通过筛选 ({len(passed)} 只) ──")
    print(f"  {'代码':<8s} {'名称':<10s} {'市值(亿)':>8s} {'PE(TTM)':>8s} {'ROE':>6s} {'PB':>6s}")
    print("  " + "-" * 54)

    for s in passed[:200]:
        cap_s = f"{s['market_cap_yi']:.1f}亿" if s.get('market_cap_yi') is not None else "  -"
        pe_s = f"{s['pe_ttm']:.1f}" if s.get('pe_ttm') is not None else (
            f"{s['pe']:.1f}" if s.get('pe') is not None else "  -")
        roe_s = _fmt_pct(s.get('roe'))
        pb_s = f"{s['pb']:.2f}" if s.get('pb') is not None else "  -"
        print(f"  {s['code']:<8s} {s['name']:<10s} {cap_s:>8s} {pe_s:>8s} {roe_s:>6s} {pb_s:>6s}")

    if len(passed) > 200:
        print(f"  ... (还有 {len(passed) - 200} 只未显示)")
    print()


def _print_json(passed, rejected, total, criteria):
    output = {
        "meta": {
            "date": time.strftime("%Y-%m-%d"),
            "total_screened": total,
            "passed": len(passed),
            "pass_rate_pct": round(len(passed) / max(total, 1) * 100, 2),
            "criteria": criteria,
        },
        "rejected_summary": _rejected_summary(rejected),
        "passed": _clean_passed(passed),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def _save_json(filepath, passed, rejected, total, criteria):
    output = {
        "meta": {
            "date": time.strftime("%Y-%m-%d"),
            "total_screened": total,
            "passed": len(passed),
            "pass_rate_pct": round(len(passed) / max(total, 1) * 100, 2),
            "criteria": criteria,
        },
        "rejected_summary": _rejected_summary(rejected),
        "passed": _clean_passed(passed),
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------

_FIELDS = "f2,f9,f12,f14,f20,f23,f37,f115"


def cmd_run(args):
    criteria = _screening_defaults()
    if args.min_cap is not None: criteria["min_cap_yi"] = args.min_cap
    if args.min_roe is not None: criteria["min_roe"] = args.min_roe
    if args.max_pe is not None: criteria["max_pe"] = args.max_pe
    if args.include_bj: criteria["exclude_bj"] = False

    verbose = not args.json

    # Step 1: 获取代码表
    if verbose:
        print("[INFO] 获取股票代码表...", file=sys.stderr)
    try:
        codes = _fetch_codes_from_akshare()
    except Exception as e:
        print(f"[ERROR] 获取代码表失败: {e}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        n_sh = sum(1 for c in codes if c["market"] == "sh")
        n_sz = sum(1 for c in codes if c["market"] == "sz")
        n_bj = sum(1 for c in codes if c["market"] == "bj")
        print(f"[INFO] 代码表: 沪市 {n_sh}, 深市 {n_sz}, 北交所 {n_bj}, "
              f"合计 {len(codes)}", file=sys.stderr)

    # 可选: 排除北交所
    if criteria["exclude_bj"]:
        codes = [c for c in codes if c["market"] != "bj"]

    # 可选: --top 模式（只取前 N，按代码排序近似 = 按市值取大盘股）
    if args.top and args.top < len(codes):
        codes = codes[:args.top]

    # Step 2: 批量拉取数据
    if verbose:
        print(f"[INFO] 开始批量拉取 {len(codes)} 只股票数据...", file=sys.stderr)
        t0 = time.time()

    raw_stocks = _fetch_all_stocks(codes, _FIELDS, verbose=verbose)

    if verbose:
        elapsed = time.time() - t0
        print(f"[INFO] 数据拉取耗时 {elapsed:.0f}s", file=sys.stderr)

    # Step 3: 解析
    stocks = []
    parse_failures = 0
    for raw in raw_stocks:
        s = _parse_stock(raw)
        if s:
            stocks.append(s)
        else:
            parse_failures += 1

    if verbose:
        print(f"[INFO] 解析: {len(stocks)} 有效, {parse_failures} 无效, "
              f"缺失 {len(codes) - len(raw_stocks)}", file=sys.stderr)

    if not stocks:
        print("[ERROR] 未能获取任何股票数据", file=sys.stderr)
        sys.exit(1)

    # Step 4: 筛选
    passed, rejected = screen_stocks(stocks, criteria)

    # Step 5: 输出
    if args.json:
        _print_json(passed, rejected, len(stocks), criteria)
    else:
        _print_text(passed, rejected, len(stocks), criteria)

    if args.output:
        _save_json(args.output, passed, rejected, len(stocks), criteria)
        print(f"[INFO] 结果已保存到 {args.output}", file=sys.stderr)


def cmd_test(args):
    """连通性测试 — 验证 AKShare 代码表 + ulist API + 筛选逻辑。"""
    print("[TEST] 获取股票代码表...", file=sys.stderr)
    try:
        codes = _fetch_codes_from_akshare()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[TEST] 获取到 {len(codes)} 只股票", file=sys.stderr)

    # 取前 100 只测试批量拉取
    test_codes = codes[:100]
    print(f"[TEST] 测试拉取前 100 只...", file=sys.stderr)
    raw_stocks = _fetch_all_stocks(test_codes, _FIELDS, verbose=False)

    stocks = [_parse_stock(r) for r in raw_stocks]
    stocks = [s for s in stocks if s is not None]
    print(f"[TEST] 成功获取 {len(stocks)} / 100 只", file=sys.stderr)

    # 筛选
    criteria = _screening_defaults()
    passed, rejected = screen_stocks(stocks, criteria)

    # 抽样
    print("\n── 原始数据抽样 (前 5) ──")
    for s in stocks[:5]:
        print(f"  {s['code']} {s['name']}: 市值={_fmt_yi(s.get('market_cap'))} "
              f"PE={s.get('pe')} PE_TTM={s.get('pe_ttm')} ROE={_fmt_pct(s.get('roe'))} PB={s.get('pb')}")

    print(f"\n── 筛选结果 ──")
    print(f"  总数: {len(stocks)}, 通过: {len(passed)}, 淘汰: {len(stocks) - len(passed)}")
    for label, count in sorted(_rejected_summary(rejected).items(), key=lambda x: -x[1]):
        print(f"    {label}: {count}")

    if passed:
        print(f"\n  通过列表:")
        for s in passed[:10]:
            print(f"    {s['code']} {s['name']} 市值={s['market_cap_yi']:.0f}亿 "
                  f"PE_TTM={s.get('pe_ttm', '-')} ROE={_fmt_pct(s.get('roe'))}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A股全市场量化快筛 — 第零层漏斗",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="全市场快筛")
    p_run.add_argument("--top", type=int, default=None, help="仅筛选前 N 只（按代码排序）")
    p_run.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_run.add_argument("--output", type=str, default=None, help="保存 JSON 结果")
    p_run.add_argument("--include-bj", action="store_true", help="包含北交所")
    p_run.add_argument("--min-cap", type=float, default=None, help="市值下限（亿），默认 50")
    p_run.add_argument("--min-roe", type=float, default=None, help="ROE 下限（%%），默认 2.5")
    p_run.add_argument("--max-pe", type=float, default=None, help="PE 上限，默认 200")

    p_test = sub.add_parser("test", help="连通性测试")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        cmd_run(args)
    elif args.command == "test":
        cmd_test(args)


if __name__ == "__main__":
    main()
