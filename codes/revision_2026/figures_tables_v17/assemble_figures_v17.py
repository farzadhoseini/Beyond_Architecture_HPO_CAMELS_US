from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
MANIFEST=json.loads((HERE/'FIGURES_MANIFEST.json').read_text(encoding='utf-8'))

def main():
    ap=argparse.ArgumentParser(description='Assemble exactly the 35 PDF figures referenced by the current main+supp manuscripts.')
    ap.add_argument('--core-dir',type=Path,required=True)
    ap.add_argument('--revision-dir',type=Path,required=True)
    ap.add_argument('--outdir',type=Path,required=True)
    a=ap.parse_args()
    core=a.core_dir.resolve(); rev=a.revision_dir.resolve(); out=a.outdir.resolve()
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True,exist_ok=True)
    missing=[]
    for rec in MANIFEST:
        fn=rec['filename']
        candidates=[core/fn,rev/fn]
        hits=[p for p in candidates if p.is_file()]
        if len(hits)!=1:
            missing.append((fn,[str(p) for p in hits]))
            continue
        shutil.copy2(hits[0],out/fn)
    if missing:
        raise RuntimeError('Figure source resolution failed: '+repr(missing))
    expected={r['filename'] for r in MANIFEST}
    actual={p.name for p in out.glob('*.pdf')}
    other=[p.name for p in out.iterdir() if p.is_file() and p.suffix.lower()!='.pdf']
    if actual != expected or other:
        raise RuntimeError(f'Final figure folder mismatch. Missing={sorted(expected-actual)} extra={sorted(actual-expected)} nonPDF={other}')
    print(f'[PASS] Overleaf figures assembled: {len(actual)} -> {out}')

if __name__=='__main__': main()
