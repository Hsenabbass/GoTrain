"""Operator-only import for prepared large ZIPs already inside data/imports/."""
import argparse
from pathlib import Path
import sys
import json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def main():
    from gotrain.requests import Requests, read_json
    from gotrain.service import validate_on_sagemaker
    if ROOT!=Path('/home/sagemaker-user/GoTrain'):
        raise RuntimeError('Use the canonical SageMaker workspace')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    args=parser.parse_args()
    source=args.archive.resolve()
    if not source.is_relative_to((ROOT/'data/imports').resolve()) or source.suffix.lower()!='.zip' or args.archive.is_symlink():
        parser.error('Use a prepared ZIP under the approved data/imports directory')
    caps=read_json(ROOT/'configs/service.json')
    caps={**caps,'upload_bytes':2*2**30,'import_seconds':600}
    store=Requests(ROOT/'artifacts/service',caps,{},validator=validate_on_sagemaker)
    print(json.dumps(store.import_zip(source),indent=2))


if __name__=='__main__': main()
