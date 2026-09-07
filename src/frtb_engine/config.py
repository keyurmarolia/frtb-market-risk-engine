"""Small, explicit helpers for reading project configuration."""

from pathlib import Path
import os
from typing import Any, Dict

import yaml


PROJECT_ROOT = Path(os.environ.get("FRTB_PROJECT_ROOT", Path(__file__).resolve().parents[2])).resolve()


def load_yaml(relative_path: str) -> Dict[str, Any]:
    """Read a YAML file relative to the project root."""
    path = PROJECT_ROOT / relative_path
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {relative_path}")
    return data


def load_project_config() -> Dict[str, Any]:
    return load_yaml("config/project.yaml")


def load_model_conventions() -> Dict[str, Any]:
    return load_yaml("config/model_conventions.yaml")


def load_regulatory_manifest() -> Dict[str, Any]:
    config = load_project_config()
    return load_yaml(config["provenance"]["regulatory_manifest"])


def load_market_data() -> Dict[str, Any]:
    return load_yaml("data/synthetic/market_data.yaml")


def load_sbm_parameters() -> Dict[str, Any]:
    return load_yaml("config/regulatory/basel_2026_08_25/sbm_parameters.yaml")


def load_drc_parameters() -> Dict[str, Any]:
    return load_yaml("config/regulatory/basel_2026_08_25/drc_parameters.yaml")


def load_rrao_parameters() -> Dict[str, Any]:
    return load_yaml("config/regulatory/basel_2026_08_25/rrao_parameters.yaml")


def load_ima_parameters() -> Dict[str, Any]:
    return load_yaml("config/regulatory/basel_2026_08_25/ima_parameters.yaml")


def load_synthetic_assumptions() -> Dict[str, Any]:
    return load_yaml("config/synthetic_assumptions.yaml")
