"""
Long-form weapon blurbs for Edgerunner flavor model names (inv/info).

Each entry is keyed by the exact ``name`` string from ``WEAPON_FLAVOR_BY_QUALITY``
(see ``world.lore_weapons.edgerunner_weapon_flavor_lore_data.FLAVOR_LONG_LORE_BY_DISPLAY_NAME``).
Lookup normalizes with ``normalize_weapon_label()`` so minor quote/spacing differences still match.
"""
from __future__ import annotations

from typing import Dict, Optional

from world.edgerunner_weapon_flavor import normalize_weapon_label
from .edgerunner_weapon_flavor_lore_data import FLAVOR_LONG_LORE_BY_DISPLAY_NAME

# Normalized name -> lore (built once; duplicate normalized keys would overwrite -- there are none)
_FLAVOR_LONG_LORE_BY_NORM_NAME: Dict[str, str] = {
    normalize_weapon_label(name): text for name, text in FLAVOR_LONG_LORE_BY_DISPLAY_NAME.items()
}

if len(_FLAVOR_LONG_LORE_BY_NORM_NAME) != len(FLAVOR_LONG_LORE_BY_DISPLAY_NAME):
    raise ValueError(
        "Weapon lore: two display names normalize the same way; fix FLAVOR_LONG_LORE_BY_DISPLAY_NAME"
    )


def get_flavor_long_description(display_name: str) -> Optional[str]:
    """Return the long lore blurb for this flavor model name, if known."""
    key = normalize_weapon_label(display_name or "")
    if not key:
        return None
    return _FLAVOR_LONG_LORE_BY_NORM_NAME.get(key)
