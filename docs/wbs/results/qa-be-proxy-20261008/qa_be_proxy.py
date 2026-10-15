"""BE 담당 QA 대행(#103 10-08 수락분) — E1 학원 서버. 본인 $RUN 검사·이미지만 만들고 지운다.
결과는 케이스별 기대·실제·판정을 JSON으로 남긴다. 공용 설정 변경·장애 주입·남의 데이터 삭제 없음."""
import csv, hashlib, io, json, re, sys, time, uuid, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

ROOT = 'C:/CQC'
DEMO = f'{ROOT}/data/processed/realtime-apple-arrival-demo/groups'
BE = 'http://192.168.133.106:8000'
KST = timezone(timedelta(hours=9))
RUN = sys.argv[2] if len(sys.argv) > 2 else 'qa-be-' + datetime.now(KST).strftime('%m%d%H%M')
REUSE = len(sys.argv) > 2
D = datetime.now(KST).strftime('%Y-%m-%d')
OUT = sys.argv[1]
MODEL = 'cqc-apple-separate12-focal-v2-cal-20260930'
results, raw = [], {}


def rec(case, verdict, expected, actual, note=''):
    results.append({'case': case, 'result': verdict, 'expected': expected, 'actual': actual, 'note': note})
    print(f'{case:10s} {verdict:6s} {json.dumps(actual, ensure_ascii=False)[:260]}', flush=True)


def http(url, method='GET', body=None, ctype=None, timeout=90):
    h = {'Content-Type': ctype} if ctype else {}
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data, st, hd = r.read(), r.status, r.headers
    except urllib.error.HTTPError as e:
        data, st, hd = e.read(), e.code, e.headers
    # 서버가 소문자 헤더 이름을 보내므로 대소문자 없이 찾는다
    hd = {k.title(): v for k, v in hd.items()}
    try:
        js = json.loads(data)
    except Exception:
        js = None
    return st, js, hd, data


def get(path):
    return http(BE + path)


def multipart(fields, files):
    bd = uuid.uuid4().hex
    body = bytearray()
    for k, v in fields:
        body += f'--{bd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for name, fn, data, ctype in files:
        body += f'--{bd}\r\nContent-Disposition: form-data; name="{name}"; filename="{fn}"\r\nContent-Type: {ctype}\r\n\r\n'.encode() + data + b'\r\n'
    body += f'--{bd}--\r\n'.encode()
    return bytes(body), f'multipart/form-data; boundary={bd}'


def send(iid, group, brix=None, n=12, broken=False):
    d = f'{DEMO}/{group}'
    meta = json.load(open(f'{d}/request.json', encoding='utf-8'))['metadata'][:n]
    fields = [('inspection_id', iid), ('metadata', json.dumps(meta))]
    if brix is not None:
        fields.append(('virtual_brix', str(brix)))
    files = []
    for i in range(n):
        data = open(f'{d}/frame_{i:02d}.png', 'rb').read()
        if broken and i == 0:
            data = data[:20000]
        files.append(('images', f'frame_{i:02d}.png', data, 'image/png'))
    body, ct = multipart(fields, files)
    st, js, _, _ = http(f'{BE}/v1/inspections', 'POST', body, ct)
    return st, js


def history(params):
    st, js, hd, _ = get('/v1/quality/inspections?' + params)
    return st, js, hd


def find(iid, extra=''):
    for page in range(1, 6):
        st, js, _ = history(f'from={D}&to={D}&pageSize=200&page={page}{extra}')
        for row in js.get('items', []):
            if row['id'] == iid:
                return row
        if len(js.get('items', [])) < 200:
            break
    return None


def images(params=''):
    return get('/v1/quality/fault-images' + (('?' + params) if params else ''))


snap0 = get('/v1/quality/snapshot')[1]
raw['preflight'] = {'run': RUN, 'date_kst': D, 'snapshot_revision': snap0['revision'], 'retention': snap0['retention'],
                    'source': snap0['source'], 'started_kst': datetime.now(KST).isoformat()}
img0 = images()[1]['items']
raw['images_before'] = {'total': len(img0), 'by_category': {c: sum(1 for x in img0 if x['category'] == c) for c in ('SYSTEM_ERROR', 'LOW_CONFIDENCE')}}
print('RUN', RUN, raw['preflight'], raw['images_before'])

# 본인 검사 6건(정상 2, 당도 누락, 저신뢰, 손상 사진, 하이픈 시작 ID)
sent = {}
for key, iid, group, brix, kw in [
    ('FL', f'{RUN}-ins01-FL-13.9', 'demo-601031008000-000', 13.9, {}),
    ('YS', f'{RUN}-ins01-YS-15.0', 'demo-601143013000-000', 15.0, {}),
    ('ins03', f'{RUN}-ins03', 'demo-601031008000-000', None, {}),
    ('LQ', f'{RUN}-ins04-LQ', 'demo-601031028000-000', 15.0, {}),
    ('ins08', f'{RUN}-ins08', 'demo-601031008000-000', 15.0, {'n': 1, 'broken': True}),
    ('ops11', f'-{RUN}-ops11', 'demo-601031008000-000', 13.9, {}),
]:
    if REUSE:  # 이미 만든 본인 검사를 다시 쓴다(중복 생성 안 함)
        sent[key] = {'id': iid, 'status': 200, 'reused': True}
        continue
    st, js = send(iid, group, brix, **kw)
    sent[key] = {'id': iid, 'status': st, 'inspection_status': (js or {}).get('inspection_status'), 'decision_reason': (js or {}).get('decision_reason'),
                 'target_bin_code': (js or {}).get('target_bin_code'), 'error_code': (js or {}).get('error_code')}
    print('send', key, sent[key])
raw['sent'] = sent
time.sleep(3)

# QA-OPS-03
row = find(sent['FL']['id'])
st, js, _ = history(f'from={D}&to={D}&pageSize=200')
ts = [r['timestamp'] for r in js['items']]
exp3 = 'B-FL 13.9: 부사/특/DEMO_BIN_01/PASS/COMPLETED/NONE, confidence≈99.0·cultivar≈100.0, brix 13.9 비실측, 모델 버전, control SUCCEEDED·persistence SAVED, 시각 3형식 일치, 내림차순, bins에 DEMO_BIN_01'
ok3 = bool(row) and row['variety'] == '부사' and row['grade'] == '특' and row['bin'] == 'DEMO_BIN_01' and row['status'] == 'PASS' \
    and row['processingStatus'] == 'COMPLETED' and row['errorCode'] == 'NONE' and abs(row['confidence'] - 99.0) < 1 and abs(row['cultivarConfidence'] - 100) < 1 \
    and row['virtualBrix'] == 13.9 and row['brixMeasured'] is False and row['modelVersion'] == MODEL and row['inferenceMs'] > 0 \
    and row['control'] == 'SUCCEEDED' and row['persistence'] == 'SAVED' and row['faults'] == [] and row['misclassification'] == 'NONE' \
    and row['reviewRequired'] is False and row['excluded'] is False and ts == sorted(ts, reverse=True)
if row:
    k = datetime.fromtimestamp(row['timestamp'] / 1000, KST)
    ok3 = ok3 and row['date'] == k.strftime('%Y-%m-%d') and row['time'] == k.strftime('%H:%M:%S.') + f'{k.microsecond // 1000:03d}'
bins = js.get('bins')
ok3 = ok3 and (bins is None or 'DEMO_BIN_01' in bins)
rec('QA-OPS-03', '통과' if ok3 else '실패', exp3, {k: row.get(k) for k in ('id', 'variety', 'grade', 'bin', 'status', 'processingStatus', 'errorCode', 'confidence', 'cultivarConfidence', 'virtualBrix', 'brixMeasured', 'modelVersion', 'inferenceMs', 'control', 'persistence', 'faults', 'misclassification', 'reviewRequired', 'excluded', 'date', 'time', 'timestamp')} if row else None,
    f'목록 {len(ts)}건 내림차순={ts == sorted(ts, reverse=True)}, bins 필드 {"있음·DEMO_BIN_01 포함" if bins and "DEMO_BIN_01" in bins else ("없음" if bins is None else "DEMO_BIN_01 없음")}')

# QA-OPS-04
rows = {k: find(sent[k]['id']) for k in ('FL', 'LQ', 'ins03', 'ins08')}
want = {'FL': ('PASS', 'COMPLETED', 'NONE', True, False, 'DEMO_BIN_'), 'LQ': ('REVIEW', 'COMPLETED', 'NONE', True, False, 'TEST_REINSPECTION_BIN'),
        'ins03': ('REVIEW', 'COMPLETED', 'NONE', True, False, 'TEST_REINSPECTION_BIN'), 'ins08': ('FAIL', 'ERROR', 'INFERENCE_ERROR', False, True, 'TEST_REINSPECTION_BIN')}
got4, ok4 = {}, True
for k, (s, p, e, has, exc, b) in want.items():
    r = rows[k]
    got4[k] = r and {x: r[x] for x in ('status', 'processingStatus', 'errorCode', 'variety', 'grade', 'excluded', 'bin', 'faults', 'confidence', 'cultivarConfidence', 'inferenceMs', 'modelVersion')}
    good = bool(r) and r['status'] == s and r['processingStatus'] == p and r['errorCode'] == e and bool(r['variety']) == has and bool(r['grade']) == has and r['excluded'] is exc and r['bin'].startswith(b)
    if k == 'ins08' and r:
        good = good and r['faults'][:1] == ['INFERENCE_ERROR'] and all(r[x] is None for x in ('confidence', 'cultivarConfidence', 'inferenceMs', 'modelVersion'))
    ok4 = ok4 and good
rec('QA-OPS-04', '통과(부분)' if ok4 else '실패', 'INS-01 정상·INS-04 저신뢰·INS-03 당도 누락·INS-08 오류 행의 status/processingStatus/errorCode/variety·grade/excluded/bin, 오류 행 faults·null 필드',
    got4, 'E1 행 4종 확인. INS-10 연결 실패·INS-12 시간 초과 행은 E2 전용이라 미확인(BE E2 INS-10·12 통과 결과로 보완)')

# QA-OPS-05
def q(extra):
    st, js, _ = history(f'from={D}&to={D}&pageSize=200{extra}')
    return st, js


checks = {}
def chk(name, extra, pred, need=None):
    st, js = q(extra)
    items = js.get('items', []) if js else []
    ids = {r['id'] for r in items}
    ok = st == 200 and all(pred(r) for r in items) and (need is None or need in ids or any(r['id'] == need for r in items))
    if need and need not in ids:
        r = find(need, extra)
        ok = ok and r is not None
    tot_ok = js['total'] >= len(items) and (js['total'] > 200 or js['total'] == len(items))
    checks[name] = {'status': st, 'total': js.get('total') if js else None, 'items': len(items), 'ok': ok and tot_ok}
    return ok and tot_ok


chk('a variety=부사', '&variety=%EB%B6%80%EC%82%AC', lambda r: r['variety'] == '부사')
chk('b 양광·보통', '&variety=%EC%96%91%EA%B4%91&grade=%EB%B3%B4%ED%86%B5', lambda r: r['variety'] == '양광' and r['grade'] == '보통', sent['YS']['id'])
chk('c bin=DEMO_BIN_02', '&bin=DEMO_BIN_02', lambda r: r['bin'] == 'DEMO_BIN_02')
chk('d 재검사함(저신뢰)', '&bin=TEST_REINSPECTION_BIN', lambda r: r['bin'] == 'TEST_REINSPECTION_BIN', sent['LQ']['id'])
chk('d 재검사함(당도 누락)', '&bin=TEST_REINSPECTION_BIN', lambda r: True, sent['ins03']['id'])
chk('d 재검사함(오류)', '&bin=TEST_REINSPECTION_BIN', lambda r: True, sent['ins08']['id'])
chk('e COMPLETED', '&processingStatus=COMPLETED', lambda r: r['processingStatus'] == 'COMPLETED')
chk('f ERROR', '&processingStatus=ERROR', lambda r: r['processingStatus'] == 'ERROR', sent['ins08']['id'])
chk('h INFERENCING', '&processingStatus=INFERENCING', lambda r: False)
checks['h INFERENCING']['ok'] = checks['h INFERENCING']['total'] == 0 and checks['h INFERENCING']['status'] == 200
chk('i errorCode=NONE', '&errorCode=NONE', lambda r: r['errorCode'] == 'NONE', sent['LQ']['id'])
chk('i errorCode=NONE(당도 누락)', '&errorCode=NONE', lambda r: True, sent['ins03']['id'])
chk('j INFERENCE_ERROR', '&errorCode=INFERENCE_ERROR', lambda r: r['errorCode'] == 'INFERENCE_ERROR', sent['ins08']['id'])
chk('l misclassification=NONE', '&misclassification=NONE', lambda r: r['misclassification'] == 'NONE')
chk('l misclassification=OTHER', '&misclassification=OTHER', lambda r: r['misclassification'] == 'OTHER')
st, js, _ = history('from=2026-01-01&to=2026-01-01&pageSize=50')
checks['m 2026-01-01'] = {'status': st, 'total': js['total'], 'ok': st == 200 and js['total'] == 0}
chk('n 부사·특·BIN_01', '&variety=%EB%B6%80%EC%82%AC&grade=%ED%8A%B9&bin=DEMO_BIN_01', lambda r: r['variety'] == '부사' and r['grade'] == '특' and r['bin'] == 'DEMO_BIN_01', sent['FL']['id'])
st, js = q('&processingStatus=TIMEOUT')
checks['g TIMEOUT(E2)'] = {'status': st, 'total': js['total'], 'ok': st == 200 and all(r['processingStatus'] == 'TIMEOUT' for r in js['items'])}
st, js = q('&errorCode=INFERENCE_TIMEOUT')
checks['k INFERENCE_TIMEOUT(E2)'] = {'status': st, 'total': js['total'], 'ok': st == 200 and all(r['errorCode'] == 'INFERENCE_TIMEOUT' for r in js['items'])}
ok5 = all(v['ok'] for v in checks.values())
rec('QA-OPS-05', '통과(부분)' if ok5 else '실패', 'a~n 필터 결과가 조건만 포함하고 본인 $RUN 행 포함, total·items 일치', checks,
    'g·k의 `$RUN-ins12`(시간 초과)는 E2 전용이라 필터 정합성만 확인. l OTHER는 BE OPS-16에서 지정 후 NONE으로 복구해 오늘 OTHER 행 수만 기록')

# QA-OPS-06
st1, p1, _ = history(f'pageSize=50&page=1')
st2, p2, _ = history(f'pageSize=50&page=2&snapshotAt={p1.get("snapshotAt", "")}' if p1.get('snapshotAt') else 'pageSize=50&page=2')
ids1, ids2 = [r['id'] for r in p1['items']], [r['id'] for r in p2['items']]
s100, j100, _ = history('pageSize=100'); s200, j200, _ = history('pageSize=200')
s20, j20, _ = history('pageSize=20'); s0, j0, _ = history('page=0')
last = (p1['total'] + 49) // 50
sl, jl, _ = history(f'pageSize=50&page={last + 1}')
o6 = {'a': [len(ids1), len(ids2), len(set(ids1) & set(ids2)), p1['total'], p2['total']], 'b': [len(j100['items']), j100.get('pageSize'), len(j200['items']), j200.get('pageSize')],
      'c': [s20, j20], 'd': [s0, j0], 'e': [sl, len(jl['items']), jl['total']]}
ok6 = len(ids1) == 50 and len(ids2) == 50 and not set(ids1) & set(ids2) and abs(p1['total'] - p2['total']) <= 2 and len(j100['items']) <= 100 and j100.get('pageSize') == 100 \
    and len(j200['items']) <= 200 and j200.get('pageSize') == 200 and s20 == 422 and j20 == {'code': 'INVALID_QUERY'} and s0 == 422 and j0 == {'code': 'INVALID_QUERY'} and sl == 200 and jl['items'] == []
rec('QA-OPS-06', '통과' if ok6 else '실패', 'a 50건씩·중복 없음, b ≤100·200·pageSize 반환, c·d 422 INVALID_QUERY, e 빈 목록', o6,
    'a의 total은 Simulator 입력으로 두 요청 사이 0~1건 늘 수 있어 ±2 허용' if p1['total'] != p2['total'] else '')

# QA-OPS-08
o8, ok8 = {}, True
now_ms = int(time.time() * 1000)
for ep in ('/v1/quality/inspections', '/v1/quality/statistics', '/v1/quality/inspections.csv', '/v1/quality/statistics.csv'):
    for name, qs, code in [('a', 'foo=1', 'UNKNOWN_QUERY_FIELD'), ('b', 'from=2026-09-30&to=2026-09-29', 'INVALID_DATE_RANGE'),
                           ('c', f'snapshotAt={now_ms + 600000}', 'INVALID_SNAPSHOT'), ('d', 'variety=%EC%82%AC%EA%B3%BC', 'INVALID_QUERY'), ('e', 'from=2026-13-01', 'INVALID_QUERY')]:
        st, js, hd, _ = get(f'{ep}?{qs}')
        good = st == 422 and js == {'code': code} and 'no-store' in hd.get('Cache-Control', '')
        o8[f'{ep.split("/")[-1]} {name}'] = [st, js]
        ok8 = ok8 and good
st, js, hd, _ = get('/v1/quality/statistics?minutes=1')
o8['statistics f minutes=1'] = [st, js]
ok8 = ok8 and st == 422 and js == {'code': 'UNKNOWN_QUERY_FIELD'}
rec('QA-OPS-08', '통과' if ok8 else '실패', '4개 엔드포인트 × a~e 422와 지정 code, f statistics?minutes=1 422 UNKNOWN_QUERY_FIELD, 본문 code 하나·no-store', o8)

# QA-OPS-10 / QA-OPS-11
st, js, hd, data = get(f'/v1/quality/inspections.csv?from={D}&to={D}')
tot = history(f'from={D}&to={D}&pageSize=50')[1]['total']
text = data.decode('utf-8-sig')
lines = data.split(b'\r\n')
rd = list(csv.reader(io.StringIO(text)))
header = rd[0]
cols = ['inspection_id', 'date', 'time_kst', 'variety', 'grade', 'cultivar_confidence_pct', 'quality_confidence_pct', 'inference_ms', 'model_version', 'target_bin', 'processing_status',
        'control_status', 'persistence_status', 'error_codes', 'misclassification', 'virtual_brix', 'brix_is_measured']
body_rows = [r for r in rd[1:] if r]
all_quoted = all(re.fullmatch(r'("([^"]|"")*")(,("([^"]|"")*"))*', ln.decode('utf-8-sig')) for ln in lines if ln)
err_row = next((r for r in body_rows if r[0] == sent['ins08']['id']), None)
o10 = {'status': st, 'content_type': hd.get('Content-Type'), 'disposition': hd.get('Content-Disposition'), 'cache': hd.get('Cache-Control'), 'bom': data[:3].hex(),
       'crlf': b'\r\n' in data and b'\n' not in data.replace(b'\r\n', b''), 'all_quoted': all_quoted, 'header_ok': header == cols, 'rows': len(body_rows), 'history_total_at_check': tot,
       'brix_all_false': all(r[16] == 'false' for r in body_rows), 'ins08_error_codes': err_row[13] if err_row else None, 'image_columns': [c for c in header if 'image' in c or 'url' in c],
       'korean_sample': next((r[3] + '/' + r[4] for r in body_rows if r[3]), None)}
ok10 = st == 200 and hd.get('Content-Type', '').startswith('text/csv') and 'utf-8' in hd.get('Content-Type', '').lower() and 'cqc-inspections.csv' in (hd.get('Content-Disposition') or '') \
    and 'no-store' in (hd.get('Cache-Control') or '') and o10['bom'] == 'efbbbf' and o10['crlf'] and all_quoted and o10['header_ok'] and abs(len(body_rows) - tot) <= 2 and o10['brix_all_false'] and not o10['image_columns']
rec('QA-OPS-10', '통과' if ok10 else '실패', '헤더 3종, BOM·CRLF·모든 칸 따옴표, 열 17개 순서, 행 수 = /inspections total, brix false, 오류 행 error_codes, 이미지 열 없음, 한글 UTF-8', o10,
    '행 수와 total은 CSV·목록 요청 사이 Simulator 입력으로 0~1건 차이 허용. Excel 미설치라 직접 열기 대신 UTF-8 BOM과 한글 디코딩으로 확인')
ops = next((r for r in body_rows if r[0].lstrip("'").startswith(f'-{RUN}-ops11')), None)
raw_line = next((ln.decode('utf-8-sig') for ln in lines if f'-{RUN}-ops11'.encode() in ln), None)
o11 = {'send': sent['ops11'], 'first_cell': ops[0] if ops else None, 'raw_line_head': raw_line[:40] if raw_line else None}
ok11 = sent['ops11']['status'] == 200 and ops is not None and ops[0] == f"'-{RUN}-ops11" and raw_line.startswith(f"\"'-{RUN}-ops11\"")
rec('QA-OPS-11', '통과' if ok11 else '실패', '하이픈 시작 ID 행 첫 칸이 작은따옴표로 시작("\'-qa-…-ops11"), 수식으로 실행되지 않음', o11,
    'Excel 미설치. 수식 시작 문자(-)가 작은따옴표로 무력화된 것을 원문 바이트로 확인')

# QA-OPS-13
o13, ok13 = {}, True
st, js, hd, data = get(f'/v1/quality/statistics.csv?from={D}&to={D}')
r = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
tot_rows = {x[4]: x[5] for x in r[1:] if len(x) > 5 and x[3] == 'total'}
o13['a'] = {'header': r[0], 'total_keys': sorted(tot_rows), 'mode': sorted({x[0] for x in r[1:] if x})}
ok13 &= r[0] == ['mode', 'from_kst', 'to_kst', 'group', 'key', 'value'] and 'reinspection_ratio' in tot_rows and 'average_inference_ms' in tot_rows and o13['a']['mode'] == ['BACKEND']
if 'reinspection' in tot_rows and 'total' in tot_rows and float(tot_rows['total']):
    ratio_ok = abs(float(tot_rows['reinspection_ratio']) - float(tot_rows['reinspection']) / float(tot_rows['total'])) < 1e-6
    o13['a']['ratio_ok'] = ratio_ok
    ok13 &= ratio_ok
for name, qs, n in [('b', '', None), ('c', '?minutes=5', 300), ('d1', '?minutes=1', 60), ('d10', '?minutes=10', 600), ('d30', '?minutes=30', 1800)]:
    st, js, hd, data = get('/v1/quality/statistics.csv' + qs)
    rr = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
    sections = sorted({x[2] for x in rr[1:] if len(x) > 2})
    last = sum(1 for x in rr[1:] if len(x) > 2 and x[2].startswith('last_'))
    good = st == 200 and data[:3].hex() == 'efbbbf' and b'\r\n' in data and rr[0] == ['mode', 'date_kst', 'section', 'key', 'value', 'last_saved_at'] and 'today' in sections
    if n:
        good &= last == n
    o13[name] = {'status': st, 'sections': sections, 'last_rows': last}
    ok13 &= good
st, js, hd, _ = get('/v1/quality/statistics.csv?minutes=2')
o13['e'] = [st, js]
ok13 &= st == 422 and js == {'code': 'INVALID_QUERY'}
rec('QA-OPS-13', '통과' if ok13 else '실패', 'a 기간 형식·total 그룹 비율/평균, b 오늘 형식·섹션, c 300행, d 60·600·1800행, e 422, BOM·CRLF·mode BACKEND', o13)

# QA-IMG-01
low = images(f'inspectionId={sent["LQ"]["id"]}')[1]['items']
none_fl = images(f'inspectionId={sent["FL"]["id"]}')[1]['items'] + images(f'inspectionId={sent["ins03"]["id"]}')[1]['items'] + images(f'inspectionId={sent["YS"]["id"]}')[1]['items']
o_img1 = {'LQ_images': len(low), 'LQ_categories': sorted({x['category'] for x in low}), 'LQ_errorCode': sorted({str(x['errorCode']) for x in low}),
          'LQ_reason': sorted({x['decisionReason'] for x in low}), 'normal_and_brix_missing_images': len(none_fl), 'LQ_send': sent['LQ']}
ok_img1 = len(low) == 12 and o_img1['LQ_categories'] == ['LOW_CONFIDENCE'] and o_img1['LQ_errorCode'] == ['None'] and all(re.fullmatch(r'LOW_(CULTIVAR|QUALITY|BOTH)_CONFIDENCE', x) for x in o_img1['LQ_reason']) and not none_fl
rec('QA-IMG-01', '통과' if ok_img1 else '실패', '정상·당도 누락 요청은 사진 저장 없음, 저신뢰 요청만 12장(LOW_CONFIDENCE, errorCode null, LOW_*_CONFIDENCE)', o_img1,
    '저신뢰 보관이 200장 한도라 전체 수 대신 검사 ID 필터로 12장 증가를 확인(오래된 저신뢰 12장은 순환 삭제 = 보존 정책)')

# QA-IMG-02
st, js, hd, _ = images()
items = js['items']
c_ok = all(re.fullmatch(r'[0-9a-f]{32}_\d{2}', x['id']) and x['previewUrl'] == f'/api/quality/previews/{x["id"]}' and x['category'] in ('SYSTEM_ERROR', 'LOW_CONFIDENCE') and 0 <= x['imageIndex'] <= 11 for x in items)
keys = sorted(items[0]) if items else []
srt = [x['createdAt'] for x in items]
mine = images(f'inspectionId={sent["ins08"]["id"]}')[1]['items']
cat = images('category=LOW_CONFIDENCE')[1]['items']
o_img2 = {'count': len(items), 'keys': keys, 'sorted_desc': srt == sorted(srt, reverse=True), 'format_ok': c_ok, 'category_filter': sorted({x['category'] for x in cat}) == ['LOW_CONFIDENCE'],
          'ins08_items': [{k: x[k] for k in ('imageIndex', 'errorCode', 'category')} for x in mine], 'by_category': {c: sum(1 for x in items if x['category'] == c) for c in ('SYSTEM_ERROR', 'LOW_CONFIDENCE')}}
need = {'id', 'inspectionId', 'imageIndex', 'createdAt', 'errorCode', 'previewUrl', 'category', 'decisionReason', 'cultivarConfidence', 'qualityConfidence', 'appliedCultivarThreshold', 'appliedQualityThreshold'}
ok_img2 = st == 200 and len(items) <= 300 and o_img2['sorted_desc'] and c_ok and need <= set(keys) and o_img2['category_filter'] and len(mine) == 1 and mine[0]['imageIndex'] == 0 and mine[0]['errorCode'] == 'INFERENCE_HTTP_ERROR'
rec('QA-IMG-02', '통과(부분)' if ok_img2 else '실패', '≤300·최신순·키 12개·id 형식·previewUrl, category·inspectionId 필터, $RUN-ins08 imageIndex 0·INFERENCE_HTTP_ERROR', o_img2,
    '시간 초과 기록(E2)의 errorCode=INFERENCE_TIMEOUT 표시는 E2 전용이라 미확인')

# QA-IMG-03
pid = mine[0]['id'] if mine else ''
st, _, hd, data = get(f'/v1/quality/previews/{pid}')
broken = open(f'{DEMO}/demo-601031008000-000/frame_00.png', 'rb').read()[:20000]
o_img3 = {'status': st, 'type': hd.get('Content-Type'), 'cache': hd.get('Cache-Control'), 'sha_match': hashlib.sha256(data).hexdigest() == hashlib.sha256(broken).hexdigest()}
bad = {}
for name, x in [('a', '0000'), ('b', '0' * 32 + '_00'), ('c', '..%2F..%2Fetc')]:
    s2, j2, _, d2 = get(f'/v1/quality/previews/{x}')
    bad[name] = [s2, j2, len(d2)]
o_img3['invalid'] = bad
ok_img3 = st == 200 and hd.get('Content-Type') == 'image/png' and 'no-store' in (hd.get('Cache-Control') or '') and o_img3['sha_match'] \
    and bad['a'][0] == 410 and bad['a'][1] == {'code': 'IMAGE_EXPIRED'} and bad['b'][0] == 410 and bad['b'][1] == {'code': 'IMAGE_EXPIRED'} and bad['c'][0] in (404, 410)
rec('QA-IMG-03', '통과' if ok_img3 else '실패', '200 image/png no-store, 보낸 손상 사진과 SHA-256 같음, a·b 410 IMAGE_EXPIRED, c 404/410(저장소 밖 미노출)', o_img3)

# QA-IMG-05 (잘못된 요청이라 지워지는 이미지 없음)
o_img5 = {}
for name, body in [('a', b'{"ids":[]}'), ('b', b'{"ids":["../x"]}'), ('c', json.dumps({'ids': [f'{i:032x}_00' for i in range(301)]}).encode()),
                   ('d', b'{"ids":["' + (low[0]['id'] if low else 'a' * 32 + '_00').encode() + b'"],"all":true}'), ('e', None)]:
    st, js, _, _ = http(f'{BE}/v1/quality/fault-images', 'DELETE', body, 'application/json' if body is not None else None)
    o_img5[name] = [st, js]
ok_img5 = o_img5['a'] == [200, {'deletedIds': []}] and all(o_img5[k] == [422, {'code': 'INVALID_IDS'}] for k in 'bcde')
after5 = images(f'inspectionId={sent["LQ"]["id"]}')[1]['items']
o_img5['own_LQ_images_after'] = len(after5)
ok_img5 = ok_img5 and len(after5) == len(low)
rec('QA-IMG-05', '통과' if ok_img5 else '실패', 'a 200 deletedIds [], b·c·d·e 422 INVALID_IDS, 이미지 그대로', o_img5, 'd는 본인 $RUN 이미지 id에 all 필드를 붙여 거부되는지 확인(삭제되지 않음)')

# QA-IMG-04 (본인 저신뢰 이미지 2장만 삭제)
A, B = low[0]['id'], low[1]['id']
before = get('/v1/quality/snapshot')[1]['retention']['images']
st, js, _, _ = http(f'{BE}/v1/quality/fault-images', 'DELETE', json.dumps({'ids': [A, B, B, 'f' * 32 + '_00']}).encode(), 'application/json')
after = get('/v1/quality/snapshot')[1]['retention']['images']
left = [x['id'] for x in images(f'inspectionId={sent["LQ"]["id"]}')[1]['items']]
pa, pb = get(f'/v1/quality/previews/{A}'), get(f'/v1/quality/previews/{B}')
still = find(sent['LQ']['id'])
_, _, _, csvd = get(f'/v1/quality/inspections.csv?from={D}&to={D}')
o_img4 = {'delete': [st, js], 'own_left': len(left), 'A_B_gone': A not in left and B not in left, 'preview_A': [pa[0], pa[1]], 'preview_B': [pb[0], pb[1]],
          'history_kept': bool(still), 'csv_kept': sent['LQ']['id'].encode() in csvd, 'retention_before_after': [before, after]}
ok_img4 = st == 200 and sorted(js.get('deletedIds', [])) == sorted([A, B]) and len(left) == 10 and o_img4['A_B_gone'] and pa[0] == 410 and pa[1] == {'code': 'IMAGE_EXPIRED'} \
    and pb[0] == 410 and o_img4['history_kept'] and o_img4['csv_kept']
rec('QA-IMG-04', '통과' if ok_img4 else '실패', '200 deletedIds [A,B](중복·없는 id 무시), A·B만 목록에서 빠짐, 미리보기 410, 이력·CSV 유지, retention -2', o_img4,
    '보존 수는 Simulator가 계속 저신뢰 이미지를 채워 300장 한도에서 바로 다시 찰 수 있어, 본인 검사 기준 12→10장으로 판정' if after != before - 2 else '')

raw['finished_kst'] = datetime.now(KST).isoformat()
json.dump({'run': RUN, 'environment': 'E1 192.168.133.106:8000 (학원 서버), 실행자 조현재(에이전트), BE 담당 대행(#103)', 'raw': raw, 'results': results},
          open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved', OUT)
