"""Check the deployed date-free CSV once, with a fixed snapshot cutoff."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import csv,io,json,re,time,urllib.request,urllib.parse,subprocess

OUT=Path('C:/CQC/outputs/qa-mo-be-followup-20261012-162118')
KST=timezone(timedelta(hours=9))
cutoff=int(time.time()*1000)
day=datetime.fromtimestamp(cutoff/1000,KST).date().isoformat()
records=[]

def fetch(label,path):
    start=time.monotonic()
    with urllib.request.urlopen('http://127.0.0.1:8000'+path,timeout=20) as r:
        data=r.read()
        records.append({'label':label,'path':path,'http_status':r.status,'elapsed_seconds':round(time.monotonic()-start,6),
            'response_headers':{k:v for k,v in r.headers.items() if k.lower() in ['content-type','content-disposition','cache-control']}})
    return data

started=datetime.now(KST).isoformat()
raw=fetch('date_free_csv','/v1/quality/statistics.csv?'+urllib.parse.urlencode({'snapshotAt':cutoff}))
(OUT/'ops13-date-free-statistics.csv').write_bytes(raw)
raw_json=fetch('same_day_json','/v1/quality/statistics?'+urllib.parse.urlencode({'from':day,'to':day,'snapshotAt':cutoff}))
(OUT/'ops13-same-day-statistics.json').write_bytes(raw_json)
summary=json.loads(raw_json)
rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
header=raw.decode('utf-8-sig').splitlines()[0]
suspicions={r['key']:r['value'] for r in rows if r['section']=='suspicions'}
expected_keys=['CULTIVAR_SUSPECT','QUALITY_SUSPECT','OTHER']
checks={
 'bom':raw.startswith(b'\xef\xbb\xbf'),
 'crlf_only':b'\n' not in raw.replace(b'\r\n',b'') and raw.endswith(b'\r\n'),
 'header':next(csv.reader([header]))==['mode','date_kst','section','key','value','last_saved_at'],
 'all_cells_quoted':all(re.fullmatch(r'"(?:[^"]|"")*"(?:,"(?:[^"]|"")*")*',line) is not None for line in raw.decode('utf-8-sig').splitlines()),
 'mode_backend':all(r['mode']=='BACKEND' for r in rows),
 'three_suspicions_once':all(sum(r['section']=='suspicions' and r['key']==k for r in rows)==1 for k in expected_keys),
 'suspicions_match_json':all(float(suspicions.get(k,'nan'))==float(summary.get('suspicions',{}).get(k,0)) for k in expected_keys),
 'sections_present':all(any(r['section']==s for r in rows) for s in ['today','grades','varieties','bins','suspicions']),
}
section_checks={}
for section in ['grades','varieties','bins']:
    found={r['key']:float(r['value']) for r in rows if r['section']==section}
    expected={k:float(v) for k,v in summary.get(section,{}).items()}
    section_checks[section]={'csv':found,'json':expected,'equal':found==expected}
    checks[section+'_match_json']=found==expected
today={r['key']:r['value'] for r in rows if r['section']=='today'}
for key in ['total','normal','excluded','reinspection']:
    checks['today_'+key+'_match_json']=float(today.get(key,'nan'))==float(summary[key])
ratio_key='reinspection_ratio'
if ratio_key in today:
    expected_ratio=summary['reinspection']/summary['total'] if summary['total'] else 0
    checks['reinspection_ratio']=abs(float(today[ratio_key])-expected_ratio)<0.000001
nums=subprocess.check_output(['docker','exec','jenkins','ls','-1','/var/jenkins_home/jobs/CQC-CICD/builds'],text=True).splitlines()
latest=max(int(n) for n in nums if n.isdigit())
checks['jenkins_still_143']=latest==143
result={'started_kst':started,'finished_kst':datetime.now(KST).isoformat(),'snapshot_at':cutoff,'date_kst':day,
 'actor':'홍유나','precondition':'User confirmed no measurement/server QA/new build in this chat before reading CSV.',
 'requests':records,'rows':len(rows),'suspicions':suspicions,'same_day_json_suspicions':summary.get('suspicions'),
 'today':today,'section_checks':section_checks,'checks':checks,'all_checks_passed':all(checks.values()),
 'scope':'One date-free CSV plus matching same-day JSON; historical period/minute CSV evidence reused, no new inspection, settings or DB write.',
 'result_for_be':'Read-only evidence for BE final QA-OPS-13 judgment; no official QA record or #65 FAIL changed.'}
(OUT/'ops13-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'started_kst':started,'finished_kst':result['finished_kst'],'suspicions':suspicions,'checks':checks,'passed':result['all_checks_passed']},ensure_ascii=True))
