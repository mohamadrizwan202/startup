from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _norm_kw(s: Any) -> str:
    if not s:
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"[\s_]+", " ", s)
    return s


def _slugify_kw(s: str) -> str:
    s = _norm_kw(s)
    if not s:
        return ""
    s = s.replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _tokens(s: Any) -> List[str]:
    if not s:
        return []
    return _WORD_RE.findall(str(s).lower())


def _goal_keywords(goal: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    kw = goal.get("keywords") or {}
    if not isinstance(kw, dict):
        kw = {}
    primary = kw.get("primary") or []
    related = kw.get("related") or []
    if not isinstance(primary, list):
        primary = []
    if not isinstance(related, list):
        related = []
    primary_n = [_norm_kw(x) for x in primary if _norm_kw(x)]
    related_n = [_norm_kw(x) for x in related if _norm_kw(x)]
    return primary_n, related_n


def compute_related_goals(
    current_slug: str,
    goals_registry: Dict[str, Any],
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Related goals ranked by keyword overlap:
      +3 per shared PRIMARY keyword (primary ∩ primary)
      +1 per shared RELATED keyword (related ∩ related)
    Returns only results with score > 0 (no fake links).
    Tie-break: name, then slug.
    """
    goals = goals_registry.get("goals") or []
    if not isinstance(goals, list):
        return []

    current = None
    for g in goals:
        if isinstance(g, dict) and g.get("slug") == current_slug:
            current = g
            break
    if not current:
        return []

    cur_primary, cur_related = _goal_keywords(current)
    cur_primary_set = set(cur_primary)
    cur_related_set = set(cur_related)

    scored: List[Tuple[int, str, str, Dict[str, Any]]] = []
    for g in goals:
        if not isinstance(g, dict):
            continue
        slug = g.get("slug")
        if not slug or slug == current_slug:
            continue

        other_primary, other_related = _goal_keywords(g)
        p_overlap = cur_primary_set.intersection(other_primary)
        r_overlap = cur_related_set.intersection(other_related)

        score = (3 * len(p_overlap)) + (1 * len(r_overlap))
        if score <= 0:
            continue

        name = (g.get("name") or slug.replace("-", " ").title()).strip()
        scored.append((score, name.lower(), slug, g))

    scored.sort(key=lambda t: (-t[0], t[1], t[2]))

    out: List[Dict[str, Any]] = []
    for score, _name_l, slug, g in scored[: max(0, int(limit))]:
        name = (g.get("name") or slug.replace("-", " ").title()).strip()
        out.append(
            {
                "slug": slug,
                "name": name,
                "summary": (g.get("summary") or "").strip(),
                "score": score,
            }
        )
    return out


def compute_related_ingredients(
    goal: Dict[str, Any],
    ingredients_registry: Dict[str, Any],
    limit: int = 12,
) -> List[Dict[str, Any]]:
    """
    Suggested ingredients derived from goal keywords:
    - Direct slug match: keyword -> slugified -> ingredients_registry key
    - Token subset match against ingredient slug + common name fields
    Scoring:
      +3 for primary keyword match
      +1 for related keyword match
    """
    if not isinstance(ingredients_registry, dict) or not ingredients_registry:
        return []

    primary, related = _goal_keywords(goal)

    ing_tokens: Dict[str, set] = {}
    ing_display: Dict[str, str] = {}
    for slug, obj in ingredients_registry.items():
        if not slug:
            continue
        if not isinstance(obj, dict):
            obj = {}
        display = (
            obj.get("display_name")
            or obj.get("name")
            or obj.get("ingredient")
            or slug.replace("-", " ").title()
        )
        ing_display[slug] = str(display).strip()
        blob = " ".join(
            [
                slug,
                str(obj.get("display_name") or ""),
                str(obj.get("name") or ""),
                str(obj.get("ingredient") or ""),
            ]
        )
        ing_tokens[slug] = set(_tokens(blob))

    scores: Dict[str, int] = {}

    def add_score(slug: str, pts: int):
        if slug in ingredients_registry:
            scores[slug] = scores.get(slug, 0) + pts

    def match_keyword(kw: str, pts: int):
        slug_cand = _slugify_kw(kw)
        if slug_cand and slug_cand in ingredients_registry:
            add_score(slug_cand, pts)
            return

        toks = [t for t in _tokens(kw) if len(t) >= 3]
        if not toks:
            return
        toks_set = set(toks)

        for slug, tset in ing_tokens.items():
            if toks_set.issubset(tset):
                add_score(slug, pts)

    for kw in primary:
        match_keyword(kw, 3)
    for kw in related:
        match_keyword(kw, 1)

    ranked = sorted(
        scores.items(),
        key=lambda kv: (-kv[1], ing_display.get(kv[0], kv[0]).lower(), kv[0]),
    )

    out: List[Dict[str, Any]] = []
    for slug, score in ranked[: max(0, int(limit))]:
        out.append(
            {
                "slug": slug,
                "name": ing_display.get(slug, slug.replace("-", " ").title()),
                "score": score,
            }
        )
    return out
