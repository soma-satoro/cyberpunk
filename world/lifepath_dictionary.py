# Lifepath data
CULTURAL_ORIGINS = [
    "North American", "South/Central American", "Western European", "Eastern European",
    "Middle Eastern/North African", "Sub-Saharan African", "South Asian", "South East Asian",
    "East Asian", "Oceania/Pacific Islander"
]

PERSONALITIES = [
    "Shy and secretive", "Rebellious, antisocial, and violent", "Arrogant, proud, and aloof",
    "Moody, rash, and headstrong", "Picky, fussy, and nervous", "Stable and serious",
    "Silly and fluff-headed", "Sneaky and deceptive", "Intellectual and detached",
    "Friendly and outgoing"
]

CLOTHING_STYLES = [
    "Generic Chic", "Leisurewear", "Urban Flash", "Businesswear", "High Fashion",
    "Bohemian", "Bag Lady Chic", "Gang Colors", "Nomad Leathers", "Asia Pop"
]

HAIRSTYLES = [
    "Mohawk", "Long and ratty", "Short and spiked", "Wild and all over",
    "Bald", "Striped", "Wild colors", "Neat and short", "Short and curly",
    "Long and straight"
]

AFFECTATIONS = [
    "Tattoos", "Mirrorshades", "Ritual scars", "Spiked gloves", "Nose rings",
    "Tongue or other piercings", "Strange fingernail implants", "Spiked boots or heels",
    "Fingerless gloves", "Strange contacts"
]

MOTIVATIONS = [
    "Money", "Honor", "Your word", "Honesty", "Knowledge", "Vengeance",
    "Love", "Power", "Family", "Friendship"
]

LIFE_GOALS = [
    "Get rid of a bad reputation", "Gain power and control",
    "Get off The Street no matter what it takes",
    "Cause pain and suffering to anyone who crosses you",
    "Live down your past life and try to forget it",
    "Hunt down those responsible for your miserable life and make them pay",
    "Get what's rightfully yours",
    "Save, if possible, anyone else involved in your background, like a lover, or family member",
    "Gain fame and recognition", "Become feared and respected"
]

VALUED_PERSON = [
    "A parent", "A brother or sister",
    "A lover", "A friend", "Yourself",
    "A pet", "A teacher or mentor",
    "A public figure",
    "A personal hero",
    "No one"
]
VALUED_POSSESSION = [
    "A weapon", "A tool", 
    "A piece of clothing",
    "A photograph", 
    "A book or diary",
    "A recording",
    "A musical instrument", 
    "A piece of jewelry", 
    "A toy", "A letter"

]
FAMILY_BACKGROUND = [
    "Corporate Execs: Wealthy, powerful, with servants, luxury homes, and the best of everything. Private security made sure you were always safe. You definitely went to a big-name private school.",
    "Corporate Managers: Well to do, with large homes, safe neighborhoods, nice cars, etc. Sometimes your parent(s) would hire servants, although this was rare. You had a mix of private and corporate education.",
    "Corporate Technicians: Middle-middle class, with comfortable conapts or Beaverville suburban homes, minivans and corporate-run technical schools. Kind of like living 1950s America crossed with 1984.",
    "Nomad Pack: You had a mix of rugged trailers, vehicles, and huge road kombis for your home. You learned to drive and fight at an early age, but the family was always there to care for you. Food was actually fresh and abundant. Mostly home schooled.",
    "Ganger 'Family': A savage, violent home in any place the gang could take over. You were usually hungry, cold, and scared. You probably didn't know who your actual parents were. Education? The Gang taught you how to fight, kill, and steal.",
    "Combat Zoners: A step up from a gang 'family,' your home was a decaying building somewhere in the 'Zone', heavily fortified. You were hungry at times, but regularly could score a bed and a meal. Home schooled.",
    "Urban Homeless: You lived in cars, dumpsters, or abandoned shipping modules. If you were lucky. You were usually hungry, cold, and scared, unless you were tough enough to fight for the scraps. Education? School of Hard Knocks.",
    "Megastructure Warren Rats: You grew up in one of the huge new megastructures that went up after the War. A tiny conapt, kibble food, a mostly warm bed. Some better educated adult warren dwellers or a local Corporation may have set up a school.",
    "Reclaimers: You started out on the road, but then moved into one of the deserted ghost towns or cities to rebuild it. Dangerous, with plenty of simple food and a safe place to sleep. You were home schooled if there was anyone who had the time.",
    "Edgerunners: Your home was always changing based on your parents' current 'job.' Could be a luxury apartment, an urban conapt, or a dumpster if you were on the run. Food and shelter ran the gamut from gourmet to kibble."
]

ENVIRONMENT = [
    "Ran on The Street, with no adult supervision.",
    "Spent in a safe Corp Zone walled off from the rest of the City.",
    "In a Nomad pack moving from place to place.",
    "In a Nomad pack with roots in transport (ships, planes, caravans).",
    "In a decaying, once upscale neighborhood, now holding off the boosters to survive.",
    "In the heart of the Combat Zone, living in a wrecked building or other squat.",
    "In a huge 'megastructure' building controlled by a Corp or the City.",
    "In the ruins of a deserted town or city taken over by the Reclaimers.",
    "In a Drift Nation (a floating offshore city) that is a meeting place for all kinds of people.",
    "In a Corporate luxury 'starscraper,' high above the rest of the teeming rabble."

]
FAMILY_CRISIS = [
    "Your family lost everything through betrayal.",
    "Your family lost everything through bad management.",
    "Your family was exiled or otherwise driven from their original home/nation/Corporation.",
    "Your family is imprisoned, and you alone escaped.",
    "Your family vanished. You are the only remaining member.",
    "Your family was killed, and you were the only survivor.",
    "Your family is involved in a long-term conspiracy, organization, or association, such as a crime family or revolutionary group.",
    "Your family was scattered to the winds due to misfortune.",
    "Your family is cursed with a hereditary feud that has lasted for generations.",
    "You are the inheritor of a family debt; you must honor this debt before moving on with your life."

]
ROLE_SPECIFIC_LIFEPATHS = {
    "Rockerboy": [
        ("What Kind of Rockerboy are You?", [
            "Musician", "Slam Poet", "Street Artist", "Performance Artist",
            "Comedian", "Orator", "Politico", "Rap Artist", "DJ", "Idoru"
        ]),
        ("Who's Gunning for You/Your Group?", [
            "Old group member who thinks you did them dirty",
            "Rival group or artist trying to steal market share",
            "Corporate enemies who don't like your message",
            "Critic or other 'influencer' trying to bring you down",
            "Older media star who feels threatened by your rising fame",
            "Romantic interest or media figure who wants revenge for personal reasons"
        ]),
        ("Where Do You Perform?", [
            "Alternative Cafes", "Private Clubs", "Seedy Dive Bars",
            "Guerrilla Performances", "Nightclubs Around the City", "On the Data Pool"
        ])
    ],
    "Solo": [
        ("What Kind of Solo are You?", [
            "Bodyguard", "Street Muscle for Hire", "Corporate Enforcer who takes jobs on the side",
            "Corporate or Freelance Black Ops Agent", "Local Vigilante for Hire", "Assassin/Hitman for Hire"
        ]),
        ("What's Your Moral Compass Like?", [
            "Always working for good, trying to take out the 'bad guys'",
            "Always spare the innocent (elderly, women, children, pets)",
            "Will occasionally slip and do unethical or bad things, but it's rare",
            "Ruthless and profit centered; you will work for anyone, take any job for the money",
            "Willing to bend the rules (and the law) to get the job done",
            "Totally evil. You engage in illegal, unethical work all the time; in fact, you enjoy it"
        ]),
        ("Who's Gunning for You?", [
            "A Corporation you may have angered",
            "A boostergang you may have tackled earlier",
            "Corrupt Lawmen or Lawmen who mistakenly think you're guilty of something",
            "A rival Solo from another Corp",
            "A Fixer who sees you as a threat",
            "A rival Solo who sees you as their nemesis"
        ]),
        ("What's Your Operational Territory?", [
            "A Corporate Zone", "Combat Zones", "The whole City",
            "The territory of a single Corporation",
            "The territory of a particular Fixer or contact",
            "Wherever the money takes you"
        ])
    ],
    "Netrunner": [
        ("What Kind of Runner are You?", [
            "Freelancer who will hack for hire",
            "Corporate 'clone runner' who hacks for the Man",
            "Hacktivist interested in cracking systems and exposing bad guys",
            "Just like to crack systems for the fun of it",
            "Part of a regular team of freelancers",
            "Hack for a Media, politico, or Lawman who hires you as needed"
        ]),
        ("Who are Some of Your Other Clients?", [
            "Local Fixers who send you clients",
            "Local gangers who also protect your work area while you sweep for NET threats",
            "Corporate Execs who use you for 'black project' work",
            "Local Solos or other combat types who use you to keep their personal systems secure",
            "Local Nomads and Fixers who use you to keep their family systems secure",
            "You work for yourself and sell whatever data you can find on the NET"
        ]),
        ("Where Do You Get Your Programs?", [
            "Dig around in old abandoned City Zones",
            "Steal them from other Netrunners you brain-burn",
            "Have a local Fixer supply programs in exchange for hack work",
            "Corporate Execs supply you with programs in exchange for your services",
            "You have backdoors into a few Corporate warehouses",
            "You hit the Night Markets and score programs whenever you can"
        ]),
        ("Who's Gunning for You?", [
            "You think it might be a rogue AI or a NET Ghost. Either way, it's bad news",
            "Rival Netrunners who just don't like you",
            "Corporates who want you to work for them exclusively",
            "Lawmen who consider you an illegal 'black hat' and want to bust you",
            "Old clients who think you screwed them over",
            "Fixer or another client who wants your services exclusively"
        ])
    ],
    "Tech": [
        ("What Kind of Tech are You?", [
            "Cyberware Technician", "Vehicle Mechanic", "Jack of All Trades",
            "Small Electronics Technician", "Weaponsmith", "Crazy Inventor",
            "Robot and Drone Mechanic", "Heavy Machinery Mechanic", "Scavenger", "Nautical Mechanic"
        ]),
        ("What's Your Workspace Like?", [
            "A mess strewn with blueprint paper",
            "Everything is color coded, but it's still a nightmare",
            "Totally digital and obsessively backed up every day",
            "You design everything on your Agent",
            "You keep everything just in case you need it later",
            "Only you understand your filing system"
        ]),
        ("Who are Your Main Clients?", [
            "Local Fixers who send you clients",
            "Local gangers who also protect your work area or home",
            "Corporate Execs who use you for 'black project' work",
            "Local Solos or other combat types who use you for weapon upkeep",
            "Local Nomads and Fixers who bring you 'found' tech to repair",
            "You work for yourself and sell what you invent/repair"
        ]),
        ("Where Do You Get Your Supplies?", [
            "Scavenge the wreckage you find in abandoned City Zones",
            "Strip gear from bodies after firefights",
            "Have a local Fixer bring you supplies in exchange for repair work",
            "Corporate Execs supply you with stuff in exchange for your services",
            "You have backdoor into a few Corporate warehouses",
            "You hit the Night Markets and score deals whenever you can"
        ]),
        ("Who's Gunning For You?", [
            "Combat Zone gangers who want you to work for them exclusively",
            "Rival Tech trying to steal your customers",
            "Corporates who want you to work for them exclusively",
            "Larger manufacturer trying to bring you down because your mods are a threat",
            "Old client who thinks you screwed them over",
            "Rival Tech trying to beat you out for resources and parts"
        ])
    ],
    "Medtech": [
        ("What Kind of Medtech are You?", [
            "Surgeon", "General Practitioner", "Trauma Medic", "Psychiatrist",
            "Cyberpsycho Therapist", "Ripperdoc", "Cryosystems Operator",
            "Pharmacist", "Bodysculptor", "Forensic Pathologist"
        ]),
        ("Who are Your Main Clients?", [
            "Local Fixers who send you clients",
            "Local gangers who also protect your work area or home in exchange for medical help",
            "Corporate Execs who use you for 'black project' medical work",
            "Local Solos or other combat types who use you for medical help",
            "Local Nomads and Fixers who bring you wounded clients",
            "Trauma Team paramedical work"
        ]),
        ("Where Do You Get Your Supplies?", [
            "Scavenge stashes of medical supplies you find in abandoned City Zones",
            "Strip parts from bodies after firefights",
            "Have a local Fixer bring you supplies in exchange for medical work",
            "Corporate Execs or Trauma Team supply you with stuff in exchange for your services",
            "You have a backdoor into a few Corporate or Hospital warehouses",
            "You hit the Night Markets and score deals whenever you can"
        ])
    ],
    "Media": [
        ("What Kind of Media are You?", [
            "Blogger", "Writer (Books)", "Videographer", "Documentarian",
            "Investigative Reporter", "Street Scribe"
        ]),
        ("How Does Your Work Reach the Public?", [
            "Monthly magazine", "Blog", "Mainstream vid feed",
            "News channel", "'Book' sales", "Screamsheets"
        ]),
        ("How Ethical are You?", [
            "Fair, honest reporting, strong ethical practices. You only report the verifiable truth",
            "Fair and honest reporting, but willing to go on hearsay and rumor if that's what it takes",
            "Will occasionally slip and do unethical things, but it's rare. You have some standards",
            "Willing to bend any rules to get the bad guys. But only the bad guys",
            "Ruthless and determined to make it big, even if it means breaking the law. You're a muckraker",
            "Totally corrupt. You take bribes, engage in illegal, unethical reporting all the time. Your pen is for hire to the highest bidder"
        ]),
        ("What Types of Stories Do You Want to Tell?", [
            "Political Intrigue", "Ecological Impact", "Celebrity News",
            "Corporate Takedowns", "Editorials", "Propaganda"
        ])
    ],
    "Exec": [
        ("What Kind of Corp Do You Work For?", [
            "Financial", "Media and Communications", "Cybertech and Medical Technologies",
            "Pharmaceuticals and Biotech", "Food, Clothing, or other General Consumables",
            "Energy Production", "Personal Electronics and Robotics", "Corporate Services",
            "Consumer Services", "Real Estate and Construction"
        ]),
        ("What Division Do You Work In?", [
            "Procurement", "Manufacturing", "Research and Development",
            "Human Resources", "Public Affairs/Publicity/Advertising", "Mergers and Acquisitions"
        ]),
        ("How Good/Bad is Your Corp?", [
            "Always working for good, fully supporting ethical practices",
            "Operates as a fair and honest business all the time",
            "Will occasionally slip and do unethical things, but it's rare",
            "Willing to bend the rules to get what it needs",
            "Ruthless and profit-centered, willing to do some bad things",
            "Totally evil. Will engage in illegal, unethical business all the time"
        ]),
        ("Where is Your Corp Based?", [
            "One city", "Several cities", "Statewide", "National",
            "International, offices in a few major cities", "International, offices everywhere"
        ]),
        ("Who's Gunning for Your Group?", [
            "Rival Corp in the same industry",
            "Law enforcement is watching you",
            "Local Media wants to bring you down",
            "Different divisions in your own company are feuding with each other",
            "Local government doesn't like your Corp",
            "International Corporations are eyeing you for a hostile takeover"
        ]),
        ("Current State with Your Boss", [
            "Your Boss mentors you but watch out for their enemies",
            "Your Boss gives you a free hand and doesn't want to know what you're up to",
            "Your Boss is a micromanager who tries to meddle in your work",
            "Your Boss is a psycho whose unpredictable outbursts are offset by quiet paranoia",
            "Your Boss is cool and watches your back against rivals",
            "Your Boss is threatened by your meteoric rise and is planning to knife you"
        ])
    ],
    "Lawman": [
        ("What is Your Position on the Force", [
            "Guard", "Standard Beat or Patrol", "Criminal Investigation",
            "Special Weapons and Tactics", "Motor Patrol", "Internal Affairs"
        ]),
        ("How Wide is Your Group's Jurisdiction?", [
            "Corporate Zones", "Standard City Patrol Zone", "Combat Zones",
            "Outer City", "Recovery Zones", "Open Highways"
        ]),
        ("How Corrupt is Your Group?", [
            "Fair, honest policing, strong ethical practices",
            "Fair and honest policing, but hard on lawbreakers",
            "Will occasionally slip and do unethical things, but it's rare",
            "Willing to bend any rules to get the bad guys",
            "Ruthless and determined to control The Street, even if it means breaking the law",
            "Totally corrupt. You take bribes, engage in illegal, and unethical business all the time"
        ]),
        ("Who's Gunning for Your Group?", [
            "Organized Crime", "Boostergangs", "Police Accountability Group",
            "Dirty Politicians", "Smugglers", "Street Criminals"
        ]),
        ("Who is Your Group's Major Target?", [
            "Organized Crime", "Boostergangs", "Drug Runners",
            "Dirty Politicians", "Smugglers", "Street Crime"
        ])
    ],
"Fixer": [
        ("What Kind of Fixer are You?", [
            "Broker deals between rival gangs",
            "Procure rare or atypical resources for exclusive clientele",
            "Specialize in brokering Solo or Tech services as an agent",
            "Supply a regular resource for the Night Markets, like food, medicines, or drugs",
            "Procure highly illegal resources, like street drugs or milspec weapons",
            "Supply resources for Techs and Medtechs, like parts and medical supplies",
            "Operate several successful Night Markets, although not as owner",
            "Broker use contracts for heavy machinery, military vehicles, and aircraft",
            "Broker deals as a fence for scavengers raiding Corps or Combat Zones",
            "Act as an exclusive agent for a Media, Rockerboy, or a Nomad Pack"
        ]),
        ("Who are Your Side Clients?", [
            "Local Rockerboys or Medias who use you to get them gigs or contacts",
            "Local gangers who also protect your work area or home",
            "Corporate Execs who use you for 'black project' procurement work",
            "Local Solos or other combat types who use you to get them jobs or contacts",
            "Local Nomads and Fixers who use you to set up transactions or deals",
            "Local politicos or Execs who depend on you for finding out information"
        ]),
        ("Who's Gunning for You?", [
            "Combat Zone gangers who want you to work for them exclusively",
            "Rival Fixers trying to steal your clients",
            "Execs who want you to work for them exclusively",
            "Enemy of a former client who wants to clean up 'loose ends'—like you",
            "Old client who thinks you screwed them over",
            "Rival Fixer trying to beat you out for resources and parts"
        ])
    ],
    "Nomad": [
        ("How Big is Your Pack?", [
            "A single extended tribe or family",
            "A couple dozen members",
            "Forty or fifty members",
            "A hundred or more members",
            "A Blood Family (hundreds of members)",
            "An Affiliated Family (made of several Blood Families)"
        ]),
        ("What Do You Do for Your Pack?", [
            "Scout (negotiator)",
            "Outrider (protection, weapons)",
            "Transport pilot/driver",
            "Loadmaster (large cargo mover, trucker)",
            "Solo smuggler",
            "Procurement (fuel, vehicles, etc.)"
        ]),
        ("What's Your Pack's Overall Philosophy?", [
            "Always working for good; your Pack accepts others, just wants to get along",
            "It's more like a family business. Operates as a fair and honest concern",
            "Will occasionally slip and do unethical things, but it's rare",
            "Willing to bend the rules whenever they get in the way to get what the Pack needs",
            "Ruthless and self-centered, willing to do some bad things if it will get the Pack ahead",
            "Totally evil. You rage up and down the highways, killing, looting, and just terrorizing everyone"
        ]),
        ("Who's Gunning for Your Pack?", [
            "Organized Crime",
            "Boostergangs",
            "Drug Runners",
            "Dirty Politicians",
            "Rival Packs in the same businesses",
            "Dirty Cops"
        ]),
        ("Is Your Pack Based on Land, Air, or Sea?", [
            "Land", "Air", "Sea"
        ]),
        ("If on Land, What Do They Do?", [
            "Gogang",
            "Passenger transport",
            "Chautauqua/school",
            "Traveling show/carnival",
            "Migrant farmers",
            "Cargo transport",
            "Shipment protection",
            "Smuggling",
            "Mercenary army",
            "Construction work gang"
        ]),
        ("If in Air, What Do They Do?", [
            "Air piracy",
            "Cargo transport",
            "Passenger transport",
            "Aircraft protection",
            "Smuggling",
            "Combat support"
        ]),
        ("If at Sea, What Do They Do?", [
            "Piracy",
            "Cargo transport",
            "Passenger transport",
            "Smuggling",
            "Combat support",
            "Submarine warfare"
        ])
    ]
}