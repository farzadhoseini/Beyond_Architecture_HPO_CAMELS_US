from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
MANIFEST=json.loads((HERE/'TABLES_MANIFEST.json').read_text(encoding='utf-8'))
DOCS={
    'main': HERE/'canonical_manuscript'/'main_current.tex',
    'supp': HERE/'canonical_manuscript'/'supp_current.tex',
}

def extract_tables(path: Path):
    s=path.read_text(encoding='utf-8',errors='replace')
    patt=re.compile(r'\\begin\{(table\*?)\}(.*?)\\end\{\1\}',re.S)
    out={}
    for m in patt.finditer(s):
        full=m.group(0).strip()+"\n"
        lm=re.search(r'\\label\{([^}]+)\}',full)
        if not lm:
            raise RuntimeError(f'Unlabelled table in {path}')
        label=lm.group(1)
        if label in out:
            raise RuntimeError(f'Duplicate table label {label} in {path}')
        out[label]=full
    return out

def main():
    ap=argparse.ArgumentParser(description='Emit the 34 canonical LaTeX tables used by the current CAMELS-US manuscripts.')
    ap.add_argument('--outdir',type=Path,required=True)
    args=ap.parse_args()
    outdir=args.outdir.resolve()
    if outdir.exists(): shutil.rmtree(outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    extracted={k:extract_tables(v) for k,v in DOCS.items()}
    expected=set()
    for rec in MANIFEST:
        label=rec['label']; doc=rec['document']; fn=rec['filename']
        if label not in extracted[doc]:
            raise RuntimeError(f'Manifest table missing from canonical {doc}: {label}')
        content=extracted[doc][label]
        # Explicit V17 reproducibility correction: the current manuscript has
        # 0.957 for Cluster 1 in tab:hydro_selection_regimes, whereas the
        # canonical bundled pre-Liu summary gives wilcoxon_p_fdr_bh=0.960420;
        # at the table's displayed precision this is 0.960.
        if label == 'tab:hydro_selection_regimes':
            old="[-0.00155, 0.00157] & 0.957 \\"
            new="[-0.00155, 0.00157] & 0.960 \\"
            if content.count(old) != 1:
                raise RuntimeError('Expected single Cluster-1 FDR transcription target not found')
            content=content.replace(old,new)
        (outdir/fn).write_text(content,encoding='utf-8')
        expected.add(fn)
    actual={p.name for p in outdir.glob('*.tex')}
    if actual != expected:
        raise RuntimeError(f'Table output mismatch. Missing={sorted(expected-actual)} extra={sorted(actual-expected)}')
    print(f'[PASS] canonical tables emitted: {len(actual)} -> {outdir}')

if __name__=='__main__': main()
