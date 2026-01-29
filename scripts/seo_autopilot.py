#!/usr/bin/env python3
"""
SEO Autopilot

Goal:
- Automatically keep data/seo_goal_enrichment.json "good enough" for new goals/ingredients.
- Then run scripts/seo_enrich_goals.py --write to push keywords into data/goals.json.

Usage:
  python3 scripts/seo_autopilot.py
  python3 scripts/seo_autopilot.py --write
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Ensure project root is on sys.path so `import utils.*` works when running from scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ENRICH_PATH = Path("data/seo_goal_enrichment.json")

# Heuristic: cluster -> candidate ingredient slugs (only use ones that exist as ingredient pages)
CLUSTER_INGREDIENTS = {
    "metabolic_balance": ["banana", "chia-seed", "peanut-butter", "strawberry", "blueberries", "avocado", "spinach", "kale"],
    "anti_inflammation": ["blueberries", "strawberry", "spinach", "kale", "chia-seed", "avocado"],
    "heart_support": ["avocado", "spinach", "kale", "blueberries", "banana", "chia-seed"],
}

# Heuristic: goal text -> clusters to attach
# This is intentionally simple. It will cover 80% and you can adjust over time.
CLUSTER_TRIGGERS = {
    "heart_support": [
        "heart", "cholesterol", "blood pressure", "circulation", "vascular", "bp",
    ],
    "anti_inflammation": [
        "inflammation", "immune", "joint", "mobility", "stress", "skin", "glow", "liver",
        "thyroid", "vision", "brain", "oral", "antioxidant",
    ],
    "metabolic_balance": [
        "blood sugar", "glycemic", "weight", "balance", "energy", "stamina",
        "digest", "gut", "metabolic", "fiber", "protein", "recovery",
    ],
}

# Heuristic: ingredient names/synonyms -> ingredient slug
ING_SYNONYMS = {
    "chia seed": "chia-seed",
    "chia": "chia-seed",
    "peanut butter": "peanut-butter",
    "blueberry": "blueberries",
    "strawberries": "strawberry",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def ensure_goal_map_shape(g: dict) -> dict:
    g.setdefault("clusters", [])
    g.setdefault("ingredients", [])
    g.setdefault("add_primary", [])
    g.setdefault("add_related", [])
    # Keep types stable
    for k in ["clusters", "ingredients", "add_primary", "add_related"]:
        if not isinstance(g.get(k), list):
            g[k] = []
    return g


def unique_extend(lst: List[str], items: List[str]) -> int:
    before = len(lst)
    seen = set(lst)
    for x in items:
        if x and x not in seen:
            lst.append(x)
            seen.add(x)
    return len(lst) - before


def pick_clusters(goal_name: str, goal_slug: str, keywords: List[str]) -> List[str]:
    hay = " | ".join([goal_name, goal_slug] + keywords)
    hay = normalize_text(hay)

    picked: List[str] = []
    for cluster, triggers in CLUSTER_TRIGGERS.items():
        for t in triggers:
            if t in hay:
                picked.append(cluster)
                break

    # fallback: always at least metabolic_balance (safe default for smoothie SEO)
    if not picked:
        picked = ["metabolic_balance"]

    # stable order (no randomness)
    order = ["heart_support", "anti_inflammation", "metabolic_balance"]
    picked_sorted = [c for c in order if c in set(picked)]
    return picked_sorted


def pick_ingredients_from_text(text: str, existing_ingredient_slugs: Set[str]) -> List[str]:
    t = normalize_text(text)
    hits: List[str] = []

    # direct slug mentions
    for slug in sorted(existing_ingredient_slugs):
        if slug.replace("-", " ") in t:
            hits.append(slug)

    # synonyms
    for k, slug in ING_SYNONYMS.items():
        if k in t and slug in existing_ingredient_slugs:
            hits.append(slug)

    # unique, keep order
    out: List[str] = []
    seen: Set[str] = set()
    for x in hits:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def pick_ingredients_from_clusters(clusters: List[str], existing_ingredient_slugs: Set[str], limit: int = 8) -> List[str]:
    out: List[str] = []
    for c in clusters:
        for slug in CLUSTER_INGREDIENTS.get(c, []):
            if slug in existing_ingredient_slugs and slug not in out:
                out.append(slug)
            if len(out) >= limit:
                return out
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write changes + run seo_enrich_goals.py --write")
    ap.add_argument("--limit", type=int, default=0, help="optional: limit how many goals to update (0 = no limit)")
    args = ap.parse_args()

    if not ENRICH_PATH.exists():
        print(f"ERROR: missing {ENRICH_PATH}")
        return 2

    # Import registries from your app utils (same pattern you already use)
    from utils.seo_registry import get_goals_registry, get_ingredients_registry  # noqa

    goals_reg = get_goals_registry()
    ingredients_reg = get_ingredients_registry()

    existing_ing_slugs: Set[str] = set()
    for ing in ingredients_reg.get("ingredients", []):
        slug = ing.get("slug")
        if slug:
            existing_ing_slugs.add(slug)

    cfg = load_json(ENRICH_PATH)
    cfg.setdefault("version", 1)
    cfg.setdefault("defaults", {"ingredient_bucket": "related", "max_primary": 12, "max_related": 18})
    cfg.setdefault("clusters", {})
    cfg.setdefault("goal_map", {})

    goal_map: Dict[str, dict] = cfg["goal_map"]

    touched = 0
    report: List[Tuple[str, dict]] = []

    # Iterate all goals and ensure they have a mapping entry
    for g in goals_reg.get("goals", []):
        slug = g.get("slug")
        if not slug:
            continue

        gm = ensure_goal_map_shape(goal_map.get(slug, {}))
        before = json.dumps(gm, sort_keys=True)

        # Collect keywords from the goal registry entry
        kws: List[str] = []
        kw_obj = g.get("keywords") or {}
        kws += (kw_obj.get("primary") or [])
        kws += (kw_obj.get("related") or [])
        kws = [normalize_text(x) for x in kws if isinstance(x, str)]

        name = g.get("name") or ""
        # Clusters
        clusters = pick_clusters(name, slug, kws)
        unique_extend(gm["clusters"], clusters)

        # Ingredients:
        # 1) from text keywords/name/slug
        text_blob = " | ".join([name, slug] + kws)
        ing_from_text = pick_ingredients_from_text(text_blob, existing_ing_slugs)

        # 2) from cluster candidates
        ing_from_clusters = pick_ingredients_from_clusters(gm["clusters"], existing_ing_slugs, limit=8)

        # Merge
        unique_extend(gm["ingredients"], ing_from_text)
        unique_extend(gm["ingredients"], ing_from_clusters)

        # Add_related: mild, safe SEO phrases that do not create medical claims
        # Keep it conservative.
        safe_phrases = []
        if "metabolic_balance" in gm["clusters"]:
            safe_phrases += ["balanced smoothie", "fiber and protein smoothie"]
        if "anti_inflammation" in gm["clusters"]:
            safe_phrases += ["anti inflammatory smoothie", "antioxidant smoothie"]
        if "heart_support" in gm["clusters"]:
            safe_phrases += ["heart healthy smoothie", "cholesterol support smoothie"]
        unique_extend(gm["add_related"], safe_phrases)

        after = json.dumps(gm, sort_keys=True)
        if after != before:
            goal_map[slug] = gm
            touched += 1
            report.append((slug, gm))
            if args.limit and touched >= args.limit:
                break

    if touched == 0:
        print("No changes proposed.")
        return 0

    print(f"Autopilot proposed changes for {touched} goal(s):")
    for slug, gm in report[:30]:
        print(f"- {slug}: clusters={gm.get('clusters', [])} ingredients={gm.get('ingredients', [])}")

    if not args.write:
        print("\nDRY RUN only. Re-run with --write to apply + enrich goals.json.")
        return 0

    save_json(ENRICH_PATH, cfg)
    print(f"\nWROTE: {ENRICH_PATH}")

    # Run your existing script to push into data/goals.json
    cmd = [sys.executable, "scripts/seo_enrich_goals.py", "--write"]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)

    print("DONE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
