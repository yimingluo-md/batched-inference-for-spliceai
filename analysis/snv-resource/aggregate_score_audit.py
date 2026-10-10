"""Validate all chromosome audits and produce manuscript-ready descriptive tables."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    manifest=json.loads(args.manifest.read_text())
    rows=[]; hashes={}; genes=Counter(); multiplicity=Counter()
    for item in manifest['files']:
        path=args.results/f'chr{item["contig"]}.json'
        row=json.loads(path.read_text())
        assert row['status']=='passed' and row['contig']==item['contig']
        assert row['records']==item['records']
        assert row['provenance']['vcf_sha256']==item['vcf_sha256']
        assert row['distal_score_thresholds_hundredths']==[1,20,50,80]
        hashes[path.name]=sha(path)
        genes.update(row['gene_entry_counts']); multiplicity.update(row['gene_multiplicity'])
        rows.append(row)
    assert len(rows)==24
    assert len({r['provenance']['analysis_source_sha256'] for r in rows})==1
    assert len({r['provenance']['task_wrapper_sha256'] for r in rows})==1
    assert len({r['provenance']['release_manifest_sha256'] for r in rows})==1
    scalar_keys=['records','variant_gene_entries','multigene_records','signed_zero_score_fields']
    list_keys=['variant_max_histogram','entry_max_histogram','variants_with_distal_event','entries_with_distal_event']
    list_keys += [e+s for e in ['AG','AL','DG','DL'] for s in ['_histogram','_distal_histogram']]
    combined={k:sum(r[k] for r in rows) for k in scalar_keys}
    for k in list_keys:combined[k]=[sum(r[k][i] for r in rows) for i in range(len(rows[0][k]))]
    combined['gene_multiplicity']=dict(sorted(multiplicity.items(),key=lambda kv:int(kv[0])))
    combined['gene_entry_counts']=dict(sorted(genes.items()))
    combined['unique_gene_symbols']=len(genes)
    combined['distal_score_thresholds_hundredths']=[1,20,50,80]
    n=combined['records']; ne=combined['variant_gene_entries']
    assert n==manifest['records']==sum(combined['variant_max_histogram'])
    assert sum(combined['entry_max_histogram'])==ne==sum(genes.values())
    assert sum(multiplicity.values())==n
    assert sum(v for k,v in multiplicity.items() if int(k)>1)==combined['multigene_records']
    for ev in ['AG','AL','DG','DL']:
        assert sum(combined[ev+'_histogram'])==ne
        assert combined[ev+'_distal_histogram'][0]==0
        assert all(d<=a for d,a in zip(combined[ev+'_distal_histogram'],combined[ev+'_histogram']))
    summary={
        'status':'passed','generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'All 24 released chromosome VCFs, not a sample; descriptive scan without inference or independent FASTA-span reconciliation.',
        'definitions':{
            'score_unit':'Published two-decimal delta score; histogram index is score multiplied by 100. Signed -0.00 is counted as zero.',
            'variant_max':'Maximum over all four score types and all gene annotations for one VCF record.',
            'entry_max':'Maximum over four score types for one variant–gene annotation.',
            'distal':'A reported score >0.00 with absolute associated delta position >50 nt (at most 500 nt).',
            'distal_threshold':'At least one individual distal event must meet the threshold; a proximal high score does not qualify a low distal score.',
            'multigene':'A VCF record with more than one distinct gene symbol; duplicate symbol entries fail the audit.',
            'interpretation':'Distal reported maxima are not a D50 rerun, a count of all affected splice sites, or an estimate of clinical sensitivity.',
        },
        'combined':combined,
        'provenance':{
            'local_release_manifest_sha256':sha(args.manifest),
            'audited_release_manifest_sha256':rows[0]['provenance']['release_manifest_sha256'],
            'analysis_source_sha256':rows[0]['provenance']['analysis_source_sha256'],
            'wrapper_sha256':rows[0]['provenance']['task_wrapper_sha256'],
            'chromosome_result_sha256':hashes,
        }
    }
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'score_audit_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    pct=lambda a,b:f'{100*a/b:.4f}%'
    lines=['# Full-release score audit','',f'All {n:,} SNV records in 24 chromosome VCFs were scanned. All compressed VCF checksums and chromosome record counts matched the release manifest. This was not an independent reference-span reconciliation.','',
           '## Score distribution','', 'Scores are the values stored in the released VCFs, rounded to two decimals. Variant-level maxima include all gene annotations.','',
           '| Maximum score | SNV records | % of SNVs | Variant–gene annotations | % of annotations |', '|---|---:|---:|---:|---:|']
    for name,lo,hi in [('0.00',0,0),('0.01–0.19',1,19),('0.20–0.49',20,49),('0.50–0.79',50,79),('0.80–1.00',80,100)]:
        v=sum(combined['variant_max_histogram'][lo:hi+1]); e=sum(combined['entry_max_histogram'][lo:hi+1])
        lines.append(f'| {name} | {v:,} | {pct(v,n)} | {e:,} | {pct(e,ne)} |')
    lines += ['', '## Annotation multiplicity','',f'There were {ne:,} variant–gene annotations and {len(genes):,} distinct gene symbols. {combined["multigene_records"]:,} SNVs ({pct(combined["multigene_records"],n)}) had annotations for multiple genes.','', '| Distinct genes per SNV | SNV records | % of SNVs |','|---|---:|---:|']
    for k,v in combined['gene_multiplicity'].items():lines.append(f'| {k} | {v:,} | {pct(v,n)} |')
    lines += ['', '## Reported distal effects','', 'Distal means absolute reported position >50 nt and a positive displayed score. Thresholds apply to the distal score itself. Events are gene-specific AG/AL/DG/DL maxima and may refer to the same genomic position.','',
              '| Score threshold | SNVs with any qualifying score | SNVs with a qualifying distal event | % of all SNVs | % of score-qualified SNVs | Variant–gene entries with a qualifying distal event | Gene-specific distal event fields |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for i,t in enumerate([1,20,50,80]):
        qualified=sum(combined['variant_max_histogram'][t:]); distal=combined['variants_with_distal_event'][i]
        events=sum(sum(combined[e+'_distal_histogram'][t:]) for e in ['AG','AL','DG','DL'])
        assert distal<=qualified
        conditional=pct(distal,qualified) if qualified else 'NA'
        lines.append(f'| ≥{t/100:.2f} | {qualified:,} | {distal:,} | {pct(distal,n)} | {conditional} | {combined["entries_with_distal_event"][i]:,} | {events:,} |')
    lines += ['', 'These descriptive counts do not establish which variants would be missed at D=50: the released D=500 maxima cannot reconstruct a D=50 calculation. A score of 0.00 may include a small unrounded prediction; its position is not counted as an effect.',f'The scan observed {combined["signed_zero_score_fields"]:,} score fields formatted as -0.00; these were counted as zero without modifying the VCFs.','', '## Distal event types','', '| Event type | Positive distal fields | Distal fields ≥0.20 | Distal fields ≥0.50 | Distal fields ≥0.80 |','|---|---:|---:|---:|---:|']
    for ev in ['AG','AL','DG','DL']:
        vals=[sum(combined[ev+'_distal_histogram'][t:]) for t in [1,20,50,80]]
        lines.append('| '+ev+' | '+' | '.join(f'{v:,}' for v in vals)+' |')
    (args.output/'score_audit_tables.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:combined[k] for k in scalar_keys+['unique_gene_symbols','variants_with_distal_event']},indent=2))


if __name__=='__main__':main()
