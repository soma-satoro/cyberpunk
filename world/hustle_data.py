"""
Cyberpunk Red Hustle tables - rules as written from the core book.

Whenever you have a full seven days free, you can work to earn eb.
Payment depends on Role, Role Ability Rank (1-4, 5-7, 8-10), and 1d6 roll.
"""

# Each role has 6 entries (roll 1-6), each with (activity_description, rank_1_4_eb, rank_5_7_eb, rank_8_10_eb)
HUSTLE_TABLES = {
    "Rockerboy": [
        ("Played a small local gig.", 200, 300, 600),
        ("No gigs or jobs to be had this week.", 0, 100, 300),
        ("Played a big gig for a rich Corporate or Local Personality.", 300, 500, 800),
        ("Got some royalties in for your most recent Data Pool download.", 300, 500, 800),
        ("Opening act for a Big-Name group.", 300, 500, 800),
        ("Personal appearance netted you a large fee.", 200, 300, 600),
    ],
    "Solo": [
        ("Bodyguard work, low-end client.", 100, 200, 500),
        ("Bodyguard work, high-end client.", 200, 300, 600),
        ("Difficult hit or extraction.", 200, 300, 600),
        ("Hired out as muscle to a Fixer, Corp, or Gang.", 100, 200, 500),
        ("Attracted undue attention, had to lay low.", 0, 100, 300),
        ("Basic enforcer or hitman work for a local Corp.", 100, 200, 500),
    ],
    "Netrunner": [
        ("Cracked a small system and sold the data.", 100, 200, 500),
        ("Cracked a major Corporate system and sold the data.", 200, 300, 600),
        ("You got sidetracked and didn't hack anything this week.", 0, 100, 300),
        ("Found a valuable data cache in an abandoned system and sold it.", 200, 300, 600),
        ("Brought down a major system with ransomware and got paid off to uninstall it.", 200, 300, 600),
        ("Sabotaged or otherwise disabled a major system for a faceless client.", 200, 300, 600),
    ],
    "Tech": [
        ("No jobs this week.", 0, 100, 300),
        ("Rebuilt some tech you scavenged in the Combat Zone.", 100, 200, 500),
        ("Helped a client break into some place or installed security systems for a client.", 200, 300, 600),
        ("Did some modifications or repairs to some cybertech.", 100, 200, 500),
        ("Did some modifications or repairs to some weapons.", 100, 200, 500),
        ("Sabotaged or otherwise disabled something for a client.", 100, 200, 500),
    ],
    "Medtech": [
        ("Patched up someone after a firefight.", 100, 200, 500),
        ("Sold cyberware from a \"failed\" medical case.", 200, 300, 600),
        ("Helped Trauma Team on some backup work when they were overloaded.", 100, 200, 500),
        ("Did some minor \"free clinic\" work for locals. You can't eat goodwill though.", 0, 100, 300),
        ("Did a major medical procedure for a very well-heeled client.", 200, 300, 600),
        ("Designed and delivered medicines or street drugs to a client.", 100, 200, 500),
    ],
    "Media": [
        ("Wrote an expose that covered a major topic, made a big sale.", 300, 500, 800),
        ("Wrote a popular \"puff piece\" that got some notice and some cash.", 200, 300, 600),
        ("Did some boring ad writing to pay the bills.", 200, 300, 600),
        ("Exposed a big story that got you a few enemies and some cash.", 200, 300, 600),
        ("No good stories or leads this week.", 0, 100, 300),
        ("Wrote an expose that blew the lid off a major topic.", 300, 500, 800),
    ],
    "Lawman": [
        ("Made a few minor busts, business as usual.", 100, 200, 500),
        ("Got a reward from a grateful citizen. Or was it a bribe?", 200, 300, 600),
        ("Bust went bad, and it came out of your salary.", 0, 100, 300),
        ("Nothing much happened this week. Collected a paycheck and that was it.", 100, 200, 500),
        ("Pulled off a major drug or smuggling bust and gained a bonus from the boss.", 200, 300, 600),
        ("Took down a big gang and got some of a \"civil seizure\" bonus.", 200, 300, 600),
    ],
    "Exec": [
        ("Landed a moderate success on a project, earned a reward bonus.", 300, 500, 800),
        ("Nothing much happened, and Corporate was unimpressed. Lost a bonus.", 0, 100, 300),
        ("Collected a paycheck and that was it.", 200, 300, 600),
        ("Got some dirt on a rival and used it to score a bonus.", 300, 500, 800),
        ("Pulled off a major project success and gained a bonus from the Head Office.", 300, 500, 800),
        ("Took out a legitimate target that was threatening a job and took their funding.", 200, 300, 600),
    ],
    "Fixer": [
        ("Got a Media some information for a good bribe.", 200, 300, 600),
        ("Got a Rocker a good Gig for your 12% fee.", 200, 300, 600),
        ("Helped a client locate a desirable item they needed and got a cut.", 200, 300, 600),
        ("Deal went south; you're keeping your head down till it blows over.", 0, 100, 300),
        ("Got a Solo or Netrunner a profitable \"job\" and took your agency fee.", 200, 300, 600),
        ("Brought in a rare, illegal, or very hard to get item for a client.", 300, 500, 800),
    ],
    "Nomad": [
        ("Made a legit shipment.", 100, 200, 500),
        ("Protected a shipment.", 100, 200, 500),
        ("Smuggled some small contraband.", 100, 200, 500),
        ("Smuggled a huge shipment.", 200, 300, 600),
        ("Delivered a client safely to destination.", 100, 200, 500),
        ("Couldn't find work this week, legit or otherwise.", 0, 100, 300),
    ],
}


def get_rank_tier(rank):
    """
    Convert Role Ability Rank (1-10) to tier for payout lookup.
    Returns 0 for rank 1-4, 1 for 5-7, 2 for 8-10.
    """
    if rank <= 0:
        return 0
    if rank <= 4:
        return 0
    if rank <= 7:
        return 1
    return 2


def get_hustle_result(role, roll, rank):
    """
    Get hustle result for a character.
    role: str, e.g. "Rockerboy", "Solo"
    roll: int 1-6 (from 1d6)
    rank: int 1-10 (Role Ability Rank)
    Returns (activity_description, eb_earned) or (None, 0) if invalid.
    """
    table = HUSTLE_TABLES.get(role)
    if not table:
        return None, 0
    if not 1 <= roll <= 6:
        return None, 0
    tier = get_rank_tier(rank)
    entry = table[roll - 1]
    activity, eb_1_4, eb_5_7, eb_8_10 = entry
    eb = [eb_1_4, eb_5_7, eb_8_10][tier]
    return activity, eb
