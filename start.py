"""Start GoTrain with one command.

On the canonical SageMaker workspace this launches the connected service through
the verified virtual environment. Everywhere else it opens the UI-only preview.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import webbrowser


ROOT = Path(__file__).resolve().parent
SAGEMAKER_PYTHON = Path('/home/sagemaker-user/gotrain-access-check/venv/bin/python')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='force the offline UI preview')
    parser.add_argument('--port', type=int, help='override 8766 (connected) or 5173 (preview)')
    args = parser.parse_args()

    connected = SAGEMAKER_PYTHON.exists() and not args.preview
    port = args.port or (8766 if connected else 5173)
    if not 1024 <= port <= 65535:
        parser.error('Use an unprivileged port')

    if connected:
        print(f'GoTrain connected service: http://127.0.0.1:{port}')
        print('Open it through the existing authenticated SageMaker proxy tab.')
        os.execv(str(SAGEMAKER_PYTHON), [str(SAGEMAKER_PYTHON),
                 str(ROOT / 'scripts' / 'serve.py'), '--port', str(port)])

    node = shutil.which('node')
    if node is None:
        raise SystemExit('The offline preview needs Node.js 18 or later.')
    if port != 5173:
        raise SystemExit('The lightweight preview currently uses port 5173.')
    print('GoTrain design preview: http://localhost:5173')
    print('Preview only: messages, uploads and training are disabled.')
    webbrowser.open('http://localhost:5173')
    raise SystemExit(subprocess.call([node, str(ROOT / 'ui' / 'server.mjs')], cwd=ROOT))


if __name__ == '__main__':
    main()
