#!/usr/bin/env python3
"""Create or verify a fingerprinted archive of the original HPO candidate YAMLs.

Create a manifest ONLY from the original candidate archive, not from regenerated random
samples. A manifest is an input for verifying a reproduction, not proof of provenance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    # End-of-line normalization preserves content under Git checkouts.
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def collect(root: Path) -> dict[str, str]:
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in {'.yaml', '.yml'})
    result = {p.relative_to(root).as_posix(): digest(p) for p in files}
    if len(result) != 2000:
        raise RuntimeError(f'Expected 2000 HPO candidates, found {len(result)} in {root}')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-dir', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create-manifest', type=Path)
    group.add_argument('--verify-manifest', type=Path)
    args = parser.parse_args()
    root = args.candidate_dir.resolve()
    if not root.is_dir():
        parser.error(f'Candidate directory not found: {root}')
    current = collect(root)
    if args.create_manifest:
        dest = args.create_manifest.resolve()
        if dest.exists():
            raise RuntimeError(f'Refusing to overwrite existing manifest: {dest}')
        dest.parent.mkdir(parents=True, exist_ok=True)
        record = {'candidate_count': 2000, 'hash_algorithm': 'sha256-normalized-LF', 'candidates': current}
        dest.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(f'HPO_CANDIDATE_MANIFEST_CREATED={dest}')
        print('PROVENANCE_STATUS=UNVERIFIED; confirm these are the original 2000 candidates')
        return
    record = json.loads(args.verify_manifest.read_text(encoding='utf-8'))
    if record.get('candidate_count') != 2000 or record.get('candidates') != current:
        old = record.get('candidates', {})
        missing = sorted(set(old) - set(current))
        added = sorted(set(current) - set(old))
        changed = sorted(k for k in set(current) & set(old) if current[k] != old[k])
        raise RuntimeError(f'HPO candidate manifest mismatch; missing={missing[:5]} added={added[:5]} changed={changed[:5]}')
    print('HPO_CANDIDATE_MANIFEST_VERIFIED=TRUE')


if __name__ == '__main__':
    main()
