from pathlib import Path
import hashlib
import json
import subprocess
import sys

root = Path('C:/CQC')
out = Path(sys.argv[1])
assert out.resolve().parent == (root / 'outputs').resolve()
provenance = json.loads((out / 'deployment-provenance.json').read_text())
project = out.name.replace('qa-mo-sim03-sim12-', 'cqc-mo103-sim0312-')
assert project.startswith('cqc-mo103-sim0312-')
workspace = '/var/jenkins_home/workspace/CQC-CICD'
previous = 'f8a200221d7aa4cb3f44877e4114d464208366d7'

def git(*args):
    return subprocess.check_output(['docker', 'exec', 'jenkins', 'git', '-C', workspace, *args], timeout=20)

def tree(sha):
    entries = git('ls-tree', '-r', '-z', sha, 'src/simulator', 'src/api').split(b'\0')
    return {e.split(b'\t',1)[1].decode(): e.split(b'\t',1)[0].split()[2].decode() for e in entries if e}

old_tree, build_tree = tree(previous), tree(provenance['source_sha'])
diff = git('diff', '--name-only', previous, provenance['source_sha'], '--', 'src/simulator', 'src/api').decode().splitlines()
records = []
for service, directory in [('simulator', 'src/simulator'), ('backend', 'src/api')]:
    code = '''import json,hashlib
from pathlib import Path
directory=Path(__import__('sys').argv[1])
result=[]
for path in sorted(directory.rglob('*.py')):
 data=path.read_bytes()
 result.append({'path':path.as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\\0'+data).hexdigest()})
print(json.dumps(result))
'''
    result = json.loads(subprocess.check_output(['docker','exec',project+'-'+service+'-1','python','-c',code,directory], timeout=20))
    for row in result:
        row['service'] = service
        row['matches_build_commit'] = row['git_blob'] == build_tree.get(row['path'])
        row['matches_previous_be_commit'] = row['git_blob'] == old_tree.get(row['path'])
        records.append(row)
    runner = subprocess.check_output(['docker','exec',project+'-'+service+'-1','cat',directory+('/runner.py' if service == 'simulator' else '/routers/quality_simulator.py')], timeout=20)
    (out / ('deployed-'+service+'-source.py')).write_bytes(runner)

assert all(row['matches_build_commit'] for row in records), 'Deployed source differs from Jenkins source'
record = {'build': provenance['build'], 'build_commit': provenance['source_sha'], 'previous_be_commit':previous,
          'all_runtime_source_matches_build':True, 'changed_api_simulator_paths_from_be_source':diff,
          'all_runtime_source_matches_be_source': all(row['matches_previous_be_commit'] for row in records),
          'files':records,
          'limit':'Compares tracked src/api and src/simulator Python source only; not all libraries or model/environment equality'}
(out / 'source-attestation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ['files']},ensure_ascii=False))
