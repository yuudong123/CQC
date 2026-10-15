"""Collect existing QA evidence using SELECT-only MySQL queries."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import json
import subprocess

ROOT = Path('C:/CQC')
KST = timezone(timedelta(hours=9))
OUT = ROOT / 'outputs' / ('qa-mo-ins14-ins17-' + datetime.now(KST).strftime('%Y%m%d-%H%M%S'))
OUT.mkdir()
ERROR_ID = 'qa-e1-20261008-091125-45628a-ins08'
SUFFIXES = ['601031008000-000-13_9', '601031008000-000-14_0',
            '601032016000-000-13_9', '601032016000-000-14_0',
            '601033004000-000-13_9', '601033004000-000-14_0',
            '601141012000-000-13_9', '601141012000-000-14_0',
            '601142007000-000-13_9', '601142007000-000-14_0',
            '601143013000-000-13_9', '601143013000-000-14_0']
TARGETS = [{'inspection_id': 'be10-2-63f2ca4e-' + suffix,
            'expected_bin': f'DEMO_BIN_{i:02d}'} for i, suffix in enumerate(SUFFIXES, 1)]
IDS = [ERROR_ID] + [r['inspection_id'] for r in TARGETS]
ID_SQL = ','.join("'" + v + "'" for v in IDS)

def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def command(*args):
    return subprocess.check_output(args, text=True, encoding='utf-8', timeout=35)

queries = [
    "SET SESSION time_zone = '+00:00'",
    "SET SESSION TRANSACTION READ ONLY",
    "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",
    "SELECT JSON_OBJECT('kind','database_info','database',DATABASE(),'queried_utc',UTC_TIMESTAMP(3),'mysql_version',VERSION(),'session_time_zone',@@session.time_zone)",
    "SELECT JSON_OBJECT('kind','inspection','inspection_id',inspection_id,'created_at',created_at,'completed_at',completed_at,'target_bin_code',target_bin_code,'inspection_status',inspection_status,'control_status',control_status,'persistence_status',persistence_status,'error_code',error_code) FROM inspections WHERE inspection_id IN (" + ID_SQL + ") ORDER BY inspection_id",
    "SELECT JSON_OBJECT('kind','inspection_error','id',id,'inspection_id',inspection_id,'component',component,'error_code',error_code,'occurred_at',occurred_at) FROM inspection_errors WHERE inspection_id IN (" + ID_SQL + ") ORDER BY inspection_id,id",
    "SELECT JSON_OBJECT('kind','control_attempt','id',id,'command_id',command_id,'inspection_id',inspection_id,'attempt_no',attempt_no,'requested_bin_code',requested_bin_code,'command_type',command_type,'control_status',control_status,'requested_at',requested_at,'responded_at',responded_at,'response_time_ms',response_time_ms,'failure_reason',failure_reason) FROM control_attempts WHERE inspection_id IN (" + ID_SQL + ") ORDER BY inspection_id,attempt_no,id",
    "SELECT JSON_OBJECT('kind','fallback_inspection','inspection_id',inspection_id,'target_bin_code',target_bin_code,'created_at',created_at,'completed_at',completed_at,'inspection_status',inspection_status,'control_status',control_status,'persistence_status',persistence_status,'error_code',error_code) FROM inspections WHERE inspection_id LIKE 'qa-be-10081636t-ins01-%' ORDER BY inspection_id",
    "SELECT JSON_OBJECT('kind','fallback_control_attempt','id',id,'inspection_id',inspection_id,'attempt_no',attempt_no,'requested_bin_code',requested_bin_code,'command_type',command_type,'control_status',control_status,'requested_at',requested_at,'responded_at',responded_at,'response_time_ms',response_time_ms,'failure_reason',failure_reason) FROM control_attempts WHERE inspection_id LIKE 'qa-be-10081636t-ins01-%' ORDER BY inspection_id,attempt_no,id",
    "ROLLBACK",
]
sql = ';\n'.join(queries) + ';\n'
(OUT / 'query.sql').write_text(sql, encoding='utf-8')
raw = command('docker', 'exec', 'cqc-cicd-mysql-1', 'sh', '-c',
              'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N --raw -e "$1"', 'sh', sql)
(OUT / 'mysql-result.jsonl').write_text(raw, encoding='utf-8')
db = [json.loads(line) for line in raw.splitlines() if line.strip()]
dump('requested-targets.json', {'ins17': ERROR_ID, 'ins14': TARGETS})
dump('ins17-db-check.json', {'inspection_id': ERROR_ID,
    'inspection_rows': [r for r in db if r.get('kind') == 'inspection' and r.get('inspection_id') == ERROR_ID],
    'inspection_error_rows': [r for r in db if r.get('kind') == 'inspection_error' and r.get('inspection_id') == ERROR_ID]})
results = []
for target in TARGETS:
    iid = target['inspection_id']
    inspections = [r for r in db if r.get('kind') == 'inspection' and r.get('inspection_id') == iid]
    controls = [r for r in db if r.get('kind') == 'control_attempt' and r.get('inspection_id') == iid]
    checks = None
    if len(controls) == 1:
        c = controls[0]
        checks = {'attempt_no_1': c['attempt_no'] == 1,
                  'route_to_bin': c['command_type'] == 'ROUTE_TO_BIN',
                  'succeeded': c['control_status'] == 'SUCCEEDED',
                  'matches_expected_bin': c['requested_bin_code'] == target['expected_bin'],
                  'response_time_below_100ms': c['response_time_ms'] is not None and c['response_time_ms'] < 100}
    results.append({**target, 'inspection_rows': inspections, 'control_attempts': controls,
                    'inspection_count': len(inspections), 'control_count': len(controls), 'checks': checks})
dump('ins14-db-check.json', results)
dump('e1-fallback-db-check.json', [r for r in db if r['kind'].startswith('fallback_')])
source = ROOT / 'docs/wbs/BE-10-2-local-evidence.jsonl'
selected = []
for line_number, line in enumerate(source.read_text(encoding='utf-8').splitlines(), 1):
    if not line.strip(): continue
    value = json.loads(line)
    if value.get('inspection_id') in IDS:
        selected.append({'source_line': line_number, 'record': value})
dump('ins14-existing-evidence-extract.json', {
    'source': source.relative_to(ROOT).as_posix(), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'source_git_blob': command('git', 'hash-object', str(source)).strip(), 'selected': selected})
csv_source = ROOT / 'outputs/qa-mo-excel-only-20261012/ops10-inspections.csv'
csv_matches = []
with csv_source.open(encoding='utf-8-sig', newline='') as f:
    for row_number, row in enumerate(csv.DictReader(f), 2):
        if ERROR_ID in row.get('inspection_id', '') or row.get('inspection_id', '').startswith('qa-be-10081636t-ins01-'):
            csv_matches.append({'source_row': row_number, 'record': row})
dump('existing-csv-extract.json', {'source_url':'https://github.com/yuudong123/CQC/blob/dev/docs/wbs/results/qa-be-proxy-20261008/supplement/ops10-inspections.csv',
    'source_sha256': hashlib.sha256(csv_source.read_bytes()).hexdigest(), 'selected': csv_matches})
containers = json.loads(command('docker', 'inspect', 'cqc-cicd-mysql-1'))
dump('database-container.json', [{
    'name': c['Name'], 'id': c['Id'], 'created': c['Created'],
    'state': {'status': c['State']['Status'], 'started_at': c['State']['StartedAt'], 'health': c['State'].get('Health',{}).get('Status')},
    'mounts': [{'type': m['Type'], 'name': m.get('Name'), 'destination': m['Destination']} for m in c['Mounts']]} for c in containers])
dump('docker-inventory.json', {'active_context':command('docker','context','show').strip(),
    'containers':command('docker','ps','-a','--format','{{.Names}}\t{{.Status}}').splitlines(),
    'volumes':command('docker','volume','ls','--format','{{.Name}}').splitlines(),
    'no_active_e2_mysql':True,
    'note':'No E2 database server was started; disconnected volume contents and databases on other computers were not inspected.'})
patterns = [ERROR_ID, 'be10-2-63f2ca4e', 'qa-be-10081636t-ins01-']
args = ['rg','-l','--hidden','--no-ignore','-F']
for text in patterns: args += ['-e',text]
for glob in ['*.json','*.jsonl','*.sql','*.csv','*.md','*.txt','*.log', '!**/node_modules/**','!.git/**','!.venv/**']:
    args += ['-g',glob]
args += ['docs','outputs','scripts']
scan = subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)
if scan.returncode not in (0,1): raise RuntimeError('Evidence search failed: '+scan.stderr)
dump('local-search.json', {'roots':['docs','outputs','scripts'], 'patterns':patterns,
    'glob_types':['json','jsonl','sql','csv','md','txt','log'], 'exit_code':scan.returncode,
    'matches':scan.stdout.splitlines(), 'limitations':'Binary archives, offline database volume contents, other computers and remote uncommitted exports not searched.'})
summary = {'queried_kst':datetime.now(KST).isoformat(),'database_info':[r for r in db if r['kind']=='database_info'],
    'ins17_inspection_count':sum(r['kind']=='inspection' and r.get('inspection_id')==ERROR_ID for r in db),
    'ins17_error_count':sum(r['kind']=='inspection_error' and r.get('inspection_id')==ERROR_ID for r in db),
    'ins14_inspection_count':sum(x['inspection_count'] for x in results),
    'ins14_control_attempt_count':sum(x['control_count'] for x in results),
    'ins14_archived_api_db_records':len(selected),
    'e1_fallback_inspection_count':sum(r['kind']=='fallback_inspection' for r in db),
    'e1_fallback_control_count':sum(r['kind']=='fallback_control_attempt' for r in db),
    'csv_ins17_matches':sum(r['record']['inspection_id']==ERROR_ID for r in csv_matches),
    'csv_e1_fallback_matches':sum(r['record']['inspection_id'].startswith('qa-be-10081636t-ins01-') for r in csv_matches)}
dump('summary.json', summary)
print(json.dumps({'output':str(OUT),'summary':summary},ensure_ascii=True))
