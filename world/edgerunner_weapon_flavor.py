"""
Flavored weapon names for generic CPR categories (poor / standard / excellent).

Used when:
- Edgerunner chargen grants a role-package weapon (standard tier from template).
- Player buys a generic weapon (e.g. \"Very Heavy Pistol=poor\") in chargen/vendor.
- Arms dealer sells a catalog row whose name is exactly a generic category.

Named catalog weapons (e.g. Dai Lung Streetmaster) are not remapped.
"""
from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional

# Top-level keys = generic \"name\" in equipment_data.weapons (EQUIPMENT / quality buy).
# Sub-keys: poor, standard, excellent - each a list of {\"name\": str, \"tagline\": str}
WEAPON_FLAVOR_BY_QUALITY: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "Medium Pistol": {
        "poor": [
            {'name': 'Budget Arms "Peashooter"', "tagline": "vending machine sidearm in a color that doesn't inspire confidence"},
            {'name': 'Dai Lung Cybermag 8 "Knockoff"', "tagline": 'the "8" is not a model number, it\'s how many times it jammed in testing'},
            {'name': 'CCMMC Type-2 "Gutter"', "tagline": "Chinese military surplus reject, technically fires in one direction"},
            {'name': 'Street Iron "Patchwork"', "tagline": "gang-assembled from mismatched parts; the welds are visible"},
            {'name': 'No-Name "Throwaway"', "tagline": "because that's what you do with it after one magazine"},
        ],
        "standard": [
            {"name": 'Federated Arms X-6 "Sparrow"', "tagline": "budget polymer frame, everywhere and forgettable"},
            {"name": "Dai Lung Cybermag 15", "tagline": "cheap Chinese-market semi-auto, notorious for loose tolerances"},
            {"name": 'Militech M-9 "Garter"', "tagline": "compact concealment pistol, issued to intelligence-adjacent personnel"},
            {"name": "Sternmeyer P-14", "tagline": "German-engineered, no-frills, built to outlast its owner"},
            {'name': 'Budget Arms "Quickdraw"', "tagline": "vending machine pistol, the name is aspirational"},
        ],
        "excellent": [
            {'name': 'Malorian Arms 1050 "Whisper"', "tagline": "hand-fitted action, hair trigger, the choice of professionals who value silence"},
            {'name': 'Arasaka "Tsubame"', "tagline": "tsubame means swallow; fast, precise, and gone before you noticed it"},
            {'name': 'Sternmeyer P-14 "Praezision"', "tagline": "the precision-grade variant of the standard line; tolerances measured in microns"},
            {'name': 'Custom Works "Surgeon"', "tagline": "bespoke Night City fabrication, made to order, no two identical"},
            {'name': 'Tsunami Arms "Koi"', "tagline": "compact carry piece for corp officers; elegant enough to pass as an accessory"},
        ],
    },
    "Heavy Pistol": {
        "poor": [
            {'name': 'Budget Arms "Stomper"', "tagline": "the frame flexes when you fire it. It still fires."},
            {"name": "Dai Lung TP-4", "tagline": "the TP stands for something the original engineers didn't intend"},
            {'name': 'CCMMC "Brickyard"', "tagline": "heavy, ugly, and occasionally accurate"},
            {'name': 'Street Forge "Slag"', "tagline": "cast from reclaimed materials; the metallurgy is unclear"},
            {'name': 'Rostovic TP-1 "Jeftino"', "tagline": "jeftino means cheap; Rostovic made this specifically to move units, not to impress"},
        ],
        "standard": [
            {'name': 'Militech M-22 "Warden"', "tagline": "standard sidearm for mid-tier corporate security, reliable and boring"},
            {"name": "Sternmeyer P-50", "tagline": "heavier Sternmeyer frame, carries authority in its weight alone"},
            {'name': 'Constitutional Arms "Bulldog"', "tagline": "American-made, American-sized, American-loud"},
            {'name': 'Arasaka "Kensei"', "tagline": "elegant framing, precision action, priced for officers not grunts"},
            {'name': 'Rostovic TP-9 "Grom"', "tagline": "Grom means thunder in Serbian. It sounds like it too."},
        ],
        "excellent": [
            {"name": "Malorian Arms 2020", "tagline": "the benchmark for what a heavy pistol should be, priced accordingly"},
            {'name': 'Arasaka "Kensei-X"', "tagline": "extended precision variant of the standard Kensei line; officer's weapon"},
            {'name': 'Sternmeyer P-50 "Adler"', "tagline": "adler means eagle; the premium P-50 variant with match-grade barrel"},
            {'name': 'Constitutional Arms "Arbiter Elite"', "tagline": "the custom shop version; walnut grips, hand-polished action"},
            {'name': 'Custom Works "Iron Covenant"', "tagline": "boutique Night City fabrication for clients who specify everything in writing"},
        ],
    },
    "Very Heavy Pistol": {
        "poor": [
            {'name': 'Budget Arms "Wallbreaker"', "tagline": "technically functions as a breaching tool if the magazine is empty"},
            {"name": "Dai Lung HVP-1", "tagline": "their attempt at the heavy market; the attempt was not fully successful"},
            {'name': 'Street Forge "Anchor"', "tagline": "named for what it feels like in your hand and what it does to your wrist"},
            {'name': 'CCMMC "Sledge"', "tagline": "enormous, unbalanced, and cheap enough that you won't mourn it when it fails"},
            {'name': 'Gutter Works "Last Resort"', "tagline": "the name is not ironic; it is a use-case description"},
        ],
        "standard": [
            {'name': 'Militech M-38 "Brute"', "tagline": "the name is accurate; no other documentation required"},
            {"name": "Sternmeyer T-80", "tagline": "T-series heavy frame, overbuilt by design, chambered in something unreasonable"},
            {'name': 'Arasaka "Raijin"', "tagline": "named for the thunder god; the muzzle flash supports the comparison"},
            {"name": "Malorian Arms 2040", "tagline": "boutique manufacture, hand-fitted action, costs more than most people's cyberware"},
            {'name': 'Constitutional Arms "Vindicator"', "tagline": "marketed to private citizens; favored by people who have made a decision"},
        ],
        "excellent": [
            {"name": "Malorian Arms 3500", "tagline": "one step below their legendary line; still worth more than most people's implants"},
            {'name': 'Arasaka "Raijin-X"', "tagline": "extended match variant; the thunder god, but angrier"},
            {'name': 'Sternmeyer T-80 "Panzer"', "tagline": "the precision-grade T-series; the barrel alone costs more than a standard pistol"},
            {'name': 'Custom Works "Deathwish"', "tagline": "bespoke boutique piece; the name was chosen by the first client, and it stuck"},
            {'name': 'Tsunami Arms "Orochi"', "tagline": "named for the eight-headed serpent; this many rounds, this much damage"},
        ],
    },
    "SMG": {
        "poor": [
            {'name': 'Budget Arms "Slaught-O-Matic Junior"', "tagline": "the smaller, cheaper, less reliable sibling of an already bad weapon"},
            {"name": "Dai Lung Tempest 10", "tagline": "the bottom of the Tempest line; clips are non-standard and hard to find"},
            {'name': 'CCMMC "Scattershot"', "tagline": "the name implies more accuracy than the weapon actually has"},
            {'name': 'Street Fab "Chatter"', "tagline": "named for the noise it makes before it jams"},
            {'name': 'No-Name "Garbage Fire"', "tagline": "a designation applied by the Night City resale market, not the manufacturer"},
        ],
        "standard": [
            {'name': 'Militech M-14 "Jackal"', "tagline": "polymer and steel, compact, widely distributed to second-tier contractors"},
            {'name': 'Arasaka WMA "Kaze-5"', "tagline": "Kaze means wind; it empties a magazine about as fast"},
            {'name': 'Federated Arms X-12 "Courier"', "tagline": "light enough to run with, accurate enough to matter"},
            {"name": "Dai Lung Tempest 30", "tagline": "Chinese-market spray-and-pray, high capacity, variable reliability"},
            {'name': 'Budget Arms "Slapdash"', "tagline": "does what you need until it doesn't"},
        ],
        "excellent": [
            {'name': 'Militech M-14 "Jackal-S"', "tagline": "special operations variant; suppressor-integrated, match-grade, limited issue"},
            {'name': 'Arasaka WMA "Kaze-9 Custom"', "tagline": "bespoke version of the Kaze line, built for clients who specify performance in contracts"},
            {'name': 'Tsunami Arms "Hayabusa"', "tagline": "hayabusa means peregrine falcon; the fastest production SMG in their catalog"},
            {'name': 'Sternmeyer K-10 "Praezision"', "tagline": "German-engineered precision SMG; the trigger pull is a religious experience"},
            {'name': 'Custom Works "Needle"', "tagline": "hand-assembled in a Night City shop; surgical accuracy, waiting list of six months"},
        ],
    },
    "Heavy SMG": {
        "poor": [
            {'name': 'Budget Arms "Bonebreaker"', "tagline": "the recoil earns the name even when the accuracy doesn't"},
            {'name': 'CCMMC TM-2 "Rattle"', "tagline": "named for the sound the action makes; not a good sign in a firearm"},
            {"name": "Dai Lung Stormfront 5", "tagline": "the bottom of the Stormfront heavy line; cycles slowly and jams faster"},
            {'name': 'Street Forge "Grinder"', "tagline": "assembled from parts that weren't designed for each other"},
            {'name': 'Gutter Works "Repurposed"', "tagline": "exactly what it sounds like; the previous application is not documented"},
        ],
        "standard": [
            {'name': 'Militech M-48 "Hellhound"', "tagline": "high-cyclic, runs hot, chews through ammunition and armor alike"},
            {'name': 'Arasaka TKI-15 "Arashi"', "tagline": "Arashi means storm; the burst pattern makes the name appropriate"},
            {'name': 'Chadran Arms "Block Warden"', "tagline": "named for what happens to a city block when you use it"},
            {"name": "Sternmeyer K-30", "tagline": "German-engineered heavy subgun, reliable past the point of reason"},
            {'name': 'Rostovic TM-7 "Klanje"', "tagline": 'Klanje translates roughly to "slaughter"; Rostovic doesn\'t do subtle'},
        ],
        "excellent": [
            {'name': 'Militech M-48 "Hellhound-S"', "tagline": "special forces variant; improved feed, reduced heat signature, controlled burst"},
            {'name': 'Arasaka TKI-15 "Arashi Custom"', "tagline": "bespoke Arashi platform, hand-tuned, available only through Arasaka's private catalog"},
            {'name': 'Chadran Arms "Block Warden Executive"', "tagline": "the irony of the name is not lost on the people who buy it"},
            {'name': 'Sternmeyer K-30 "Sturmadler"', "tagline": "Sturmadler means storm eagle; the K-30 built to specification for serious work"},
            {'name': 'Tsunami Arms "Ryujin"', "tagline": "named for the dragon king; the premium heavy subgun in their lineup"},
        ],
    },
    "Bow": {
        "poor": [
            {"name": "Nomad Scrap Recurve", "tagline": "bent rebar and salvaged cables; draws inconsistently, releases honestly"},
            {'name': 'Gutter Works "Twig"', "tagline": "assembled from construction materials; technically a ranged weapon"},
            {'name': 'Backyard Compound "Cobble"', "tagline": "homemade compound bow with a pull weight that varies with the weather"},
            {'name': 'Street Fab "Stick and String"', "tagline": "the formal designation, written on a piece of tape on the limb"},
            {'name': 'Discount Fletch "Bargain Draw"', "tagline": "the cheapest manufactured bow available; the warranty is two words: \"good luck\""},
        ],
        "standard": [
            {"name": "Compound Ghost", "tagline": "carbon-fiber limbs, near-zero electronic signature, a runner's weapon"},
            {'name': 'Cascade Arms "Heron"', "tagline": "folding takedown design, fits in a gear bag, legal almost everywhere"},
            {"name": "Ragged Whisper", "tagline": "nomad-crafted recurve, salvaged materials, carries more history than specification"},
            {"name": "SilentField RX-3", "tagline": "commercial tactical bow marketed to sport hunters and the paranoid alike"},
            {"name": "Thornwood Composite", "tagline": "boutique artisan manufacture, sold through underground fixers, priced accordingly"},
        ],
        "excellent": [
            {'name': 'Cascade Arms "Phantom"', "tagline": "the premium Cascade platform; carbon nanotube limbs, zero vibration on release"},
            {'name': 'Thornwood "Obsidian Series"', "tagline": "top-tier boutique manufacture, each bow individually certified by the builder"},
            {'name': 'SilentField RX-9 "Ghost"', "tagline": "the precision variant; adjustable draw weight, integrated dampening, near-inaudible"},
            {'name': 'Custom Works "Stillwater"', "tagline": "bespoke commission piece; clients wait three months and pay without complaint"},
            {'name': 'Nomad Craft "Elder Make"', "tagline": "hand-built by a Nomad artisan with forty years of practice; not for sale, only gifted"},
        ],
    },
    "Crossbow": {
        "poor": [
            {'name': 'Gutter Works "Bolt Chucker"', "tagline": "the internal designation became the street name"},
            {"name": "CCMMC CB-1", "tagline": "the bolt retention system is \"functional\" in the loosest sense of that word"},
            {'name': 'Street Fab "Splinter"', "tagline": "what it does to the bolt as often as the target"},
            {'name': 'Budget Arms "Snap"', "tagline": "named either for the firing sound or what the string does after fifty shots"},
            {'name': 'Discount Fletch "One-Shot"', "tagline": 'technically marketed as a hunting weapon; the "one-shot" refers to reliability, not intent'},
        ],
        "standard": [
            {'name': 'Rostovic "Strela"', "tagline": "Strela means arrow; simple, mechanical, no batteries required"},
            {"name": "Sternmeyer CB-12", "tagline": "German-engineered repeating crossbow, overbuilt and proud of it"},
            {'name': 'Cascade Arms "Falcon"', "tagline": "compact pistol crossbow, concealable under a long coat"},
            {'name': 'Darra Polytechnic "Spine"', "tagline": "lightweight frame, integrated scope mount, technically street-legal"},
            {"name": "Nomad Rail Mk.II", "tagline": "improvised-looking, precisely built, often assembled from salvaged vehicle components"},
        ],
        "excellent": [
            {'name': 'Sternmeyer CB-12 "Praezision"', "tagline": "the precision-grade Sternmeyer crossbow; machined action, glass-smooth trigger"},
            {'name': 'Cascade Arms "Falcon-X"', "tagline": "the premium Falcon platform with adjustable stock and integrated optics mount"},
            {'name': 'Darra Polytechnic "Spine Elite"', "tagline": "the top of the Darra line; hand-fitted prod, custom string, tested to spec"},
            {'name': 'Custom Works "Quarrel"', "tagline": "boutique Night City manufacture; the name is a pun the builder refuses to acknowledge"},
            {'name': 'Thornwood "Ironwood Series"', "tagline": "artisan crossbow from the same shop as the bows; different weapon, same obsessive quality"},
        ],
    },
    "Assault Rifle": {
        "poor": [
            {'name': 'Budget Arms "Warzone"', "tagline": "the name dramatically oversells the product"},
            {'name': 'Dai Lung AR-3 "Copycat"', "tagline": "a reproduction of a reproduction; the original model is unclear"},
            {'name': 'CCMMC Type-7 "Surplus"', "tagline": "military reject stock, sold by the crate, functionally interchangeable with scrap"},
            {'name': 'Street Forge "Rattler"', "tagline": "full-auto capable, in theory; the action makes the decision on a shot-by-shot basis"},
            {'name': 'Gutter Works "Trench Broom"', "tagline": "because cleaning out enclosed spaces is all it's reliably good for"},
        ],
        "standard": [
            {'name': 'Militech M-76 "Sentinel"', "tagline": "reliable workhorse, standard issue for corporate infantry and PMC grunts"},
            {'name': 'Arasaka HJSH-22 "Nobunaga"', "tagline": "high-end battle rifle, named for a warlord, priced like one too"},
            {'name': 'Constitutional Arms "Minuteman"', "tagline": "American-built, marketed to patriotic demographics and anyone who'll pay"},
            {'name': 'Rostovic AK-77 "Udar"', "tagline": "Udar means strike or impact; the Rostovic assault rifle is exactly what it sounds like"},
            {"name": "Federated Arms Tech-Assault VII", "tagline": "budget battle rifle, designed to be good enough and nothing more"},
        ],
        "excellent": [
            {'name': 'Arasaka HJSH-22 "Nobunaga Custom"', "tagline": "bespoke version of the Nobunaga line, built for executives who go into the field personally"},
            {'name': 'Militech M-76 "Sentinel-S"', "tagline": "special operations variant; improved gas system, match barrel, limited production run"},
            {'name': 'Constitutional Arms "Minuteman Elite"', "tagline": "the top of their rifle line; priced for clients who file taxes as a corporation"},
            {'name': 'Tsunami Arms Type-12 "Kamikaze"', "tagline": "premium assault platform; the name is either ironic or a promise depending on who's holding it"},
            {'name': 'Custom Works "Ironclad"', "tagline": "Night City fabrication, fully hand-fitted, built to a client's exact specifications"},
        ],
    },
    "Sniper Rifle": {
        "poor": [
            {'name': 'Budget Arms "Long Shot"', "tagline": "the name is both a product description and a probability assessment"},
            {'name': 'Street Forge "Pipe Dream"', "tagline": "a literal pipe, machined to accept a scope; results are variable"},
            {'name': 'Dai Lung SR-2 "Farshot"', "tagline": "the bottom of any sniper market; the glass is worse than the action"},
            {'name': 'CCMMC "Surplus Precision"', "tagline": "the word precision appears nowhere in the actual specifications"},
            {'name': 'Gutter Works "Reach"', "tagline": "what you're doing when you describe this as a sniper rifle"},
        ],
        "standard": [
            {'name': 'Tsunami Arms "Karasu"', "tagline": "Karasu means crow; long, patient, and strikes from places you didn't notice"},
            {'name': 'Militech M-210 "Longbow"', "tagline": "semi-auto precision platform, corp overwatch standard"},
            {"name": "Sternmeyer SR-55", "tagline": "bolt-action, German manufacture, the kind of rifle that outlasts the conflict it was bought for"},
            {'name': 'Arasaka "Izanagi"', "tagline": "named for the creator god; the implication is that what it touches stops existing"},
            {'name': 'Rostovic DM-12 "Lovac"', "tagline": "Lovac means hunter; single-shot, heavy caliber, unsubtle"},
        ],
        "excellent": [
            {'name': 'Tsunami Arms "Karasu Custom"', "tagline": "the premium Karasu platform; individually zeroed at the factory, shipped with a certificate"},
            {'name': 'Militech M-210 "Longbow-S"', "tagline": "special operations longbow variant; suppressor-threaded, chassis-mounted, limited issue"},
            {'name': 'Sternmeyer SR-55 "Meisterwerk"', "tagline": "meisterwerk means masterwork; the definitive Sternmeyer precision rifle"},
            {'name': 'Arasaka "Izanagi-X"', "tagline": "the extended precision Izanagi; used by Arasaka's own long-range elimination teams"},
            {'name': 'Custom Works "Patience"', "tagline": "bespoke Night City commission; the waiting list is as long as the barrel"},
        ],
    },
    "Shotgun": {
        "poor": [
            {'name': 'Budget Arms "Doorstop"', "tagline": "because that's what you use it for when it fails to fire"},
            {'name': 'Street Forge "Blunderbuss"', "tagline": "deliberately named for an antique; the comparison is more accurate than flattering"},
            {'name': 'CCMMC SG-1 "Scatter"', "tagline": "the pattern is wide, the reliability is not"},
            {'name': 'Dai Lung SG-3 "Buckshot Special"', "tagline": "the only thing special about it is that it sometimes works"},
            {'name': 'Gutter Works "Noisemaker"', "tagline": "loud, short-ranged, and better at causing panic than damage"},
        ],
        "standard": [
            {'name': 'Militech M-60 "Bulldozer"', "tagline": "pump action, built for breaching and close-quarters attrition"},
            {'name': 'Rostovic DB-4 "Ulaz"', "tagline": "Ulaz means entrance or breach; double-barrel, the name is ironic and accurate"},
            {'name': 'Constitutional Arms "Gatekeeper"', "tagline": "marketed to private property owners; used in less civil contexts"},
            {'name': 'Budget Arms "Splatter"', "tagline": "the name is the specification sheet"},
            {"name": "Sternmeyer SG-20", "tagline": "semi-auto German-frame combat shotgun, reliable enough for security work"},
        ],
        "excellent": [
            {'name': 'Militech M-60 "Bulldozer-S"', "tagline": "special operations variant; improved choke, reduced recoil, extended tube magazine"},
            {'name': 'Sternmeyer SG-20 "Rammstein"', "tagline": "named for the German word for ramming stone; the premium Sternmeyer combat shotgun"},
            {'name': 'Constitutional Arms "Gatekeeper Elite"', "tagline": "the top of their shotgun line; hand-fitted action, ported barrel, walnut stock optional"},
            {'name': 'Rostovic DB-6 "Grmljavina"', "tagline": "grmljavina means thunderstorm; Rostovic's attempt at a prestige product, and it succeeded"},
            {'name': 'Custom Works "Last Argument"', "tagline": "boutique Night City fabrication; the name was the client's idea and nobody argued"},
        ],
    },
    "Grenade Launcher": {
        "poor": [
            {'name': 'Street Forge "Thumper"', "tagline": "because that's the sound it makes when the grenade doesn't clear the barrel"},
            {'name': 'Budget Arms "Boom Box"', "tagline": "single-shot, break-action, the spring mechanism is unreliable"},
            {'name': 'CCMMC GL-1 "Surplus Fire"', "tagline": "military reject launcher; the safety is a suggestion"},
            {'name': 'Gutter Works "Lobber"', "tagline": "technically functions as a grenade launcher; the arc is an adventure every time"},
            {'name': 'No-Name "Punt Gun"', "tagline": "what the Night City resale market calls anything this bad at its job"},
        ],
        "standard": [
            {"name": "Towa Manufacturing Type-K", "tagline": "compact single-shot, break-action, the budget end of indirect fire"},
            {'name': 'Militech M-90 "Hellfire"', "tagline": "multi-shot rotary launcher, expensive and very much worth it"},
            {"name": "Sternmeyer GL-7", "tagline": "German-engineered, semi-auto, designed for sustained fire support"},
            {'name': 'Constitutional Arms "Arbiter"', "tagline": "the name implies finality; the munitions deliver on that promise"},
            {"name": "Tsunami Arms Type-22 AGL", "tagline": "Tsunami's precision-class launcher; accurate enough to embarrass other manufacturers"},
        ],
        "excellent": [
            {'name': 'Militech M-90 "Hellfire-S"', "tagline": "special operations rotary launcher; programmable fusing, extended magazine, the works"},
            {'name': 'Tsunami Arms Type-22 "Raiden"', "tagline": "raiden means thunder and lightning; the premium Tsunami AGL, precision-engineered"},
            {'name': 'Sternmeyer GL-7 "Artillerie"', "tagline": "artillerie is self-explanatory; the definitive Sternmeyer launcher platform"},
            {'name': 'Constitutional Arms "Arbiter Supreme"', "tagline": "the name escalates appropriately from their standard Arbiter line"},
            {'name': 'Custom Works "Final Motion"', "tagline": "boutique fabrication; built for clients who need the first shot to be the last"},
        ],
    },
    "Rocket Launcher": {
        "poor": [
            {'name': 'Street Forge "Tube"', "tagline": "a metal tube with a firing pin; the guidance system is \"point it\""},
            {'name': 'Budget Arms "Firework"', "tagline": "the comparison to consumer explosives is not entirely inaccurate"},
            {'name': 'Gutter Works "One Way"', "tagline": "named for the projectile's likelihood of going roughly forward"},
            {'name': 'CCMMC RL-1 "Surplus Boom"', "tagline": "military reject launcher; the seals have degraded and nobody tested the propellant"},
            {'name': 'No-Name "Desperation Shot"', "tagline": "what you grab when everything else is gone and something needs to stop existing"},
        ],
        "standard": [
            {'name': 'Militech M-115 "Javelin"', "tagline": "single-shot disposable, fire-and-drop, designed for urban anti-vehicle work"},
            {'name': 'Militech M-120 "Dawnbreaker"', "tagline": "guided munitions variant, target-lock capable, corp operator standard"},
            {"name": "Sternmeyer RL-20", "tagline": "reloadable platform, German-built, intended for extended engagements"},
            {'name': 'KTech "Hammerfall"', "tagline": "marketed aggressively to anyone who'll buy it; the guidance system is optimistic"},
            {'name': 'Constitutional Arms "Finality"', "tagline": "the product name doubles as legal advice about what happens next"},
        ],
        "excellent": [
            {'name': 'Militech M-120 "Dawnbreaker-S"', "tagline": "special operations variant; multi-mode guidance, encrypted targeting, corp clearance required"},
            {'name': 'KTech "Hammerfall Elite"', "tagline": "the premium KTech platform; the guidance system is no longer optimistic, it is correct"},
            {'name': 'Sternmeyer RL-20 "Donnerkeil"', "tagline": "donnerkeil means thunderbolt; the precision reloadable platform built for extended operations"},
            {'name': 'Constitutional Arms "Finality Plus"', "tagline": "because someone at Constitutional Arms has a sense of humor about product naming"},
            {'name': 'Custom Works "Extinction Event"', "tagline": "a bespoke launcher commission; the client named it, the fabricator agreed it was appropriate"},
        ],
    },
}

GENERIC_FLAVOR_WEAPON_NAMES = frozenset(WEAPON_FLAVOR_BY_QUALITY.keys())


def normalize_weapon_label(s: str) -> str:
    """Lowercase, strip quotes, collapse whitespace - for matching flavor chart names."""
    t = (s or "").strip().lower()
    t = t.replace('"', "").replace("'", "")
    return " ".join(t.split())


def _build_flavor_name_index() -> Dict[str, tuple[str, str]]:
    """Map normalized flavor name -> (generic category key, quality tier)."""
    idx: Dict[str, tuple[str, str]] = {}
    for generic, tiers in WEAPON_FLAVOR_BY_QUALITY.items():
        for tier, entries in tiers.items():
            for entry in entries:
                key = normalize_weapon_label(entry.get("name") or "")
                if key:
                    idx[key] = (generic, tier)
    return idx


# Resolved once at import
FLAVOR_NAME_TO_GENERIC_TIER: Dict[str, tuple[str, str]] = _build_flavor_name_index()


def lookup_flavor_generic_and_tier(display_name: str) -> Optional[tuple[str, str]]:
    """If display_name is a flavor model from the chart, return (generic key, poor|standard|excellent)."""
    key = normalize_weapon_label(display_name)
    if not key:
        return None
    return FLAVOR_NAME_TO_GENERIC_TIER.get(key)


def generic_category_for_weapon(weapon) -> Optional[str]:
    """
    Map an inventory Weapon row to a generic equipment_data name (WEAPON_FLAVOR key), if any.
    Uses flavored display name, exact generic name, or weapon_type.
    """
    name = (getattr(weapon, "name", None) or "").strip()
    for k in WEAPON_FLAVOR_BY_QUALITY:
        if k.lower() == name.lower():
            return k
    lt = lookup_flavor_generic_and_tier(name)
    if lt:
        return lt[0]
    wt = normalize_weapon_label(getattr(weapon, "weapon_type", None) or "")
    if wt:
        for k in WEAPON_FLAVOR_BY_QUALITY:
            if normalize_weapon_label(k) == wt:
                return k
    return None


def flavor_quality_tier_for_weapon(weapon) -> Optional[str]:
    """Quality tier implied by the flavor chart for this weapon's name, if any."""
    lt = lookup_flavor_generic_and_tier((getattr(weapon, "name", None) or "").strip())
    if lt:
        return lt[1]
    return None


def effective_weapon_quality_tier(weapon) -> str:
    """Use flavor-chart tier when the weapon name is a flavored model; else DB quality."""
    ft = flavor_quality_tier_for_weapon(weapon)
    if ft:
        return (ft or "standard").strip().lower()
    q = (getattr(weapon, "quality", None) or "standard").strip().lower()
    if q not in ("poor", "standard", "excellent"):
        return "standard"
    return q


def resolve_weapon_equipment_template(weapon) -> Optional[Dict[str, Any]]:
    """
    equipment_data weapons row for this instance: generic template for flavored weapons,
    else lookup by exact weapon name (named catalog weapons, melee, etc.).
    """
    from world.equipment_data import get_weapon_by_name

    generic = generic_category_for_weapon(weapon)
    if generic:
        row = get_weapon_by_name(generic)
        if row:
            return row
    return get_weapon_by_name(getattr(weapon, "name", None) or "")


def augmented_weapon_label_for_combat_rules(weapon) -> str:
    """
    Combined label so combat_rules substring checks (smg, shotgun, assault rifle) still work
    when weapon.name is a flavored model string.
    """
    parts = [
        getattr(weapon, "weapon_type", None) or "",
        getattr(weapon, "name", None) or "",
    ]
    g = generic_category_for_weapon(weapon)
    if g:
        parts.append(g)
    return " ".join(p for p in parts if p).strip()


def _attachment_slots_default(category: str, weapon_type: str) -> int:
    wt = (weapon_type or "").lower()
    if wt == "flamethrower":
        return 0
    if category == "heavy_weapons":
        return 3
    return 3


def build_weapon_description(
    template: Dict[str, Any],
    tagline: str,
    *,
    source_note: str = "Edgerunner role package",
) -> str:
    q = (template.get("quality") or "standard").title()
    wt = template.get("weapon_type") or "weapon"
    base = template.get("_generic_name") or template.get("name") or "Firearm"
    return f"{tagline.strip()}. {q} quality {wt} ({source_note} - same game stats as {base})."


def reflavor_weapon_instance(
    weapon,
    *,
    quality: Optional[str] = None,
    source_note: str = "Inventory reflavor",
) -> tuple[bool, str]:
    """
    Assign a new **random** flavor model name (from ``WEAPON_FLAVOR_BY_QUALITY``) to an
    existing :class:`~world.inventory.models.Weapon` row and **save** it.

    Eligible weapons are those whose current name or ``weapon_type`` maps to a **generic**
    category key (e.g. "Very Heavy Pistol", "SMG"). Named catalog items (no generic mapping)
    are rejected.

    Updates: ``name``, ``description``, ``quality``, core stat fields from the resolved dict.
    ``clip`` / max ammo are only set from the template if the weapon currently has no clip.

    Returns:
        ``(True, success_message)`` or ``(False, error_message)``.
    """
    from world.equipment_data import get_weapon_by_name

    generic = generic_category_for_weapon(weapon)
    if not generic or generic not in WEAPON_FLAVOR_BY_QUALITY:
        return (
            False,
            "That weapon is not a generic category that can be re-flavored. "
            "Use this on items like \"Very Heavy Pistol\" or types that match a generic row; "
            "named catalog weapons keep their manufacturer model names.",
        )

    base = get_weapon_by_name(generic)
    if not base:
        return False, f"No equipment template found for {generic}."

    q = quality or (getattr(weapon, "quality", None) or base.get("quality") or "standard")
    q = str(q).strip().lower()
    if q not in ("poor", "standard", "excellent"):
        q = "standard"

    flavored = resolve_weapon_for_inventory(copy.deepcopy(base), quality=q, source_note=source_note)

    weapon.name = flavored["name"]
    weapon.description = flavored.get("description") or ""
    weapon.quality = flavored.get("quality", q)

    for attr, key in (
        ("damage", "damage"),
        ("rof", "rof"),
        ("hands", "hands"),
        ("concealable", "concealable"),
        ("category", "category"),
        ("weapon_type", "weapon_type"),
        ("attachment_slots", "attachment_slots"),
    ):
        if key in flavored and flavored[key] is not None:
            setattr(weapon, attr, flavored[key])

    tpl_clip = int(flavored.get("clip") or 0)
    if tpl_clip and not (getattr(weapon, "clip", None) or 0):
        weapon.clip = tpl_clip
        weapon.max_ammo = tpl_clip
        cur = getattr(weapon, "current_ammo", 0) or 0
        weapon.current_ammo = min(cur, tpl_clip)

    weapon.save()
    return True, (
        f"Re-flavored to |w{weapon.name}|n ({weapon.quality}). "
        f"Stats stay the same as |w{generic}|n - only the street identity changed."
    )


def resolve_weapon_for_inventory(
    base_weapon: Dict[str, Any],
    *,
    quality: Optional[str] = None,
    paid_value: Optional[int] = None,
    source_note: str = "Purchase",
) -> Dict[str, Any]:
    """
    If ``base_weapon['name']`` is a generic category in WEAPON_FLAVOR_BY_QUALITY, pick a random
    model for the given quality tier (poor / standard / excellent). Otherwise return a copy
    with optional quality/value overrides.

    Sets ``_generic_name`` on the dict for description text when flavored.
    """
    out = copy.deepcopy(base_weapon)
    generic = out.get("name")
    q = (quality or out.get("quality") or "standard").strip().lower()
    if q not in ("poor", "standard", "excellent"):
        q = "standard"
    out["quality"] = q

    if paid_value is not None:
        out["value"] = paid_value

    if generic not in WEAPON_FLAVOR_BY_QUALITY:
        out.pop("_generic_name", None)
        return out

    out["_generic_name"] = generic
    pools = WEAPON_FLAVOR_BY_QUALITY[generic]
    options = pools.get(q) or pools.get("standard") or []
    if not options:
        out.pop("_generic_name", None)
        return out

    choice = random.choice(options)
    out["name"] = choice["name"]
    out["description"] = build_weapon_description(out, choice["tagline"], source_note=source_note)
    if out.get("attachment_slots") is None:
        out["attachment_slots"] = _attachment_slots_default(
            str(out.get("category") or ""), str(out.get("weapon_type") or "")
        )
    out.pop("_generic_name", None)
    return out


def flavor_edgerunner_weapon(template: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Chargen package weapons: standard (or template) quality, Edgerunner wording in description."""
    if not template:
        return None
    q = (template.get("quality") or "standard").strip().lower()
    return resolve_weapon_for_inventory(
        template,
        quality=q,
        source_note="Edgerunner role package",
    )


def ammunition_catalog_weapon_type(weapon) -> str:
    """
    Map an inventory Weapon to ammunition_data \"weapon_type\" (Pistol, Rifle, SMG, ...).
    Uses weapon.weapon_type when set (required for flavor names); falls back to legacy name parsing.
    """
    wt = (getattr(weapon, "weapon_type", None) or "").strip().lower()
    if wt in ("medium pistol", "heavy pistol", "very heavy pistol"):
        return "Pistol"
    if wt in ("smg", "heavy smg"):
        return "SMG"
    if wt == "shotgun":
        return "Shotgun"
    if wt in ("assault rifle", "sniper rifle"):
        return "Rifle"
    if wt in ("grenade launcher", "rocket launcher", "flamethrower"):
        return "Heavy Weapons"
    if wt in ("bow", "crossbow"):
        return "Archery"
    name = getattr(weapon, "name", "") or ""
    if name:
        return name.split()[-1]
    return ""


def pick_ammunition_for_weapon(ammunition_list: list, weapon) -> Optional[dict]:
    """Choose ammo dict for this weapon; for Archery prefers cheapest BASIC if present."""
    label = ammunition_catalog_weapon_type(weapon)
    if not label:
        return None
    matches = [a for a in ammunition_list if a.get("weapon_type") == label]
    if not matches:
        return None
    if label == "Archery":
        basic = [a for a in matches if str(a.get("ammo_type", "")).upper() == "BASIC"]
        if basic:
            return min(basic, key=lambda a: a.get("cost", 999999))
    return matches[0]
