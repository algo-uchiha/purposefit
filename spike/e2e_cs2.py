"""Spike: CS-S1 scorecard for B2-k vs B2-k + hybrid redaction + minimisation (withhold customers table)."""
import sys, shutil, importlib.util, json
from pathlib import Path
import pandas as pd
ROOT=Path(sys.argv[1]); sys.path.insert(0,str(ROOT/'baselines'))
from _common import catalog_for, io, protect_table, write_protected
from pets_eval.scorecard import run_scorecard
spec=importlib.util.spec_from_file_location('rs','/home/claude/spike/redact_spike.py')
sys.argv=[sys.argv[0],str(ROOT)]; rs=importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)
def red(t):
    t=t or ''; out,pos=[],0
    for s in rs.detect(t): out+= [t[pos:s['start']],f"[{s['label']}]"]; pos=s['end']
    return ''.join(out)+t[pos:]
cat=catalog_for('customer_service'); orig=io.load_tables(ROOT/'data/customer_service')
for name,mode in [('ours',1)]:
    prot={t:protect_table('customer_service',t,df,cat,'b2k') for t,df in orig.items()}
    if mode:
        prot['turns']['text']=orig['turns']['text'].map(red)
        prot['conversations']['agent_note']=orig['conversations']['agent_note'].map(red)
        prot['turns']['conversation_id']=orig['turns']['conversation_id']  # keep join consistent (keyed pseudonym in real build)
        prot.pop('customers')                      # data minimisation: CS-S1 tasks do not need it
        prot['conversations']=prot['conversations'].drop(columns=['customer_id'])
    out=Path(f'/home/claude/spike/out_{name}'); shutil.rmtree(out,ignore_errors=True)
    write_protected(prot,orig,out,cat,'customer_service')
    rep=run_scorecard(ROOT/'data/customer_service',out,scenario='CS-S1',root=ROOT,out_dir=out)
    print(name, rep['summary']['privacy'],rep['summary']['utility'],rep['summary']['composite'])
    print('  ',{u['id']:u['score'] for u in rep['utility']})
    print('  ',{k:round(v,3) for k,v in rep['risk_components'].items() if v})
