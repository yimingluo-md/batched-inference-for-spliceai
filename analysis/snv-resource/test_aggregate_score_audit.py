"""Exercise all-chromosome aggregation and denominators on a small fixture."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from test_score_audit import reference


def main():
    with tempfile.TemporaryDirectory(prefix='spliceai-aggregate-test-') as tmp:
        root=Path(tmp); results=root/'chromosomes'; results.mkdir()
        manifest={'records':24,'files':[]}
        for chrom in list(map(str,range(1,23)))+['X','Y']:
            annotation='C|G|0.01|0.00|0.00|0.00|50|0|0|0'
            if chrom=='1':annotation='C|G|0.80|0.20|0.00|0.00|0|51|0|0,C|H|0.50|0.00|0.00|0.00|-500|0|0|0'
            if chrom=='2':annotation='C|G|-0.00|0.00|0.00|0.00|500|0|0|0'
            data=reference([f'{chrom}\t1\t.\tA\tC\t.\t.\tSpliceAI={annotation}\n'])
            data.update(status='passed',contig=chrom,distal_score_thresholds_hundredths=[1,20,50,80],provenance={
                'vcf_sha256':'test-vcf','analysis_source_sha256':'test-source',
                'task_wrapper_sha256':'test-wrapper','release_manifest_sha256':'test-manifest',
            })
            (results/f'chr{chrom}.json').write_text(json.dumps(data))
            manifest['files'].append({'contig':chrom,'records':1,'vcf_sha256':'test-vcf'})
        mpath=root/'manifest.json';mpath.write_text(json.dumps(manifest))
        command=[sys.executable,str(Path(__file__).with_name('aggregate_score_audit.py')),
                 '--results',str(results),'--manifest',str(mpath),'--output',str(root/'summary')]
        subprocess.run(command,check=True,capture_output=True)
        combined=json.loads((root/'summary/score_audit_summary.json').read_text())['combined']
        assert combined['records']==24
        assert combined['variant_gene_entries']==25
        assert combined['multigene_records']==1
        assert combined['signed_zero_score_fields']==1
        assert combined['variants_with_distal_event']==[1,1,1,0]
        assert combined['entries_with_distal_event']==[2,2,1,0]
        assert combined['variant_max_histogram'][0]==1
        assert combined['variant_max_histogram'][1]==22
        assert combined['variant_max_histogram'][80]==1
        (results/'chrY.json').rename(results/'chrY.hidden')
        assert subprocess.run(command,capture_output=True).returncode!=0
    print('PASS: 24-chromosome fixture, threshold/denominator checks, and incomplete-audit rejection.')


if __name__=='__main__':main()
