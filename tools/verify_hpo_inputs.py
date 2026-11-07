#!/usr/bin/env python3
"""Read-only verification of inputs for the regional CAMELS-US HPO notebook."""
from __future__ import annotations
import argparse
import csv
import hashlib
from pathlib import Path

def check(condition: bool, description: str, problems: list[str]) -> None:
    print(f"{'PASS' if condition else 'FAIL'} {description}")
    if not condition:
        problems.append(description)

def read_ids(path: Path) -> list[str]:
    rows = list(csv.reader(path.open(encoding='utf-8-sig', newline='')))
    ids = [row[0].strip() for row in rows if row and row[0].strip()]
    if ids and ids[0].lower() in {'gauge_id', 'basin', 'basin_id'}:
        ids = ids[1:]
    return ids

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-root',type=Path,required=True)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--strict',action='store_true',help='Exit 2 if any required input fails validation')
    args=p.parse_args()
    work=args.work_root.resolve(); repo=args.repo.resolve()
    base_yml=work/'configs'/'configRegional_Fred.yml'
    observations=work/'data'/'CAMELS_US'
    basin_file=work/'data'/'531Basins.csv'
    cluster_dir=work/'data'/'camels_attributes_v2.0'/'attributes_cluster_splits'
    metrics=work/'metrics.py'
    canonical_metrics=repo/'codes'/'CAMELS_US_clean_HPO_repro_package'/'metrics.py'
    hpo_notebook=repo/'codes'/'CAMELS_US_clean_HPO_repro_package'/'CAMELS_US_clean_HPO_randomsearch_ensemble_evaluation.ipynb'
    canonical_basin=repo/'531_basin_list.txt'
    problems=[]
    check(base_yml.is_file() and base_yml.stat().st_size>100 if base_yml.is_file() else False,
          f'Base YAML present: {base_yml}',problems)
    check(observations.is_dir() and any(observations.iterdir()) if observations.is_dir() else False,
          f'CAMELS-US data folder nonempty: {observations}',problems)
    check(metrics.is_file() and canonical_metrics.is_file(),f'metrics.py present: {metrics}',problems)
    if metrics.is_file() and canonical_metrics.is_file():
        check(hashlib.sha256(metrics.read_bytes()).hexdigest()==hashlib.sha256(canonical_metrics.read_bytes()).hexdigest(),
              'Workspace metrics.py matches repository source',problems)
    check(hpo_notebook.is_file(),'Regional HPO notebook exists in repository',problems)
    check(canonical_basin.is_file(),'Repository 531-basin reference list present',problems)
    ref=[]
    if canonical_basin.is_file():
        ref=[s.strip() for s in canonical_basin.read_text(encoding='utf8').splitlines() if s.strip()]
        check(len(ref)==531 and len(set(ref))==531,'Repository has exactly 531 unique reference basins',problems)
    check(basin_file.is_file(),f'HPO basin list exists: {basin_file}',problems)
    if basin_file.is_file() and ref:
        ids=read_ids(basin_file)
        check(len(ids)==531 and len(set(ids))==531 and set(ids)==set(ref),
              'Workspace basin set matches all 531 reference IDs',problems)
    all_cluster=[];membership=[]
    for i in range(6):
        f=cluster_dir/f'cluster_{i}.txt'
        check(f.is_file(),f'Cluster split {i} exists: {f}',problems)
        if f.is_file():
            ids=read_ids(f)
            membership.append((i,ids))
            all_cluster.extend(ids)
            check(len(ids)>0 and len(set(ids))==len(ids),f'Cluster {i} has nonempty unique basin IDs',problems)
    if len(membership)==6 and ref:
        check(len(all_cluster)==531 and len(set(all_cluster))==531 and set(all_cluster)==set(ref),
              'Six clusters form a disjoint partition of all 531 basins',problems)
    print('HPO_INPUTS_READY='+str(not problems).upper())
    if problems:print('UNSATISFIED_CHECKS='+str(len(problems)))
    if args.strict and problems:
        raise SystemExit(2)

if __name__=='__main__':
    main()
