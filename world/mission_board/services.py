"""
Mission Board service layer - job creation, payouts, rep, mail.
"""
from django.utils import timezone
from evennia.utils import create, logger
from evennia.utils.search import search_object, search_account
from evennia.comms.models import ChannelDB

from world.mission_board.models import Mission, MissionTeamMember
from world.jobs.models import Job, Queue, JobAttachment
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.factions.models import FactionReputation


FIXER_REP_CAP = 20
MISSION_QUEUE_NAME = "MISSION"


def _get_character_display_name(char):
    """Get display name for a character (full_name or key)."""
    if not char:
        return "---"
    if hasattr(char, 'db') and getattr(char.db, 'full_name', None):
        return char.db.full_name
    return getattr(char, 'key', str(char))


def is_faction_member(character, faction_model):
    """Check if character is a member of the faction (via faction typeclass)."""
    from typeclasses.factions import Faction
    faction_obj = Faction.get_faction(faction_model.name)
    if not faction_obj:
        return False
    return character.id in (faction_obj.db.members or []) or getattr(character.db, 'faction', None) == faction_obj.key


def is_faction_head(character, faction_model):
    """Check if character is the faction head."""
    return faction_model.faction_head_id == character.id if faction_model.faction_head_id else False


def can_post_faction_mission(character, faction_model):
    """True if character can post missions for this faction."""
    from world.mission_board.models import FactionMissionPoster
    if is_faction_head(character, faction_model):
        return True
    if FactionMissionPoster.objects.filter(faction=faction_model, character=character).exists():
        return True
    return False


def can_see_mission(character, mission):
    """True if character can see this mission (public or faction member for faction_only)."""
    if mission.faction_visibility == 'public':
        return True
    if not mission.faction:
        return True
    return is_faction_member(character, mission.faction)


def init_mission_system():
    """Initialize mission board (ensure queue exists). Replaces old script-based init."""
    _get_or_create_mission_queue()
    return True


def _get_or_create_mission_queue():
    return Queue.objects.get_or_create(
        name=MISSION_QUEUE_NAME,
        defaults={'automatic_assignee': None}
    )[0]


def create_mission_job(mission, poster_account):
    """Create a Job for the mission, linked and with poster as requester."""
    queue = _get_or_create_mission_queue()
    job = Job.objects.create(
        title=f"[Mission #{mission.id}] {mission.name}",
        description=mission.description,
        requester=poster_account,
        queue=queue,
        status='open'
    )
    mission.job = job
    mission.save()
    return job


def sync_mission_to_job(mission):
    """Sync mission team to job participants. Add GM, Fixer/Staff, lead, team. Remove leavers."""
    if not mission.job:
        return
    job = mission.job
    accounts_to_have = set()
    # Poster (Fixer or staff) - use account
    if mission.posted_by:
        acc = getattr(mission.posted_by, 'account', None)
        if acc:
            accounts_to_have.add(acc)
    # GM (prefer gm_character, fallback to gm account)
    if mission.gm_character:
        acc = getattr(mission.gm_character, 'account', None)
        if acc:
            accounts_to_have.add(acc)
    elif mission.gm:
        accounts_to_have.add(mission.gm)
    # Team members (lead + added)
    for mtm in mission.team_members.order_by('order'):
        char = mtm.character
        acc = getattr(char, 'account', None)
        if acc:
            accounts_to_have.add(acc)
    # Add missing
    for acc in accounts_to_have:
        if acc not in job.participants.all():
            job.participants.add(acc)
    # Remove those no longer on mission
    for acc in list(job.participants.all()):
        if acc not in accounts_to_have:
            job.participants.remove(acc)
    job.save()


def mission_add_comment_and_mail(mission, author_name, text, use_job=True):
    """Add update to mission, post as job comment, send mail to all attached."""
    entry = {
        "date": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        "author": author_name,
        "text": text
    }
    mission.updates = mission.updates or []
    mission.updates.append(entry)
    mission.save()
    if use_job and mission.job:
        job = mission.job
        job.comments = job.comments or []
        job.comments.append({
            "author": author_name,
            "text": text,
            "created_at": entry["date"]
        })
        job.save()
        _mail_mission_attached(mission, f"Mission #{mission.id} Update: {text}")


def _mail_mission_attached(mission, message):
    """Send mail to everyone attached to the mission (by character for mailbox display)."""
    from world.mail.models import MailMessage
    from evennia.objects.models import ObjectDB

    chars = set()
    if mission.posted_by:
        chars.add(mission.posted_by)
    for mtm in mission.team_members.all():
        chars.add(mtm.character)
    # GM - use gm_character if set, else find char for account
    if mission.gm_character:
        chars.add(mission.gm_character)
    elif mission.gm:
        gm_chars = ObjectDB.objects.filter(db_account=mission.gm)
        if gm_chars.exists():
            chars.add(gm_chars.first())

    subject = f"Mission #{mission.id}: {mission.name}"
    body = f"{message}\n\nMission: {mission.name}\nID: {mission.id}"
    if chars:
        recipient_keys = ','.join(c.key for c in chars)
        try:
            msg = MailMessage.objects.create(
                sender="Mission Board",
                recipients=recipient_keys,
                subject=subject,
                body=body
            )
            for c in chars:
                msg.character_recipients.add(c)
        except Exception as e:
            logger.log_err(f"Mission mail failed: {e}")


def apply_rep_to_character(character, amount, faction=None):
    """Apply reputation points to character (faction or general)."""
    if faction:
        fr, _ = FactionReputation.objects.get_or_create(
            character=character, faction=faction,
            defaults={'reputation_points': 0, 'rep': 0, 'notoriety_points': 0, 'notoriety': 0}
        )
        fr.reputation_points += amount
        fr.update_rep()
        fr.save()
    else:
        if not hasattr(character, 'db'):
            return
        character.db.reputation_points = getattr(character.db, 'reputation_points', 0) + amount
        character.db.rep = min(character.db.reputation_points // 100, 10)
        if hasattr(character, 'character_sheet') and character.character_sheet:
            character.character_sheet.reputation_points = character.db.reputation_points
            character.character_sheet.rep = character.db.rep
            character.character_sheet.save()


def apply_notoriety_to_character(character, amount, faction=None):
    """Apply notoriety to character on mission failure."""
    if faction:
        fr, _ = FactionReputation.objects.get_or_create(
            character=character, faction=faction,
            defaults={'reputation_points': 0, 'rep': 0, 'notoriety_points': 0, 'notoriety': 0}
        )
        fr.notoriety_points += amount
        fr.update_notoriety()
        fr.save()
    else:
        if not hasattr(character, 'db'):
            return
        character.db.notoriety_points = getattr(character.db, 'notoriety_points', 0) + amount
        character.db.notoriety = min(character.db.notoriety_points // 100, 10)
        if hasattr(character, 'character_sheet') and character.character_sheet:
            character.character_sheet.notoriety_points = character.db.notoriety_points
            character.character_sheet.notoriety = character.db.notoriety
            character.character_sheet.save()


def complete_mission(mission, survivors=None):
    """
    Apply payouts for a completed mission.

    Args:
        mission: The completed mission.
        survivors: Optional list of characters (ObjectDB) who survived the scene.
                   Only survivors get money split. If None, all team members get paid.
                   Rep/items still go to survivors only when specified.
    """
    team = list(mission.team_members.order_by('order'))
    if not team:
        return

    # Determine who gets payouts - survivors only, or all if not specified
    if survivors is not None:
        survivor_ids = {c.id for c in survivors if c}
        payees = [mtm for mtm in team if mtm.character_id in survivor_ids]
        lead = payees[0].character if payees else team[0].character
    else:
        payees = team
        lead = team[0].character

    # Fixer cut: when mission from story seed with fixer poster, pay fixer (max_budget - payout)
    if mission.source_seed and mission.posted_by and not mission.posted_by_staff:
        seed = mission.source_seed
        fixer_cut = max(0, seed.max_budget - mission.money_amount)
        if fixer_cut > 0:
            CharacterMoneyService.add_money(mission.posted_by, fixer_cut)
            logger.log_info(f"Mission #{mission.id}: Fixer {mission.posted_by.key} paid {fixer_cut} eb (budget {seed.max_budget} - payout {mission.money_amount})")

    # Player money: split among survivors only
    if mission.money_amount > 0 and not mission.money_pay_on_delivery and payees:
        per_player = mission.money_amount // len(payees)
        for mtm in payees:
            CharacterMoneyService.add_money(mtm.character, per_player)

    # Rep: survivors only (or all team if survivors not specified)
    rep_recipients = payees if survivors is not None else team
    if mission.rep_amount > 0:
        for mtm in rep_recipients:
            apply_rep_to_character(mtm.character, mission.rep_amount, None)
    if getattr(mission, 'faction_rep_amount', 0) > 0 and mission.faction:
        for mtm in rep_recipients:
            apply_rep_to_character(mtm.character, mission.faction_rep_amount, mission.faction)

    # Voucher/items: go to lead (first survivor)
    if not mission.rewards_pay_on_delivery:
        for dbref in (mission.voucher_rewards or []):
            ref = f"#{dbref}" if isinstance(dbref, int) else str(dbref)
            objs = search_object(ref)
            if objs:
                obj = objs[0]
                if hasattr(obj, 'move_to') and obj.location:
                    obj.move_to(lead, quiet=True)
        for dbref in (mission.item_rewards or []):
            ref = f"#{dbref}" if isinstance(dbref, int) else str(dbref)
            objs = search_object(ref)
            if objs:
                obj = objs[0]
                if hasattr(obj, 'move_to') and obj.location:
                    obj.move_to(lead, quiet=True)


def fail_mission(mission):
    """Apply notoriety and optional money penalty on failure."""
    team = list(mission.team_members.order_by('order'))
    # Notoriety = rep amounts that would have been awarded (general + faction)
    if mission.rep_amount > 0:
        for mtm in team:
            apply_notoriety_to_character(mtm.character, mission.rep_amount, None)
    if getattr(mission, 'faction_rep_amount', 0) > 0 and mission.faction:
        for mtm in team:
            apply_notoriety_to_character(mtm.character, mission.faction_rep_amount, mission.faction)
    # Money penalty (spend_money returns False if insufficient - we still apply)
    if mission.failure_penalty_amount > 0:
        if mission.failure_penalty_scope == 'team':
            for mtm in team:
                CharacterMoneyService.spend_money(mtm.character, mission.failure_penalty_amount)
        else:
            if team:
                CharacterMoneyService.spend_money(team[0].character, mission.failure_penalty_amount)
