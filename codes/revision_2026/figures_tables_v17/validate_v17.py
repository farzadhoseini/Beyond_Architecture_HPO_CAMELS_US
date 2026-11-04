from __future__ import annotations
import argparse, json, re, py_compile, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
FIG=json.loads((HERE/'FIGURES_MANIFEST.json').read_text(encoding='utf-8'))
TAB=json.loads((HERE/'TABLES_MANIFEST.json').read_text(encoding='utf-8'))
HASH=json.loads((HERE/'CANONICAL_MANUSCRIPT_SHA256.json').read_text(encoding='utf-8'))

def source_gate():
    py=list(HERE.glob('*.py'))
    for p in py: py_compile.compile(str(p),doraise=True)
    print(f'[PASS] Python syntax: {len(py)} files')
    for key,rel in [('main','main_current.tex'),('supp','supp_current.tex')]:
        p=HERE/'canonical_manuscript'/rel
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        if h != HASH[key]['sha256']: raise RuntimeError(f'Canonical manuscript hash mismatch: {key}')
    print('[PASS] canonical manuscript hashes')
    if len(FIG)!=35 or len({r['filename'] for r in FIG})!=35: raise RuntimeError('Figure manifest must contain 35 unique files')
    if len(TAB)!=34 or len({r['label'] for r in TAB})!=34 or len({r['filename'] for r in TAB})!=34: raise RuntimeError('Table manifest must contain 34 unique tables')
    print('[PASS] manifests: 35 figures + 34 tables')
    rev=(HERE/'revision_results_figures_v17.py').read_text(encoding='utf-8')
    required_snippets=[
        '("Kratzert ensemble", "Cluster-wise", "Hydrologically informed")',
        '("HESS-LSTM (single published seed)", "Cluster-wise", "Hydrologically informed")',
        '("Cluster-wise", "Hydrologically informed")',
        'labels.append(f"{model_label} vs {ref_short}")',
        'label=legend_label',
    ]
    for required in required_snippets:
        if required not in rev: raise RuntimeError(f'Missing direct revision label logic: {required}')
    print('[PASS] revised publication labels are direct source logic')

def output_gate(root: Path):
    figdir=root/'figures'; tabdir=root/'tables'
    ef={r['filename'] for r in FIG}; et={r['filename'] for r in TAB}
    af={p.name for p in figdir.glob('*.pdf')} if figdir.exists() else set()
    at={p.name for p in tabdir.glob('*.tex')} if tabdir.exists() else set()
    if af!=ef: raise RuntimeError(f'Figure final gate failed. Missing={sorted(ef-af)} extra={sorted(af-ef)}')
    if at!=et: raise RuntimeError(f'Table final gate failed. Missing={sorted(et-at)} extra={sorted(at-et)}')
    # Validate each table contains exactly its manifest label.
    for rec in TAB:
        s=(tabdir/rec['filename']).read_text(encoding='utf-8',errors='replace')
        labs=re.findall(r'\\label\{([^}]+)\}',s)
        if labs != [rec['label']]: raise RuntimeError(f'Table label mismatch {rec["filename"]}: {labs}')
    # No extra file types inside the two final Overleaf folders.
    badf=[p.name for p in figdir.iterdir() if p.is_file() and p.suffix.lower()!='.pdf']
    badt=[p.name for p in tabdir.iterdir() if p.is_file() and p.suffix.lower()!='.tex']
    if badf or badt: raise RuntimeError(f'Non-final file types present figures={badf} tables={badt}')
    print('[PASS] FINAL Overleaf payload: exactly 35 PDFs + 34 TEX tables')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--final-root',type=Path)
    a=ap.parse_args()
    source_gate()
    if a.final_root: output_gate(a.final_root.resolve())
    print('V17 STRICT GATE: PASS')
if __name__=='__main__': main()
