"""Independent Python cross-check of the C++ counters and failure gates."""
import gzip
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from collections import Counter


def reference(lines):
    out = dict(records=0, variant_gene_entries=0, multigene_records=0, signed_zero_score_fields=0)
    for key in ['variant_max_histogram', 'entry_max_histogram']:
        out[key] = [0]*101
    for ev in ['AG','AL','DG','DL']:
        out[ev+'_histogram'] = [0]*101
        out[ev+'_distal_histogram'] = [0]*101
    out['variants_with_distal_event'] = [0]*4
    out['entries_with_distal_event'] = [0]*4
    genes, multiplicity = Counter(), Counter()
    for line in lines:
        if line.startswith('#'): continue
        c=line.rstrip().split('\t')
        info=dict(x.split('=',1) for x in c[7].split(';') if '=' in x)
        annotations=[x.split('|') for x in info['SpliceAI'].split(',')]
        scores=[]; distal=[]
        for a in annotations:
            out['signed_zero_score_fields']+=a[2:6].count('-0.00')
            ds=[round(float(x)*100) for x in a[2:6]]
            dp=[int(x) for x in a[6:10]]
            out['entry_max_histogram'][max(ds)]+=1
            out['variant_gene_entries']+=1
            genes[a[1]]+=1
            scores.extend(ds)
            ed=[s for s,p in zip(ds,dp) if s>0 and abs(p)>50]
            distal.extend(ed)
            for i,t in enumerate([1,20,50,80]):
                out['entries_with_distal_event'][i]+=any(s>=t for s in ed)
            for ev,s,p in zip(['AG','AL','DG','DL'],ds,dp):
                out[ev+'_histogram'][s]+=1
                if s>0 and abs(p)>50: out[ev+'_distal_histogram'][s]+=1
        out['variant_max_histogram'][max(scores)]+=1
        out['records']+=1
        count=len({a[1] for a in annotations})
        out['multigene_records']+=count>1
        multiplicity[str(count)]+=1
        for i,t in enumerate([1,20,50,80]):
            out['variants_with_distal_event'][i]+=any(s>=t for s in distal)
    out['gene_entry_counts']=dict(genes)
    out['unique_genes']=len(genes)
    out['gene_multiplicity']=dict(multiplicity)
    return out


def main():
    binary=sys.argv[1]
    rng=random.Random(20261009)
    lines=['#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n']
    for i in range(1000):
        entries=[]
        for j in range(rng.randint(1,4)):
            ds=[rng.choice([0,1,19,20,49,50,79,80,100]) for _ in range(4)]
            dp=[rng.choice([-500,-51,-50,0,50,51,500]) for _ in range(4)]
            formatted=['-0.00' if s==0 and rng.random()<0.5 else f'{s/100:.2f}' for s in ds]
            entries.append('|'.join(['C',f'GENE{j}']+formatted+list(map(str,dp))))
        lines.append(f'1\t{i+1}\t.\tA\tC\t.\t.\tSpliceAI={",".join(entries)}\n')
    with tempfile.TemporaryDirectory(prefix='spliceai-audit-test-') as tmp:
        inp=Path(tmp)/'test.vcf.gz'; output=Path(tmp)/'result.json'
        with gzip.open(inp,'wt') as f:f.writelines(lines)
        subprocess.run([binary,str(inp),'1',str(output)],check=True)
        observed=json.loads(output.read_text())
        expected=reference(lines)
        for key,value in expected.items(): assert observed[key]==value,key
        invalid=[
            '1\t1\t.\tA\tC\t.\t.\t.\n',
            '1\t1\t.\tA\tC\t.\t.\tSpliceAI=C|G|.|0.00|0.00|0.00|0|0|0|0\n',
            '1\t1\t.\tA\tC\t.\t.\tSpliceAI=C|G|1.01|0.00|0.00|0.00|0|0|0|0\n',
            '1\t1\t.\tA\tC\t.\t.\tSpliceAI=C|G|0.20|0.00|0.00|0.00|501|0|0|0\n',
            '1\t1\t.\tA\tC\t.\t.\tSpliceAI=C|G|0.00|0.00|0.00|0.00|0|0|0|0,C|G|0.00|0.00|0.00|0.00|0|0|0|0\n',
        ]
        for line in invalid:
            with gzip.open(inp,'wt') as f:f.write(line)
            assert subprocess.run([binary,str(inp),'1',str(output)],capture_output=True).returncode!=0
        real_count=0
        for sample in sys.argv[2:]:
            by_contig={}
            with open(sample) as f:
                for line in f:
                    if not line.startswith('#'):
                        by_contig.setdefault(line.split('\t')[0],[]).append(line)
            for contig,records in by_contig.items():
                records.sort(key=lambda line:(int(line.split('\t')[1]),line.split('\t')[4]))
                with gzip.open(inp,'wt') as f:f.writelines(records)
                subprocess.run([binary,str(inp),contig,str(output)],check=True,capture_output=True)
                observed=json.loads(output.read_text())
                for key,value in reference(records).items():assert observed[key]==value,(sample,contig,key)
                real_count+=len(records)
        if real_count:print(f'PASS: {real_count} real production sample records match independent Python counters.')
    print('PASS: 1,000 synthetic records match independent Python counters; five invalid-input gates fail closed.')


if __name__=='__main__':main()
