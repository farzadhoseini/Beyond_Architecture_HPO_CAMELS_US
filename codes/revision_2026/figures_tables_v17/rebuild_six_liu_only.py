"""Produce exactly six display-label-only figures, preserving frozen analysis keys.
Run next to revision_results_figures_v17.py; never overwrites final V17 results.
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
import revision_results_figures_v17 as r

OUT_NAME={
    'fig_results_paired_nse_references.pdf':'fig04_results_paired_nse_references.pdf',
    'fig_results_threshold_coverage.pdf':'fig07_results_threshold_coverage.pdf',
    'fig_results_hess_metric_tradeoff.pdf':'fig16_results_hess_metric_tradeoff.pdf',
    'fig_results_hess_architecture_context.pdf':'fig17_results_hess_architecture_context.pdf',
    'fig_results_spatial_delta_hess.pdf':'fig_supp17_results_spatial_delta_hess.pdf',
    'fig_supp_hess_cluster_metric_heatmap.pdf':'fig_supp18_hess_cluster_metric_heatmap.pdf',
}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--outdir',type=Path,required=True)
    args=parser.parse_args()
    target=args.outdir.resolve()
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f'Refusing to overwrite a nonempty directory: {target}')
    target.mkdir(parents=True,exist_ok=True)
    internal=target/'_internal_names'
    internal.mkdir()
    r.apply_style()
    base=Path(__file__).resolve().parent
    frozen,preliu=r.resolve_revision_inputs(base/'revision_data')
    for fn in [r.figure_paired_nse,r.figure_threshold_coverage,r.figure_hess_tradeoff,r.figure_hess_architecture_context,r.figure_spatial_delta_hess]:
        print('REBUILD',fn.__name__,flush=True)
        fn(frozen,internal)
    print('REBUILD figure_hess_cluster_metric_context',flush=True)
    r.figure_hess_cluster_metric_context(frozen,internal,target/'_internal_derived_tables')
    manifest=[]
    for src_name,public_name in OUT_NAME.items():
        src=internal/src_name
        if not src.is_file(): raise FileNotFoundError(str(src))
        dest=target/public_name
        shutil.copy2(src,dest)
        manifest.append(dict(name=public_name,original_v17_name=src_name,bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
    (target/'SIX_FIGURES_SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('SIX_LIU_ONLY_PASS: 6 PDF',target)
if __name__ == '__main__': main()
