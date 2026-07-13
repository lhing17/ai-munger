"""Re-analyze stocks from 002533 onwards that used quarterly ROE as fallback."""
import re, json, urllib.request, time, sys

with open('reports/results.md', 'r', encoding='utf-8') as f:
    results = f.read()

with open('reports/layer1-passed-2026-07-13.md', 'r', encoding='utf-8') as f:
    layer1 = f.read()

# Find line index where 002533 first appears in results.md
all_lines = results.split('\n')
start_idx = None
for i, line in enumerate(all_lines):
    if '002533' in line and line.strip().startswith('| '):
        start_idx = i
        break

if start_idx is None:
    print('ERROR: Could not find 002533 in results.md')
    sys.exit(1)

# Collect all codes from this point onwards (excluding later manually analyzed ones)
manual_codes = {'601857','300750','600519','600809','000858','603195'}
affected = []
for i in range(start_idx, len(all_lines)):
    line = all_lines[i].strip()
    m = re.match(r'\|\s*(\d{6})\s*\|', line)
    if m:
        code = m.group(1)
        if code not in manual_codes:
            affected.append(code)

# Remove duplicates preserving order
seen = set()
affected_unique = []
for c in affected:
    if c not in seen:
        seen.add(c)
        affected_unique.append(c)

print(f'Found {len(affected_unique)} unique codes to re-analyze (from line {start_idx+1})')

# Parse layer1 for PE data
layer1_data = {}
current_ind = ''
for line in layer1.split('\n'):
    s = line.strip()
    if s.startswith('### '):
        m = re.match(r'### (.+?)（\d', s)
        if m: current_ind = m.group(1)
    m = re.match(r'\|\s*\d+\s*\|\s*(\d{6})\s*\|\s*(.+?)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|', s)
    if m:
        code = m.group(1)
        name = m.group(2).strip().split('|')[0].strip()
        layer1_data[code] = {'name': name, 'pe': m.group(4), 'ind': current_ind}

def fetch_with_retry(code, retries=3):
    """Fetch annual ROE with retry and delay."""
    mkt = 'SH' if code.startswith(('6','9')) else 'SZ'
    url = (f'https://datacenter.eastmoney.com/securities/api/data/get'
           f'?type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL&p=1&ps=5&sr=-1&st=REPORT_DATE'
           f'&filter=(SECUCODE=%22{code}.{mkt}%22)(REPORT_TYPE=%22%E5%B9%B4%E6%8A%A5%22)'
           f'&source=HSF10&client=PC')
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            records = (data.get('result') or {}).get('data') or []
            if records:
                return [r.get('ROEJQ') for r in records[:5] if r.get('ROEJQ') is not None]
            # Try without annual filter
            url2 = url.replace('%E5%B9%B4%E6%8A%A5', '')
            req2 = urllib.request.Request(url2, headers={
                'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/'})
            with urllib.request.urlopen(req2, timeout=15) as resp2:
                data2 = json.loads(resp2.read().decode('utf-8'))
            records2 = (data2.get('result') or {}).get('data') or []
            return [r.get('ROEJQ') for r in records2[:5] if r.get('ROEJQ') is not None]
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
    return None

def judge(roes, pe_str):
    if roes is None or len(roes) < 3:
        return ('REJECT', f'财务数据不足(仅{len(roes) if roes else 0}年)')
    below_12 = sum(1 for r in roes if r < 12)
    has_loss = any(r < 0 for r in roes)
    avg_roe = sum(roes) / len(roes)
    try: pe = float(pe_str)
    except: pe = 999
    roe_str = str([round(r,1) for r in roes[:5]])

    if has_loss:
        return ('REJECT', f'ROE{roe_str}含亏损年')
    if below_12 >= 3:
        return ('REJECT', f'ROE{roe_str}至少3年<12%, 长期质量不足')
    if avg_roe < 10:
        return ('REJECT', f'ROE{roe_str}5年均值<10%, 回报严重不足')
    if below_12 >= 2:
        return ('REJECT', f'ROE{roe_str}2年<12%, PE{pe}x')
    if pe > 80:
        return ('REJECT', f'ROE{roe_str}合格但PE{pe}x极贵(Gate 3 ABSURD)')
    if pe > 50:
        return ('CAUTION', f'ROE{roe_str}质量不错但PE{pe}x偏高')
    if below_12 == 1:
        return ('CAUTION', f'ROE{roe_str}1年<12%, PE{pe}x')
    if avg_roe >= 25 and pe < 20:
        return ('PASS', f'ROE{roe_str}极优(均值{avg_roe:.0f}%), PE{pe}x便宜')
    if avg_roe >= 20:
        return ('PASS', f'ROE{roe_str}优秀(均值{avg_roe:.0f}%), PE{pe}x合理')
    if avg_roe >= 15:
        return ('PASS', f'ROE{roe_str}良好(均值{avg_roe:.0f}%), PE{pe}x')
    return ('PASS', f'ROE{roe_str}全>12%(均值{avg_roe:.0f}%), PE{pe}x')

# Also need to track all lines to properly rebuild results.md
# Strategy: rebuild the file from scratch

# First pass: build a map of code -> corrected entry
corrected = {}
changes_summary = {'PASS->PASS':0, 'PASS->CAUTION':0, 'PASS->REJECT':0,
                   'CAUTION->PASS':0, 'CAUTION->CAUTION':0, 'CAUTION->REJECT':0,
                   'REJECT->PASS':0, 'REJECT->CAUTION':0, 'REJECT->REJECT':0,
                   'SKIP': 0}

processed = 0
for code in affected_unique:
    fd = layer1_data.get(code, {})
    if not fd:
        continue

    name = fd['name']
    pe = fd['pe']
    ind = fd['ind']

    # Get old verdict
    old_line = ''
    for l in all_lines:
        if l.strip().startswith(f'| {code} |'):
            old_line = l
            old_verdict = 'PASS' if 'PASS' in l else ('CAUTION' if 'CAUTION' in l else 'REJECT')
            break

    roes = fetch_with_retry(code)
    if roes is None:
        corrected[code] = old_line  # Keep original
        changes_summary['SKIP'] += 1
        processed += 1
        continue

    verdict, reason = judge(roes, pe)
    full_reason = f'{ind}, {reason}'

    score_map = {'PASS': '6.5/10', 'CAUTION': '5.0/10', 'REJECT': '-'}
    verd_map = {'PASS': 'PASS 可以买入', 'CAUTION': 'CAUTION 观察', 'REJECT': 'REJECT'}
    link = '-'

    entry = f'| {code} | {verd_map[verdict]} | {score_map[verdict]} | {name} | {ind} | {link} | {full_reason} |'
    corrected[code] = entry
    changes_summary[f'{old_verdict}->{verdict}'] += 1

    processed += 1
    if processed % 20 == 0:
        print(f'  [{processed}/{len(affected_unique)}]')
    time.sleep(0.15)  # Light rate limit

# Now rebuild results.md: keep lines before 002533, then use corrected entries
new_results = all_lines[:start_idx]  # Header + first part
for code in affected_unique:
    if code in corrected:
        new_results.append(corrected[code])
    else:
        # Keep old line if exists
        for l in all_lines:
            if l.strip().startswith(f'| {code} |'):
                new_results.append(l)
                break

# Add any remaining lines after the affected range
# Find the last affected line index
last_idx = start_idx
for i in range(len(all_lines)-1, start_idx, -1):
    for code in affected_unique:
        if code in all_lines[i]:
            last_idx = max(last_idx, i)
            break

# Add non-affected lines after the range
for i in range(last_idx + 1, len(all_lines)):
    line = all_lines[i]
    m = re.match(r'\|\s*(\d{6})\s*\|', line.strip())
    if m and m.group(1) in corrected:
        continue  # Already handled
    new_results.append(line)

# Fix stats
pass_n = len([l for l in new_results if 'PASS 可以买入' in l and l.strip().startswith('| ')])
caut_n = len([l for l in new_results if 'CAUTION 观察' in l and l.strip().startswith('| ')])
rej_n = len([l for l in new_results if '| REJECT |' in l and l.strip().startswith('| ')])
total = pass_n + caut_n + rej_n

for i, l in enumerate(new_results):
    if '统计' in l and l.strip().startswith('>'):
        new_results[i] = f'> 统计: {total} 已分析 | PASS {pass_n}只 | CAUTION {caut_n}只 | REJECT {rej_n}只 | 拒绝率 {rej_n/total*100:.1f}% | 通过率 {pass_n/total*100:.1f}%'
        break

with open('reports/results.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_results))

print(f'\nDone! Re-analyzed {processed} stocks ({changes_summary["SKIP"]} API failures)')
print('Changes:')
for k, v in sorted(changes_summary.items()):
    if v > 0:
        print(f'  {k}: {v}')
print(f'Final: PASS={pass_n} CAUTION={caut_n} REJECT={rej_n} Total={total}')
