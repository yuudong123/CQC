"""Run the requested SIM-04/05 QA against a fresh isolated Compose project.

No product changes, builds, pulls, public-server writes, or official QA decisions.
Credentials exist only in this process's environment; evidence is redacted.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

ROOT = Path('C:/CQC')
KST = timezone(timedelta(hours=9))
RUN = datetime.now(KST).strftime('%Y%m%d-%H%M%S')
PROJECT = 'cqc-mo103-sim0405-' + RUN
OUT = ROOT / 'outputs' / ('qa-mo-sim04-sim05-' + RUN)
OUT.mkdir()
RESUME = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if RESUME:
    previous = json.loads((RESUME / 'summary.json').read_text(encoding='utf-8'))
    PROJECT = previous['project']
    assert PROJECT.startswith('cqc-mo103-sim0405-20261013-')
BE = 'http://127.0.0.1:28000'
SIM = 'http://127.0.0.1:28002'
CONFIG_KEYS = ['revision', 'running', 'concurrency', 'intervalMs', 'faults', 'scope']
credential_values = [secrets.token_hex(24) for _ in range(3)]
if RESUME:
    # Recover only this dedicated project's runtime credentials in memory.
    old = json.loads(subprocess.check_output(['docker', 'inspect', PROJECT + '-mysql-1', PROJECT + '-backend-1'], timeout=15))
    assert all(c['Config']['Labels']['com.docker.compose.project'] == PROJECT for c in old)
    assert all(c['State']['Status'] == 'exited' for c in old)
    mysql_env = dict(v.split('=', 1) for v in old[0]['Config']['Env'])
    backend_env = dict(v.split('=', 1) for v in old[1]['Config']['Env'])
    credential_values = [mysql_env['MYSQL_PASSWORD'], mysql_env['MYSQL_ROOT_PASSWORD'], backend_env['SIMULATOR_FAULT_TOKEN']]
env = os.environ.copy()
for key in ['COMPOSE_FILE', 'COMPOSE_PROJECT_NAME', 'DATABASE_URL', 'SIMULATOR_FAULT_TOKEN', 'INFERENCE_URL']:
    env.pop(key, None)
env.update(dict(zip(['CQC_QA_MYSQL_PASSWORD', 'CQC_QA_MYSQL_ROOT_PASSWORD', 'CQC_QA_FAULT_TOKEN'], credential_values)))
summary = {'run': RUN, 'project': PROJECT, 'actor': '홍유나 (Codex)',
           'started_kst': datetime.now(KST).isoformat(), 'cases': {},
           'official_qa_decision': 'Pending Backend evidence review',
           'scope': 'SIM-04/05 only; fresh isolated runtime using currently deployed images'}
if RESUME:
    summary['setup_attempt_evidence'] = str(RESUME)
    summary['scope'] = 'SIM-04/05 only; retained dedicated setup project; internal HTTP transport'
created = False

def redact(value):
    if isinstance(value, str):
        for secret in credential_values:
            value = value.replace(secret, '[REDACTED]')
        return value
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value

def save(name, value):
    (OUT / name).write_text(json.dumps(redact(value), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def note(msg):
    print(datetime.now(KST).strftime('%H:%M:%S') + ' ' + msg, flush=True)

def command(*args, timeout=20, check=True):
    proc = subprocess.run(args, env=env, capture_output=True, timeout=timeout)
    stdout = proc.stdout.decode('utf-8', errors='replace')
    stderr = proc.stderr.decode('utf-8', errors='replace')
    if check and proc.returncode:
        raise RuntimeError(redact(f'{args[:3]} exit {proc.returncode}: {stderr[:3000]} {stdout[:1000]}'))
    return {'exit_code': proc.returncode, 'stdout': stdout, 'stderr': stderr}

def docker(*args, **kwargs):
    return command('docker', *args, **kwargs)['stdout'].strip()

def compose(*args, timeout=40, check=True):
    assert PROJECT.startswith('cqc-mo103-sim0405-')
    return command('docker', 'compose', '--env-file', str(OUT / 'empty.env'),
                   '-p', PROJECT, '-f', str(OUT / 'isolated-compose.json'),
                   *args, timeout=timeout, check=check)

def public_containers():
    names = ['backend', 'inference', 'simulator', 'mysql', 'logistics-web', 'logistics-api', 'logistics-mongodb']
    data = json.loads(docker('inspect', *['cqc-cicd-' + n + '-1' for n in names]))
    return [{'name': c['Name'], 'id': c['Id'], 'image': c['Image'],
             'started_at': c['State']['StartedAt'], 'status': c['State']['Status'],
             'health': c['State'].get('Health', {}).get('Status')} for c in data]

def qa_containers():
    ids = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT).splitlines()
    if not ids:
        return []
    return json.loads(docker('inspect', *ids))

def safe_container(c):
    return {'name': c['Name'], 'id': c['Id'], 'image': c['Image'],
            'service': c['Config']['Labels'].get('com.docker.compose.service'),
            'status': c['State']['Status'], 'health': c['State'].get('Health', {}).get('Status'),
            'started_at': c['State']['StartedAt'], 'networks': list(c['NetworkSettings']['Networks']),
            'ports': c['NetworkSettings']['Ports'],
            'mounts': [{'type': m['Type'], 'name': m.get('Name'), 'destination': m['Destination'], 'rw': m['RW']} for m in c['Mounts']]}

def api(label, base, path, method='GET', payload=None):
    assert base in [BE, SIM, 'http://127.0.0.1:28001']
    internal = {BE: 'http://127.0.0.1:8000', SIM: 'http://simulator:8002', 'http://127.0.0.1:28001': 'http://inference:8001'}
    url = internal[base] + path
    code = '''import sys,json,time,urllib.request,urllib.error
from datetime import datetime,timezone,timedelta
url,method,payload=sys.argv[1:]; data=json.loads(payload)
request_body=None if data is None else json.dumps(data).encode()
req=urllib.request.Request(url,data=request_body,headers={'Content-Type':'application/json'} if request_body is not None else {},method=method)
zone=timezone(timedelta(hours=9)); started=datetime.now(zone).isoformat(); start=time.monotonic()
try:response=urllib.request.urlopen(req,timeout=15)
except urllib.error.HTTPError as error:response=error
with response:
 raw=response.read().decode('utf-8',errors='replace')
 try:parsed=json.loads(raw)
 except json.JSONDecodeError:parsed=raw
 result={'started_kst':started,'finished_kst':datetime.now(zone).isoformat(),'elapsed_ms':(time.monotonic()-start)*1000,'request':{'url':url,'method':method,'body':data},'response':{'status':response.status,'headers':dict(response.headers),'body':parsed}}
print(json.dumps(result,ensure_ascii=False))
'''
    result = json.loads(docker('exec', PROJECT + '-backend-1', 'python', '-c', code, url, method, json.dumps(payload), timeout=25))
    result['transport'] = 'Real HTTP from dedicated Backend container; no mock or in-process test client'
    save(label + '.json', result)
    return result

def body(record):
    assert record['response']['status'] == 200, record
    return record['response']['body']

def settings_sim(state):
    return {k: state[k] for k in CONFIG_KEYS}

def settings_be(snapshot):
    return {'revision': snapshot['revision'], **{k: snapshot['state'][k] for k in CONFIG_KEYS if k != 'revision'}}

def db(label):
    sql = 'SELECT COUNT(*) FROM inspections; SELECT inspection_id,inspection_status,control_status,persistence_status FROM inspections ORDER BY created_at; SELECT version_num FROM alembic_version; SELECT COUNT(*) FROM bin_mappings;'
    shell = 'MYSQL_PWD="$MYSQL_PASSWORD" mysql --protocol=TCP -h127.0.0.1 -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -B -e "$1"'
    result = docker('exec', PROJECT + '-mysql-1', 'sh', '-c', shell, 'qa-count', sql)
    record = {'queried_kst': datetime.now(KST).isoformat(), 'sql': sql, 'raw_tsv': result,
              'inspection_count': int(result.splitlines()[0])}
    save(label + '.json', record)
    return record

def observations(label):
    simulator = body(api(label + '-simulator', SIM, '/state'))
    snapshot = body(api(label + '-snapshot', BE, '/v1/quality/snapshot'))
    database = db(label + '-database')
    return {'simulator': settings_sim(simulator), 'backend': settings_be(snapshot),
            'jobs': snapshot['state']['jobs'], 'inspection_count': database['inspection_count']}

try:
    note('Preflight: pin current images and verify independent resources')
    e1_before = public_containers()
    save('e1-before.json', e1_before)
    assert all(c['health'] == 'healthy' for c in e1_before), 'Public baseline unhealthy'
    if not RESUME:
        assert not docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT), 'Project already exists'
    config = json.loads((ROOT / 'docs/wbs/results/qa-mo-be-followup-20261012/isolated-compose.json').read_text())
    selected = json.loads(docker('inspect', *['cqc-cicd-' + n + '-1' for n in config['services']]))
    current = {c['Config']['Labels']['com.docker.compose.service']: c for c in selected}
    if RESUME:
        original_config = json.loads((RESUME / 'isolated-compose.json').read_text(encoding='utf-8'))
        assert all(c['Image'] == original_config['services'][n]['image'] for n, c in current.items()), 'Public deployment changed since setup attempt'
    safe_env_keys = {
        'backend': ['INFERENCE_CLIENT_MODE', 'INFERENCE_URL', 'INFERENCE_CONNECT_TIMEOUT_MS',
                    'INFERENCE_BUSINESS_DEADLINE_MS', 'INFERENCE_HARD_TIMEOUT_MS',
                    'CULTIVAR_CONFIDENCE_THRESHOLD', 'QUALITY_CONFIDENCE_THRESHOLD',
                    'SIMULATOR_INTERNAL_URL', 'FAULT_IMAGE_STORAGE_ROOT'],
        'simulator': ['SIMULATOR_DATASET_ROOT', 'SIMULATOR_BRIX_CSV_PATH', 'SIMULATOR_POSITION_PATH',
                      'SIMULATOR_BACKEND_URL', 'SIMULATOR_INTERVAL_MS'],
        'inference': ['MODEL_DIR', 'MODEL_PATH', 'MODEL_CARD_PATH', 'INFERENCE_HOST', 'INFERENCE_PORT'],
        'mysql': []}
    for name, service in config['services'].items():
        c = current[name]
        service['image'] = c['Image']
        service['command'] = c['Config']['Cmd']
        service['working_dir'] = c['Config']['WorkingDir'] or '/'
        if c['Config']['Entrypoint'] is not None:
            service['entrypoint'] = c['Config']['Entrypoint']
        else:
            service.pop('entrypoint', None)
        actual_env = dict(v.split('=', 1) for v in c['Config']['Env'])
        service['environment'].update({k: actual_env[k] for k in safe_env_keys[name] if k in actual_env})
        assert json.loads(docker('image', 'inspect', c['Image']))[0]['Id'] == c['Image']
    save('isolated-compose.json', config)
    (OUT / 'empty.env').write_bytes(b'')
    render = compose('config', '--format', 'json')
    rendered = json.loads(render['stdout'])
    for name, service in rendered['services'].items():
        assert 'build' not in service and service['pull_policy'] == 'never'
        assert service['image'] == current[name]['Image']
        for m in service.get('volumes', []):
            assert m['source'].startswith('qa_') or (m['source'] == 'dataset' and m['read_only'])
        for p in service.get('ports', []):
            assert p['host_ip'] == '127.0.0.1'
    assert rendered['services']['backend']['environment']['DATABASE_URL'].endswith('@mysql:3306/cqc_mo103_qa')
    assert rendered['networks']['qa']['internal'] is True
    assert all(v['name'].startswith(PROJECT + '_') for k, v in rendered['volumes'].items() if k != 'dataset')
    assert rendered['volumes']['dataset']['external'] and rendered['volumes']['dataset']['name'] == 'cqc_simulator_dataset'
    for port in [28000, 28001, 28002]:
        sock = socket.socket(); sock.settimeout(.5)
        listening = sock.connect_ex(('127.0.0.1', port)) == 0; sock.close()
        assert not listening, f'Port {port} already occupied'
    assert json.loads(docker('volume', 'inspect', 'cqc_simulator_dataset'))
    save('compose-rendered-redacted.json', rendered)
    base = '/var/jenkins_home/jobs/CQC-CICD/builds'
    nums = sorted(int(n) for n in docker('exec', 'jenkins', 'ls', '-1', base).splitlines() if n.isdigit())
    build = nums[-1]
    xml = ET.fromstring(docker('exec', 'jenkins', 'cat', f'{base}/{build}/build.xml'))
    assert xml.findtext('result') == 'SUCCESS', 'Latest Jenkins build not completed successfully'
    log = docker('exec', 'jenkins', 'cat', f'{base}/{build}/log')
    sha = re.findall(r'Checking out Revision ([0-9a-f]{40})', log)[-1]
    node_digests = dict(re.findall(r'#(\d+) exporting manifest list (sha256:[0-9a-f]{64})', log))
    service_digests = {service: node_digests[node] for node, service in re.findall(r'#(\d+) naming to docker.io/library/cqc-cicd-([a-z-]+):latest', log) if node in node_digests}
    matches = {n: current[n]['Image'] == service_digests.get(n) for n in ['backend', 'inference', 'simulator']}
    assert all(matches.values()), 'Current image differs from latest successful build'
    summary.update({'source_sha': sha, 'jenkins_build': build, 'build_image_matches': matches})
    save('deployment-provenance.json', {'build': build, 'result': xml.findtext('result'), 'source_sha': sha,
          'images': {n: c['Image'] for n, c in current.items()}, 'build_image_matches': matches,
          'runtime_same_host': True, 'jenkins_live_queue_verified': False,
          'schedule_authorization': 'User confirmed no build running and explicitly requested SIM-04/05 execution'})
    save('preflight.json', {'project': PROJECT, 'checks': 'All configured isolation/image/port assertions passed',
          'services': list(config['services']), 'disk_free_bytes': {p: shutil.disk_usage(p).free for p in ['C:/', 'D:/']},
          'shared_resource_limit': 'Shares host CPU/RAM/disk with E1; separate network/DB/position/images/logs',
          'no_build': True, 'no_pull': True})
    note('Starting only new QA MySQL, Inference, Backend; waiting for health')
    created = True
    started = compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '240', 'mysql', 'inference', 'backend', timeout=270)
    save('startup-dependencies.json', started)
    api('backend-health-before', BE, '/health')
    api('inference-health-before', 'http://127.0.0.1:28001', '/health')
    hashes = "import json,hashlib; from pathlib import Path; p=Path('/app/models/approved'); print(json.dumps([{'path':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(p.rglob('*')) if f.is_file()]))"
    save('model-checksums.json', json.loads(docker('exec', PROJECT + '-inference-1', 'python', '-c', hashes)))
    note('Starting QA Simulator; stop after first successful completed input')
    save('startup-simulator.json', compose('up', '-d', '--no-build', '--pull', 'never', 'simulator', timeout=30))
    deadline = time.monotonic() + 90
    first = None
    startup_failures = []
    while time.monotonic() < deadline:
        try:
            first = body(api('startup-simulator-state', SIM, '/state'))
            if first['lastSeenAt'] is not None and first['running'] and first['status'] == 'healthy':
                break
        except (OSError, AssertionError, RuntimeError) as exc:
            startup_failures.append({'at_kst': datetime.now(KST).isoformat(), 'error': str(exc)})
        time.sleep(1)
    else:
        raise RuntimeError('QA Simulator did not complete initial input within 90s')
    save('startup-readiness-retries.json', startup_failures)
    stopped = api('setup-stop', BE, '/v1/quality/simulator', 'PUT', {'expectedRevision': first['revision'], 'running': False})
    assert stopped['response']['status'] == 200
    note('Waiting for all initial QA requests to finish and inspection count to stabilize')
    samples = []
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        o = observations('drain-' + str(len(samples)))
        samples.append(o)
        if len(samples) >= 3 and all(not s['jobs'] and not s['simulator']['running'] for s in samples[-3:]) and len({s['inspection_count'] for s in samples[-3:]}) == 1:
            break
        time.sleep(2)
    else:
        raise RuntimeError('Initial requests did not drain')
    assert samples[-1]['inspection_count'] > 0
    save('startup-drain-summary.json', samples)
    containers = qa_containers()
    save('qa-runtime-before-tests.json', [safe_container(c) for c in containers])
    for c in containers:
        assert list(c['NetworkSettings']['Networks']) == [PROJECT + '_qa']
        for m in c['Mounts']:
            assert (m.get('Name', '').startswith(PROJECT + '_') or (m.get('Name') == 'cqc_simulator_dataset' and not m['RW']))
        assert c['Image'] == current[c['Config']['Labels']['com.docker.compose.service']]['Image']
    note('SIM-04: actual change, stale revision rejection, unchanged state, restore')
    before = observations('sim04-before')
    assert before['simulator'] == before['backend'] and before['simulator']['concurrency'] == 1 and not before['jobs']
    r = before['simulator']['revision']
    update = api('sim04-change', BE, '/v1/quality/simulator', 'PUT', {'expectedRevision': r, 'concurrency': 2})
    after_change = observations('sim04-after-change')
    stale = api('sim04-stale-revision', BE, '/v1/quality/simulator', 'PUT', {'expectedRevision': r, 'concurrency': 1})
    after_stale = observations('sim04-after-stale')
    restore = api('sim04-restore', BE, '/v1/quality/simulator', 'PUT', {'expectedRevision': after_stale['simulator']['revision'], 'concurrency': 1})
    after_restore = observations('sim04-after-restore')
    checks = {
        'change_200': update['response']['status'] == 200,
        'change_r_plus_1': after_change['simulator']['revision'] == r + 1 and update['response']['body'].get('revision') == r + 1,
        'actual_concurrency_2': after_change['simulator']['concurrency'] == 2,
        'backend_actual_state_agree': after_change['backend'] == after_change['simulator'],
        'stale_409_revision_conflict': stale['response']['status'] == 409 and stale['response']['body'].get('code') == 'REVISION_CONFLICT',
        'stale_settings_and_revision_unchanged': after_stale['simulator'] == after_change['simulator'] and after_stale['backend'] == after_change['backend'],
        'restore_200_r_plus_2': restore['response']['status'] == 200 and after_restore['simulator']['revision'] == r + 2,
        'restored_original_settings': {k:v for k,v in after_restore['simulator'].items() if k != 'revision'} == {k:v for k,v in before['simulator'].items() if k != 'revision'},
        'restore_backend_actual_state_agree': after_restore['backend'] == after_restore['simulator'],
        'inspection_count_unchanged_no_jobs': all(o['inspection_count'] == before['inspection_count'] and not o['jobs'] for o in [before, after_change, after_stale, after_restore]),
        'response_cache_no_store': all({k.lower():v for k,v in x['response']['headers'].items()}.get('cache-control') == 'no-store' for x in [update, stale, restore])}
    summary['cases']['SIM-04'] = {'observed_result': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'initial_revision': r, 'final_revision': after_restore['simulator']['revision']}
    save('sim04-checks.json', summary['cases']['SIM-04'])
    note('SIM-05: ten invalid settings; compare Backend and Simulator state each time')
    matrix = json.loads((ROOT / 'docs/wbs/results/qa-mo-be-followup-20261012/sim05-request-matrix.json').read_text())
    results = []
    for case in matrix['cases']:
        label = 'sim05-' + case['case']
        before = observations(label + '-before')
        payload = dict(case['additional_payload'])
        if not case.get('omit_expectedRevision'):
            payload = {'expectedRevision': before['simulator']['revision'], **payload}
        result = api(label + '-request', BE, '/v1/quality/simulator', 'PUT', payload)
        after = observations(label + '-after')
        checks = {
            '422_invalid_settings': result['response']['status'] == 422 and result['response']['body'].get('code') == 'INVALID_SETTINGS',
            'simulator_settings_and_revision_unchanged': before['simulator'] == after['simulator'],
            'backend_settings_and_revision_unchanged': before['backend'] == after['backend'],
            'backend_actual_state_agree': before['backend'] == before['simulator'] == after['backend'] == after['simulator'],
            'inspection_count_unchanged': before['inspection_count'] == after['inspection_count'] == samples[-1]['inspection_count'],
            'no_inflight_jobs': not before['jobs'] and not after['jobs'],
            'cache_no_store': {k.lower():v for k,v in result['response']['headers'].items()}.get('cache-control') == 'no-store'}
        results.append({'case': case['case'], 'status': result['response']['status'], 'checks': checks, 'observed_result': 'PASS' if all(checks.values()) else 'FAIL'})
    summary['cases']['SIM-05'] = {'observed_result': 'PASS' if all(r['observed_result'] == 'PASS' for r in results) else 'FAIL', 'passed': sum(r['observed_result'] == 'PASS' for r in results), 'total': len(results), 'rows': results}
    save('sim05-checks.json', summary['cases']['SIM-05'])
    summary['final_observations'] = observations('final')
    note('Tests complete; exporting evidence and stopping only this QA project')
except Exception as exc:
    summary['execution_error'] = redact(str(exc))
    save('execution-error.json', {'error': str(exc), 'traceback': traceback.format_exc()})
    note('Execution stopped: ' + redact(str(exc))[:500])
finally:
    if created:
        try:
            containers = qa_containers()
            save('qa-runtime-after-tests.json', [safe_container(c) for c in containers])
            for c in containers:
                service = c['Config']['Labels']['com.docker.compose.service']
                log = command('docker', 'logs', '--timestamps', c['Id'], timeout=15, check=False)
                (OUT / (service + '.log')).write_text(redact(log['stdout'] + log['stderr']), encoding='utf-8')
            sql_shell = 'MYSQL_PWD="$MYSQL_PASSWORD" mysqldump --single-transaction --no-tablespaces -u"$MYSQL_USER" "$MYSQL_DATABASE"'
            dump = command('docker', 'exec', PROJECT + '-mysql-1', 'sh', '-c', sql_shell, timeout=20, check=False)
            (OUT / 'qa-database.sql').write_text(redact(dump['stdout']), encoding='utf-8')
            save('database-export-result.json', {'exit_code': dump['exit_code'], 'stderr': dump['stderr']})
            position = command('docker', 'exec', PROJECT + '-simulator-1', 'cat', '/data/state/position.json', check=False)
            save('position-export.json', position)
            save('qa-stop-simulator.json', compose('stop', '--timeout', '20', 'simulator', timeout=40, check=False))
            save('qa-stop.json', compose('stop', '--timeout', '25', 'backend', 'inference', 'mysql', timeout=55, check=False))
            save('qa-stopped-runtime.json', [safe_container(c) for c in qa_containers()])
            summary['qa_resources_preserved'] = True
        except Exception as exc:
            summary['cleanup_error'] = redact(str(exc))
            note('Evidence/stop limitation: ' + redact(str(exc))[:300])
            try:
                save('qa-stop-retry.json', compose('stop', '--timeout', '10', timeout=35, check=False))
            except Exception as stop_exc:
                summary['stop_retry_error'] = redact(str(stop_exc))
    try:
        e1_after = public_containers()
        save('e1-after.json', e1_after)
        summary['public_containers_unchanged_and_healthy'] = e1_before == e1_after
    except Exception as exc:
        summary['public_postcheck_error'] = str(exc)
    summary['finished_kst'] = datetime.now(KST).isoformat()
    save('summary.json', summary)
    shutil.copy2(__file__, OUT / Path(__file__).name)
    # Never package raw secrets, environment credentials, or complete docker inspect.
    files = list(OUT.iterdir())
    for f in files:
        data = f.read_bytes()
        assert not any(v.encode() in data for v in credential_values), f'Secret in evidence: {f.name}'
    lines = [hashlib.sha256(f.read_bytes()).hexdigest() + '  ' + f.name for f in sorted(files) if f.is_file()]
    (OUT / 'manifest.sha256').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    note('Evidence: ' + str(OUT))
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    raise SystemExit(1 if summary.get('execution_error') or summary.get('cleanup_error') or any(c['observed_result'] != 'PASS' for c in summary['cases'].values()) else 0)
