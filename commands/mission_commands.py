"""
Mission Board commands - virtual mission board accessible via 'mission'.

Staff and Fixers post jobs; players accept, form teams, complete/fail.
"""
from datetime import datetime
from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.search import search_object, search_account
from django.utils import timezone
from django.db.models import Max

from world.mission_board.models import Mission, MissionTeamMember, StorySeed
from world.mission_board import services
from world.mission_board.services import (
    _get_character_display_name,
    is_faction_member,
    is_faction_head,
    can_post_faction_mission,
    can_see_mission,
)
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.utils.formatting import header, footer, divider
from world.utils.character_utils import is_character_approved
from evennia.utils import logger


def _is_staff(caller):
    return caller.check_permstring("Builder")


def _is_fixer(caller):
    return getattr(caller.db, 'role', None) == 'Fixer'


def _can_post_mission(caller):
    return _is_staff(caller) or _is_fixer(caller)


def _can_post_faction_mission(caller, faction_model):
    """Can post missions for this faction?"""
    if _is_staff(caller):
        return True
    if is_faction_head(caller, faction_model):
        return True
    if _is_fixer(caller) and services.is_faction_member(caller, faction_model):
        return True
    return can_post_faction_mission(caller, faction_model)


def _is_storyteller(caller):
    return caller.check_permstring("storyteller")


def _get_character_for_arg(caller, arg):
    """Resolve character from arg (name or #dbref)."""
    if not arg:
        return None
    arg = arg.strip()
    if arg.startswith('#'):
        try:
            dbref = int(arg[1:])
            from evennia.objects.models import ObjectDB
            objs = ObjectDB.objects.filter(id=dbref)
            if objs.exists():
                return objs.first()
        except ValueError:
            pass
    results = search_object(arg, typeclass="typeclasses.characters.Character")
    if results and len(results) == 1:
        return results[0]
    if results and len(results) > 1:
        return None  # ambiguous
    return None


def _get_npc_for_arg(caller, arg):
    """Resolve NPC from arg (name or #dbref)."""
    if not arg:
        return None
    arg = arg.strip()
    if arg.startswith('#'):
        try:
            dbref = int(arg[1:])
            from evennia.objects.models import ObjectDB
            objs = ObjectDB.objects.filter(id=dbref, db_typeclass_path="typeclasses.npcs.NPC")
            if objs.exists():
                return objs.first()
        except ValueError:
            pass
    results = search_object(arg, typeclass="typeclasses.npcs.NPC")
    if results and len(results) == 1:
        return results[0]
    if results and len(results) > 1:
        return None
    return None


def _parse_mon_day_year(s):
    """Parse MON-DAY-YEAR e.g. Mar-08-2025."""
    try:
        return datetime.strptime(s.strip(), "%b-%d-%Y").date()
    except ValueError:
        return None


class CmdMission(MuxCommand):
    """
    Mission board - view, accept, manage missions.

    Usage:
      mission                     - List all available missions
      mission <#>                 - View mission info (alias: mission/info)
      mission/info <#>
      mission/accept <#>          - Accept a mission (you become lead)
      mission/add <#>=<character>  - Add team member (lead/staff)
      mission/remove <#>=<character> - Remove from team (lead/staff)
      mission/revoke <character>   - Staff: remove invalid player from their mission
      mission/leave [<#>]         - Leave your mission
      mission/gm <#>=<name>       - Assign GM (staff/storyteller for pickup)
      mission/complete <#>[=<dead1>,<dead2>,...] - GM: complete; optional =dead chars (survivors split payout)
      mission/fail <#>            - GM: mark mission failed, apply penalties
      mission/cancel <#>          - Fixer/staff: cancel mission
      mission/update <#>=<message> - Send update to everyone on mission
      mission/scene <#>=<desc>/<MON-DAY-YEAR> - Set scene info
      mission/create              - Staff/Fixer: create mission (interactive)
      mission/modify <#>          - Staff/Fixer: modify mission
      mission/mine                - List missions you're on
      mission/faction <#>=<faction> - Set mission's faction (staff/fixer/faction head)
      mission/fixer <#>=<npc>      - Staff: assign an NPC as the mission fixer (bypasses payout requirements)
      mission/reward <#>=apartment:#id[,apartment:#id,...] - Staff: add apartment rewards (staff missions only)
      mission/reward <#>/clear     - Staff: clear apartment rewards
      mission/reward <#>/remove=#id[,#id,...] - Staff: remove apartment rewards by dbref
      mission/seeds               - Fixers: list available story seeds
      mission/seed <#>            - View story seed details
      mission/seed/create <name>=<desc>/<max_budget>[/rep][/FactionName][/faction_rep][/voucher:#id][/item:#id] - Staff: create seed
      mission/seed/reward <#>=voucher:#id[,item:#id,...] - Staff: add rewards
      mission/seed/reward <#>/clear - Staff: clear all rewards
      mission/seed/reward <#>/remove=#id[,#id,...] - Staff: remove rewards by dbref
      mission/grab <#>=<name>/<desc>/<due>/<payout>/<rep>[/pod][/faction_rep][/FactionName][/faction_only] - Fixer: grab seed, create mission
    """
    key = "mission"
    aliases = ["missions"]
    locks = "cmd:all()"
    help_category = "Missions"

    def func(self):
        try:
            self._dispatch()
        except Exception as err:
            logger.log_err(f"Mission command error: {err}", exc_info=True)
            self.caller.msg(f"|rMission command error: {err}|n")

    def _dispatch(self):
        if not self.switches:
            if self.args:
                self.view_mission_info()
            else:
                self.list_missions()
            return

        if "info" in self.switches:
            self.view_mission_info()
        elif "accept" in self.switches:
            self.cmd_accept()
        elif "add" in self.switches:
            self.cmd_add()
        elif "remove" in self.switches:
            self.cmd_remove()
        elif "revoke" in self.switches:
            self.cmd_revoke()
        elif "leave" in self.switches:
            self.cmd_leave()
        elif "gm" in self.switches:
            self.cmd_gm()
        elif "complete" in self.switches:
            self.cmd_complete()
        elif "fail" in self.switches:
            self.cmd_fail()
        elif "cancel" in self.switches:
            self.cmd_cancel()
        elif "update" in self.switches:
            self.cmd_update()
        elif "scene" in self.switches:
            self.cmd_scene()
        elif "seed" in self.switches:
            if "create" in self.switches:
                self.cmd_seed_create()
            elif "reward" in self.switches:
                self.cmd_seed_reward()
            else:
                self.cmd_seed()
        elif "create" in self.switches:
            self.cmd_create()
        elif "modify" in self.switches:
            self.cmd_modify()
        elif "mine" in self.switches:
            self.cmd_mine()
        elif "faction" in self.switches:
            self.cmd_faction()
        elif "fixer" in self.switches:
            self.cmd_fixer()
        elif "reward" in self.switches:
            self.cmd_reward()
        elif "seeds" in self.switches:
            self.cmd_seeds()
        elif "grab" in self.switches:
            self.cmd_grab()
        else:
            self.caller.msg("Unknown switch. See 'help mission' for usage.")

    def _get_mission(self, mid):
        try:
            return Mission.objects.get(id=int(mid))
        except (ValueError, Mission.DoesNotExist):
            return None

    def list_missions(self):
        """List all open/active missions (filter by faction visibility for faction_only)."""
        missions = Mission.objects.filter(status__in=['open', 'active']).order_by('-posted_date')
        missions = [m for m in missions if can_see_mission(self.caller, m)]
        if not missions:
            self.caller.msg("No missions available on the board.")
            return
        W = 78
        out = header("Mission Board", width=W, fillchar="|b-|n")
        out += f"|y{'ID':<6}{'Name':<25}{'Poster':<15}{'Due':<12}{'Status':<12}{'Team':<6}|n\n"
        for m in missions:
            team_count = m.team_members.count()
            due = m.due_date.strftime("%m/%d/%y") if m.due_date else "---"
            name = (m.name[:22] + "...") if len(m.name) > 25 else m.name
            poster = (m.get_poster_name()[:12] + "...") if len(m.get_poster_name()) > 15 else m.get_poster_name()
            out += f"|w{m.id:<6}{name:<25}{poster:<15}{due:<12}{m.status:<12}{team_count:<6}|n\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def view_mission_info(self):
        """View detailed info for a mission."""
        if not self.args:
            self.caller.msg("Usage: mission <#> or mission/info <#>")
            return
        mission = self._get_mission(self.args.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        if not can_see_mission(self.caller, mission):
            self.caller.msg("You cannot see that mission.")
            return

        out = header(f"Mission #{mission.id}: {mission.name}", width=78, fillchar="|b-|n") + "\n"
        out += f"|cPosted:|n {mission.posted_date.strftime('%Y-%m-%d %H:%M')} by |w{mission.get_poster_name()}|n\n"
        out += f"|cDue:|n {mission.due_date.strftime('%Y-%m-%d') if mission.due_date else '---'}\n"
        out += f"|cStatus:|n {mission.status}\n"
        gm_name = _get_character_display_name(mission.gm_character) if mission.gm_character else (
            mission.gm.username if mission.gm else ('Pickup' if mission.gm_type == 'pickup' else '---'))
        out += f"|cGM:|n {gm_name}\n"
        out += f"|cTeam:|n "
        team = list(mission.team_members.order_by('order'))
        if team:
            names = [mtm.character.key for mtm in team]
            lead_mark = lambda i, n: f"{n} (lead)" if i == 0 else n
            out += ", ".join(lead_mark(i, n) for i, n in enumerate(names)) + "\n"
        else:
            out += "---\n"
        out += f"|cPayout:|n {mission.money_amount} eb"
        if mission.money_pay_on_delivery:
            out += " (pay on delivery)"
        out += f", {mission.rep_amount} rep"
        apt_rewards = getattr(mission, 'apartment_rewards', None) or []
        if mission.posted_by_staff and apt_rewards:
            out += f" |cApartment rewards:|n {len(apt_rewards)}"
        if getattr(mission, 'faction_rep_amount', 0) > 0 and mission.faction:
            out += f", {mission.faction_rep_amount} {mission.faction.name} rep"
        elif mission.faction and mission.rep_amount and not getattr(mission, 'faction_rep_amount', 0):
            out += f" ({mission.faction.name})"
        out += "\n"
        out += divider("Description", width=78, fillchar="-", color="|b", text_color="|c") + "\n"
        out += mission.description + "\n"
        if mission.scene_description:
            out += divider("Scheduled Scene", width=78, fillchar="-", color="|b", text_color="|c") + "\n"
            out += f"|cDate:|n {mission.scene_date}\n" if mission.scene_date else ""
            out += mission.scene_description + "\n"
        if mission.updates:
            out += divider("Updates", width=78, fillchar="-", color="|b", text_color="|c") + "\n"
            for u in mission.updates[-5:]:
                out += f"|c[{u['date']}] {u['author']}:|n {u['text']}\n"
        out += footer(width=78, fillchar="|b-|n")
        self.caller.msg(out)

    def cmd_accept(self):
        """Accept a mission - caller becomes lead."""
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before taking on missions.")
            return
        if not self.args:
            self.caller.msg("Usage: mission/accept <#>")
            return
        mission = self._get_mission(self.args.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        if mission.status != 'open':
            self.caller.msg("That mission is not available.")
            return
        if not can_see_mission(self.caller, mission):
            self.caller.msg("You cannot see that mission.")
            return
        if not hasattr(self.caller, 'account'):
            self.caller.msg("You must be a character to accept missions.")
            return

        if MissionTeamMember.objects.filter(mission=mission, character=self.caller).exists():
            self.caller.msg("You're already on this mission.")
            return

        max_order = MissionTeamMember.objects.filter(mission=mission).aggregate(m=Max('order'))['m'] or -1
        MissionTeamMember.objects.create(mission=mission, character=self.caller, order=max_order + 1)
        mission.status = 'active'
        mission.save()

        # Create job if not exists
        poster_account = getattr(mission.posted_by, 'account', None) if mission.posted_by else None
        if not mission.job and poster_account:
            services.create_mission_job(mission, poster_account)
        services.sync_mission_to_job(mission)
        services.mission_add_comment_and_mail(mission, self.caller.key, f"{self.caller.key} accepted the mission as lead.")
        self.caller.msg(f"You accepted mission #{mission.id} and are the lead.")

    def cmd_add(self):
        """Add character to mission team (lead or staff)."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/add <#>=<character name>")
            return
        mid, char_arg = self.args.split("=", 1)
        char = _get_character_for_arg(self.caller, char_arg.strip())
        if not char:
            self.caller.msg("Character not found.")
            return
        if not is_character_approved(char):
            self.caller.msg("That character must be approved before joining missions.")
            return
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        team = list(mission.team_members.order_by('order'))
        if not team:
            self.caller.msg("Mission has no lead. It must be accepted first.")
            return
        lead = team[0].character
        if lead != self.caller and not _is_staff(self.caller):
            self.caller.msg("Only the mission lead or staff can add team members.")
            return
        if MissionTeamMember.objects.filter(mission=mission, character=char).exists():
            self.caller.msg(f"{char.key} is already on the mission.")
            return
        max_order = MissionTeamMember.objects.filter(mission=mission).aggregate(m=Max('order'))['m'] or -1
        MissionTeamMember.objects.create(mission=mission, character=char, order=max_order + 1)
        services.sync_mission_to_job(mission)
        services.mission_add_comment_and_mail(mission, self.caller.key, f"{self.caller.key} added {char.key} to the mission.")
        self.caller.msg(f"Added {char.key} to mission #{mission.id}.")

    def cmd_remove(self):
        """Remove character from mission (lead or staff)."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/remove <#>=<character name>")
            return
        mid, char_arg = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        team = list(mission.team_members.order_by('order'))
        if not team:
            self.caller.msg("Mission has no team.")
            return
        lead = team[0].character
        if lead != self.caller and not _is_staff(self.caller):
            self.caller.msg("Only the mission lead or staff can remove team members.")
            return
        char = _get_character_for_arg(self.caller, char_arg)
        if not char:
            self.caller.msg("Character not found.")
            return
        mtm = MissionTeamMember.objects.filter(mission=mission, character=char).first()
        if not mtm:
            self.caller.msg(f"{char.key} is not on the mission.")
            return
        if mtm.character == lead:
            self.caller.msg("Use mission/leave to drop lead. Removing the lead requires staff.")
            return
        mtm.delete()
        services.sync_mission_to_job(mission)
        services.mission_add_comment_and_mail(mission, self.caller.key, f"{self.caller.key} removed {char.key} from the mission.")
        self.caller.msg(f"Removed {char.key} from mission #{mission.id}.")

    def cmd_revoke(self):
        """Staff: revoke a character from their mission (invalid/unfair)."""
        if not _is_staff(self.caller):
            self.caller.msg("Only staff can revoke a player from a mission.")
            return
        if not self.args:
            self.caller.msg("Usage: mission/revoke <character name>")
            return
        char = _get_character_for_arg(self.caller, self.args.strip())
        if not char:
            self.caller.msg("Character not found.")
            return
        mtm = MissionTeamMember.objects.filter(character=char).first()
        if not mtm:
            self.caller.msg(f"{char.key} is not on any mission.")
            return
        mission = mtm.mission
        mtm.delete()
        services.sync_mission_to_job(mission)
        services.mission_add_comment_and_mail(mission, self.caller.key, f"Staff revoked {char.key} from the mission.")
        self.caller.msg(f"Revoked {char.key} from mission #{mission.id}.")

    def cmd_leave(self):
        """Leave current mission. If lead, next most recent becomes lead."""
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff to use mission commands.")
            return
        mtm = MissionTeamMember.objects.filter(character=self.caller).first()
        if not mtm:
            mid = self.args.strip() if self.args else None
            if mid:
                mission = self._get_mission(mid)
                if mission:
                    self.caller.msg("You are not on that mission.")
                else:
                    self.caller.msg("Mission not found.")
            else:
                self.caller.msg("You are not on any mission.")
            return
        mission = mtm.mission
        team = list(mission.team_members.order_by('-order'))
        mtm.delete()
        remaining = list(mission.team_members.order_by('order'))
        if not remaining:
            mission.status = 'open'
            mission.save()
            self.caller.msg("You left the mission. It is now open for others.")
        else:
            services.sync_mission_to_job(mission)
            services.mission_add_comment_and_mail(mission, self.caller.key, f"{self.caller.key} left the mission.")
            self.caller.msg("You left the mission.")
        services.sync_mission_to_job(mission)

    def cmd_gm(self):
        """Assign GM to mission by character name (staff or storyteller for pickup)."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/gm <#>=<character name>")
            return
        mid, name = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        if mission.gm_type == 'assigned' and not _is_staff(self.caller):
            self.caller.msg("Only staff can reassign an assigned GM.")
            return
        if mission.gm_type == 'pickup' and not (_is_staff(self.caller) or _is_storyteller(self.caller)):
            self.caller.msg("Only staff or player storytellers can claim pickup missions.")
            return
        char = _get_character_for_arg(self.caller, name.strip())
        if not char:
            self.caller.msg("Character not found.")
            return
        mission.gm_character = char
        mission.gm = getattr(char, 'account', None)
        mission.gm_type = 'assigned'
        mission.save()
        services.sync_mission_to_job(mission)
        gm_display = _get_character_display_name(char)
        services.mission_add_comment_and_mail(mission, self.caller.key, f"GM assigned: {gm_display}")
        self.caller.msg(f"GM for mission #{mission.id} set to {gm_display}.")

    def cmd_complete(self):
        """GM: mark mission complete and apply payouts. Optional =dead1,dead2 for casualties."""
        if not self.args:
            self.caller.msg("Usage: mission/complete <#>[=<dead1>,<dead2>,...]")
            return
        # Parse mission id and optional dead characters
        dead_chars = None
        if "=" in self.args:
            mid, dead_arg = self.args.split("=", 1)
            mid = mid.strip()
            dead_names = [n.strip() for n in dead_arg.split(",") if n.strip()]
            if dead_names:
                dead_chars = []
                for name in dead_names:
                    c = _get_character_for_arg(self.caller, name)
                    if c:
                        dead_chars.append(c)
                    else:
                        self.caller.msg(f"Character '{name}' not found.")
                        return
        else:
            mid = self.args.strip()

        mission = self._get_mission(mid)
        if not mission:
            self.caller.msg("Mission not found.")
            return
        is_gm = (mission.gm_character == self.caller) or (mission.gm and getattr(self.caller, 'account', None) == mission.gm)
        if not is_gm and not _is_staff(self.caller):
            self.caller.msg("Only the assigned GM or staff can complete the mission.")
            return
        if mission.status not in ('open', 'active'):
            self.caller.msg("Mission cannot be completed in its current state.")
            return

        # Compute survivors: team minus dead (if specified)
        survivors = None
        if dead_chars:
            team_ids = {mtm.character_id for mtm in mission.team_members.all()}
            dead_ids = {c.id for c in dead_chars}
            survivor_ids = team_ids - dead_ids
            survivors = [mtm.character for mtm in mission.team_members.filter(character_id__in=survivor_ids).order_by('order')]
            if not survivors:
                self.caller.msg("All team members marked dead. No payouts to players.")
                return

        mission.status = 'completed'
        mission.save()
        services.complete_mission(mission, survivors=survivors)
        dead_note = f" (survivors: {', '.join(c.key for c in survivors)})" if survivors and dead_chars else ""
        services.mission_add_comment_and_mail(
            mission, self.caller.key,
            f"Mission completed. Payouts applied.{dead_note}"
        )
        self.caller.msg(f"Mission #{mission.id} completed. Payouts applied.")

    def cmd_fail(self):
        """GM: mark mission failed and apply penalties."""
        if not self.args:
            self.caller.msg("Usage: mission/fail <#>")
            return
        mission = self._get_mission(self.args.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        is_gm = (mission.gm_character == self.caller) or (mission.gm and getattr(self.caller, 'account', None) == mission.gm)
        if not is_gm and not _is_staff(self.caller):
            self.caller.msg("Only the assigned GM or staff can fail the mission.")
            return
        if mission.status not in ('open', 'active'):
            self.caller.msg("Mission cannot be failed in its current state.")
            return
        mission.status = 'failed'
        mission.save()
        services.fail_mission(mission)
        services.mission_add_comment_and_mail(mission, self.caller.key, "Mission failed. Penalties applied.")
        self.caller.msg(f"Mission #{mission.id} failed. Penalties applied.")

    def cmd_cancel(self):
        """Fixer/staff: cancel mission."""
        if not self.args:
            self.caller.msg("Usage: mission/cancel <#>")
            return
        mission = self._get_mission(self.args.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        poster = mission.posted_by
        if poster != self.caller and not _is_staff(self.caller):
            self.caller.msg("Only the poster or staff can cancel this mission.")
            return
        if mission.status in ('completed', 'failed', 'cancelled'):
            self.caller.msg("Mission is already closed.")
            return
        mission.status = 'cancelled'
        mission.save()
        services.mission_add_comment_and_mail(mission, self.caller.key, "Mission cancelled.")
        self.caller.msg(f"Mission #{mission.id} cancelled.")

    def cmd_update(self):
        """Send update to everyone on mission."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/update <#>=<message>")
            return
        mid, msg = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        team = list(mission.team_members.all())
        is_on_mission = (any(mtm.character == self.caller for mtm in team) or
                         mission.posted_by == self.caller or
                         mission.gm_character == self.caller or
                         (mission.gm and getattr(self.caller, 'account', None) == mission.gm))
        if not is_on_mission and not _is_staff(self.caller):
            self.caller.msg("You are not on this mission.")
            return
        services.mission_add_comment_and_mail(mission, self.caller.key, msg.strip())
        self.caller.msg("Update sent.")

    def cmd_scene(self):
        """Set scene date and description on mission."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/scene <#>=<description>/<MON-DAY-YEAR>")
            return
        mid, rest = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        if "/" not in rest:
            self.caller.msg("Use format: description/Mon-Day-Year (e.g. The Heist/Mar-15-2025)")
            return
        desc, date_str = rest.split("/", 1)
        date_val = _parse_mon_day_year(date_str)
        if not date_val:
            self.caller.msg("Invalid date. Use MON-DAY-YEAR (e.g. Mar-15-2025)")
            return
        mission.scene_description = desc.strip()
        mission.scene_date = date_val
        mission.save()
        services.mission_add_comment_and_mail(mission, self.caller.key, f"Scene set: {desc.strip()} on {date_val}")
        self.caller.msg(f"Scene set for mission #{mission.id}.")

    def cmd_create(self):
        """Create mission. Staff/Fixer/Faction head/poster. Usage: mission/create <name>=<desc>/<due>/<money>/<rep>[/faction_rep][/pod][/FactionName][/faction_only][/fail:amt:team|leader]"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/create <name>=<desc>/<due>/<money>/<rep>[/faction_rep][/pod][/FactionName][/faction_only][/fail:amt:scope]")
            self.caller.msg("Faction missions: add /FactionName, optional /faction_rep and /faction_only.")
            return
        name, rest = self.args.split("=", 1)
        name = name.strip()
        parts = rest.split("/")
        if len(parts) < 4:
            self.caller.msg("Provide: description/due_date/money/rep")
            return
        desc = parts[0].strip()
        due_str = parts[1].strip()
        try:
            money = int(parts[2].strip())
            rep = int(parts[3].strip())
        except ValueError:
            self.caller.msg("Money and rep must be numbers.")
            return
        faction_rep = 0
        pod = False
        faction_name = None
        faction_only = False
        fail_amt, fail_scope = 0, 'leader'
        for p in parts[4:]:
            p = p.strip()
            if p.lower() == 'pod':
                pod = True
            elif p.lower() == 'faction_only':
                faction_only = True
            elif p.lower().startswith('fail:'):
                sub = p[5:].split(':')
                if len(sub) >= 2:
                    try:
                        fail_amt = int(sub[0])
                        fail_scope = 'team' if sub[1].lower() == 'team' else 'leader'
                    except ValueError:
                        pass
            elif p.isdigit():
                faction_rep = int(p)
            else:
                faction_name = p or None
        try:
            due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
            due_dt = timezone.make_aware(datetime.combine(due_date, datetime.min.time()))
        except ValueError:
            self.caller.msg("Due date format: YYYY-MM-DD")
            return

        from world.factions.models import Faction as FactionModel
        faction = None
        if faction_name:
            facs = FactionModel.objects.filter(name__iexact=faction_name)
            if facs.exists():
                faction = facs.first()
                if not _can_post_faction_mission(self.caller, faction):
                    self.caller.msg("You cannot create missions for this faction.")
                    return
            else:
                self.caller.msg(f"Faction '{faction_name}' not found.")
                return
        elif not _can_post_mission(self.caller):
            self.caller.msg("Only staff, Fixers, faction heads, or designated mission posters can create missions.")
            return

        is_staff = _is_staff(self.caller)
        is_fixer_or_faction = _is_fixer(self.caller) or (faction and _can_post_faction_mission(self.caller, faction))
        if not is_staff and is_fixer_or_faction:
            total_rep = rep + faction_rep
            if total_rep > services.FIXER_REP_CAP:
                self.caller.msg(f"Fixers and faction posters can offer max {services.FIXER_REP_CAP} total rep.")
                return
            if not pod and money > 0:
                bal = CharacterMoneyService.get_balance(self.caller)
                if bal < money:
                    self.caller.msg(f"Insufficient funds. You have {bal} eb, need {money}.")
                    return
                CharacterMoneyService.spend_money(self.caller, money)

        poster_account = getattr(self.caller, 'account', None)
        mission = Mission.objects.create(
            name=name,
            description=desc,
            posted_by=self.caller,
            posted_by_staff=is_staff,
            posted_date=timezone.now(),
            due_date=due_dt,
            money_amount=money,
            money_pay_on_delivery=pod,
            rep_amount=rep,
            faction_rep_amount=faction_rep,
            faction=faction,
            faction_visibility='faction_only' if faction_only and faction else 'public',
            failure_penalty_amount=fail_amt,
            failure_penalty_scope=fail_scope,
            status='open'
        )
        job = services.create_mission_job(mission, poster_account) if poster_account else None
        self.caller.msg(f"Mission #{mission.id} created." + (f" Job #{job.id} linked." if job else ""))

    def cmd_modify(self):
        """Staff/Fixer: modify mission. Usage: mission/modify <#>=<field> <value>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/modify <#>=<field> <value>")
            self.caller.msg("Fields: name, description, due_date (YYYY-MM-DD). Staff can also modify money, rep, failure_penalty.")
            return
        mid, rest = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        poster = mission.posted_by
        if poster != self.caller and not _is_staff(self.caller):
            self.caller.msg("You cannot modify this mission.")
            return
        parts = rest.strip().split(None, 1)
        if len(parts) < 2:
            self.caller.msg("Provide field and value.")
            return
        field, value = parts[0].lower(), parts[1].strip()
        is_staff = _is_staff(self.caller)
        if field == 'name':
            mission.name = value[:255]
            mission.save()
            self.caller.msg("Name updated.")
        elif field == 'description':
            mission.description = value
            mission.save()
            self.caller.msg("Description updated.")
        elif field == 'due_date':
            try:
                d = datetime.strptime(value, "%Y-%m-%d").date()
                mission.due_date = timezone.make_aware(datetime.combine(d, datetime.min.time()))
                mission.save()
                self.caller.msg("Due date updated.")
            except ValueError:
                self.caller.msg("Use YYYY-MM-DD format.")
        elif is_staff:
            if field == 'money':
                mission.money_amount = int(value)
                mission.save()
                self.caller.msg("Money amount updated.")
            elif field == 'rep':
                mission.rep_amount = int(value)
                mission.save()
                self.caller.msg("Rep amount updated.")
            elif field == 'failure_penalty' and ':' in value:
                amt, scope = value.split(':', 1)
                mission.failure_penalty_amount = int(amt)
                mission.failure_penalty_scope = 'team' if scope.strip().lower() == 'team' else 'leader'
                mission.save()
                self.caller.msg("Failure penalty updated.")
            else:
                self.caller.msg("Unknown field or insufficient permission.")
        else:
            self.caller.msg("Fixers can only modify name and description.")

    def cmd_faction(self):
        """Set mission's faction. Staff: any; Fixers: only if faction member; Faction heads: own faction (or if member of another)."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/faction <#>=<faction name>")
            return
        mid, faction_name = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        from world.factions.models import Faction as FactionModel
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name.strip())
        except FactionModel.DoesNotExist:
            self.caller.msg(f"Faction '{faction_name}' not found.")
            return
        can_set = False
        if _is_staff(self.caller):
            can_set = True
        elif _is_fixer(self.caller) and is_faction_member(self.caller, faction):
            can_set = True
        elif is_faction_head(self.caller, faction):
            can_set = True  # Own faction
        elif is_faction_member(self.caller, faction):
            can_set = True  # Member of target faction (e.g. faction head of A, member of B)
        if not can_set:
            self.caller.msg("Only staff, faction heads (for own faction), fixers in the faction, or members of the target faction can set mission faction.")
            return
        mission.faction = faction
        mission.save()
        services.mission_add_comment_and_mail(mission, self.caller.key, f"Mission faction set to {faction.name}.")
        self.caller.msg(f"Mission #{mission.id} faction set to {faction.name}.")

    def cmd_fixer(self):
        """Staff: assign an NPC as the mission fixer. NPC fixers bypass payout requirements."""
        if not _is_staff(self.caller):
            self.caller.msg("Only staff can assign an NPC as mission fixer.")
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/fixer <#>=<npc name>")
            return
        mid, npc_name = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        npc = _get_npc_for_arg(self.caller, npc_name.strip())
        if not npc:
            self.caller.msg(f"NPC '{npc_name}' not found.")
            return
        if getattr(npc.db, 'npc_type', 'minor') != 'major':
            self.caller.msg("Only major NPCs can be assigned as mission fixers.")
            return
        mission.posted_by = npc
        mission.posted_by_staff = True  # NPC fixers bypass payout/rep restrictions
        # NPCs cannot post gear or vouchers as rewards - clear them
        if mission.voucher_rewards or mission.item_rewards:
            mission.voucher_rewards = []
            mission.item_rewards = []
            self.caller.msg("|yNote: Cleared voucher/item rewards (NPCs cannot offer these).|n")
        mission.save()
        services.sync_mission_to_job(mission)
        display = _get_character_display_name(npc)
        services.mission_add_comment_and_mail(mission, self.caller.key, f"Fixer assigned: {display} (NPC)")
        self.caller.msg(f"Mission #{mission.id} fixer set to {display} (NPC - bypasses payout requirements).")

    def cmd_reward(self):
        """Staff: add/remove apartment rewards on staff missions. Only staff missions can have apartment rewards."""
        if not _is_staff(self.caller):
            self.caller.msg("Only staff can set mission apartment rewards.")
            return
        if not self.args:
            self.caller.msg("Usage: mission/reward <#>=apartment:#id[,apartment:#id,...] | /clear | /remove=#id,#id")
            return
        from typeclasses.rental import RentableRoom

        if "/clear" in self.args:
            mid = self.args.replace("/clear", "").strip()
            mission = self._get_mission(mid)
            if not mission:
                self.caller.msg("Mission not found.")
                return
            if not mission.posted_by_staff:
                self.caller.msg("Only staff missions can have apartment rewards.")
                return
            mission.apartment_rewards = []
            mission.save()
            self.caller.msg(f"Cleared apartment rewards for mission #{mission.id}.")
            return

        if "/remove=" in self.args:
            mid, rest = self.args.split("/remove=", 1)
            mid = mid.strip()
            mission = self._get_mission(mid)
            if not mission:
                self.caller.msg("Mission not found.")
                return
            if not mission.posted_by_staff:
                self.caller.msg("Only staff missions can have apartment rewards.")
                return
            ids_str = rest.strip()
            to_remove = []
            for part in ids_str.split(","):
                part = part.strip().strip("#")
                if part.isdigit():
                    to_remove.append(int(part))
            rewards = list(mission.apartment_rewards or [])
            for rid in to_remove:
                if rid in rewards:
                    rewards.remove(rid)
            mission.apartment_rewards = rewards
            mission.save()
            self.caller.msg(f"Mission #{mission.id} apartment rewards: {len(rewards)} remaining.")
            return

        if "=" not in self.args:
            self.caller.msg("Usage: mission/reward <#>=apartment:#id[,apartment:#id,...] | /clear | /remove=#id,#id")
            return

        mid, rest = self.args.split("=", 1)
        mission = self._get_mission(mid.strip())
        if not mission:
            self.caller.msg("Mission not found.")
            return
        if not mission.posted_by_staff:
            self.caller.msg("Only staff missions can have apartment rewards.")
            return

        apartment_rewards = list(mission.apartment_rewards or [])
        for part in rest.split(","):
            part = part.strip()
            if not part.lower().startswith("apartment:"):
                continue
            id_str = part[10:].strip().strip("#")
            if not id_str.isdigit():
                continue
            objs = search_object(f"#{id_str}")
            if not objs:
                self.caller.msg(f"Object #{id_str} not found.")
                continue
            obj = objs[0]
            main = obj.get_main_room() if hasattr(obj, 'get_main_room') else obj
            if not isinstance(main, RentableRoom):
                self.caller.msg(f"#{main.id} is not a rentable apartment.")
                continue
            main_id = main.id
            if main_id not in apartment_rewards:
                apartment_rewards.append(main_id)
        mission.apartment_rewards = apartment_rewards
        mission.save()
        self.caller.msg(f"Mission #{mission.id} apartment rewards: {len(apartment_rewards)} apartment(s).")

    def cmd_seeds(self):
        """List story seeds. Fixers see available; staff see all."""
        if not _is_fixer(self.caller) and not _is_staff(self.caller):
            self.caller.msg("Only Fixers and staff can view the story seed board.")
            return
        if _is_staff(self.caller):
            seeds = StorySeed.objects.all().order_by('-created_at')[:50]
        else:
            seeds = StorySeed.objects.filter(status='available').order_by('-created_at')
        if not seeds:
            self.caller.msg("No story seeds available.")
            return
        W = 80
        out = header("Story Seeds (Fixer Board)", width=W, fillchar="|b-|n")
        out += f"|y{'ID':<6}{'Name':<24}{'Budget':<8}{'Faction':<14}{'Status':<12}|n\n"
        for s in seeds:
            name = (s.name[:21] + "...") if len(s.name) > 24 else s.name
            fac = (s.faction.name[:12] + "..") if s.faction else "---"
            out += f"|w{s.id:<6}{name:<24}{s.max_budget:<8}{fac:<14}{s.status:<12}|n\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def cmd_seed(self):
        """View story seed details."""
        if not self.args:
            self.caller.msg("Usage: mission/seed <#>")
            return
        if not _is_fixer(self.caller) and not _is_staff(self.caller):
            self.caller.msg("Only Fixers and staff can view story seeds.")
            return
        try:
            seed = StorySeed.objects.get(id=int(self.args.strip()))
        except (ValueError, StorySeed.DoesNotExist):
            self.caller.msg("Story seed not found.")
            return
        if seed.status == 'claimed' and not _is_staff(self.caller):
            self.caller.msg("That seed has been claimed.")
            return
        out = header(f"Story Seed #{seed.id}: {seed.name}", width=78, fillchar="|b-|n") + "\n"
        out += f"|cMax Budget:|n {seed.max_budget} eb\n"
        out += f"|cStatus:|n {seed.status}\n"
        out += f"|cRep:|n {seed.rep_amount}"
        if seed.faction:
            if seed.faction_rep_amount:
                out += f", {seed.faction_rep_amount} {seed.faction.name} rep"
            else:
                out += f" ({seed.faction.name})"
        elif seed.faction_rep_amount:
            out += f" (faction rep: {seed.faction_rep_amount})"
        out += "\n"
        v_rewards = seed.voucher_rewards or []
        i_rewards = seed.item_rewards or []
        out += f"|cRewards:|n {len(v_rewards)} vouchers, {len(i_rewards)} items"
        if v_rewards or i_rewards:
            from evennia.objects.models import ObjectDB
            all_refs = [(rid, "voucher") for rid in v_rewards] + [(rid, "item") for rid in i_rewards]
            for rid, label in all_refs:
                try:
                    obj = ObjectDB.objects.get(id=rid)
                except ObjectDB.DoesNotExist:
                    out += f"\n  |c#{rid}|n (not found)"
                    continue
                vouch_key = getattr(obj, 'key', None) or str(obj)
                if hasattr(obj, 'get_items') and callable(obj.get_items):
                    items = obj.get_items()
                    names = [f"{it.get('name', '?')} x{it.get('quantity', 1)}" for it in items]
                    contents = ", ".join(names) if names else "(empty)"
                    out += f"\n  |c#{rid}|n {vouch_key}: {contents}"
                else:
                    out += f"\n  |c#{rid}|n {vouch_key}"
        out += "\n"
        out += divider("Description", width=78, fillchar="-", color="|b", text_color="|c") + "\n"
        out += seed.description + "\n"
        out += footer(width=78, fillchar="|b-|n")
        self.caller.msg(out)

    def cmd_seed_create(self):
        """Staff: create a story seed for fixers."""
        if not _is_staff(self.caller):
            self.caller.msg("Only staff can create story seeds.")
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/seed/create <name>=<desc>/<max_budget>[/rep][/FactionName][/faction_rep][/voucher:#id][/item:#id]")
            return
        name, rest = self.args.split("=", 1)
        name = name.strip()
        parts = rest.split("/")
        if len(parts) < 2:
            self.caller.msg("Provide: description/max_budget")
            return
        desc = parts[0].strip()
        try:
            max_budget = int(parts[1].strip())
        except ValueError:
            self.caller.msg("Max budget must be a number.")
            return
        rep = 0
        faction_rep = 0
        faction = None
        voucher_rewards = []
        item_rewards = []
        from world.factions.models import Faction as FactionModel
        for p in parts[2:]:
            p = p.strip()
            if p.isdigit():
                if faction_rep == 0 and rep == 0:
                    rep = int(p)
                else:
                    faction_rep = int(p)
            elif p.lower().startswith("voucher:"):
                try:
                    vid_str = p[8:].lstrip("#").strip()
                    if vid_str.isdigit():
                        voucher_rewards.append(int(vid_str))
                except ValueError:
                    pass
            elif p.lower().startswith("item:"):
                try:
                    iid_str = p[5:].lstrip("#").strip()
                    if iid_str.isdigit():
                        item_rewards.append(int(iid_str))
                except ValueError:
                    pass
            elif p:
                facs = FactionModel.objects.filter(name__iexact=p)
                if facs.exists():
                    faction = facs.first()
        acc = getattr(self.caller, 'account', None)
        seed = StorySeed.objects.create(
            name=name,
            description=desc,
            max_budget=max_budget,
            rep_amount=rep,
            faction_rep_amount=faction_rep,
            faction=faction,
            voucher_rewards=voucher_rewards,
            item_rewards=item_rewards,
            created_by=acc,
            status='available'
        )
        reward_note = ""
        if voucher_rewards or item_rewards:
            reward_note = f" ({len(voucher_rewards)} vouchers, {len(item_rewards)} items)"
        self.caller.msg(f"Story seed #{seed.id} created with max budget {max_budget} eb{reward_note}.")

    def cmd_seed_reward(self):
        """Staff: add, remove, or clear voucher/item rewards on a story seed."""
        if not _is_staff(self.caller):
            self.caller.msg("Only staff can set seed rewards.")
            return
        if not self.args:
            self.caller.msg("Usage: mission/seed/reward <#>=voucher:#id[,item:#id] | /clear | /remove=#id,#id")
            return
        # Parse seed id - may be "2", "2/clear", "2/remove=id,id", or "2=voucher:#id"
        raw = self.args.strip()
        do_clear = "/clear" in raw or raw.endswith("clear")
        do_remove = "/remove" in raw
        sid = None
        rest = ""
        if "=" in raw:
            sid, rest = raw.split("=", 1)
        else:
            sid = raw
        sid = sid.strip()
        if "/" in sid:
            sid = sid.split("/")[0].strip()
        try:
            seed = StorySeed.objects.get(id=int(sid))
        except (ValueError, StorySeed.DoesNotExist):
            self.caller.msg("Story seed not found.")
            return
        voucher_rewards = list(seed.voucher_rewards or [])
        item_rewards = list(seed.item_rewards or [])

        if do_clear:
            voucher_rewards = []
            item_rewards = []
        elif do_remove:
            if "=" in raw:
                rest = raw.split("=", 1)[1]
            to_remove = []
            for part in rest.split(","):
                part = part.strip().lstrip("#").strip()
                if part.isdigit():
                    to_remove.append(int(part))
            for rid in to_remove:
                if rid in voucher_rewards:
                    voucher_rewards.remove(rid)
                if rid in item_rewards:
                    item_rewards.remove(rid)
        else:
            for part in rest.split(","):
                part = part.strip()
                if part.lower().startswith("voucher:"):
                    try:
                        vid_str = part[8:].lstrip("#").strip()
                        if vid_str.isdigit():
                            voucher_rewards.append(int(vid_str))
                    except ValueError:
                        pass
                elif part.lower().startswith("item:"):
                    try:
                        iid_str = part[5:].lstrip("#").strip()
                        if iid_str.isdigit():
                            item_rewards.append(int(iid_str))
                    except ValueError:
                        pass
        seed.voucher_rewards = voucher_rewards
        seed.item_rewards = item_rewards
        seed.save()
        self.caller.msg(f"Seed #{seed.id} rewards updated: {len(voucher_rewards)} vouchers, {len(item_rewards)} items.")

    def cmd_grab(self):
        """Fixer: grab a story seed and create a mission. Payout must be <= max_budget."""
        if not _is_fixer(self.caller):
            self.caller.msg("Only Fixers can grab story seeds.")
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: mission/grab <seed#>=<name>/<desc>/<due>/<payout>/<rep>[/pod][/faction_rep][/FactionName][/faction_only]")
            self.caller.msg("Payout is what players split; your cut = seed max_budget - payout.")
            return
        sid, rest = self.args.split("=", 1)
        try:
            seed = StorySeed.objects.get(id=int(sid.strip()), status='available')
        except (ValueError, StorySeed.DoesNotExist):
            self.caller.msg("Available story seed not found.")
            return
        parts = rest.split("/")
        if len(parts) < 5:
            self.caller.msg("Provide: name/description/due_date/payout/rep")
            return
        name = parts[0].strip()
        desc = parts[1].strip()
        due_str = parts[2].strip()
        try:
            payout = int(parts[3].strip())
            rep = int(parts[4].strip())
        except ValueError:
            self.caller.msg("Payout and rep must be numbers.")
            return
        if payout > seed.max_budget:
            self.caller.msg(f"Payout {payout} exceeds seed max budget {seed.max_budget}. Your cut = budget - payout.")
            return
        try:
            due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
            due_dt = timezone.make_aware(datetime.combine(due_date, datetime.min.time()))
        except ValueError:
            self.caller.msg("Due date format: YYYY-MM-DD")
            return
        faction_rep = 0
        pod = False
        faction_name = None
        faction_only = False
        for p in parts[5:]:
            p = p.strip()
            if p.lower() == 'pod':
                pod = True
            elif p.lower() == 'faction_only':
                faction_only = True
            elif p.isdigit():
                faction_rep = int(p)
            elif p:
                faction_name = p
        from world.factions.models import Faction as FactionModel
        faction = None
        if faction_name:
            facs = FactionModel.objects.filter(name__iexact=faction_name)
            if facs.exists():
                faction = facs.first()
                if not _can_post_faction_mission(self.caller, faction):
                    self.caller.msg("You cannot create missions for this faction.")
                    return
        elif seed.faction and seed.faction_rep_amount:
            faction = seed.faction
            if faction_rep == 0:
                faction_rep = seed.faction_rep_amount
        total_rep = rep + faction_rep
        if total_rep > services.FIXER_REP_CAP:
            self.caller.msg(f"Fixers can offer max {services.FIXER_REP_CAP} total rep.")
            return
        fixer_cut = seed.max_budget - payout
        poster_account = getattr(self.caller, 'account', None)
        mission = Mission.objects.create(
            name=name,
            description=desc,
            posted_by=self.caller,
            posted_by_staff=False,
            posted_date=timezone.now(),
            due_date=due_dt,
            money_amount=payout,
            money_pay_on_delivery=pod,
            rep_amount=rep,
            faction_rep_amount=faction_rep,
            faction=faction,
            faction_visibility='faction_only' if faction_only and faction else 'public',
            voucher_rewards=list(seed.voucher_rewards or []),
            item_rewards=list(seed.item_rewards or []),
            source_seed=seed,
            status='open'
        )
        seed.status = 'claimed'
        seed.claimed_by = self.caller
        seed.claimed_at = timezone.now()
        seed.save()
        job = services.create_mission_job(mission, poster_account) if poster_account else None
        self.caller.msg(
            f"Grabbed seed #{seed.id}, created mission #{mission.id}. "
            f"Payout: {payout} eb to players | Your cut: {fixer_cut} eb on completion."
            + (f" Job #{job.id} linked." if job else "")
        )

    def cmd_mine(self):
        """List missions you're on."""
        from django.db.models import Q
        q = Q(team_members__character=self.caller) | Q(posted_by=self.caller)
        acc = getattr(self.caller, 'account', None)
        if acc:
            q |= Q(gm=acc)
        missions = Mission.objects.filter(q, status__in=['open', 'active']).distinct()
        if not missions:
            self.caller.msg("You are not on any active missions.")
            return
        W = 78
        out = header("Your Missions", width=W, fillchar="|b-|n")
        out += f"|y{'ID':<6}{'Name':<30}{'Role':<12}{'Status':<12}|n\n"
        for m in missions:
            mtm = MissionTeamMember.objects.filter(mission=m, character=self.caller).first()
            role = "Lead" if mtm and mtm.order == 0 else ("Team" if mtm else ("GM" if acc and m.gm == acc else "Poster"))
            name = (m.name[:27] + "...") if len(m.name) > 30 else m.name
            out += f"|w{m.id:<6}{name:<30}{role:<12}{m.status:<12}|n\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

