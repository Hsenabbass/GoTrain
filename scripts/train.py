"""Manual train/verify entry point; all ML execution belongs on SageMaker."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gotrain.training import main

if __name__ == '__main__':
    main()
