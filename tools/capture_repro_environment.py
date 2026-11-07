#!/usr/bin/env python3
"""Record the independent reproduction environment and its package versions."""
from __future__ import annotations
import argparse
import datetime
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

PACKAGES = ('neuralhydrology','torch','numpy','pandas','xarray','scipy','scikit-learn','matplotlib','pyyaml','jupyter','geopandas','cartopy')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result={'collected_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'python':sys.version,'platform':platform.platform(),'packages':{}}
    for package in PACKAGES:
        try:result['packages'][package]=metadata.version(package)
        except metadata.PackageNotFoundError:result['packages'][package]=None
    try:
        import torch
        result['torch_cuda_version']=torch.version.cuda
        result['cuda_available']=torch.cuda.is_available()
        if torch.cuda.is_available():result['gpu_names']=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    except (ImportError,RuntimeError):pass
    dest=a.output.resolve()
    if dest.exists():raise RuntimeError(f'Output already exists: {dest}')
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(f'ENVIRONMENT_CAPTURED={dest}')
    print('This records the current environment; it does not establish the original training versions.')
if __name__=='__main__':main()
