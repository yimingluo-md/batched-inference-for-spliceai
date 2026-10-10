"""CPU-only chromosome task; validates input SHA and publishes results atomically."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--release',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--contig',required=True)
    args=p.parse_args()
    started=datetime.now(timezone.utc).isoformat(); t=time.monotonic()
    source=Path(__file__).parent
    manifest_path=args.release/'metadata/release-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    entry=next(e for e in manifest['files'] if e['contig']==args.contig)
    inp=args.release/entry['vcf']
    digest=sha(inp)
    assert digest==entry['vcf_sha256'],'VCF SHA-256 mismatch'
    assert inp.stat().st_size==entry['vcf_bytes'],'VCF size mismatch'
    args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.chr{args.contig}-',dir=args.output) as tmp:
        result=Path(tmp)/'result.json'
        subprocess.run([str(source/'score_audit'),str(inp),args.contig,str(result)],check=True)
        data=json.loads(result.read_text())
        assert data['records']==entry['records'],'Record count mismatch'
        assert sum(data['variant_max_histogram'])==data['records']
        assert sum(data['entry_max_histogram'])==data['variant_gene_entries']
        assert sum(data['gene_entry_counts'].values())==data['variant_gene_entries']
        assert sum(int(k)*v for k,v in data['gene_multiplicity'].items())==data['variant_gene_entries']
        for ev in ['AG','AL','DG','DL']:assert sum(data[ev+'_histogram'])==data['variant_gene_entries']
        data['provenance']={
            'vcf_file':inp.name,'vcf_sha256':digest,
            'release_manifest_sha256':sha(manifest_path),
            'analysis_source_sha256':sha(source/'score_audit.cpp'),
            'analysis_binary_sha256':sha(source/'score_audit'),
            'task_wrapper_sha256':sha(Path(__file__)),
            'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds':round(time.monotonic()-t,3),
            'job_id':os.environ.get('SLURM_JOB_ID'),
            'array_task_id':os.environ.get('SLURM_ARRAY_TASK_ID'),
        }
        data['status']='passed'
        result.write_text(json.dumps(data,indent=2)+'\n')
        os.replace(result,args.output/f'chr{args.contig}.json')
    print(json.dumps({'contig':args.contig,'records':data['records'],'status':'passed','elapsed_seconds':data['provenance']['elapsed_seconds']}),flush=True)


if __name__=='__main__':main()
