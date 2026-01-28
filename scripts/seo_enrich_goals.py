from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def norm_kw(s: Any) -> str:
    if not s:
        return ""
    s = str(s).strip().lower()
    s = " ".join(s.split())
    return s


def slug_to_phrase(slug: str) -> str:
    return norm_kw(slug.replace("-", " "))


def uniq_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        x = norm_kw(x)
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def remove_cross_dupes(primary: List[str], related: List[str]) -> Tuple[List[str], List[str]]:
    pset = set(primary)
    related2 = [x for x in related if x not in pset]
    return primary, related2


def clamp(items: List[str], max_n: int) -> List[str]:
    if max_n <= 0:
        return items
    return items[:max_n]


def ensure_keywords(goal: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    kw = goal.get("keywords") or {}
    if not isinstance(kw, dict):
        kw = {}
    primary = kw.get("primary") or []
    related = kw.get("related") or []
    if not isinstance(primary, list):
        primary = []
    if not isinstance(related, list):
        related = []
    return uniq_keep_order(primary), uniq_keep_order(related)


def write_keywords(goal: Dict[str, Any], primary: List[str], related: List[str]) -> None:
    goal["keywords"] = {"primary": primary, "related": related}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="data/seo_goal_enrichment.json")
    ap.add_argument("--goals", default="data/goals.json")
    ap.add_argument("--ingredients", default="data/ingredients.json")
    ap.add_argument("--write", action="store_true", help="Apply changes to goals.json")
    args = ap.parse_args()

    config_path = Path(args.config)
    goals_path = Path(args.goals)
    ing_path = Path(args.ingredients)

    cfg = load_json(config_path)
    goals_doc = load_json(goals_path)
    ing_doc = load_json(ing_path)

    if not isinstance(goals_doc, dict) or "goals" not in goals_doc:
        raise SystemExit("goals.json must be an object with key 'goals' (list).")
    if not isinstance(ing_doc, dict):
        raise SystemExit("ingredients.json must be a dict keyed by ingredient slug.")

    clusters = cfg.get("clusters") or {}
    goal_map = cfg.get("goal_map") or {}
    defaults = cfg.get("defaults") or {}

    ingredient_bucket = defaults.get("ingredient_bucket", "related")
    max_primary = int(defaults.get("max_primary", 12))
    max_related = int(defaults.get("max_related", 18))

    ing_slugs = set(ing_doc.keys())

    changed = 0
    report_lines: List[str] = []

    for g in goals_doc.get("goals", []):
        if not isinstance(g, dict):
            continue
        slug = g.get("slug")
        if not slug or slug not in goal_map:
            continue

        spec = goal_map.get(slug) or {}
        cur_primary, cur_related = ensure_keywords(g)

        add_primary = uniq_keep_order(spec.get("add_primary") or [])
        add_related = uniq_keep_order(spec.get("add_related") or [])

        # cluster keywords -> related bucket by default
        for cname in spec.get("clusters") or []:
            kws = clusters.get(cname) or []
            add_related.extend(kws)

        add_related = uniq_keep_order(add_related)

        # ingredient slugs -> phrase keywords
        added_ingredients: List[str] = []
        for ing_slug in spec.get("ingredients") or []:
            ing_slug = str(ing_slug).strip()
            if ing_slug not in ing_slugs:
                report_lines.append(f"[WARN] {slug}: ingredient slug not found in ingredients.json: {ing_slug}")
                continue
            added_ingredients.append(slug_to_phrase(ing_slug))

        # Merge
        new_primary = uniq_keep_order(cur_primary + add_primary)
        if ingredient_bucket == "primary":
            new_primary = uniq_keep_order(new_primary + added_ingredients)
            new_related = uniq_keep_order(cur_related + add_related)
        else:
            new_related = uniq_keep_order(cur_related + add_related + added_ingredients)

        new_primary, new_related = remove_cross_dupes(new_primary, new_related)

        new_primary = clamp(new_primary, max_primary)
        new_related = clamp(new_related, max_related)

        if new_primary != cur_primary or new_related != cur_related:
            changed += 1
            report_lines.append(f"[CHANGE] {slug}")
            report_lines.append(f"  primary +{[x for x in new_primary if x not in cur_primary]}")
            report_lines.append(f"  related +{[x for x in new_related if x not in cur_related]}")

        write_keywords(g, new_primary, new_related)

    if not report_lines:
        print("No changes proposed.")
    else:
        print("\n".join(report_lines))
        print(f"\nGoals touched: {changed}")

    if args.write and changed > 0:
        goals_path.write_text(json.dumps(goals_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nWROTE: {goals_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
