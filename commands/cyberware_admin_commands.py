"""
Admin commands for cyberware management.
"""
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberware.models import Cyberware
from world.inventory.models import CyberwareInstance, Inventory
from world.cyberpunk_sheets.edgerunner import EdgerunnerChargen


def _cyberware_allows_multiple_installed_instances(cyberware: Cyberware) -> bool:
    """
    True for limb/option gear that can be installed more than once (different parents),
    e.g. Extra-Jointed on each cyberarm. Paired bases (Cybereye, Cyberarm) still use /pair.
    """
    ctype = (cyberware.type or "").strip()
    if ctype in ("Cyberlimb", "Cyberarm Option", "Cyberleg Option"):
        return True
    desc = (cyberware.description or "").strip().lower()
    if desc.startswith(
        ("cyberlimb option.", "cyberarm option.", "cyberleg option.")
    ):
        return True
    name = (cyberware.name or "").strip().lower()
    return name in {
        "hardened shielding",
        "plastic covering",
        "realskinn covering",
        "superchrome covering",
        "gorilla arm",
        "mantis blade",
        "reinforced cyberlimb upgrade",
        "extra-jointed cyberlimb upgrade",
        "hardened cybereye casing",
        "standard hand",
        "standard foot",
        "modular finger cyberhand",
    }


class CmdAddCyberware(MuxCommand):
    """
    Add cyberware to a character (staff only).

    Usage:
      addcyberware <cyberware item>=<character name>
      addcyberware/pair <cyberware item>=<character name>

    Examples:
      addcyberware Sandevistan=Soma
      addcyberware/pair Cybereye=Soma

    Adds the specified cyberware to the character's inventory, installed.
    With /pair: adds a second Cybereye/Cyberarm/Cyberleg and pairs it to the existing one.
    Cyberware must exist in the database (run populate_cyberware if needed).
    """

    key = "addcyberware"
    switches = [("pair", "pair")]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: addcyberware <cyberware item>=<character name>")
            return

        cyberware_name = self.lhs.strip().strip('"')
        character_name = self.rhs.strip().strip('"')

        if not cyberware_name or not character_name:
            self.caller.msg("Usage: addcyberware <cyberware item>=<character name>")
            return

        # Find the cyberware
        try:
            cyberware = Cyberware.objects.get(name__iexact=cyberware_name)
        except Cyberware.DoesNotExist:
            self.caller.msg(
                f"Cyberware '{cyberware_name}' not found in database. "
                "Run 'populate_cyberware' to load cyberware from the data files."
            )
            return

        # Find the character
        character = self.caller.search(character_name, typeclass="typeclasses.characters.Character", global_search=True)
        if not character:
            character = self.caller.search(character_name, global_search=True)
        if not character:
            return

        # Get character sheet (required for inventory/humanity)
        char_sheet = getattr(character, "character_sheet", None)
        if not char_sheet:
            self.caller.msg(f"{character.key} does not have a character sheet.")
            return

        # Get or create inventory
        inventory, _ = Inventory.get_or_create_for_character(character)

        use_pair = "pair" in (self.switches or [])

        if use_pair:
            # Find existing installed instance to pair with
            first_instance = inventory.cyberware.filter(
                cyberware__name__iexact=cyberware_name,
                installed=True,
                paired_with__isnull=True,
            ).first()
            if not first_instance:
                self.caller.msg(
                    f"{character.key} does not have an unpaired {cyberware.name} to pair with. "
                    "Add the first one with addcyberware (without /pair)."
                )
                return
            # Check they don't already have a paired second
            if inventory.cyberware.filter(
                cyberware__name__iexact=cyberware_name,
                installed=True,
                paired_with=first_instance,
            ).exists():
                self.caller.msg(f"{character.key} already has a paired {cyberware.name}.")
                return

            cw_instance = CyberwareInstance.objects.create(
                cyberware=cyberware,
                character_object=character,
                character_sheet=char_sheet,
                installed=True,
                active=False,
                paired_with=first_instance,
            )
        else:
            # Normal add: block duplicate *unless* this item can exist on multiple limbs/options
            if not _cyberware_allows_multiple_installed_instances(cyberware):
                if inventory.cyberware.filter(
                    cyberware__name__iexact=cyberware_name, installed=True
                ).exists():
                    self.caller.msg(
                        f"{character.key} already has {cyberware.name} installed. "
                        "Use addcyberware/pair to add a paired second (e.g. second Cybereye)."
                    )
                    return

            cw_instance = CyberwareInstance.objects.create(
                cyberware=cyberware,
                character_object=character,
                character_sheet=char_sheet,
                installed=True,
                active=False,
            )

        inventory.cyberware.add(cw_instance)
        char_sheet.consume_uninstalled_hl_for_cyberware(cyberware)
        char_sheet.calculate_humanity_loss()

        if cyberware.name.lower() == "cyberarm":
            char_sheet.has_cyberarm = True
            char_sheet.recalculate_derived_stats()

        pair_msg = " (paired)" if use_pair else ""
        self.caller.msg(
            f"Added {cyberware.name}{pair_msg} (installed) to {character.key}. "
            f"Humanity loss: {cyberware.humanity_loss}."
        )
        character.msg(
            f"A {cyberware.name}{pair_msg} has been added to your cyberware (installed)."
        )


class CmdParentCyberware(MuxCommand):
    """
    Assign a cyberware option to its parent limb/suite (staff only).

    Usage:
      parentcyberware <character name>=<child cyberware>/<parent cyberware>

    Examples:
      parentcyberware Soma=Anti-Dazzle/Cybereye
      parentcyberware Soma="Popup Ranged Weapon"/Cyberarm

    Assigns the child option to the parent. Both must belong to the character.
    Child can be installed (reassign) or uninstalled (install and assign).
    """

    key = "parentcyberware"
    aliases = ["parentcyber", "assigncyberware"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: parentcyberware <character name>=<child cyberware>/<parent cyberware>")
            return

        character_name = self.lhs.strip().strip('"')
        rhs = self.rhs.strip().strip('"')

        if "/" not in rhs:
            self.caller.msg("Usage: parentcyberware <character name>=<child cyberware>/<parent cyberware>")
            return

        child_name, parent_name = rhs.split("/", 1)
        child_name = child_name.strip()
        parent_name = parent_name.strip()

        if not character_name or not child_name or not parent_name:
            self.caller.msg("Usage: parentcyberware <character name>=<child cyberware>/<parent cyberware>")
            return

        # Find the character
        character = self.caller.search(
            character_name, typeclass="typeclasses.characters.Character", global_search=True
        )
        if not character:
            character = self.caller.search(character_name, global_search=True)
        if not character:
            return

        char_sheet = getattr(character, "character_sheet", None)
        if not char_sheet:
            self.caller.msg(f"{character.key} does not have a character sheet.")
            return

        # Find parent instance (must be installed)
        parent_inst = CyberwareInstance.objects.filter(
            character_sheet=char_sheet,
            cyberware__name__iexact=parent_name,
            installed=True,
        ).first()

        if not parent_inst:
            self.caller.msg(
                f"{character.key} does not have installed cyberware named '{parent_name}'."
            )
            return

        # Find child instance (installed or uninstalled); disambiguate when multiples exist
        from world.cyberware.validation import validate_parent_child, select_child_instance_for_parenting

        child_qs = CyberwareInstance.objects.filter(
            character_sheet=char_sheet,
            cyberware__name__iexact=child_name,
        )
        if not child_qs.exists():
            inventory, _ = Inventory.get_or_create_for_character(character)
            inv_pks = list(
                inventory.cyberware.filter(cyberware__name__iexact=child_name).values_list("pk", flat=True)
            )
            child_qs = CyberwareInstance.objects.filter(pk__in=inv_pks)

        if not child_qs.exists():
            self.caller.msg(
                f"{character.key} does not have cyberware named '{child_name}' in inventory."
            )
            return

        child_inst, pick_status = select_child_instance_for_parenting(
            child_qs, parent_inst, allow_uninstalled=True
        )
        if pick_status == "already":
            self.caller.msg(
                f"{child_inst.cyberware.name} is already assigned to {parent_inst.cyberware.name}."
            )
            return
        if pick_status == "all_busy" or child_inst is None:
            self.caller.msg(
                f"Every '{child_name}' on {character.key} is already assigned to another limb. "
                f"Unparent one first."
            )
            return
        ok, err = validate_parent_child(parent_inst, child_inst)
        if not ok:
            self.caller.msg(err)
            return

        child_inst.parent = parent_inst
        was_uninstalled = not child_inst.installed
        if was_uninstalled:
            child_inst.installed = True
            inventory, _ = Inventory.get_or_create_for_character(character)
            inventory.cyberware.add(child_inst)
        child_inst.save()
        if was_uninstalled:
            char_sheet.consume_uninstalled_hl_for_cyberware(child_inst.cyberware)
            char_sheet.calculate_humanity_loss()
            EdgerunnerChargen.recalculate_humanity_for_typeclass(character)
            self.caller.msg(
                f"Assigned {child_inst.cyberware.name} to {parent_inst.cyberware.name} on {character.key} "
                f"(installed). Humanity recalculated."
            )
        else:
            child_inst.save()
            self.caller.msg(
                f"Assigned {child_inst.cyberware.name} to {parent_inst.cyberware.name} on {character.key}."
            )

        character.msg(
            f"Your {child_inst.cyberware.name} has been assigned to {parent_inst.cyberware.name}."
        )


class CmdUnparentCyberware(MuxCommand):
    """
    Unparent a cyberware option from its parent (staff only).

    Usage:
      unparentcyberware <child cyberware>=<character name>

    Examples:
      unparentcyberware Anti-Dazzle=Soma
      unparentcyberware "Popup Ranged Weapon"=Soma

    Disconnects the option from its parent limb/suite. The option is uninstalled
    (moved to inventory as uninstalled). Humanity loss is preserved - reinstalling
    the same type won't cost extra. Use cyberware/parent to re-assign it later.
    """

    key = "unparentcyberware"
    aliases = ["unparentcyber", "detachcyberware"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: unparentcyberware <child cyberware>=<character name>")
            return

        child_name = self.lhs.strip().strip('"')
        character_name = self.rhs.strip().strip('"')

        if not child_name or not character_name:
            self.caller.msg("Usage: unparentcyberware <child cyberware>=<character name>")
            return

        # Find the character
        character = self.caller.search(
            character_name, typeclass="typeclasses.characters.Character", global_search=True
        )
        if not character:
            character = self.caller.search(character_name, global_search=True)
        if not character:
            return

        char_sheet = getattr(character, "character_sheet", None)
        if not char_sheet:
            self.caller.msg(f"{character.key} does not have a character sheet.")
            return

        # Find installed child instance with a parent
        child_inst = CyberwareInstance.objects.filter(
            character_sheet=char_sheet,
            cyberware__name__iexact=child_name,
            installed=True,
            parent__isnull=False,
        ).select_related("cyberware", "parent").first()

        if not child_inst:
            # Also try via inventory
            inventory, _ = Inventory.get_or_create_for_character(character)
            child_inst = inventory.cyberware.filter(
                cyberware__name__iexact=child_name,
                installed=True,
                parent__isnull=False,
            ).select_related("cyberware", "parent").first()

        if not child_inst:
            self.caller.msg(
                f"No installed {child_name} with a parent found on {character.key}. "
                "Use removecyberware to remove cyberware entirely."
            )
            return

        cyberware = child_inst.cyberware
        parent_name = child_inst.parent.cyberware.name if child_inst.parent else "?"
        humanity_loss = cyberware.humanity_loss

        # Unparent and uninstall (preserve humanity - add to uninstalled tracking)
        child_inst.parent = None
        child_inst.installed = False
        child_inst.active = False
        child_inst.save()

        # Preserve humanity: add to uninstalled_cyberware_hl so reinstall doesn't cost extra
        if humanity_loss > 0 and hasattr(char_sheet, "uninstalled_cyberware_hl"):
            uhl = getattr(char_sheet, "uninstalled_cyberware_hl", None) or {}
            if not isinstance(uhl, dict):
                uhl = {}
            cw_name = cyberware.name
            uhl[cw_name] = uhl.get(cw_name, 0) + humanity_loss
            char_sheet.uninstalled_cyberware_hl = uhl
            char_sheet.save(skip_recalculation=True)

        # Recalculate humanity
        char_sheet.calculate_humanity_loss()
        EdgerunnerChargen.recalculate_humanity_for_typeclass(character)

        self.caller.msg(
            f"Unparented {cyberware.name} from {parent_name} on {character.key}. "
            f"Humanity preserved - reinstall same type for no extra humanity cost."
        )
        character.msg(
            f"Your {cyberware.name} has been disconnected from {parent_name} and uninstalled. "
            f"Humanity preserved. Use cyberware/parent to re-assign it."
        )
