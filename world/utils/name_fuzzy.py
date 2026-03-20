"""
Fuzzy resolution of user input against a fixed pool of display names (inventory, catalog).
Uses case-insensitive exact match, unique prefix/substring, then difflib close matches.
"""
from __future__ import annotations

from difflib import get_close_matches
from typing import List, Optional, Tuple, TypeVar

T = TypeVar("T")


def pick_named_candidate(
    query: str,
    candidates: List[Tuple[str, T]],
    *,
    cutoff: float = 0.55,
) -> Tuple[Optional[T], Optional[str]]:
    """
    Match ``query`` to one of ``(display_name, payload)`` pairs.

    Returns:
        (payload, None) on success,
        (None, error_message) on failure or ambiguity.
    """
    q = (query or "").strip().lower()
    if not q:
        return None, "No name given."
    if not candidates:
        return None, "Nothing to match."

    lowered = [(str(name or ""), payload) for name, payload in candidates]

    # 1) Case-insensitive exact
    for name, payload in lowered:
        if name.lower() == q:
            return payload, None

    # 2) Unique prefix
    pref = [(n, p) for n, p in lowered if n.lower().startswith(q)]
    if len(pref) == 1:
        return pref[0][1], None
    if len(pref) > 1:
        names = [x[0] for x in pref[:10]]
        more = f" (+{len(pref) - 10} more)" if len(pref) > 10 else ""
        return None, f"Multiple items start with '{query}': {', '.join(names)}{more}."

    # 3) Unique substring
    subs = [(n, p) for n, p in lowered if q in n.lower()]
    if len(subs) == 1:
        return subs[0][1], None
    if len(subs) > 1:
        names = [x[0] for x in subs[:10]]
        more = f" (+{len(subs) - 10} more)" if len(subs) > 10 else ""
        return None, f"Multiple items contain '{query}': {', '.join(names)}{more}."

    # 4) Close string matches (typo tolerance)
    pool_keys = [n.lower() for n, _ in lowered]
    close = get_close_matches(q, pool_keys, n=5, cutoff=cutoff)
    if len(close) == 1:
        idx = pool_keys.index(close[0])
        return lowered[idx][1], None
    if len(close) > 1:
        originals = []
        for c in close:
            idx = pool_keys.index(c)
            originals.append(lowered[idx][0])
        return None, f"Which did you mean? {', '.join(originals)}"

    return None, None
