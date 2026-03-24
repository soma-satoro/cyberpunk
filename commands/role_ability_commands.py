"""
Role-ability gameplay commands:
- backup  (Lawman)
- impact  (Rockerboy)
- scoop   (Media)
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import gametime
from evennia.server.models import ServerConfig

from world.improvement_points import get_character_stat_value
from world.utils.character_utils import is_character_approved


def _normalize_key(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _role_rank(caller, key: str) -> int:
    try:
        return int(get_character_stat_value(caller, key) or 0)
    except Exception:
        return 0


class CmdBackup(MuxCommand):
    """
    Lawman Backup call and reference.

    Usage:
      backup
      backup <tier>
      backup/info
      backup/log

    Notes:
      - Roll 1d10 <= Backup rank to get a response.
      - On response, roll 1d6 for ETA in rounds.
      - If ETA roll is 6, backup escalates by one tier (rank 10 gets two groups).
    """

    key = "backup"
    locks = "cmd:all()"
    help_category = "Combat"

    def _profile_for_rank(self, rank: int) -> Dict[str, str]:
        if rank <= 2:
            return {
                "label": "Corporate Security",
                "unit": "4 local renta-cops on foot",
                "combat_number": "8",
                "sp": "7",
                "hp": "20",
                "move_body": "4",
                "gear": "Heavy Pistols, Kevlar",
            }
        if rank <= 4:
            return {
                "label": "Local Beat Cops",
                "unit": "4 local cops in 2 Compact Groundcars",
                "combat_number": "10",
                "sp": "7",
                "hp": "25",
                "move_body": "5",
                "gear": "Heavy Pistols, Kevlar",
            }
        if rank <= 7:
            return {
                "label": "Sheriff Department",
                "unit": "2 county mounties in High Performance Groundcar",
                "combat_number": "14",
                "sp": "13",
                "hp": "35",
                "move_body": "4",
                "gear": "Heavy Pistols, Assault Rifles, Heavy Armorjack",
            }
        if rank == 8:
            return {
                "label": "Recovery Zone Marshal",
                "unit": "1 marshal on Superbike",
                "combat_number": "16",
                "sp": "15",
                "hp": "50",
                "move_body": "6",
                "gear": "V Heavy Pistol, Assault Rifle, Grenade Launcher, Flak",
            }
        if rank == 9:
            return {
                "label": "C-SWAT",
                "unit": "2 psycho squad hitters via AV-4",
                "combat_number": "15",
                "sp": "18",
                "hp": "35",
                "move_body": "4",
                "gear": "Assault Rifles, Rocket Launchers, Metalgear",
            }
        return {
            "label": "National/Interpol/Netwatch",
            "unit": "2 national-level hitters via AV-4",
            "combat_number": "14",
            "sp": "11",
            "hp": "35",
            "move_body": "6",
            "gear": "V Heavy Pistols, Assault Rifles, Light Armorjack",
        }

    def _render_profile(self, rank: int) -> str:
        p = self._profile_for_rank(rank)
        return (
            f"|wTier {rank}:|n {p['label']}\n"
            f"  Unit: {p['unit']}\n"
            f"  Combat Number/SP/HP/MOVE&BODY: {p['combat_number']} / {p['sp']} / {p['hp']} / {p['move_body']}\n"
            f"  Gear: {p['gear']}"
        )

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using backup.")
            return

        rank = _role_rank(self.caller, "backup")
        if rank <= 0:
            self.caller.msg("You do not have the Backup role ability.")
            return

        if "info" in (self.switches or []):
            lines = [f"|wYour Backup rank:|n {rank}", ""]
            for tier in (2, 4, 7, 8, 9, 10):
                lines.append(self._render_profile(tier))
                lines.append("")
            self.caller.msg("\n".join(lines).strip())
            return

        if "log" in (self.switches or []):
            log = list(getattr(self.caller.db, "backup_call_log", []) or [])
            if not log:
                self.caller.msg("No backup call log yet.")
                return
            lines = ["|wRecent Backup Calls|n"]
            for row in log[-10:]:
                lines.append(
                    f"- t={row.get('time')} req:{row.get('requested_tier')} got:{row.get('actual_tier')} "
                    f"eta:{row.get('eta_rounds')} success:{row.get('success')}"
                )
            self.caller.msg("\n".join(lines))
            return

        requested_tier = rank
        if self.args:
            try:
                requested_tier = int(self.args.strip())
            except ValueError:
                self.caller.msg("Usage: backup [tier], backup/info, backup/log")
                return
            if requested_tier < 1 or requested_tier > rank:
                self.caller.msg(f"You can request backup from tier 1 to your current rank ({rank}).")
                return

        now = int(gametime.gametime())
        last_call = int(getattr(self.caller.db, "backup_last_call_ts", 0) or 0)
        if now - last_call < 30:
            self.caller.msg("You just called for backup. Give it a moment before calling again.")
            return

        self.caller.db.backup_last_call_ts = now
        response_roll = random.randint(1, 10)
        success = response_roll <= rank
        if not success:
            self.caller.msg(
                f"You call for backup (roll {response_roll} vs rank {rank}) but nobody responds this turn."
            )
            self._append_log(now, requested_tier, requested_tier, 0, False)
            return

        eta = random.randint(1, 6)
        groups: List[int]
        actual_tier = requested_tier
        if eta == 6 and rank == 10:
            groups = [10, 10]
            actual_tier = 10
        elif eta == 6:
            actual_tier = min(rank, requested_tier + 1)
            groups = [actual_tier]
        else:
            groups = [requested_tier]

        self._append_log(now, requested_tier, actual_tier, eta, True)
        self.caller.db.backup_pending = {
            "requested_tier": requested_tier,
            "actual_groups": groups,
            "eta_rounds": eta,
            "called_at": now,
        }

        # If scene combat is active, queue arrivals into initiative tracker.
        room = getattr(self.caller, "location", None)
        queued = False
        if room is not None:
            try:
                from commands.combat_system import queue_backup_arrival
                queued = bool(
                    queue_backup_arrival(
                        room,
                        source_name=self.caller.key,
                        tiers=groups,
                        eta_rounds=eta,
                        team="backup",
                    )
                )
            except Exception:
                queued = False

        if len(groups) == 2:
            gtxt = " and ".join(self._profile_for_rank(g)["label"] for g in groups)
            self.caller.msg(
                f"|gBackup confirmed!|n ETA: {eta} rounds. Special escalation: two groups inbound ({gtxt})."
                + (" |x(Queued into active combat initiative.)|n" if queued else "")
            )
            return

        special = " |y(ETA 6 escalation: higher tier responding)|n" if eta == 6 else ""
        self.caller.msg(
            f"|gBackup confirmed!|n ETA: {eta} rounds.{special}\n"
            f"{self._render_profile(groups[0])}"
            + ("\n|xQueued into active combat initiative tracker.|n" if queued else "")
        )

    def _append_log(self, now: int, req: int, got: int, eta: int, success: bool):
        log = list(getattr(self.caller.db, "backup_call_log", []) or [])
        log.append(
            {
                "time": now,
                "requested_tier": req,
                "actual_tier": got,
                "eta_rounds": eta,
                "success": bool(success),
            }
        )
        self.caller.db.backup_call_log = log[-50:]


class CmdImpact(MuxCommand):
    """
    Rockerboy Charismatic Impact workflow.

    Usage:
      impact
      impact/make <single|small|huge>=<target>
      impact/ask <target>=<single|small|huge>:<favor text>
      impact/fan <target>[=<single|small|huge>]      (manual fan mark)
      impact/unfan <target>
    """

    key = "impact"
    aliases = ["charisma", "fans"]
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    _DV_BY_SIZE = {"single": 8, "small": 10, "huge": 12}

    def _is_in_combat(self) -> bool:
        room = getattr(self.caller, "location", None)
        if not room:
            return False
        return bool(getattr(room.ndb, "combat_state", None))

    def _resolve_npc_target(self, query: str):
        room = getattr(self.caller, "location", None)
        if not room:
            self.caller.msg("You are nowhere.")
            return None
        q = _normalize_key(query)
        if not q:
            return None
        matches = [obj for obj in room.contents if q in _normalize_key(getattr(obj, "key", ""))]
        if not matches:
            self.caller.msg("No matching target here.")
            return None
        exact = [obj for obj in matches if _normalize_key(getattr(obj, "key", "")) == q]
        target = exact[0] if len(exact) == 1 else matches[0]
        if bool(getattr(target, "has_account", False)):
            self.caller.msg("Charismatic Impact cannot target PCs. Choose an NPC target.")
            return None
        return target

    def _fan_store(self) -> Dict[str, Dict]:
        data = getattr(self.caller.db, "rocker_fans", None)
        if not isinstance(data, dict):
            data = {}
            self.caller.db.rocker_fans = data
        return data

    def _cooldowns(self) -> Dict[str, int]:
        data = getattr(self.caller.db, "rocker_favor_cooldowns", None)
        if not isinstance(data, dict):
            data = {}
            self.caller.db.rocker_favor_cooldowns = data
        return data

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using impact.")
            return

        rank = _role_rank(self.caller, "charismatic_impact")
        if rank <= 0:
            self.caller.msg("You do not have Charismatic Impact.")
            return

        if not self.switches:
            fans = self._fan_store()
            lines = [f"|wCharismatic Impact Rank:|n {rank}", f"|wKnown fan tags:|n {len(fans)}"]
            for tag, info in list(fans.items())[-15:]:
                display = info.get("name") or tag
                lines.append(f"- {display} ({info.get('size', 'single')})")
            lines.extend(
                [
                    "",
                    "Use |wimpact/make <single|small|huge>=<target>|n to make new fans.",
                    "Use |wimpact/ask <target>=<single|small|huge>:<favor>|n to ask for favors.",
                ]
            )
            self.caller.msg("\n".join(lines))
            return

        sw = self.switches[0].lower()
        if sw == "make":
            self._make_fans(rank)
            return
        if sw == "ask":
            self._ask_favor(rank)
            return
        if sw == "fan":
            self._manual_fan()
            return
        if sw == "unfan":
            self._unfan()
            return

        self.caller.msg("Usage: impact, impact/make, impact/ask, impact/fan, impact/unfan")

    def _parse_size(self, raw: str) -> str:
        key = _normalize_key(raw)
        if key in ("single", "one", "person"):
            return "single"
        if key in ("small", "group", "group6"):
            return "small"
        if key in ("huge", "crowd", "mass"):
            return "huge"
        return ""

    def _size_allowed(self, rank: int, size: str) -> Tuple[bool, str]:
        if size == "huge" and rank <= 2:
            return False, "At rank 1-2 you do not yet have huge-group impact."
        return True, ""

    def _make_fans(self, rank: int):
        if self._is_in_combat():
            self.caller.msg("You cannot use Charismatic Impact to make fans in combat.")
            return
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: impact/make <single|small|huge>=<target>")
            return
        size_raw, target_raw = [x.strip() for x in self.args.split("=", 1)]
        size = self._parse_size(size_raw)
        if not size:
            self.caller.msg("Usage: impact/make <single|small|huge>=<target>")
            return
        target_obj = self._resolve_npc_target(target_raw)
        if not target_obj:
            return
        target = f"npc:{target_obj.id}"
        ok, err = self._size_allowed(rank, size)
        if not ok:
            self.caller.msg(err)
            return

        dv = self._DV_BY_SIZE[size]
        roll = rank + random.randint(1, 10)
        if roll > dv:
            fans = self._fan_store()
            fans[target] = {"size": size, "since": int(gametime.gametime()), "name": target_obj.key}
            self.caller.db.rocker_fans = fans
            self.caller.msg(f"|gSuccess.|n You win over |w{target_obj.key}|n as |w{size}|n fans ({roll} vs DV {dv}).")
        else:
            self.caller.msg(f"|rFailure.|n You fail to convert |w{target_obj.key}|n this time ({roll} vs DV {dv}).")

    def _ask_favor(self, rank: int):
        if self._is_in_combat():
            self.caller.msg("You cannot use Charismatic Impact favors in combat.")
            return
        if "=" not in (self.args or "") or ":" not in self.args:
            self.caller.msg("Usage: impact/ask <target>=<single|small|huge>:<favor text>")
            return
        target_raw, right = [x.strip() for x in self.args.split("=", 1)]
        size_raw, favor = [x.strip() for x in right.split(":", 1)]
        target_obj = self._resolve_npc_target(target_raw)
        if not target_obj:
            return
        target_key = f"npc:{target_obj.id}"
        size = self._parse_size(size_raw)
        if not size or not favor:
            self.caller.msg("Usage: impact/ask <target>=<single|small|huge>:<favor text>")
            return

        fans = self._fan_store()
        if target_key not in fans:
            self.caller.msg(f"{target_obj.key} is not in your fan list yet.")
            return

        ok, err = self._size_allowed(rank, size)
        if not ok:
            self.caller.msg(err)
            return

        cooldowns = self._cooldowns()
        cd_key = f"{target_key}|{size}|{_normalize_key(favor)}"
        now = int(gametime.gametime())
        until = int(cooldowns.get(cd_key, 0) or 0)
        if until > now:
            self.caller.msg("Those fans recently refused that same favor. You must wait about a week before retrying.")
            return

        dv = self._DV_BY_SIZE[size]
        roll = rank + random.randint(1, 10)
        if roll > dv:
            self.caller.msg(
                f"|gSuccess.|n {target_obj.key} puts in best effort for: |w{favor}|n ({roll} vs DV {dv})."
            )
        else:
            cooldowns[cd_key] = now + 7 * 24 * 60 * 60
            self.caller.db.rocker_favor_cooldowns = cooldowns
            self.caller.msg(
                f"|rFailure.|n The ask falls flat ({roll} vs DV {dv}). "
                f"You cannot ask these same fans for this same favor again for a week."
            )

    def _manual_fan(self):
        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg("Usage: impact/fan <target>[=<single|small|huge>]")
            return
        if "=" in raw:
            target_raw, size_raw = [x.strip() for x in raw.split("=", 1)]
            size = self._parse_size(size_raw) or "single"
        else:
            target_raw = raw
            size = "single"
        target_obj = self._resolve_npc_target(target_raw)
        if not target_obj:
            self.caller.msg("Usage: impact/fan <target>[=<single|small|huge>]")
            return
        fans = self._fan_store()
        target_key = f"npc:{target_obj.id}"
        fans[target_key] = {"size": size, "since": int(gametime.gametime()), "name": target_obj.key}
        self.caller.db.rocker_fans = fans
        self.caller.msg(f"Added fan tag |w{target_obj.key}|n ({size}).")

    def _unfan(self):
        target_obj = self._resolve_npc_target(self.args or "")
        if not target_obj:
            self.caller.msg("Usage: impact/unfan <target>")
            return
        target = f"npc:{target_obj.id}"
        fans = self._fan_store()
        if target in fans:
            del fans[target]
            self.caller.db.rocker_fans = fans
            self.caller.msg(f"Removed fan tag |w{target_obj.key}|n.")
        else:
            self.caller.msg(f"No fan tag found for |w{target_obj.key}|n.")


class CmdScoop(MuxCommand):
    """
    Media Credibility command: rumors and publishing.

    Usage:
      scoop
      scoop/passive
      scoop/rumor [vague|typical|substantial|detailed]
      scoop/hear
      scoop/follow <lead_id>
      scoop/publish <topic>[=<evidence_count>][:<article_text>]
      scoop/publish/newinfo <topic>[=<evidence_count>][:<article_text>]
    """

    key = "scoop"
    aliases = ["media", "rumor"]
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    _RUMOR_TABLE = {
        "vague": {"passive": 7, "active": 13},
        "typical": {"passive": 9, "active": 15},
        "substantial": {"passive": 11, "active": 17},
        "detailed": {"passive": 13, "active": 21},
    }
    _ORDER = ("vague", "typical", "substantial", "detailed")
    _EVIDENCE_BY_TIER = {"vague": 1, "typical": 1, "substantial": 2, "detailed": 3}
    _SHARED_RUMOR_KEY = "shared_rumor_feed"
    _FOLLOW_DV_BY_TIER = {"vague": 7, "typical": 9, "substantial": 11, "detailed": 13}
    _NET_TIERS = {"substantial", "detailed"}

    def _believability_chance(self, rank: int) -> int:
        if rank <= 2:
            return 2
        if rank <= 4:
            return 3
        if rank <= 6:
            return 4
        if rank <= 8:
            return 5
        if rank == 9:
            return 6
        return 7

    def _best_rumor_tier(self, total: int, mode: str) -> str:
        best = ""
        for tier in self._ORDER:
            dv = int(self._RUMOR_TABLE[tier][mode])
            if total > dv:
                best = tier
        return best

    def _evidence_pool(self) -> int:
        try:
            return max(0, int(getattr(self.caller.db, "media_evidence_pool", 0) or 0))
        except Exception:
            return 0

    def _award_evidence(self, tier: str, source: str):
        amount = int(self._EVIDENCE_BY_TIER.get(tier, 1))
        pool = self._evidence_pool() + amount
        self.caller.db.media_evidence_pool = pool
        plural = "" if amount == 1 else "s"
        self.caller.msg(
            f"|gEvidence gained:|n +{amount} point{plural} from {source} intel. "
            f"|wAvailable evidence:|n {pool}"
        )

    def _load_shared_rumors(self) -> List[Dict]:
        data = ServerConfig.objects.conf(self._SHARED_RUMOR_KEY, default=[]) or []
        return data if isinstance(data, list) else []

    def _save_shared_rumors(self, rumors: List[Dict]):
        ServerConfig.objects.conf(self._SHARED_RUMOR_KEY, rumors[-200:])

    def _pick_mystery_hook(self) -> Dict:
        """
        Select a currently open mystery to reference in street chatter.
        Returns a lightweight dict safe to persist in ServerConfig.
        """
        try:
            from world.mystery.models import Mystery

            mystery = Mystery.objects.filter(is_solved=False).order_by("?").first()
            if not mystery:
                return {}
            return {
                "mystery_id": int(mystery.id),
                "mystery_name": mystery.name,
                "mystery_hint": (mystery.starting_location_hint or mystery.public_description or "").strip()[:240],
            }
        except Exception:
            return {}

    def _pick_net_hook(self, tier: str) -> Dict:
        """
        Select a NET floor lead for higher-quality rumors.
        """
        if tier not in self._NET_TIERS:
            return {}
        try:
            from world.netrunning.models import NetFloorLead

            lead = NetFloorLead.objects.order_by("?").first()
            if not lead:
                return {}
            arch = getattr(lead, "architecture_object", None)
            return {
                "net_lead_id": int(lead.id),
                "net_architecture_id": int(lead.architecture_object_id),
                "net_architecture_key": getattr(arch, "key", "NET"),
                "net_floor": int(lead.floor_number),
                "net_label": lead.label,
            }
        except Exception:
            return {}

    def _share_rumor(self, tier: str, source: str):
        rumors = self._load_shared_rumors()
        now = int(gametime.gametime())
        next_id = int(rumors[-1]["id"]) + 1 if rumors else 1
        mystery_hook = self._pick_mystery_hook()
        net_hook = self._pick_net_hook(tier)
        hook = {}
        hook.update(mystery_hook)
        hook.update(net_hook)
        rumors.append(
            {
                "id": next_id,
                "tier": tier,
                "source": source,
                "origin": self.caller.key,
                "timestamp": now,
                "claimed_by": [],
                "hook": hook,
            }
        )
        self._save_shared_rumors(rumors)
        self.caller.msg(f"|xStreet chatter seeded:|n rumor lead #{next_id} enters circulation.")

    def _hear_shared_rumors(self):
        rumors = self._load_shared_rumors()
        if not rumors:
            self.caller.msg("No shared rumor leads are circulating right now.")
            return
        lines = ["|wShared Rumor Leads|n (newest first)"]
        for row in reversed(rumors[-10:]):
            hook = dict(row.get("hook", {}) or {})
            tags = []
            if hook.get("mystery_id"):
                tags.append("mystery")
            if hook.get("net_lead_id"):
                tags.append("net")
            tag_txt = f" [{' / '.join(tags)}]" if tags else ""
            lines.append(
                f"- #{row.get('id')} | {str(row.get('tier', 'vague')).title()} lead | "
                f"origin: {row.get('origin', 'unknown')}{tag_txt}"
            )
        lines.append("")
        lines.append("Use |wscoop/follow <lead_id>|n to chase one of these leads.")
        self.caller.msg("\n".join(lines))

    def _grant_mystery_rumor_benefits(self, target: Dict):
        hook = dict(target.get("hook", {}) or {})
        mid = int(hook.get("mystery_id") or 0)
        if mid <= 0:
            return
        try:
            from world.mystery.models import Mystery, MysteryClue, ClueExposure
            from world.mystery.services import follow_mystery_for_character

            mystery = Mystery.objects.filter(id=mid, is_solved=False).first()
            if not mystery:
                return
            follow_mystery_for_character(self.caller, mystery)

            # Soft assist: expose one first-step clue so player can start investigating.
            clue = (
                MysteryClue.objects.filter(mystery=mystery, required_clues__isnull=True, gating_obstacle__isnull=True)
                .order_by("discovery_priority", "id")
                .first()
            )
            if clue:
                ClueExposure.objects.get_or_create(character=self.caller, clue=clue)

            hint_row = {
                "mystery_id": mystery.id,
                "mystery": mystery.name,
                "hint": (hook.get("mystery_hint") or mystery.starting_location_hint or "").strip(),
                "time": int(gametime.gametime()),
                "source": target.get("origin", "unknown"),
            }
            hints = list(getattr(self.caller.db, "mystery_rumor_hints", []) or [])
            hints.append(hint_row)
            self.caller.db.mystery_rumor_hints = hints[-50:]

            msg = f"|cMystery thread connected:|n |w{mystery.name}|n."
            if hint_row["hint"]:
                msg += f" Start point: {hint_row['hint']}"
            msg += " (Check |w+mystery|n / |w+investigate/leads|n.)"
            self.caller.msg(msg)
        except Exception:
            return

    def _grant_net_rumor_benefits(self, target: Dict):
        hook = dict(target.get("hook", {}) or {})
        lead_id = int(hook.get("net_lead_id") or 0)
        arch_id = int(hook.get("net_architecture_id") or 0)
        floor = int(hook.get("net_floor") or 0)
        if lead_id <= 0 or arch_id <= 0 or floor <= 0:
            return

        intel = list(getattr(self.caller.db, "net_rumor_intel", []) or [])
        key = f"{arch_id}:{floor}:{lead_id}"
        if not any(str(row.get("key", "")) == key for row in intel):
            intel.append(
                {
                    "key": key,
                    "lead_id": lead_id,
                    "architecture_id": arch_id,
                    "architecture_key": hook.get("net_architecture_key", "NET"),
                    "floor": floor,
                    "label": hook.get("net_label", "Unknown lead"),
                    "bonus": 2,
                    "consumed": False,
                    "time": int(gametime.gametime()),
                    "source": target.get("origin", "unknown"),
                }
            )
            self.caller.db.net_rumor_intel = intel[-80:]

        self.caller.msg(
            "|cNetrunning intel acquired:|n "
            f"{hook.get('net_architecture_key', 'NET')} floor {floor} may hold |w{hook.get('net_label', 'a hidden lead')}|n. "
            "This grants a rumor edge on |w+net/delve|n when you're there."
        )

    def _follow_shared_rumor(self, rank: int):
        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg("Usage: scoop/follow <lead_id>")
            return
        try:
            lead_id = int(raw)
        except ValueError:
            self.caller.msg("Lead ID must be a number. Usage: scoop/follow <lead_id>")
            return

        rumors = self._load_shared_rumors()
        target = None
        for row in rumors:
            if int(row.get("id", 0) or 0) == lead_id:
                target = row
                break
        if not target:
            self.caller.msg("That lead does not exist anymore.")
            return

        claimed = list(target.get("claimed_by", []) or [])
        caller_ref = str(self.caller.id)
        if caller_ref in claimed:
            self.caller.msg("You already followed this lead.")
            return

        tier = _normalize_key(str(target.get("tier", "vague")))
        dv = int(self._FOLLOW_DV_BY_TIER.get(tier, 9))
        total = max(0, int(rank or 0)) + random.randint(1, 10)
        claimed.append(caller_ref)
        target["claimed_by"] = claimed
        self._save_shared_rumors(rumors)

        if total > dv:
            clue = {
                "lead_id": lead_id,
                "tier": tier,
                "time": int(gametime.gametime()),
                "source": target.get("origin", "unknown"),
            }
            clues = list(getattr(self.caller.db, "rumor_clues", []) or [])
            clues.append(clue)
            self.caller.db.rumor_clues = clues[-50:]
            self.caller.msg(
                f"|gLead followed.|n You pull useful details from rumor #{lead_id} "
                f"({total} vs DV {dv})."
            )
            self._grant_mystery_rumor_benefits(target)
            self._grant_net_rumor_benefits(target)
            return

        self.caller.msg(
            f"|rNo traction.|n You fail to turn rumor #{lead_id} into useful intel "
            f"({total} vs DV {dv})."
        )

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using scoop.")
            return

        rank = _role_rank(self.caller, "credibility")
        sw = self.switches[0].lower() if self.switches else ""
        if rank <= 0 and sw not in ("hear", "follow"):
            self.caller.msg(
                "You do not have Credibility. You can still use |wscoop/hear|n and |wscoop/follow <lead_id>|n."
            )
            return

        if not self.switches:
            chance = self._believability_chance(rank)
            pool = self._evidence_pool()
            self.caller.msg(
                f"|wCredibility Rank:|n {rank}\n"
                f"|wBelievability baseline:|n {chance}/10\n"
                f"|wAvailable evidence:|n {pool}\n"
                "Use |wscoop/passive|n, |wscoop/rumor|n, or |wscoop/publish|n."
            )
            return

        if sw == "passive":
            self._passive(rank)
            return
        if sw == "rumor":
            self._active_rumor(rank)
            return
        if sw == "hear":
            self._hear_shared_rumors()
            return
        if sw == "follow":
            self._follow_shared_rumor(rank)
            return
        if sw == "publish":
            self._publish(rank, allow_repeat=("newinfo" in (self.switches or [])))
            return
        self.caller.msg(
            "Usage: scoop/passive, scoop/rumor [tier], scoop/hear, scoop/follow <lead_id>, "
            "scoop/publish <topic>[=<evidence_count>][:<article_text>]"
        )

    def _passive(self, rank: int):
        total = rank + random.randint(1, 10)
        tier = self._best_rumor_tier(total, mode="passive")
        if tier:
            self.caller.msg(
                f"|gPassive rumor hit:|n |w{tier.title()}|n (roll {total}). "
                "You hear a lead worth following."
            )
            self._award_evidence(tier, "passive")
            self._share_rumor(tier, "passive")
        else:
            self.caller.msg(f"No useful passive rumor this cycle (roll {total}).")

    def _active_rumor(self, rank: int):
        target_tier = _normalize_key(self.args or "")
        if target_tier and target_tier not in self._RUMOR_TABLE:
            self.caller.msg("Tier must be one of: vague, typical, substantial, detailed.")
            return

        total = rank + random.randint(1, 10)
        if target_tier:
            dv = int(self._RUMOR_TABLE[target_tier]["active"])
            ok = total > dv
            self.caller.msg(
                f"Active rumor search ({target_tier.title()}): roll {total} vs DV {dv} - "
                f"{'|gSuccess|n' if ok else '|rFailure|n'}."
            )
            if ok:
                self._award_evidence(target_tier, "active")
                self._share_rumor(target_tier, "active")
            return

        best = self._best_rumor_tier(total, mode="active")
        if best:
            self.caller.msg(
                f"|gActive search finds:|n |w{best.title()} rumor|n (roll {total})."
            )
            self._award_evidence(best, "active")
            self._share_rumor(best, "active")
        else:
            self.caller.msg(f"No actionable rumor found this search (roll {total}).")

    def _publish(self, rank: int, allow_repeat: bool):
        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg("Usage: scoop/publish <topic>[=<evidence_count>][:<article_text>]")
            return

        # Require Screamsheets board to exist for publishing workflow.
        try:
            from world.utils.bbs_utils import get_or_create_bbs_controller
            bbs = get_or_create_bbs_controller()
            board = bbs.get_board("Screamsheets")
            if not board:
                self.caller.msg(
                    "Screamsheets board is not configured. Ask staff to create a BBS board named 'Screamsheets'."
                )
                return
            if not bbs.has_write_access(board["id"], self.caller.key):
                self.caller.msg(
                    "You cannot post to Screamsheets right now (board may be read-only/restricted). Ask staff."
                )
                return
        except Exception:
            self.caller.msg(
                "Screamsheets board is unavailable. Ask staff to verify the BBS setup."
            )
            return

        if ":" in raw:
            publish_raw, article_text = [x.strip() for x in raw.split(":", 1)]
        else:
            publish_raw, article_text = raw, ""

        if "=" in publish_raw:
            topic_raw, evidence_raw = [x.strip() for x in publish_raw.split("=", 1)]
            try:
                evidence_count = max(0, int(evidence_raw))
            except ValueError:
                self.caller.msg("Evidence count must be a number.")
                return
        else:
            topic_raw = publish_raw
            evidence_count = 0

        topic = _normalize_key(topic_raw)
        if not topic:
            self.caller.msg("Topic cannot be empty.")
            return

        available_evidence = self._evidence_pool()
        if evidence_count > available_evidence:
            self.caller.msg(
                f"You only have {available_evidence} evidence point(s). "
                "Gather more with |wscoop/passive|n or |wscoop/rumor|n."
            )
            return

        published = dict(getattr(self.caller.db, "media_published_topics", {}) or {})
        if topic in published and not allow_repeat:
            self.caller.msg(
                "You already published on that exact topic. Use |wscoop/publish/newinfo|n for follow-up coverage."
            )
            return

        base_chance = self._believability_chance(rank)
        evidence_bonus = 0
        if evidence_count >= 1:
            evidence_bonus += 1
        if evidence_count > 4:
            evidence_bonus += 2
        final_chance = min(10, base_chance + evidence_bonus)
        d10 = random.randint(1, 10)
        believed = d10 <= final_chance

        now = int(gametime.gametime())
        published[topic] = {
            "last_published": now,
            "evidence_count": evidence_count,
            "believed": believed,
            "roll": d10,
            "chance": final_chance,
            "article_text": article_text,
        }
        self.caller.db.media_published_topics = published
        self.caller.db.media_evidence_pool = max(0, available_evidence - evidence_count)

        if believed:
            self.caller.msg(
                f"|gPublished.|n Your audience buys the story on |w{topic}|n "
                f"({d10} <= {final_chance})."
            )
        else:
            self.caller.msg(
                f"|yPublished, but contested.|n The audience is split on |w{topic}|n "
                f"({d10} > {final_chance})."
            )

        # Mirror publication to Screamsheets board.
        status = "Believed" if believed else "Contested"
        title = f"{topic.title()} [{status}]"
        body = (
            f"Reporter: {self.caller.key}\n"
            f"Topic: {topic}\n"
            f"Evidence count: {evidence_count}\n"
            f"Believability roll: {d10} <= {final_chance} ({status})\n"
        )
        if article_text:
            body += f"\nArticle:\n{article_text}\n"
        try:
            bbs.create_post("Screamsheets", title, body, self.caller.key)
            self.caller.msg("|xPosted to Screamsheets.|n")
        except Exception:
            self.caller.msg("Published, but failed to post to Screamsheets. Ask staff to check board permissions.")
