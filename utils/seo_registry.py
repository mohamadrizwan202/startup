from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from flask import current_app, has_app_context


def _log_error(msg: str, *args):
    if has_app_context():
        current_app.logger.error(msg, *args)
    else:
        print("ERROR:", msg % args)


def _log_exception(msg: str, *args):
    if has_app_context():
        current_app.logger.exception(msg, *args)
    else:
        print("EXCEPTION:", msg % args)


def _base_root() -> Path:
    if has_app_context():
        return Path(current_app.root_path)
    return Path(__file__).resolve().parents[1]


def _data_path(filename: str) -> Path:
    return _base_root() / "data" / filename


@lru_cache(maxsize=32)
def _load_json_cached(abs_path: str, mtime: float) -> Any:
    with open(abs_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_registry(filename: str) -> Any:
    path = _data_path(filename)

    try:
        stat = path.stat()
    except FileNotFoundError:
        _log_error(
            "SEO registry missing: path=%s | cwd=%s | base_root=%s",
            str(path),
            os.getcwd(),
            str(_base_root()),
        )
        raise

    try:
        return _load_json_cached(str(path), stat.st_mtime)
    except Exception:
        _log_exception(
            "SEO registry failed to load/parse: path=%s | size=%s bytes",
            str(path),
            stat.st_size,
        )
        raise


def get_goals_registry() -> Dict[str, Any]:
    data = load_json_registry("goals.json")
    if not isinstance(data, dict) or "goals" not in data or not isinstance(data["goals"], list):
        raise ValueError("goals.json must be an object with a list field 'goals'")
    return data


def get_goal_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    reg = get_goals_registry()
    for g in reg["goals"]:
        if isinstance(g, dict) and g.get("slug") == slug:
            g.setdefault("keywords", {})
            if not isinstance(g["keywords"], dict):
                g["keywords"] = {}
            g["keywords"].setdefault("primary", [])
            g["keywords"].setdefault("related", [])
            return g
    return None


def get_ingredients_registry() -> Dict[str, Any]:
    data = load_json_registry("ingredients.json")
    if not isinstance(data, dict):
        raise ValueError("ingredients.json must be an object keyed by slug")
    return data
