"""Extract only selected historical tool outputs, never full chats or reasoning."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

ROOT=Path('C:/CQC')
OUT=ROOT/'outputs/qa-mo-sim06-sim09-session-recovery-20261014'
OUT.mkdir(exist_ok=True)
SESSION=Path('C:/Users/admin/.codex/sessions/2026/10/06/rollout-2026-10-06T09-26-05-01a10e9a-73ec-74b0-810c-78ca566d56cf.jsonl')
raw_lines=SESSION.read_bytes().splitlines(keepends=True)
objects=[json.loads(line) for line in raw_lines]

def outputs(payload):
    raw=payload.get('output',[])
    texts=[raw] if isinstance(raw,str) else [b.get('text','') for b in raw if isinstance(b,dict)]
    result=[]
    for i,text in enumerate(texts):
        try:value=json.loads(text)
        except ValueError:
            if text.startswith('Script completed') and text.endswith('Output:\n'):continue
            result.append((i,'text',text))
            continue
        if isinstance(value,dict) and isinstance(value.get('output'),str):
            result.append((i,'json.output',value['output']))
    return result

selected={2935:'sim06-compose-cleanup.txt',4212:'sim09-during-recovery-container-status.txt',4225:'sim09-run-completion-and-cleanup.txt'}
provenance=[]
for n,name in selected.items():
    obj=objects[n-1]
    assert obj['payload']['type'] in ['custom_tool_call_output','function_call_output']
    parts=outputs(obj['payload'])
    assert len(parts)==1, 'Expect one stdout capture, not merged messages'
    index,kind,text=parts[0]
    # These captures are service state/cleanup and test summaries, not inspect Env.
    assert 'cqc-mo09-e2-' in text
    assert not any(key in text for key in ['MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD','SIMULATOR_FAULT_TOKEN','Authorization','DATABASE_URL'])
    (OUT/name).write_bytes(text.encode('utf-8'))
    assert (OUT/name).read_text(encoding='utf-8')==text.replace('\r\n','\n')
    provenance.append({'file':name,'source_session':str(SESSION),'source_session_sha256':hashlib.sha256(SESSION.read_bytes()).hexdigest(),'source_line':n,'source_line_sha256':hashlib.sha256(raw_lines[n-1]).hexdigest(),'tool_call_id':obj['payload']['call_id'],'captured_at_utc':obj['timestamp'],'source_field':'payload.output['+str(index)+'].text ('+kind+')','stored_stdout_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),'limit':'Extracted original tool stdout scalar; historical encoding/truncation is retained. Not a copy of the full session.'})
sim06=(OUT/selected[2935]).read_text(encoding='utf-8')
sim09=(OUT/selected[4225]).read_text(encoding='utf-8')
assert all('cqc-mo09-e2-final-20261006_'+v+' Removed' in sim06 for v in ['mysql_data','backend_logs','simulator_logs'])
assert all('cqc-mo09-e2-recovery2-20261006_'+v+' Removed' in sim09 for v in ['mysql_data','backend_logs','simulator_logs'])
(OUT/'session-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

ids=json.loads((ROOT/'docs/wbs/results/qa-mo-sim06-sim09-inventory-20261014/text-search.json').read_text(encoding='utf-8'))['patterns']
sessions=[SESSION,Path('C:/Users/admin/.codex/sessions/2026/10/07/rollout-2026-10-07T09-47-42-01a113d4-9933-70c2-afc1-1fcfd9dfa324.jsonl')]
matched=[]
for file in sessions:
    for n,line in enumerate(file.open(encoding='utf-8'),1):
        obj=json.loads(line);payload=obj.get('payload',{})
        if payload.get('type') not in ['custom_tool_call_output','function_call_output']:continue
        text='\n'.join(part[2] for part in outputs(payload))
        found=[s for s in ids if s in text]
        if found:matched.append({'session':file.name,'line':n,'captured_at_utc':obj['timestamp'],'call_id':payload.get('call_id'),'matching_ids':found,'has_attempt_no_text':'attempt_no' in text,'has_successful_bin_statistics_text':'successful_bin' in text,'literal_id_lines':sum(any(s in r for s in found) for r in text.splitlines())})
(OUT/'session-target-search.json').write_text(json.dumps({'sessions':[str(p) for p in sessions],'types_searched':['custom_tool_call_output','function_call_output'],'patterns':ids,'matches':matched,'limit':'Presence of code/field names with an ID is a candidate, not evidence that individual rows exist; no messages/reasoning exported'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Compare the only recovered orphan blob; it adds no fields to the known evidence.
blob_sha='0d23a36381afc982781ad35518ad662a27fb3f0d'
blob=subprocess.check_output(['git','cat-file','blob',blob_sha])
known=json.loads((ROOT/'outputs/mo09-e2-recovery2-20261006/recovery-evidence.json').read_text(encoding='utf-8'))
assert json.loads(blob)==known
(OUT/'orphan-comparison.json').write_text(json.dumps({'blob':blob_sha,'bytes':len(blob),'same_json_values_as':'outputs/mo09-e2-recovery2-20261006/recovery-evidence.json','new_fields':[]},indent=2)+'\n',encoding='utf-8')
archive=Path('C:/Users/admin/Documents/Codex/2026-10-12/new-chat/outputs/CQC_Codex_handoff.zip')
with zipfile.ZipFile(archive) as z:
    matches=[]
    for n in z.namelist():
        if Path(n).suffix.lower() not in ['.md','.txt','.json','.sql','.log','.csv']:continue
        data=z.read(n)
        found=[s for s in ids if s.encode() in data]
        if found:matches.append({'member':n,'patterns':found})
    archive_record={'path':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'members':len(z.namelist()),'matches':matches}
(OUT/'handoff-archive-search.json').write_text(json.dumps(archive_record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'extracted_tool_outputs':len(provenance),'session_id_matches':len(matched),'cleanup_removal_confirmed':['SIM-06','SIM-09'],'orphan_adds_fields':False},ensure_ascii=False))
