"""Run the thin same-origin service; live mode is restricted to SageMaker."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gotrain.service import main
main()
