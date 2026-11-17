import os
import sys
from pathlib import Path

# Las pruebas controlan el estado del esquema; desactiva la creación automática en segundo plano.
os.environ["LAB_AUTO_SEED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
