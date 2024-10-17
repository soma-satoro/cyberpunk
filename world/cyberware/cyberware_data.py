# world/cyberware/cyberware_data.py

from .models import Cyberware
"""
The dictionary data utilizes the following pattern for an entry:

    {
        "name": "",
        "type": "",
        "slots": ,
        "humanity_loss": ,
        "cost": ,
        "description": " "
    },

    """

CYBERWARE_DATA_LIST = [
    # Fashionware
    {
        "name": "Biomonitor",
        "type": "Fashionware",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Subdermal implant which generates a constant LED readout of pulse, temperature, respiration, blood sugar, etc. You can link your Biomonitor to your Agent to allow it to track your wellness."
    },
    {
        "name": "Chemskin",
        "type": "Fashionware",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Dyes and pigments infused into the skin to permanently change its hue."
    },
    {
        "name": "EMP Threading",
        "type": "Fashionware",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 10,
        "is_weapon": False,
        "description": "Thin silver lines that run in circuit-like patterns across the body."
    },
    {
        "name": "Light Tattoo",
        "type": "Fashionware",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Subdermal patches store light and project colored tattoos under the skin. +2 to Style if the user has three or more tattoos."
    },
    {
        "name": "Shift Tacts",
        "type": "Fashionware",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Color-changing lenses implanted into the eye itself!"
    },
    {
        "name": "Skinwatch",
        "type": "Fashionware",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Subdermally implanted LED watch."
    },
    {
        "name": "Techhair",
        "type": "Fashionware",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Color-light-emitting artificial hair."
    },
    # Add more Fashionware items -- Leaving open in case of new book releases.

    # Neuralware
    {
        "name": "Neural Link",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Wired artificial nervous system. Required to use Neuralware and Subdermal Grip. System has 5 Option Slots for Neuralware Options."
    },
    {
        "name": "Kerenzikov",
        "type": "Neuralware",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 500,
        "is_weapon": False,
        "description": "Speedware. User adds +2 to Initiative. Only 1 piece of Speedware can be installed at a time."
    },
    {
        "name": "Braindance Recorder",
        "type": "Neuralware",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Records user's experiences to memory chip or external device. Requires Neural Link.",
        "requirements": "Neural Link",
    },
    {
        "name": "Chipware Socket",
        "type": "Neuralware",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "A single socket installed in the back of the neck that allows quick installation of a single piece of Chipware, of which there are many varieties. Installing or uninstalling a single piece of Chipware from a Chipware Socket is an Action. The first time you install a piece of Chipware you've never used before, you always accrue Humanity Loss. Re-installing Chipware you've already used doesn't do this. Chipware does not take up a Neural Link Option Slot. Multiple sockets may be installed, but each must be paid for individually. Requires Neural Link.",
        "requirements": "Neural Link",
    },
    {
        "name": "Interface Plugs",
        "type": "Neuralware",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Plugs in wrist or head that allow connection to machines."
    },
    {
        "name": "Sandevistan",
        "type": "Neuralware",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Speedware. When activated as an Action adds +3 initiative for one minute. Has 1 hour cool down period. Only 1 piece of speedware can be installed at a time. Requires Neural Link.",
        "requirements": "Neural Link",
    },
    {
        "name": "Chemical Analyzer",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": False,
        "description": "Chipware. Tests substance for precise chemical composition and compares to a database. Requires Chipware Socket.",
        "requirements": "Chipware Socket",
    },
    {
        "name": "Memory Chip",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 0,
        "cost": 10,
        "is_weapon": False,
        "description": "Chipware. The standard for data storage. While installed into a Chipware socket, the user's cyberware can store data on it or access data stored on it. Requires Chipware Socket.",
        "requirements": "Chipware Socket",
    },
    {
        "name": "Olfactory Boost",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 100,
        "is_weapon": False,
        "description": "Chipware. While installed into a Chipware Socket, the user's sense of smell is boosted, allowing them to use the Tracking Skill to track scent in addition to visual clues. Requires Chipware Socket.",
        "requirements": "Chipware Socket",
    },
    {
        "name": "Pain Editor",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": False,
        "description": "Chipware. While installed into a Chipware Socket, a Pain Editor shuts off the user's pain receptors dynamically, allowing them to ignore the effects of the Seriously Wounded Wound State. Requires Chipware Socket.",
        "requirements": "Chipware Socket",
    },
    {
        "name": "Basic Skill Chip",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Chipware. While installed into a Chipware Socket, a Skill Chip makes the Skill it was made for trained for the user at +3, unless the user's Skill was already trained higher than +3, in which case it does nothing. Requires Chipware Socket.",
        "requirements": "Chipware Socket",
    },
    {
        "name": "Advanced Skill Chip",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 1000,
        "is_weapon": False,
        "description": "Chipware. While installed into a Chipware Socket, a Skill Chip makes the Skill it was made for trained for the user at +3, unless the user's Skill was already trained higher than +3, in which case it does nothing. This is for any skill that is purchased at 2x (Pilot Air, Martial Arts, Autofire, Heavy Weapons, Demolitions, Electronics, or Paramedic) Requires Chipware Socket.",
        "requirements": "Chipware Socket",
    },
    {
        "name": "Tactile Boost",
        "type": "Neuralware",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 100,
        "is_weapon": False,
        "description": "Chipware. While installed into a Chipware Socket, it boosts the user's sense of touch, allowing them to detect motion within 20m/yds of them, as long as their hand is touching a surface. While in use as a motion detector, that hand can't be used to do anything else. Requires Chipware Socket.",
        "requirements": "Chipware Socket",
    },
    # Add more Neuralware items -- Leaving open in case of new book releases.

    # Cyberoptics
    {
        "name": "Cybereye",
        "type": "Cyberoptics",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 100,
        "is_weapon": False,
        "description": "All following options are installed in an artificial eye that replaces a meat one. Each Cybereye has 3 Option Slots for Cybereye Options. Some options must be paired to work properly (purchased twice and installed in two different Cybereyes on a user. Humanity Loss is calculated separately for each purchase)."
    },
    {
        "name": "Chyron",
        "type": "Cyberoptics",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": " Projects a tiny subscreen into user's normal field of vision for messages, video, etc. from a user's other cyberware or electronics. Picture in a picture for real life. Requires a Cybereye.",
        "requirements": "Cybereye",
    },
    {
        "name": "Color Shift",
        "type": "Cyberoptics",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "Cosmetic upgrade allows unlimited color and pattern changes to be made as an Action. Eye can optionally be temperature sensitive or reactant to hormone changes in the body. Requires a Cybereye.",
        "requirements": "Cybereye",
    },
    {
        "name": "Dartgun",
        "type": "Cyberoptics",
        "slots": 3,
        "humanity_loss": 2,
        "cost": 500,
        "is_weapon": False,
        "description": "Dartgun Exotic Weapon, with only a single shot in the clip, concealed inside the Cybereye. Requires a Cybereye and takes 3 Option Slots.",
        "requirements": "Cybereye",
    },
    {
        "name": "Image Enhance",
        "type": "Cyberoptics",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": False,
        "description": "User adds +2 to their Perception, Lip Reading, and Conceal/Reveal Object Skills for Checks which include sight. Requires two Cybereyes and must be paired.",
        "requirements": "Cybereye",
    },
    {
        "name": "Low Light-IR-UV",
        "type": "Cyberoptics",
        "slots": 2,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": False,
        "description": "Reduces penalties imposed by darkness and other intangible obscurement, like smoke, fog, etc. to 0. User can distinguish hot meat from cold metal but cannot see through anything that could provide cover. Requires two Cybereyes, must be paired, and takes 2 Option Slots per Cybereye.",
        "requirements": "Cybereye",
    },
    {
        "name": "MicroVideo",
        "type": "Cyberoptics",
        "slots": 2,
        "humanity_loss": 2,
        "cost": 500,
        "is_weapon": False,
        "description": "Camera in eye records video and audio to a standard Memory Chip or linked Agent. Requires a Cybereye and takes 2 option slots.",
        "requirements": "Cybereye",
    },
    {
        "name": "Radiation Detector",
        "type": "Cyberoptics",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 1000,
        "is_weapon": False,
        "description": "Radiation readings within 100m/yds of the user are displayed in user's vision hovering over their source in the form of a blue glow.  Requires a Cybereye.",
        "requirements": "Cybereye",
    },
    {
        "name": "Targeting Scope",
        "type": "Cyberoptics",
        "slots": 1,
        "humanity_loss": 4,
        "cost": 500,
        "is_weapon": False,
        "description": "User gets a +1 to their Check when making an Aimed Shot. Multiple installations of this option provide user no additional benefit. Requires a Cybereye.",
        "requirements": "Cybereye",
    },
    {
        "name": "TeleOptics",
        "type": "Cyberoptics",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": False,
        "description": "User can see detail up to 800m/yds away. When attacking a target 51m/yds or further away with either a weapon's single shot firing mode or an Aimed Shot, you can add a +1 to your Check. Multiple installations of this option provide user no additional benefit. Does not stack with Sniping Scope Weapon Attachment.  Requires a Cybereye.",
        "requirements": "Cybereye",
    },
    {
        "name": "Virtuality",
        "type": "Cyberoptics",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "Projects cyberspace imagery over user's view of the world. Never forget your Virtuality Goggles again. Requires two Cybereyes and must be paired.",
        "requirements": "Cybereye",
    },

    # Add more Cyberoptics items -- Leaving open in case of new book releases.

    # Cyberaudio
    {
        "name": "Cyberaudio Suite",
        "type": "Cyberaudio",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Cyberaudio Suite is installed invisibly in the skull. System has 3 options for Cyberaudio Options. The user can only have one Cyberaudio Suite installed."
    },
    {
        "name": "Amplified Hearing",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": False,
        "description": "User adds +2 to their Perception Skill for Checks which include hearing. Requires a Cyberaudio Suite. Multiple installations of this option provide user no additional benefit.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Audio Recorder",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "Records audio to a standard Memory Chip or a linked Agent. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Bug Detector",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": " Beeps when user is within 2m/yds of a tap, bug, or other listening device. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Homing Tracer",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "Can follow a linked tracer up to 1 mile away. Comes with a free button-sized linked tracer. Replacements are 50eb. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Internal Agent",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": False,
        "description": "Fully functional Agent, controlled entirely via voice commands. Images are described, but output can be linked to a Cybereye with Chyron or a nearby screen if visual output is desired. The implanted Agent's Memory Chip cannot be removed without surgery. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Level Damper",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "Automatic noise compensation. User is immune to deafness or other effects caused by dangerously loud noises, like those produced by a flashbang. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Radio Communicator",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "User can communicate via radio, 1-mile range. Cyberaudio Suite. Requires a Cyberaudio Suite",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Radio Scanner and Music Player",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 50,
        "is_weapon": False,
        "description": "User can use an Action to scan all radio bands within a mile that are currently being used and tune into them. Music player can link to the Data Pool to listen to the hottest music or play directly from a Memory Chip. Understanding scrambled channels requires a Scrambler/Descrambler. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Radar Detector",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 500,
        "is_weapon": False,
        "description": "Beeps if active radar beam is present within 100m/yds. Requires a Cyberaudio Suite",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Scrambler Descrambler",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "Allows user to scramble outgoing communications so they cannot be understood without a descrambler, which is also included at no extra charge. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },
    {
        "name": "Voice Stress Analyzer",
        "type": "Cyberaudio",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": False,
        "description": "User adds +2 to their Human Perception and Interrogation Skills. User can activate a special lie-detecting function for a minute with an Action, during which time the GM rolls all your Character's Human Perception and Interrogation Checks privately, beeping once whenever it detects a lie, or whenever they desire after a failed roll. Beware of false positives and negatives. Requires a Cyberaudio Suite.",
        "requirements": "Cyberaudio Suite",
    },


    # Add more Cyberaudio items -- Leaving open in case of new book releases.


    # Internal Cyberware
    {
        "name": "AudioVox",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": False,
        "description": "Vocal synthesizer. User adds +2 to their Acting skill and also adds +2 to their Play Instrument Skill while singing. Multiple installations of this option provide user no additional benefit."
    },
    {
        "name": "Contraceptive Implant",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 0,
        "cost": 10,
        "is_weapon": False,
        "description": "Implant prevents undesired pregnancy regardless of equipment."
    },
    {
        "name": "Enhanced Antibodies",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 500,
        "is_weapon": False,
        "description": "After stabilization, the user heals a number of Hit Points equal to twice their BODY for each day they spend resting, doing only light activity, and spending the majority of the day taking it easy until returning to full HP, instead of at their typical rate."
    },
    {
        "name": "Cybersnake",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": True,
        "damage_dice": 4,
        "damage_die_type": 6,
        "rate_of_fire": 1,
        "description": "Horrifying throat/esophagus-mounted tentacle weapon. A Very Heavy Melee Weapon (4d6, 1 ROF) that can be successfully concealed without a Check."
    },
    {
        "name": "Gills",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 1000,
        "is_weapon": False,
        "description": "User can breathe underwater."
    },
    {
        "name": "Grafted Muscle and Bone Lace",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": False,
        "description": "User increases their Body by 2. This increase in Body changes a Character's HP, Wound Threshhold, and Death Save. Multiple installments stack. Cannot raise Body above 10."
    },
    {
        "name": "Independent Air Supply",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 1000,
        "is_weapon": False,
        "description": "Contains 30 minutes of air, before the user needs to refill the tank from the ambient air, which takes an hour. Alternatively, replacing an empty tank with a full one (50eb), takes an Action."
    },
    {
        "name": "Midnight Lady Sexual Implant",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 100,
        "is_weapon": False,
        "description": "Be a Venus, be the fire. Be desire."
    },
    {
        "name": "Mr. Studd Sexual Implant",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 100,
        "is_weapon": False,
        "description": "All night, every night. And they'll never know."
    },
    {
        "name": "Nasal Filters",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "User is immune to the effects of toxic gasses, fumes, and all similar dangers that must be inhaled to affect the user. User can deactivate nasal filters, if desired, without an Action."
    },
    {
        "name": "Radar Sonar Implant",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 1000,
        "is_weapon": False,
        "description": "Constantly scans terrain within 50m/yds of user, including underwater, for new threats. Scan does not include anything behind cover, like the contents of a room behind a closed door. User receives a beep from the GM along with the direction of its source whenever a new moving object is detected on the scan."
    },
    {
        "name": "Toxin Binders",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": False,
        "description": "User adds +2 to their Resist Torture/Drugs Skill. Multiple installations of this option provide user no additional benefit."
    },
    {
        "name": "Vampyres",
        "type": "Internal Body",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 500,
        "is_weapon": True,
        "damage_dice": 1,
        "damage_die_type": 6,
        "rate_of_fire": 2,
        "description": "Fangs implanted in the user's mouth. An Excellent Quality Light Melee Weapon (1d6 damage, 2 ROF) that can be successfully concealed without a Check. A Vial of Poison or Biotoxin (see gear) can be safely stored and concealed in a compartment in the roof of the mouth near the fangs without a Check. The contents of the stored vial can then be applied to the Vampyres silently anytime without an Action. Each application uses an entire vial and lasts for 30 minutes. Installation of Vampyres includes a complete rework of the user's mouth which prevents the possibility of poisoning yourself accidentally with your fangs halfway through a slice of pizza or due to a bad Check." 
    },
    # Add more Internal Cyberware items -- Leaving open in case of new book releases.


    # External Cyberware
    {
        "name": "Hidden Holster",
        "type": "External Body",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Holster inside the user's body can store a weapon already capable of concealment so that it can be successfully concealed without a roll. Weapon can be drawn from the hidden holster without an Action, as long as it is implanted in an easily accessible place on the user's body. You don't want one in your thigh unless you don't wear pants."
    },
    {
        "name": "Skin Weave",
        "type": "External Body",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "User's body and head are armored at SP7. Your SP in any location is determined by your highest source of SP in that location. Additionally, whenever your armor is ablated in a location, all your sources of SP in that location are ablated at the same time. Whenever the user successfully completes a day of natural healing, nanomachines present in the Skin Weave repair both the body and head location of the Skin Weave for one point of its lost SP."
    },
    {
        "name": "Subdermal Armor",
        "type": "External Body",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": False,
        "description": "User's body and head are armored at SP11. Your SP in any location is determined by your highest source of SP in that location. Additionally, whenever your armor is ablated in a location, all your sources of SP in that location are ablated at the same time. Whenever the user successfully completes a day of natural healing, nanomachines present in the Subdermal Armor repair both the body and head location of the Subdermal Armor for one point of its lost SP."
    },
    {
        "name": "Subdermal Pocket",
        "type": "External Body",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": False,
        "description": "2x4 (5cm x 10cm) space with a Realskinn zipper. Contents can be successfully concealed without a Check."
    },

    # Add more External Cyberware items -- Leaving open in case of new book releases.

    # Cyberlimbs
    {
        "name": "Cyberarm",
        "type": "Cyberarm",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Replacement arm. Does not have to be paired. A Cyberarm has 4 Option Slots for Cyberarm or Cyberlimb Options, and each comes pre-installed with a Standard Hand that doesn't cost any Humanity Loss or take up a Cyberarm Option Slot."
    },
    {
        "name": "Standard Hand",
        "type": "Cyberarm",
        "slots": 0,
        "humanity_loss": 2,
        "cost": 100,
        "description": "Resembles a normal hand. If installed into a meat arm, a standard hand doesn't count towards the number of pieces of cyberware installed in a meat arm. Doesn't take up a Cyberarm Option Slot."
    },
    {
        "name": "Big Knucks",
        "type": "Cyberarm",
        "slots": 0,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": True,
        "damage_dice": 2,
        "damage_die_type": 6,
        "rate_of_fire": 2,
        "description": "Armored knuckles. A Medium Melee Weapon (2d6 damage, 2 ROF) that can be successfully concealed without a Check. When wielded as a weapon, user can't hold anything in this arm's hand. Can be installed as the only piece of Cyberware in a meat arm."
    },
    {
        "name": "Cyberdeck",
        "type": "Cyberarm",
        "slots": 3,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": False,
        "description": "Cyberdeck permanently installed into the user's Cyberarm. A Cyberdeck must be provided by the user at the time of installation. In addition to never accidentally misplacing your Cyberdeck, integration into a Cyberarm gives any Cyberdeck 1 extra slot that can be used for either Programs or Hardware. This is a permanent upgrade. Attempting to uninstall the Cyberdeck from the Cyberarm breaks it beyond repair, but any Programs or Hardware on it could be easily recovered. Requires a Cyberarm and takes 3 Option Slots. Cyberdeck still requires Interface Plugs and Neural Link to be operated by the user.",
        "requirements": "Cyberarm",
    },
    {
        "name": "Grapple Hand",
        "type": "Cyberarm",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": False,
        "description": "User, as an Action, can fire a rocket propelled grapple that will attach securely to any Thick cover up to 30m/yds away. Line can only support two times the user's body weight, and has 10 HP. The user negates the normal movement penalty for climbing when they climb this line, and can retract the line without an Action, including as they climb. When used as a grapple, user can't hold anything in this arm's hand. Ineffective as a weapon and cannot be used to make the Grab Action. Requires a Cyberarm.",
        "requirements": "Cyberarm",
    },
    {
        "name": "Medscanner",
        "type": "Cyberarm",
        "slots": 2,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Scanner with external probes and contacts diagnoses injury and illness, assisting user in medical emergencies not requiring the Surgery Skill. User adds +2 to their First Aid and Paramedic Skills. Requires a Cyberarm and takes 2 Option Slots. Multiple installations of this option provide user no additional benefit.",
        "requirements": "Cyberarm",
    },
    {
        "name": "Popup Grenade Launcher",
        "type": "Cyberarm",
        "slots": 2,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "A One-Handed Grenade Launcher with only a single grenade in its magazine that is incompatible with all Weapon Attachments except Smartgun Link is installed into the Cyberarm. Launcher can be successfully concealed without a Check and can be drawn and stowed without an Action. While the weapon is 'popped up,' the user can't hold anything in this arm's hand. Requires a Cyberarm and takes 2 Option Slots.",
        "requirements": "Cyberarm"
    },
    {
        "name": "Popup Melee Weapon",
        "type": "Cyberarm",
        "slots": 2,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "A One-Handed Light, Medium, or Heavy Melee Weapon (that need not be concealable before its installation) is installed in a Cyberarm so that it can be successfully concealed without a roll, and can be drawn and stowed without an Action. While the weapon is 'popped up,' the user can't hold anything in this arm's hand. Requires a Cyberarm and takes 2 Option Slots.",
        "requirements": "Cyberarm"
    },
    {
        "name": "Popup Shield",
        "type": "Cyberarm",
        "slots": 3,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "A Bulletproof Shield which is concealed while it is folded inside the Cyberarm. It can be drawn or stowed without an Action, provided that the shield has more than 0 HP. When extended, you can't use the Cyberarm to do anything else other than serve as a shield, and you can't hold anything in that Cyberarm's hand other than the shield. The Bulletproof Shield installed inside your Cyberarm is easily removable and replaceable with another Bulletproof Shield, for ease of cleaning and repair. Requires a Cyberarm and takes 3 Option Slots.",
        "requirements": "Cyberarm"
    },
    {
        "name": "Popup Ranged Weapon",
        "type": "Cyberarm",
        "slots": 2,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": " A One-Handed Ranged Weapon (that need not be concealable before its installation) provided by the user is permanently installed into the Cyberarm (along with any weapon attachments attached to it) so that it can be successfully concealed without a Check, and can be drawn and stowed without an Action. While the weapon is “popped up,” the user can't hold anything in this arm's hand. Requires a Cyberarm and takes 2 Option Slots.",
        "requirements": "Cyberarm"

    },
    {
        "name": "Quick Change Mount",
        "type": "Cyberarm",
        "slots": 1,
        "humanity_loss": 7,
        "cost": 100,
        "is_weapon": False,
        "description": "Cyberarm can be installed in an open socket or uninstalled with an Action. The first time you install a brand new Cyberarm, whether using a Quick Change Mount or otherwise, you always accrue Humanity Loss. Reattaching one you've already used before with a Quick Change Mount does not do this. Requires a Cyberarm.",
        "requirements": "Cyberarm"
    },
    {
        "name": "Rippers",
        "type": "Cyberarm",
        "slots": 0,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": True,
        "damage_dice": 2,
        "damage_die_type": 6,
        "rate_of_fire": 2,
        "description": "Extendable Carbo-glass fingernails. A Medium Melee Weapon (2d6 damage, 2 ROF) that can be successfully concealed without a Check. When wielded as a weapon, user can't hold anything in this arm's hand. Can be installed as the only piece of Cyberware in a meat arm."
    },
    {
        "name": "Scratchers",
        "type": "Cyberarm",
        "slots": 0,
        "humanity_loss": 2,
        "cost": 100,
        "is_weapon": True,
        "damage_dice": 1,
        "damage_die_type": 6,
        "rate_of_fire": 2,
        "description": "Carbo-glass artificial fingernails that cut on a diagonal slice. A Light Melee Weapon (1d6 damage, 2 ROF) that can be successfully concealed without a Check. When wielded as a weapon, user can't hold anything in this arm's hand. Can be installed as the only piece of Cyberware in a meat arm."
    },
    {
        "name": "Shoulder Cam",
        "type": "Cyberarm",
        "slots": 2,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Camera in a popup in the user's shoulder that tracks independently of the user and records video and audio to an onboard Memory Chip or a linked Agent. Camera can be successfully concealed without a Check and can be drawn and stowed without an Action. Requires a Cyberarm and takes 2 Option Slots.",
        "requirements": "Cyberarm"
    },
    {
        "name": "Slice N Dice",
        "type": "Cyberarm",
        "slots": 0,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": True,
        "damage_dice": 2,
        "damage_die_type": 6,
        "rate_of_fire": 2,
        "description": "Monofilament whip implanted in the user's thumb. A Medium Melee Weapon (2d6 damage, 2 ROF) that can be successfully concealed without a Check. When wielded as a weapon, user can't hold anything in this arm's hand. Can be installed as the only piece of Cyberware in a meat arm."
    },
    {
        "name": "Subdermal Grip",
        "type": "Cyberarm",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": False,
        "description": "Subdermal plate under the palm allows user to make use of Smartguns. A cost-effective alternative to Interface Plugs. Can be installed as the only piece of Cyberware in a meat arm. Requires Neural Link and takes up a Neuralware Option Slot.",
        "requirements": "Neural Link"
    },
{
        "name": "Techscanner",
        "type": "Cyberarm",
        "slots": 2,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": False,
        "description": "Scanner diagnoses a wide variety of machinery and electronics, assisting the user in repairs or other technical work. User adds +2 to their Basic Tech, Cybertech, Land Vehicle Tech, Sea Vehicle Tech, Air Vehicle Tech, Electronics/Security Tech, and Weaponstech Skills. Requires a Cyberarm and takes 2 Option Slots. Multiple installations of this option provide user no additional benefit.",
        "requirements": "Cyberarm"
},
    {
        "name": "Wolvers",
        "type": "Cyberarm",
        "slots": 0,
        "humanity_loss": 7,
        "cost": 500,
        "is_weapon": True,
        "damage_dice": 3,
        "damage_die_type": 6,
        "rate_of_fire": 2,
        "description": " Extendable Carbo-glass claws in the knuckles. A Heavy Melee Weapon (3d6 damage, 2 ROF) that can be successfully concealed without a Check. When wielded as a weapon, user can't hold anything in this arm's hand. Can be installed as the only piece of Cyberware in a meat arm."
    },
    {
        "name": "Cyberleg",
        "type": "Cyberleg",
        "slots": 0,
        "humanity_loss": 3,
        "cost": 100,
        "is_weapon": False,
        "description": "Replacement leg. Does not have to be paired. A Cyberleg has 3 Option Slots for Cyberleg or Cyberlimb Options and each comes pre-installed with a Standard Foot that doesn't cost any Humanity Loss or take up a Cyberleg Option Slot. Most Cyberleg options must be paired to work properly (purchased twice and installed in two different Cyberlegs on a user. Humanity Loss is calculated separately for each purchase)."
    },
    {
        "name": "Standard Foot",
        "type": "Cyberleg",
        "slots": 0,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Resembles a normal foot. If installed into a meat leg, a Standard Foot doesn't count towards the number of pieces of cyberware installed in a meat leg. Doesn't take up a Cyberleg Option Slot."
    },
    {
        "name": "Grip Foot",
        "type": "Cyberleg",
        "slots": 2,
        "humanity_loss": 6,
        "cost": 1000,
        "is_weapon": False,
        "description": "Feet are coated with state-of-the-art traction material. The user negates the normal movement penalty for climbing. Requires two Cyberlegs and must be paired.",
        "requirements": "Cyberleg"
    },
    {
        "name": "Jump Booster",
        "type": "Cyberleg",
        "slots": 4,
        "humanity_loss": 6,
        "cost": 1000,
        "is_weapon": False,
        "description": "Hydraulics in legs. Negates movement penalty when jumping. Requires two Cyberlegs, takes up 2 Option Slots, and must be paired.",
        "requirements": "Cyberleg"
    },
    {
        "name": "Skate Foot",
        "type": "Cyberleg",
        "slots": 2,
        "humanity_loss": 6,
        "cost": 1000,
        "description": "Inline skates built into feet. Can be concealed. Increases movement by 6m/yds when using Run Action. Requires two Cyberlegs and must be paired.",
        "requirements": "Cyberleg"
    },
    {
        "name": "Talon Foot",
        "type": "Cyberleg",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 500,
        "is_weapon": True,
        "damage_dice": 1,
        "damage_die_type": 6,
        "rate_of_fire": 2,
        "description": "Blade mounted in foot. Light Melee Weapon (1d6 ROF 2). Can be concealed without a Check. Can be installed as the only piece of Cyberware in a meat leg."
    },
    {
        "name": "Web Foot",
        "type": "Cyberleg",
        "slots": 2,
        "humanity_loss": 6,
        "cost": 1000,
        "is_weapon": False,
        "description": "Thin webbing between toes. Negates movement penalty when swimming. Requires Two Cyberlegs and must be paired",
        "requirements": "Cyberleg"
    },
    {
        "name": "Hardened Shielding",
        "type": "Cyberlimb",
        "slots": 1,
        "humanity_loss": 3,
        "cost": 1000,
        "is_weapon": False,
        "description": "Cyberlimb and installed options cannot be rendered inoperable by EMP effects, like Microwaver pulses, or Non-Black ICE Program effects. Requires Cyberarm or Cyberleg.",
        "requirements": "Cyberlimb"
    },
    {
        "name": "Plastic Covering",
        "type": "Cyberlimb",
        "slots": 0,
        "humanity_loss": 0,
        "cost": 100,
        "is_weapon": False,
        "description": "Plastic coating for Cyberlimb. Available in wide variety of colors and patterns. Requires a Cyberarm or Cyberleg but does not take an Option Slot.",
        "requirements": "Cyberlimb"
    },
    {
        "name": "Realskinn Covering",
        "type": "Cyberlimb",
        "slots": 0,
        "humanity_loss": 0,
        "cost": 500,
        "is_weapon": False,
        "description": "Artificial skin coating for Cyberlimb. Requires a Cyberarm or Cyberleg but does not take an Option Slot.",
        "requirements": "Cyberlimb"
    },
    {
        "name": "Superchrome Covering",
        "type": "Cyberlimb",
        "slots": 0,
        "humanity_loss": 0,
        "cost": 1000,
        "is_weapon": False,
        "description": "Shiny metallic coating for Cyberlimb. +2 to Style. This bonus only applies once. Requires a Cyberarm or Cyberleg but does not take an Option Slot.",
        "requirements": "Cyberlimb"
    },

    # Add more Cyberlimb items -- Leaving open in case of new book releases.


    # Borgware
    {
        "name": "Artificial Shoulder Mount",
        "type": "Borgware",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": False,
        "description": "User can mount 2 Cyberarms under first set of arms. User can only have one Artificial Shoulder Mount installed."
    },
    {
        "name": "Implanted Linear Frame Sigma",
        "type": "Borgware",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": False,
        "description": "An enhanced skeleton and support structure with hydraulic and myomar muscles. User increases their BODY to 12. This increase in BODY changes a Character's HP and Death Save. This cannot increase the user's BODY to 13 or higher. Installation requires BODY 6 and Grafted Muscle and Bone Lace."
    },
    {
        "name": "Implanted Linear Frame Beta",
        "type": "Borgware",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 5000,
        "is_weapon": False,
        "description": "A heavily enhanced skeleton and support structure with even more hydraulic and myomar muscles. User increases their BODY to 14. This increase in BODY changes a Character's HP and Death Save. This cannot increase the user's BODY to 15 or higher. Installation requires BODY 8 and Two Grafted Muscle and Bone Lace."
    },
    {
        "name": "MultiOptic Mount",
        "type": "Borgware",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": False,
        "description": "User can mount up to 5 additional Cybereyes into the MultiOptic Mount. Cybereyes sold and installed separately. User can only have one MultiOptic Mount installed."
    },
    {
        "name": "Sensor Array",
        "type": "Borgware",
        "slots": 1,
        "humanity_loss": 14,
        "cost": 1000,
        "is_weapon": False,
        "description": "Twin flattened antennae protruding from the user's head improving their Cyberaudio Suite, sometimes referred to as 'Rabbit Ears.' User can install up to 5 additional Cyberaudio Options into their Cyberaudio Suite. User can only have one Sensor Array installed. Requires Cyberaudio Suite but doesn't take up a Cyberaudio Option Slot.",
        "requirements": "Cyberaudio Suite"
    }
]

CYBERWARE_DATA = {item['name']: item for item in CYBERWARE_DATA_LIST}