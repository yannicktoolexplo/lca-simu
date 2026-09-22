"""Compatibility entrypoint; implementation lives in visualization.maps.journey_scenario_delivery."""
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from etudecas.visualization.maps.journey_scenario_delivery import build_scenario_explorer, main  # noqa: F401,E402

if __name__ == "__main__":
    main()
