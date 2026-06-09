import json
from pathlib import Path

p = Path('UI/custom_workflows/klein_ready_20260609_183406.json')
if p.exists():
    with open(p, encoding='utf-8') as f:
        wf = json.load(f)
    print('=== Verification of saved JSON from test queue ===')
    loads = [n for n in wf['nodes'] if n.get('type')=='LoadImage']
    sorted_l = sorted(loads, key=lambda n: (n.get('pos') or [9999])[0])[:3]
    for n in sorted_l:
        print(f"  LoadImage id={n['id']}: {n['widgets_values'][0]}")
    pnode = next((n for n in wf['nodes'] if n.get('type')=='String Literal' and n.get('title')=='PROMPT'), None)
    if pnode:
        print(f"  PROMPT node: {pnode['widgets_values'][0][:90]}...")
    print('Refs and prompt ARE in the JSON. Good.')
else:
    print('No test JSON found from previous run.')
    print('Listing recent in custom_workflows:')
    for f in sorted(Path('UI/custom_workflows').glob('*.json'), key=lambda x:x.stat().st_mtime, reverse=True)[:3]:
        print('  ', f.name)