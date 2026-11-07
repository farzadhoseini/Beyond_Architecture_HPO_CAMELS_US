#!/usr/bin/env python3
"""Export manuscript-ready figure names without modifying V17 scientific outputs."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as src:
        for block in iter(lambda: src.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def load_map():
    raw = json.loads((HERE / 'HESS_FIGURE_MAP.json').read_text(encoding='utf8'))
    existing = json.loads((HERE / 'FIGURES_MANIFEST.json').read_text(encoding='utf8'))
    got = raw['figures']
    if len(got) != 35 or len(existing) != 35:
        raise RuntimeError('Expected 35 mapped figures and 35 V17 manifest figures')
    keys = [(x['document'], x['order']) for x in got]
    old = [(x['document'], x['order']) for x in existing]
    if keys != old:
        raise RuntimeError('Figure ordering does not match V17 manifest')
    if any(a['v17_filename'] != b['filename'] for a,b in zip(got, existing)):
        raise RuntimeError('Figure sources differ from the validated V17 manifest')
    if len({a['hess_filename'] for a in got}) != 35:
        raise RuntimeError('Duplicate HESS figure filename')
    if len({a['v17_filename'] for a in got}) != 35:
        raise RuntimeError('Duplicate V17 source filename')
    for r in got:
        if any('/' in r[x] or '\\' in r[x] or '..' in r[x] for x in ('v17_filename','hess_filename')):
            raise RuntimeError('Unsafe filename in map')
    return got


def export(source_root: Path, output_root: Path, check_only=False):
    figs = load_map()
    src_figs = source_root / 'figures'
    src_tabs = source_root / 'tables'
    tables = json.loads((HERE / 'TABLES_MANIFEST.json').read_text(encoding='utf8'))
    if len(tables) != 34 or len({t['filename'] for t in tables})!=34:
        raise RuntimeError('Expected 34 unique tables in V17 manifest')
    expected_old = {x['v17_filename'] for x in figs}
    actual_old = {p.name for p in src_figs.glob('*.pdf')}
    if expected_old != actual_old:
        raise RuntimeError(f'V17 figures incomplete: missing={sorted(expected_old - actual_old)} extra={sorted(actual_old - expected_old)}')
    expected_t = {x['filename'] for x in tables}
    actual_t = {p.name for p in src_tabs.glob('*.tex')}
    if expected_t != actual_t:
        raise RuntimeError(f'V17 tables incomplete: missing={sorted(expected_t - actual_t)} extra={sorted(actual_t - expected_t)}')
    if check_only:
        print('HESS_EXPORT_INPUT_GATE=PASS; figures=35; tables=34')
        return
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError('Output folder is not empty; choose a new folder to avoid overwriting existing results')
    dest_f = output_root / 'figures'
    dest_t = output_root / 'tables'
    dest_f.mkdir(parents=True,exist_ok=True)
    dest_t.mkdir(parents=True,exist_ok=True)
    records=[]
    for m in figs:
        src = src_figs / m['v17_filename']
        dest = dest_f / m['hess_filename']
        shutil.copy2(src,dest)
        if digest(src)!=digest(dest):
            raise RuntimeError(f'PDF copy validation failed: {dest}')
        records.append({'manuscript':m['document'],'order':m['order'],'v17':src.name,'hess':dest.name,'sha256':digest(dest)})
    for name in sorted(expected_t):
        shutil.copy2(src_tabs / name, dest_t / name)
        if digest(src_tabs / name)!=digest(dest_t / name):
            raise RuntimeError(f'Table copy validation failed: {name}')
    if {p.name for p in dest_f.iterdir()} != {m['hess_filename'] for m in figs}:
        raise RuntimeError('HESS final figure set mismatch')
    if {p.name for p in dest_t.iterdir()} != expected_t:
        raise RuntimeError('HESS final table set mismatch')
    (output_root / 'HESS_ASSET_MANIFEST.json').write_text(json.dumps({'figure_count':35,'table_count':34,'figures':records},indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(f'HESS_EXPORT_PASS=TRUE; figures=35; tables=34; out={output_root}')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--v17-root',type=Path,required=True,help='Existing results/CAMELS_V17_FINAL folder')
    ap.add_argument('--outdir',type=Path,help='New empty folder; contains figures/, tables/ and manifest')
    ap.add_argument('--check-only',action='store_true')
    a=ap.parse_args()
    if not a.check_only and not a.outdir:
        ap.error('--outdir required unless --check-only')
    export(a.v17_root.resolve(),a.outdir.resolve() if a.outdir else Path('.'),a.check_only)

if __name__=='__main__':
    main()
