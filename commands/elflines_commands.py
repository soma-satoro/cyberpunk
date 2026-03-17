"""
Elflines Online commands - +elo, +elfline, +elologin, +elologout.
"""

from evennia import Command
from evennia.utils import evtable
from evennia.commands.default.muxcommand import MuxCommand

from world.elflines.models import ElflineSheet, Elfline, ElflineMembership
from world.elflines.services import (
    get_or_create_elfline_sheet,
    get_elo_sheet_for_character,
    get_elo_lobby,
    is_in_elo,
    elo_login,
    elo_logout,
)
from world.utils.character_utils import is_character_approved
from world.elflines.elflines_data import (
    ELO_ARMORY,
    ELO_SKILLS,
    ELO_STATS,
    ELO_TITLES_BY_STAT,
    ELO_GP_PER_EB,
)


class CmdElo(MuxCommand):
    """
    Elflines Online - the MMO within the Cyberpunk universe.

    Usage:
      +elo                    - Show your ELO status
      +elo/sheet              - View or create your ELO character sheet
      +elo/login              - Enter the Elflands (requires headset + subscription)
      +elo/logout             - Leave the Elflands, return to meat world
      +elo/who                - List players currently in the Elflands
      +elo/armory             - List equipment available in ELO
    """

    key = "+elo"
    aliases = ["elo", "+elolines"]
    locks = "cmd:all()"
    help_category = "Elflines Online"

    def func(self):
        caller = self.caller
        if not caller.location:
            caller.msg("You cannot use Elflines commands right now.")
            return
        if not is_character_approved(caller):
            caller.msg("You must be approved by staff before using Elflines Online.")
            return

        switches = self.switches or []
        if not switches:
            self._show_status()
            return
        switch = switches[0].lower()
        if switch == "sheet":
            self._show_sheet()
        elif switch == "login":
            self._login()
        elif switch == "logout":
            self._logout()
        elif switch == "who":
            self._who()
        elif switch == "armory":
            self._armory()
        else:
            caller.msg(f"Unknown switch. Use |w+help +elo|n for usage.")

    def _show_status(self):
        caller = self.caller
        in_elo = is_in_elo(caller)
        status = "|cIn the Elflands|n" if in_elo else "|yIn the meat world|n"
        sheet = get_elo_sheet_for_character(caller)
        if sheet:
            elfname = sheet.elfname or "(unnamed)"
            elfline = sheet.elfline.get_bracket_name() if sheet.elfline else "None"
            caller.msg(
                f"|wElflines Online|n\n"
                f"Status: {status}\n"
                f"Elfname: |c{elfname}|n  Elfline: {elfline}\n"
                f"Rank: {sheet.rank}  gp: {sheet.gp}  HP: {sheet.current_hp}/{sheet.max_hp}"
            )
        else:
            caller.msg(
                f"|wElflines Online|n\n"
                f"Status: {status}\n"
                f"You have no ELO character yet. Use |w+elo/sheet|n to create one."
            )

    def _show_sheet(self):
        caller = self.caller
        sheet = get_or_create_elfline_sheet(caller)
        title = sheet.get_title_display()
        elfline_str = sheet.elfline.get_bracket_name() if sheet.elfline else "None"

        stats = " ".join(f"{s[:3].upper()}:{getattr(sheet, s)}" for s in ELO_STATS)
        skills_list = [f"{sk}:{sheet.skills.get(sk, 0)}" for sk, _, _ in ELO_SKILLS if sheet.skills.get(sk, 0)]
        skills_list.extend(f"{k}:{v}" for k, v in sheet.skills.items() if k not in (x[0] for x in ELO_SKILLS) and v)
        skills_str = ", ".join(skills_list) if skills_list else "—"

        hint = "" if sheet.is_complete else "\n|yUse |wsheet/elo|n to complete character generation.|n"
        caller.msg(
            f"|wElflines Online Character Sheet|n\n"
            f"|c{sheet.elfname or 'Unnamed'}|n  Rank {sheet.rank}  {title}\n"
            f"Elfline: {elfline_str}  gp: {sheet.gp}\n"
            f"HP: {sheet.current_hp}/{sheet.max_hp}"
            + (" |r[Revive Sickness]|n" if sheet.revive_sickness else "")
            + f"\n\n|wSTATS|n  {stats}\n|wSKILLS|n  {skills_str}{hint}"
        )

    def _login(self):
        ok, err = elo_login(self.caller)
        if ok:
            self.caller.msg(
                "|gYou don your Segotari RUSH REVOLUTION headset. Reality shifts...|n\n"
                "|cYou are now in the Elflands. The forces of darkness await.|n"
            )
        else:
            self.caller.msg(f"|r{err}|n")

    def _logout(self):
        ok, err = elo_logout(self.caller)
        if ok:
            self.caller.msg("|yYou remove your headset. The Elflands fade...|n\n|gYou are back in the meat world.|n")
        else:
            self.caller.msg(f"|r{err}|n")

    def _who(self):
        lobby = get_elo_lobby()
        if not lobby:
            self.caller.msg("The ELO lobby has not been set up.")
            return
        # Find all ELO rooms and characters in them
        from evennia.utils import search_object
        from evennia.objects.models import ObjectDB
        elo_rooms = ObjectDB.objects.filter(
            db_typeclass_path="typeclasses.elflines_rooms.ElflinesRoom"
        )
        chars = []
        for room in elo_rooms:
            for obj in room.contents:
                if hasattr(obj, "has_account") and obj.has_account:
                    sheet = get_elo_sheet_for_character(obj)
                    elfname = sheet.elfname if sheet else obj.key
                    elfline = sheet.elfline.get_bracket_name() if sheet and sheet.elfline else "—"
                    chars.append((elfname, elfline, room.key))
        if not chars:
            self.caller.msg("|wElflands Who|n\nNo one is currently in the Elflands.")
            return
        tbl = evtable.EvTable("|wElfname|n", "|wElfline|n", "|wLocation|n", border="cells")
        for elfname, elfline, loc in chars:
            tbl.add_row(elfname, elfline, loc)
        self.caller.msg(f"|wElflands Who|n\n{str(tbl)}")

    def _armory(self):
        tbl = evtable.EvTable("|wItem|n", "|wgp|n", "|wCPR Equivalent|n", border="cells")
        for key, name, gp, cpr in ELO_ARMORY:
            tbl.add_row(name, gp, cpr)
        self.caller.msg(f"|wElflines Online Armory|n\n{str(tbl)}\n1 eb = {ELO_GP_PER_EB} gp (pay to win)")


class CmdElfline(Command):
    """
    Manage your Elfline (guild) in Elflines Online.

    Usage:
      +elfline                    - List elflines you're in
      +elfline/create <name>      - Create a new elfline
      +elfline/info [<name>]      - Info on an elfline
      +elfline/join <name>        - Join an elfline
      +elfline/leave [<name>]     - Leave your elfline
      +elfline/invite <player>    - Invite to your elfline (leader/officer)
      +elfline/kick <player>      - Remove from elfline (leader/officer)
    """

    key = "+elfline"
    aliases = ["elfline", "+elfline"]
    locks = "cmd:all()"
    help_category = "Elflines Online"

    def func(self):
        caller = self.caller
        if not is_character_approved(caller):
            caller.msg("You must be approved by staff before using Elflines Online.")
            return
        switches = self.switches or []
        arg = self.args.strip()
        if not switches:
            self._list()
            return
        switch = switches[0].lower()
        if switch == "create" and arg:
            self._create(arg)
        elif switch == "info":
            self._info(arg or None)
        elif switch == "join" and arg:
            self._join(arg)
        elif switch == "leave":
            self._leave(arg or None)
        elif switch == "invite" and arg:
            self._invite(arg)
        elif switch == "kick" and arg:
            self._kick(arg)
        else:
            caller.msg("Usage: +elfline/create <name>, /join <name>, /leave, /info [name], /invite <who>, /kick <who>")

    def _list(self):
        memberships = ElflineMembership.objects.filter(character=self.caller)
        if not memberships.exists():
            self.caller.msg("You are not in any Elfline. Use |w+elfline/join <name>|n to join one.")
            return
        lines = ["|wYour Elflines|n"]
        for m in memberships:
            lines.append(f"  {m.elfline.get_bracket_name()} ({m.role or 'Member'})")
        self.caller.msg("\n".join(lines))

    def _create(self, name):
        from evennia.utils import search_object
        if Elfline.objects.filter(name__iexact=name).exists():
            self.caller.msg(f"An Elfline named '{name}' already exists.")
            return
        elfline = Elfline.objects.create(name=name, leader=self.caller)
        ElflineMembership.objects.create(elfline=elfline, character=self.caller, role="Leader")
        sheet = get_elo_sheet_for_character(self.caller)
        if sheet:
            sheet.elfline = elfline
            sheet.save()
        self.caller.msg(f"You have founded the Elfline {elfline.get_bracket_name()}.")

    def _info(self, name):
        if name:
            try:
                elfline = Elfline.objects.get(name__iexact=name)
            except Elfline.DoesNotExist:
                self.caller.msg(f"No Elfline named '{name}' found.")
                return
        else:
            sheet = get_elo_sheet_for_character(self.caller)
            if not sheet or not sheet.elfline:
                self.caller.msg("You are not in an Elfline. Specify one with +elfline/info <name>")
                return
            elfline = sheet.elfline
        mems = ElflineMembership.objects.filter(elfline=elfline)
        leader = elfline.leader.get_display_name(self.caller) if elfline.leader else "None"
        self.caller.msg(
            f"|w{elfline.get_bracket_name()}|n\n"
            f"Leader: {leader}\n"
            f"Members: {mems.count()}\n"
            f"{elfline.description or '(No description)'}"
        )

    def _join(self, name):
        try:
            elfline = Elfline.objects.get(name__iexact=name)
        except Elfline.DoesNotExist:
            self.caller.msg(f"No Elfline named '{name}' found.")
            return
        if ElflineMembership.objects.filter(elfline=elfline, character=self.caller).exists():
            self.caller.msg(f"You are already in {elfline.get_bracket_name()}.")
            return
        ElflineMembership.objects.create(elfline=elfline, character=self.caller, role="Member")
        sheet = get_elo_sheet_for_character(self.caller)
        if sheet:
            sheet.elfline = elfline
            sheet.save()
        self.caller.msg(f"You have joined {elfline.get_bracket_name()}.")

    def _leave(self, name):
        sheet = get_elo_sheet_for_character(self.caller)
        if not sheet:
            self.caller.msg("You have no ELO character.")
            return
        elfline = sheet.elfline
        if not elfline:
            self.caller.msg("You are not in an Elfline.")
            return
        if name and elfline.name.lower() != name.lower():
            self.caller.msg(f"You're in {elfline.get_bracket_name()}, not '{name}'.")
            return
        ElflineMembership.objects.filter(elfline=elfline, character=self.caller).delete()
        sheet.elfline = None
        sheet.save()
        self.caller.msg(f"You have left {elfline.get_bracket_name()}.")

    def _invite(self, arg):
        sheet = get_elo_sheet_for_character(self.caller)
        if not sheet or not sheet.elfline:
            self.caller.msg("You must be in an Elfline to invite.")
            return
        m = ElflineMembership.objects.filter(elfline=sheet.elfline, character=self.caller).first()
        if not m or m.role not in ("Leader", "Officer"):
            self.caller.msg("Only leaders and officers can invite.")
            return
        tgt = self.caller.search(arg)
        if not tgt:
            return
        if not hasattr(tgt, "has_account") or not tgt.has_account:
            self.caller.msg("You can only invite player characters.")
            return
        if ElflineMembership.objects.filter(elfline=sheet.elfline, character=tgt).exists():
            self.caller.msg(f"{tgt.get_display_name(self.caller)} is already in your Elfline.")
            return
        ElflineMembership.objects.create(elfline=sheet.elfline, character=tgt, role="Member")
        tgt_sheet = get_elo_sheet_for_character(tgt)
        if tgt_sheet:
            tgt_sheet.elfline = sheet.elfline
            tgt_sheet.save()
        self.caller.msg(f"You have invited {tgt.get_display_name(self.caller)} to {sheet.elfline.get_bracket_name()}.")
        tgt.msg(f"{self.caller.get_display_name(tgt)} has invited you to join {sheet.elfline.get_bracket_name()}.")

    def _kick(self, arg):
        sheet = get_elo_sheet_for_character(self.caller)
        if not sheet or not sheet.elfline:
            self.caller.msg("You must be in an Elfline to kick.")
            return
        m = ElflineMembership.objects.filter(elfline=sheet.elfline, character=self.caller).first()
        if not m or m.role != "Leader":
            self.caller.msg("Only the leader can kick members.")
            return
        tgt = self.caller.search(arg)
        if not tgt:
            return
        tgt_mem = ElflineMembership.objects.filter(elfline=sheet.elfline, character=tgt).first()
        if not tgt_mem:
            self.caller.msg(f"{tgt.get_display_name(self.caller)} is not in your Elfline.")
            return
        tgt_mem.delete()
        tgt_sheet = get_elo_sheet_for_character(tgt)
        if tgt_sheet:
            tgt_sheet.elfline = None
            tgt_sheet.save()
        self.caller.msg(f"You have removed {tgt.get_display_name(self.caller)} from the Elfline.")
        tgt.msg(f"You have been removed from {sheet.elfline.get_bracket_name()} by {self.caller.get_display_name(tgt)}.")


class CmdEloSetup(Command):
    """
    Staff: Set up Elflines Online - create lobby and initial grid.

    Usage:
      +elosetup    - Create ELO Lobby room if missing
    """

    key = "+elosetup"
    locks = "cmd:perm(Builder)"
    help_category = "Elflines Online"

    def func(self):
        from evennia.utils import search_object, create
        existing = search_object("ELO Lobby", typeclass="typeclasses.elflines_rooms.ElflinesRoom")
        if existing:
            self.caller.msg("ELO Lobby already exists.")
            return
        room = create.create_object(
            "typeclasses.elflines_rooms.ElflinesRoom",
            key="ELO Lobby",
            location=None,
        )
        room.db.desc = (
            "The grand hall of the Elflands greets you. Ancient trees form pillars, and the scent of sacred herbs "
            "hangs in the air. Elves from across Citinet gather here to form Elflines, trade, and prepare for "
            "raids against the forces of darkness. Exits lead to the Valley of Ancients and beyond."
        )
        room.db.is_miasma = False  # Safe zone
        self.caller.msg(f"Created ELO Lobby: {room} (#{room.id}). Add exits to build the Elflands grid.")
