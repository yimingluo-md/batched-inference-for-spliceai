"""Recompute production allocation and application-time totals from public records."""
import json
import math
from pathlib import Path

root=Path(__file__).parent/'results'
accepted=json.loads((root/'accepted-scoring-times.json').read_text())
allocations=json.loads((root/'gpu-allocations.json').read_text())
summary=json.loads((root/'production-runtime-summary.json').read_text())
assert len(accepted)==3449
assert len({r['scoring_unit'] for r in accepted})==3449
assert sum(r['records'] for r in accepted)==3408398835
assert len({r['parent_shard'] for r in accepted})==3419
assert math.isclose(math.fsum(r['application_seconds'] for r in accepted),summary['accepted_application_seconds'],abs_tol=1e-6)
assert math.isclose(math.fsum(r['command_wall_seconds'] for r in accepted),summary['accepted_command_wall_seconds'],abs_tol=1e-6)
for group,key in [('accepted','accepted_jobs'),('unsuccessful','other_production_attempts'),('chunk_control','chunk_equivalence_control')]:
    rows=[r for r in allocations if r['scope']==group]
    assert len(rows)==summary[key]['accounting_rows']
    seconds=sum(r['elapsed_seconds']*r['gpus'] for r in rows)
    assert seconds==summary[key]['gpu_seconds']
    print(f'{group}: {len(rows)} jobs; {seconds/3600:.4f} allocated GPU-hours')
assert sum(r['scheduler_seconds'] for r in accepted)==summary['accepted_jobs']['gpu_seconds']
assert not any(r['application_seconds']>r['command_wall_seconds']+1 or r['command_wall_seconds']>r['scheduler_seconds']+2 for r in accepted)
print('PASS: record lineage, job counts, allocation totals, and application timers.')
