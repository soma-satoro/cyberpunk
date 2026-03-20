"""
Skill chip logic: installed chipware that boosts skills to rating 3.
Chips only apply when natural rating < 3; if natural >= 3, chip has no effect.
"""

from world.inventory.models import Inventory, CyberwareInstance
from world.cyberware.models import Cyberware

# 2x (advanced) skills per CPR - these use Advanced Skill Chips
DOUBLE_COST_SKILLS = frozenset([
    "autofire", "martial_arts", "pilot_air", "heavy_weapons",
    "demolitions", "electronics_security_tech", "paramedic",
])
SKILL_CHIP_BOOST = 3


def get_installed_skill_chip_targets(character):
    """
    Get set of skill_target strings for installed skill chips on this character.
    skill_target format: "education" or "martial_arts(krav maga)" (instance is lowercased; spaces OK)
    """
    targets = set()
    if not character:
        return targets
    try:
        inventory, _ = Inventory.get_or_create_for_character(character)
    except Exception:
        return targets
    installed = CyberwareInstance.objects.filter(
        character_sheet_id=getattr(getattr(character, "character_sheet", None), "pk", None),
        installed=True,
    ) | CyberwareInstance.objects.filter(
        character_object=character,
        installed=True,
    )
    for inst in installed.select_related("cyberware"):
        target = getattr(inst.cyberware, "skill_chip_target", None)
        if target and (target := (target or "").strip()):
            targets.add(target.lower())
    return targets


def get_effective_skill_value(character, skill_key, natural_value):
    """
    Given natural skill value, return effective value (considering skill chips).
    Skill chips set effective to 3 if natural < 3 and chip for that skill is installed.
    skill_key: "education" or "martial_arts(krav maga)" format
    """
    if natural_value is None:
        natural_value = 0
    natural_value = max(0, int(natural_value))
    norm_key = (skill_key or "").strip().lower()
    after_chip = natural_value
    if natural_value < SKILL_CHIP_BOOST:
        targets = get_installed_skill_chip_targets(character)
        if norm_key in targets:
            after_chip = max(natural_value, SKILL_CHIP_BOOST)
    try:
        from world.cyberware.stat_bonuses import get_cyberware_skill_bonus

        return after_chip + get_cyberware_skill_bonus(character, norm_key)
    except ImportError:
        return after_chip
