"""Create or repair the project environment and its Jupyter kernel."""

import os
import json
import subprocess
import sys
import venv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = PROJECT_ROOT / ".frtb_sa_env"


def environment_python() -> Path:
    return ENVIRONMENT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> None:
    if not environment_python().exists():
        if sys.version_info < (3, 11):
            raise RuntimeError("Python 3.11 or newer is required to create the environment.")
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)

    marker = ENVIRONMENT / "project-location.json"
    identity = {"root": str(PROJECT_ROOT), "dependencies": (PROJECT_ROOT / "pyproject.toml").read_text()}
    if marker.exists() and json.loads(marker.read_text()) == identity:
        return
    subprocess.run([str(environment_python()), "-m", "pip", "install", "-e", f"{PROJECT_ROOT}[dev]"], check=True)

    subprocess.run([str(environment_python()), "-m", "ipykernel", "install", "--user", "--name", "frtb-sa-local", "--display-name", "Python (FRTB Market Risk)"], check=True)
    marker.write_text(json.dumps(identity, indent=2))
    print("Project environment and notebook kernel are ready.")


if __name__ == "__main__":
    main()
