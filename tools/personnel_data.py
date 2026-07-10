#!/usr/bin/env python3
"""A股管理层/股东数据工具 — 东方财富 API，零外部依赖。

为 management-check Skill 提供高管履历、股东结构、质押、分红数据。

用法:
    python tools/personnel_data.py full 600519
    python tools/personnel_data.py executives 600519
    python tools/personnel_data.py shareholders 600519
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

_TIMEOUT = 15
_API_BASE = "https://datacenter.eastmoney.com/securities/api/data/get"


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
        raise ConnectionError(f"请求失败: {url} -- {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def _fetch_json(url, params=None):
    if params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(params)}"
    return json.loads(_fetch(url))


def _clean_code(code: str) -> str:
    code = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    return code


def _market(code: str) -> str:
    code = _clean_code(code)
    if code.startswith(("6", "9", "5")):
        return "SH"
    return "SZ"


def _secucode(code: str) -> str:
    return f"{_clean_code(code)}.{_market(code)}"


# ---------------------------------------------------------------------------
# 公司基本信息（含高管、实控人）
# ---------------------------------------------------------------------------

def _get_basic_info(code: str) -> dict:
    """RPT_F10_ORG_BASICINFO -- 包含董事长/总经理/董秘/实控人。"""
    params = {
        "type": "RPT_F10_ORG_BASICINFO",
        "sty": "ALL",
        "filter": f'(SECUCODE="{_secucode(code)}")',
        "p": "1", "ps": "1",
        "source": "HSF10", "client": "PC",
    }
    try:
        data = _fetch_json(_API_BASE, params)
        rows = data.get("result", {}).get("data", [])
        return rows[0] if rows else {}
    except Exception as e:
        print(f"[WARN] 公司基本信息获取失败: {e}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# 高管信息
# ---------------------------------------------------------------------------

def cmd_executives(code: str) -> dict:
    """从 RPT_F10_ORG_BASICINFO 提取高管信息。"""
    info = _get_basic_info(code)

    key_positions = []
    if info.get("CHAIRMAN"):
        key_positions.append({"name": info["CHAIRMAN"], "title": "董事长"})
    if info.get("PRESIDENT") and info.get("PRESIDENT") != info.get("CHAIRMAN"):
        key_positions.append({"name": info["PRESIDENT"], "title": "总经理/总裁"})
    if info.get("SECRETARY"):
        key_positions.append({"name": info["SECRETARY"], "title": "董事会秘书"})
    if info.get("LEGAL_PERSON") and info.get("LEGAL_PERSON") != info.get("CHAIRMAN"):
        key_positions.append({"name": info["LEGAL_PERSON"], "title": "法定代表人"})

    # 独立董事
    ind_dir_str = info.get("INDEDIRECTORS", "")
    ind_directors = [n.strip() for n in ind_dir_str.split(",") if n.strip()] if ind_dir_str else []

    return {
        "code": _clean_code(code),
        "company_name": info.get("SECURITY_NAME_ABBR", ""),
        "key_executives": key_positions,
        "independent_directors": ind_directors,
        "founded": str(info.get("FOUND_DATE", ""))[:10],
        "listed": str(info.get("LISTING_DATE", ""))[:10],
    }


# ---------------------------------------------------------------------------
# 股东信息（前十大股东 + 实控人 + 质押风险评估）
# ---------------------------------------------------------------------------

def cmd_shareholders(code: str) -> dict:
    """RPT_DMSK_HOLDERS + RPT_F10_ORG_BASICINFO 获取股东/实控人。"""
    secucode = _secucode(code)

    # 前十大股东（取最近报告期）
    top10 = []
    try:
        params = {
            "type": "RPT_DMSK_HOLDERS",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": "1", "ps": "50",
            "sr": "-1", "st": "END_DATE",
            "source": "HSF10", "client": "PC",
        }
        data = _fetch_json(_API_BASE, params)
        rows = data.get("result", {}).get("data", [])
        # 只取最新报告期的前10大股东
        if rows:
            latest_date = rows[0].get("END_DATE", "")
            latest_rows = [r for r in rows if r.get("END_DATE") == latest_date]
            # 按排名排序
            latest_rows.sort(key=lambda r: r.get("RANK", 999))
            for r in latest_rows[:10]:
                ratio_val = r.get("HOLD_RATIO")
                if isinstance(ratio_val, (int, float)):
                    pct = float(ratio_val)
                elif isinstance(ratio_val, str) and ratio_val:
                    try:
                        pct = float(ratio_val.replace("%", ""))
                    except (ValueError, TypeError):
                        pct = None
                else:
                    pct = None
                top10.append({
                    "name": r.get("HOLDER_NAME", ""),
                    "stake_pct": round(pct, 2) if pct is not None else None,
                    "shares_held": r.get("HOLD_NUM"),
                    "type": r.get("HOLDER_NATURE", ""),
                    "rank": r.get("RANK"),
                })
    except Exception as e:
        print(f"[WARN] 股东数据获取失败: {e}", file=sys.stderr)

    # 实控人
    info = _get_basic_info(code)
    controlling = info.get("CONTROL_HOLDER", "")
    control_ratio = info.get("CONTROL_DIRECT_RATIO", "")
    real_controller = info.get("REAL_CONTROLER", "")

    # 质押风险评估：通过控股股东是否质押间接判断
    # 注：东方财富 datacenter API 不直接提供单只股票质押比例，
    # 质押信息需通过 RPT_GDZY_ZYJG_SUM（机构维度）或网页端获取。
    # 此处暂用间接方式：如果控股股东的持股无变化或被冻结，标记关注。
    pledge_risk = "需通过其他渠道核实质押详情（东方财富datacenter API未提供单只股票质押比例接口）"

    for h in top10:
        if h.get("name") == controlling:
            pledge_risk = ("控股股东位列十大股东，质押状态需查网页端"
                           " https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html"
                           f"?type=web&code={secucode}#/pledge")

    return {
        "code": _clean_code(code),
        "top10_shareholders": top10,
        "controlling_shareholder": controlling,
        "controlling_shareholder_stake": control_ratio,
        "real_controller": real_controller,
        "pledge_assessment": pledge_risk,
    }


# ---------------------------------------------------------------------------
# 分红记录 + 股本变动
# ---------------------------------------------------------------------------

def cmd_capital_actions(code: str) -> dict:
    """RPT_SHAREBONUS_DET 分红 + RPT_F10_EH_EQUITY 股本变动。"""
    secucode = _secucode(code)

    # 分红记录
    dividends = []
    try:
        params = {
            "type": "RPT_SHAREBONUS_DET",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": "1", "ps": "5",
            "sr": "-1", "st": "REPORT_DATE",
            "source": "HSF10", "client": "PC",
        }
        data = _fetch_json(_API_BASE, params)
        rows = data.get("result", {}).get("data", [])
        for r in rows[:5]:
            report_date = str(r.get("REPORT_DATE", ""))[:10]
            year = report_date[:4] if report_date else ""
            dividends.append({
                "year": year,
                "report_date": report_date,
                "dividend_per_share": r.get("PRETAX_BONUS_RMB"),
                "plan": r.get("IMPL_PLAN_PROFILE", ""),
                "ex_date": str(r.get("EX_DIVIDEND_DATE", ""))[:10],
                "status": r.get("ASSIGN_PROGRESS", ""),
            })
    except Exception as e:
        print(f"[WARN] 分红数据获取失败: {e}", file=sys.stderr)

    # 股本变动
    dilution = None
    dilution_assessment = "数据不足"
    try:
        params = {
            "type": "RPT_F10_EH_EQUITY",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": "1", "ps": "5",
            "sr": "-1", "st": "END_DATE",
            "source": "HSF10", "client": "PC",
        }
        data = _fetch_json(_API_BASE, params)
        rows = data.get("result", {}).get("data", [])
        shares_list = []
        for s in rows[:5]:
            ts = s.get("TOTAL_SHARES")
            if ts:
                shares_list.append(float(ts))
        if len(shares_list) >= 2:
            dilution = round(
                (shares_list[0] / shares_list[-1]) ** (1 / (len(shares_list) - 1)) - 1, 4
            ) * 100
            if dilution < 1:
                dilution_assessment = "股本稳定，无明显稀释"
            elif dilution < 3:
                dilution_assessment = f"轻微稀释，年化{dilution:.1f}%"
            else:
                dilution_assessment = f"稀释率偏高: {dilution:.1f}%/年（>3%，红警）"
    except Exception as e:
        print(f"[WARN] 股本数据获取失败: {e}", file=sys.stderr)

    return {
        "code": _clean_code(code),
        "dividend_history": dividends,
        "total_shares_dilution_pct_annual": dilution,
        "dilution_assessment": dilution_assessment,
    }


# ---------------------------------------------------------------------------
# 完整报告
# ---------------------------------------------------------------------------

def cmd_full(code: str) -> dict:
    return {
        "code": _clean_code(code),
        "executives": cmd_executives(code),
        "ownership": cmd_shareholders(code),
        "capital_actions": cmd_capital_actions(code),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A股管理层/股东/分红数据工具 -- 东方财富API，零外部依赖",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_exe = sub.add_parser("executives", help="高管信息（董事长/总经理/董秘/独董）")
    p_exe.add_argument("code", help="股票代码，如 600519")

    p_sh = sub.add_parser("shareholders", help="前十股东 + 实控人")
    p_sh.add_argument("code", help="股票代码，如 600519")

    p_cap = sub.add_parser("dividends", help="分红记录 + 股本变动")
    p_cap.add_argument("code", help="股票代码，如 600519")

    p_full = sub.add_parser("full", help="完整报告（高管+股东+分红）")
    p_full.add_argument("code", help="股票代码，如 600519")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "executives": lambda: cmd_executives(args.code),
        "shareholders": lambda: cmd_shareholders(args.code),
        "dividends": lambda: cmd_capital_actions(args.code),
        "full": lambda: cmd_full(args.code),
    }

    result = cmds[args.command]()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
