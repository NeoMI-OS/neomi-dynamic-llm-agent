"""
Pipeline konfiguráció betöltő és validáló modul.
YAML alapú kísérlet konfigurációkat kezel.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from typing import Optional

EXPERIMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "experiments")

REQUIRED_NODES = {"context_analyst", "needs_analyzer", "curriculum_designer", "content_writer", "critic"}


def _experiments_dir() -> str:
    """Visszaadja a kísérletek könyvtárának elérési útját."""
    return EXPERIMENTS_DIR


def load_experiment(experiment_id: str) -> dict:
    """
    Betölt egy YAML kísérlet konfigurációt az experiment ID alapján.

    Args:
        experiment_id: A kísérlet azonosítója (pl. "exp-001")

    Returns:
        A kísérlet konfigurációs dict-je

    Raises:
        FileNotFoundError: Ha a konfiguráció nem található
        ValueError: Ha a konfiguráció érvénytelen
    """
    exp_dir = _experiments_dir()

    # Keresés az összes YAML fájlban
    matched_file = None
    for filename in os.listdir(exp_dir):
        if not filename.endswith(".yaml") and not filename.endswith(".yml"):
            continue
        filepath = os.path.join(exp_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if config and config.get("experiment", {}).get("id") == experiment_id:
                matched_file = filepath
                break
        except Exception:
            continue

    if matched_file is None:
        raise FileNotFoundError(f"Kísérlet nem található: '{experiment_id}'")

    with open(matched_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    _validate_experiment(config)
    return config


def list_experiments() -> list[dict]:
    """
    Visszaadja az összes elérhető kísérlet metaadatait.

    Returns:
        Lista dict-ekkel, amelyek az experiment metaadatokat tartalmazzák
    """
    exp_dir = _experiments_dir()
    experiments = []

    for filename in sorted(os.listdir(exp_dir)):
        if not filename.endswith(".yaml") and not filename.endswith(".yml"):
            continue
        filepath = os.path.join(exp_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if config and "experiment" in config:
                meta = dict(config["experiment"])
                meta["filename"] = filename
                # Node összefoglaló hozzáadása
                nodes = config.get("nodes", {})
                meta["nodes"] = {
                    node_name: {
                        "model": node_cfg.get("model"),
                        "provider": node_cfg.get("provider"),
                    }
                    for node_name, node_cfg in nodes.items()
                }
                meta["settings"] = config.get("settings", {})
                experiments.append(meta)
        except Exception:
            continue

    return experiments


def get_node_llm(node_config: dict):
    """
    Visszaad egy LangChain LLM példányt a node konfigurációja alapján.

    Args:
        node_config: A node konfigurációs dict-je (model, provider, temperature mezőkkel)

    Returns:
        LangChain chat model példány

    Raises:
        ValueError: Ha ismeretlen provider van megadva
    """
    provider = node_config.get("provider", "openai")
    model = node_config.get("model", "gpt-4o-mini")
    temperature = node_config.get("temperature", 0.5)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    else:
        raise ValueError(f"Ismeretlen provider: '{provider}'")


def _validate_experiment(config: dict) -> None:
    """
    Validálja a kísérlet konfigurációt.

    Raises:
        ValueError: Ha a konfiguráció hiányos vagy érvénytelen
    """
    if "experiment" not in config:
        raise ValueError("Hiányzó 'experiment' szekció a konfigurációból")

    exp = config["experiment"]
    for field in ("id", "name", "description"):
        if not exp.get(field):
            raise ValueError(f"Hiányzó kötelező mező az experiment szekcióban: '{field}'")

    if "nodes" not in config:
        raise ValueError("Hiányzó 'nodes' szekció a konfigurációból")

    nodes = config["nodes"]
    missing_nodes = REQUIRED_NODES - set(nodes.keys())
    if missing_nodes:
        raise ValueError(f"Hiányzó node-ok a konfigurációból: {missing_nodes}")

    for node_name, node_cfg in nodes.items():
        if not node_cfg.get("model"):
            raise ValueError(f"Hiányzó 'model' a node konfigurációban: '{node_name}'")
        if not node_cfg.get("provider"):
            raise ValueError(f"Hiányzó 'provider' a node konfigurációban: '{node_name}'")
