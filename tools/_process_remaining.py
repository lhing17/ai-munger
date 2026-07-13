"""Process remaining unmarked stocks in layer1-passed file."""
import re, json, urllib.request, sys, time

with open('reports/layer1-passed-2026-07-13.md', 'r', encoding='utf-8') as f:
    content = f.read()

with open('reports/reject_reasons.json', 'r', encoding='utf-8') as f:
    saved_reasons = json.load(f)

with open('reports/results.md', 'r', encoding='utf-8') as f:
    results = f.read()

# Find all unmarked
unmarked = []
current_ind = ''
for line in content.split('\n'):
    s = line.strip()
    if s.startswith('### '):
        m = re.match(r'### (.+?)（\d', s)
        if m: current_ind = m.group(1)
    if not re.match(r'^\|\s*\d+\s*\|\s*\d{6}\s*\|', s):
        continue
    parts = [p.strip() for p in s.split('|')]
    code = parts[2]
    name = parts[3]
    if not code.isdigit() or len(code) != 6:
        continue
    if chr(0x2705) in s or chr(0x26a0) in s or chr(0x1f6ab) in s:
        continue
    pe_raw = parts[5]
    roe_raw = parts[6]
    unmarked.append((code, name, current_ind, pe_raw, roe_raw))

print(f'Processing {len(unmarked)} unmarked stocks...')

def fetch_roes(code):
    """Fetch 5-year annual ROE for a stock."""
    mkt = 'SH' if code.startswith(('6','9')) else 'SZ'
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL&p=1&ps=5&sr=-1&st=REPORT_DATE&filter=(SECUCODE=%22{code}.{mkt}%22)(REPORT_TYPE=%22年报%22)&source=HSF10&client=PC'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        reports = (data.get('result') or {}).get('data') or []
        return [r.get('ROEJQ') for r in reports[:5] if r.get('ROEJQ') is not None]
    except Exception as e:
        return None

def judge(code, name, ind, pe_str, roes):
    """Apply Gate 2 quality screen to ROE data."""
    if roes is None or len(roes) < 3:
        return ('REJECT', f'{ind}, 财务数据不足(仅{len(roes) if roes else 0}年), 无法评估')

    roes_5 = roes[:5]
    below_12 = sum(1 for r in roes_5 if r < 12)
    has_loss = any(r < 0 for r in roes_5)
    extreme_vol = max(roes_5) > 3 * min(roes_5) if min(roes_5) > 0 else True
    avg_roe = sum(roes_5) / len(roes_5)

    try: pe = float(pe_str)
    except: pe = 999

    if has_loss:
        return ('REJECT', f'{ind}, ROE{roes_5}含亏损年, 芒格不投亏损公司')
    if below_12 >= 3:
        return ('REJECT', f'{ind}, ROE{roes_5} 至少3年<12%, 长期质量不合格')
    if below_12 >= 2 and extreme_vol:
        return ('REJECT', f'{ind}, ROE{roes_5} 2年<12%+极端波动, commodity周期股')
    if avg_roe < 12:
        return ('REJECT', f'{ind}, ROE{roes_5} 5年均值<12%, 整体回报不足')
    if below_12 >= 2:
        return ('REJECT', f'{ind}, ROE{roes_5} 2年<12%, PE {pe}x')

    if pe > 80:
        return ('REJECT', f'{ind}, ROE{roes_5}合格但PE {pe}x极贵(Gate 3 ABSURD), 芒格不付百倍PE')
    if pe > 50:
        return ('CAUTION', f'{ind}, ROE{roes_5}质量不错但PE {pe}x偏贵, 安全边际不足')

    if below_12 == 1:
        return ('CAUTION', f'{ind}, ROE{roes_5} 1年<12%, PE {pe}x')

    if avg_roe >= 20 and pe < 20:
        score = min(8.0, 7.5 + (avg_roe - 20) / 20)
        return ('PASS', f'{ind}, ROE{roes_5}全>12%+5年均{avg_roe:.0f}%极优, PE{pe}x便宜')
    if avg_roe >= 15:
        return ('PASS', f'{ind}, ROE{roes_5}全>15%稳定, PE {pe}x合理')
    return ('PASS', f'{ind}, ROE{roes_5}全>12%, PE {pe}x')

pass_add = caut_add = rej_add = 0
processed = 0

for code, name, ind, pe, roe in unmarked:
    print(f'  [{processed+1}/{len(unmarked)}] {code} {name}...', end=' ', flush=True)
    roes = fetch_roes(code)
    if roes is None:
        # Use screener ROE as fallback
        try: r = float(roe)
        except: r = 0
        if r < 5:
            verdict, reason = 'REJECT', f'{ind}, ROE仅{roe}%(数据获取失败,用快筛值), PE {pe}x'
        elif r < 12:
            verdict, reason = 'REJECT', f'{ind}, ROE{roe}%<12%门槛(数据获取失败), PE {pe}x'
        else:
            verdict, reason = 'CAUTION', f'{ind}, 财务数据获取失败, 快筛ROE{roe}%, PE {pe}x, 保守标记'
        roes_str = f'[{roe}]'
    else:
        roes_str = str([round(x,1) for x in roes[:5]])
        verdict, reason = judge(code, name, ind, pe, roes)

    # Update layer1
    mark_map = {'PASS': '✅ 6.0分 可买入', 'CAUTION': '⚠️ CAUTION 5.0分 观察', 'REJECT': '🚫 Gate 2 FAIL'}
    for i, old_line in enumerate(content.split('\n')):
        if old_line.strip().startswith(f'| ') and code in old_line:
            content = content.replace(old_line, old_line.rstrip() + ' ' + mark_map[verdict])
            break

    saved_reasons[code] = reason

    # Add to results
    if verdict == 'PASS':
        pass_add += 1
        ins = f'| {code} | PASS 可以买入 | 6.5/10 | {name} | {ind} | - | {reason} |\n'
    elif verdict == 'CAUTION':
        caut_add += 1
        ins = f'| {code} | CAUTION 观察 | 5.0/10 | {name} | {ind} | - | {reason} |\n'
    else:
        rej_add += 1
        ins = f'| {code} | REJECT | - | {name} | {ind} | - | {reason} |\n'
    results = results.replace('> 统计', ins + '\n> 统计')

    processed += 1
    print(f'{verdict}')
    if processed % 20 == 0:
        # Save checkpoint
        with open('reports/layer1-passed-2026-07-13.md', 'w', encoding='utf-8') as f:
            f.write(content)
        with open('reports/reject_reasons.json', 'w', encoding='utf-8') as f:
            json.dump(saved_reasons, f, ensure_ascii=False, indent=2)
        with open('reports/results.md', 'w', encoding='utf-8') as f:
            f.write(results)
        print(f'  [Checkpoint saved at {processed}]')
        time.sleep(0.5)

# Update stats
import re as re_mod
n = 348 + processed
results = re_mod.sub(r'(\d+)已分析', f'{n}已分析', results)
results = re_mod.sub(r'PASS (\d+)只', f'PASS {int(re_mod.search(r"PASS (\d+)只", results).group(1)) + pass_add}只', results) if re_mod.search(r'PASS (\d+)只', results) else results
results = re_mod.sub(r'CAUTION (\d+)只', lambda m: f'CAUTION {int(m.group(1))+caut_add}只', results)
results = re_mod.sub(r'REJECT (\d+)只', lambda m: f'REJECT {int(m.group(1))+rej_add}只', results)

# Final save
with open('reports/layer1-passed-2026-07-13.md', 'w', encoding='utf-8') as f:
    f.write(content)
with open('reports/reject_reasons.json', 'w', encoding='utf-8') as f:
    json.dump(saved_reasons, f, ensure_ascii=False, indent=2)
with open('reports/results.md', 'w', encoding='utf-8') as f:
    f.write(results)

print(f'\nDone! {n}/556 marked ({n/556*100:.1f}%)')
print(f'PASS +{pass_add}, CAUTION +{caut_add}, REJECT +{rej_add}')
