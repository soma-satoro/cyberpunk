from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from evennia.accounts.models import AccountDB
from evennia.objects.models import ObjectDB
from evennia.utils.idmapper.models import SharedMemoryModel
from django.apps import apps
from evennia.utils import logger
from world.languages.models import Language, CharacterLanguage
from world.languages.language_dictionary import LANGUAGES
from world.inventory.models import CyberwareInstance, Inventory
from world.utils.calculation_utils import calculate_points_spent

class CharacterSheet(SharedMemoryModel):
    account = models.OneToOneField(AccountDB, related_name='character_sheet', on_delete=models.CASCADE, null=True)
    character = models.OneToOneField(ObjectDB, related_name='character_sheet', on_delete=models.CASCADE, null=True, unique=True)
    db_object = models.OneToOneField('objects.ObjectDB', related_name='db_character_sheet', on_delete=models.CASCADE, null=True)
    
    class Meta:
        unique_together = ('account', 'character')
    
    @classmethod
    def create_sheet(cls, account, character, **kwargs):
        sheet = cls.objects.create(account=account, character=character, **kwargs)
        if character:
            character.db.character_sheet_id = sheet.id
        return sheet

    @property
    def language_list(self):
        return [
            {
                'name': lang.language.name,
                'level': lang.level
            }
            for lang in self.character_languages.all()
        ]

    def add_language(self, language_name, level):
        from world.languages.models import Language, CharacterLanguage
        language, _ = Language.objects.get_or_create(name=language_name)
        char_lang, _ = CharacterLanguage.objects.get_or_create(
            character_sheet=self,
            language=language,
            defaults={'level': level}
        )
        char_lang.level = level
        char_lang.save()

    def remove_language(self, language_name):
        from world.languages.models import Language, CharacterLanguage
        try:
            language = Language.objects.get(name__iexact=language_name)
            CharacterLanguage.objects.filter(character_sheet=self, language=language).delete()
        except Language.DoesNotExist:
            pass  # Language not found, nothing to remove

    def calculate_spent_points(self):
        try:
            stat_points = sum([
                self.intelligence, self.reflexes, self.dexterity, self.technology,
                self.cool, self.willpower, self.luck, self.move, self.body, self.empathy
            ])
            logger.log_info(f"Stat points: {stat_points}")

            double_cost_skills = ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics', 'paramedic'], 
            skill_points = sum([
                getattr(self, skill) * (2 if skill in double_cost_skills else 1)
                for skill in [
                    'concentration', 'conceal_object', 'lip_reading', 'perception', 'tracking', 'athletics', 
                    'contortionist', 'dance', 'endurance', 'resist_torture_drugs', 'stealth', 'drive_land', 
                    'pilot_air', 'pilot_sea', 'riding', 'accounting', 'animal_handling', 'bureaucracy', 'business', 
                    'composition', 'criminology', 'cryptography', 'deduction', 'education', 'gamble', 'languages', 
                    'library_search', 'local_expert', 'tactics', 'wilderness_survival', 'brawling', 'evasion', 'martial_arts', 
                    'melee', 'acting', 'archery', 'autofire', 'handgun', 'heavy_weapons', 'shoulder_arms', 'bribery', 'conversation', 
                    'human_perception', 'interrogation', 'persuasion', 'streetwise', 'trading', 'style', 'air_vehicle_tech', 
                    'basic_tech', 'cybertech', 'demolitions', 'electronics', 'first_aid', 'forgery', 'land_vehicle_tech', 'artistry', 
                    'paramedic', 'photography', 'pick_lock', 'pick_pocket', 'sea_vehicle_tech', 'weaponstech', 'charismatic_impact', 
                    'combat_awareness', 'interface', 'maker', 'medicine', 'credibility', 'teamwork', 'backup', 'operator', 'moto',
                    'zoology', 'stock_market', 'physics', 'biology', 'chemistry', 'neuroscience', 'data_science', 'economics', 'sociology',
                    'political_science', 'genetics', 'anatomy', 'robotics', 'nanotechnology'
                ]
            ])

            # Add points from languages
            language_points = sum(lang.level for lang in self.character_languages.all())
            
            total_skill_points = skill_points + language_points
            logger.log_info(f"Total skill points (including languages): {total_skill_points}")

            return stat_points, total_skill_points
        except Exception as e:
            logger.log_err(f"Error in calculate_spent_points: {str(e)}")
            return 0, 0  # Return default values in case of error

    def get_remaining_points(self):
        stat_points_spent, skill_points_spent = calculate_points_spent(self)
        remaining_stat_points = max(0, 62 - stat_points_spent)
        remaining_skill_points = max(0, 86 - skill_points_spent)
        return remaining_stat_points, remaining_skill_points

    @classmethod
    def create_character_sheet(cls, account):
        character_sheet = cls.objects.create(account=account)
        Inventory.objects.get_or_create(character=character_sheet)
        return character_sheet

    def set_default_language(self):
        english = Language.objects.get(name="English")
        CharacterLanguage.objects.get_or_create(
            character=self,
            language=english,
            defaults={'level': 4}
        )

    # Add all fields from the migration file here
    full_name = models.CharField(max_length=255, blank=True)
    handle = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=50, blank=True)
    age = models.PositiveIntegerField(default=0)
    hometown = models.CharField(max_length=40, blank=True)
    height = models.PositiveIntegerField(default=0)
    weight = models.PositiveIntegerField(default=0)
    current_luck = models.PositiveIntegerField(default=1)
    _max_hp = models.PositiveIntegerField(default=0)
    _current_hp = models.PositiveIntegerField(default=0)
    humanity = models.IntegerField(default=0)
    humanity_loss = models.IntegerField(default=0)
    total_cyberware_humanity_loss = models.IntegerField(default=0)
    death_save = models.PositiveIntegerField(default=0)
    serious_wounds = models.PositiveIntegerField(default=0)
    eqweapon = models.ForeignKey('inventory.Weapon', on_delete=models.SET_NULL, null=True, blank=True, related_name='equipped_by')
    eqarmor = models.ForeignKey('inventory.Armor', on_delete=models.SET_NULL, null=True, blank=True, related_name='equipped_by')
    eurodollars = models.IntegerField(default=0)
    reputation_points = models.IntegerField(default=0)
    rep = models.IntegerField(default=0)
    is_complete = models.BooleanField(default=False)

    # General lifepath fields
    cultural_origin = models.CharField(max_length=100, blank=True)
    personality = models.CharField(max_length=100, blank=True)
    clothing_style = models.CharField(max_length=100, blank=True)
    hairstyle = models.CharField(max_length=100, blank=True)
    affectation = models.CharField(max_length=100, blank=True)
    motivation = models.CharField(max_length=100, blank=True)
    life_goal = models.CharField(max_length=200, blank=True)
    valued_person = models.CharField(max_length=200, blank=True)
    valued_possession = models.CharField(max_length=200, blank=True)
    family_background = models.CharField(max_length=255, blank=True)
    environment = models.CharField(max_length=255, blank=True)
    family_crisis = models.CharField(max_length=255, blank=True)

    # Role-specific fields
    what_kind_of_rockerboy_are_you = models.CharField(max_length=100, blank=True)
    whos_gunning_for_you_your_group = models.CharField(max_length=200, blank=True)
    where_do_you_perform = models.CharField(max_length=100, blank=True)
    what_kind_of_solo_are_you = models.CharField(max_length=100, blank=True)
    whats_your_moral_compass_like = models.CharField(max_length=200, blank=True)
    whos_gunning_for_you = models.CharField(max_length=200, blank=True)
    whats_your_operational_territory = models.CharField(max_length=100, blank=True)
    what_kind_of_runner_are_you = models.CharField(max_length=100, blank=True)
    who_are_some_of_your_other_clients = models.CharField(max_length=200, blank=True)
    where_do_you_get_your_programs = models.CharField(max_length=200, blank=True)
    what_kind_of_tech_are_you = models.CharField(max_length=100, blank=True)
    whats_your_workspace_like = models.CharField(max_length=200, blank=True)
    who_are_your_main_clients = models.CharField(max_length=200, blank=True)
    where_do_you_get_your_supplies = models.CharField(max_length=200, blank=True)
    what_kind_of_medtech_are_you = models.CharField(max_length=100, blank=True)
    what_kind_of_media_are_you = models.CharField(max_length=100, blank=True)
    how_does_your_work_reach_the_public = models.CharField(max_length=100, blank=True)
    how_ethical_are_you = models.CharField(max_length=200, blank=True)
    what_types_of_stories_do_you_want_to_tell = models.CharField(max_length=100, blank=True)
    what_kind_of_corp_do_you_work_for = models.CharField(max_length=100, blank=True)
    what_division_do_you_work_in = models.CharField(max_length=100, blank=True)
    how_good_bad_is_your_corp = models.CharField(max_length=200, blank=True)
    where_is_your_corp_based = models.CharField(max_length=100, blank=True)
    current_state_with_your_boss = models.CharField(max_length=200, blank=True)
    what_is_your_position_on_the_force = models.CharField(max_length=100, blank=True)
    how_wide_is_your_groups_jurisdiction = models.CharField(max_length=100, blank=True)
    how_corrupt_is_your_group = models.CharField(max_length=200, blank=True)
    who_is_your_groups_major_target = models.CharField(max_length=100, blank=True)
    what_kind_of_fixer_are_you = models.CharField(max_length=200, blank=True)
    how_big_is_your_pack = models.CharField(max_length=100, blank=True)
    what_do_you_do_for_your_pack = models.CharField(max_length=100, blank=True)
    whats_your_packs_overall_philosophy = models.CharField(max_length=200, blank=True)
    is_your_pack_based_on_land_air_or_sea = models.CharField(max_length=100, blank=True)
    if_on_land_what_do_they_do = models.CharField(max_length=100, blank=True)
    if_in_air_what_do_they_do = models.CharField(max_length=100, blank=True)
    if_at_sea_what_do_they_do = models.CharField(max_length=100, blank=True)

    # attributes
    intelligence = models.PositiveIntegerField(default=1)
    reflexes = models.PositiveIntegerField(default=1)
    dexterity = models.PositiveIntegerField(default=1)
    technology = models.PositiveIntegerField(default=1)
    cool = models.PositiveIntegerField(default=1)
    willpower = models.PositiveIntegerField(default=1)
    luck = models.PositiveIntegerField(default=1)
    move = models.PositiveIntegerField(default=1)
    body = models.PositiveIntegerField(default=1)
    empathy = models.PositiveIntegerField(default=1)

    # skills
    # Awareness Skills
    concentration = models.PositiveIntegerField(default=0)
    conceal_object = models.PositiveIntegerField(default=0)
    lip_reading = models.PositiveIntegerField(default=0)
    perception = models.PositiveIntegerField(default=0)
    tracking = models.PositiveIntegerField(default=0)
    # Body Skills
    athletics = models.PositiveIntegerField(default=0)
    contortionist = models.PositiveIntegerField(default=0)
    dance = models.PositiveIntegerField(default=0)
    endurance = models.PositiveIntegerField(default=0)
    resist_torture_drugs = models.PositiveIntegerField(default=0)
    stealth = models.PositiveIntegerField(default=0)
    # Control Skills
    drive_land = models.PositiveIntegerField(default=0)
    pilot_air = models.PositiveIntegerField(default=0)
    pilot_sea = models.PositiveIntegerField(default=0)
    riding = models.PositiveIntegerField(default=0)
    # Education Skills
    accounting = models.PositiveIntegerField(default=0)
    animal_handling = models.PositiveIntegerField(default=0)
    bureaucracy = models.PositiveIntegerField(default=0)
    business = models.PositiveIntegerField(default=0)
    composition = models.PositiveIntegerField(default=0)
    criminology = models.PositiveIntegerField(default=0)
    cryptography = models.PositiveIntegerField(default=0)
    deduction = models.PositiveIntegerField(default=0)
    education = models.PositiveIntegerField(default=0)
    gamble = models.PositiveIntegerField(default=0)
    library_search = models.PositiveIntegerField(default=0)
    local_expert = models.PositiveIntegerField(default=0)
    zoology = models.PositiveIntegerField(default=0)
    physics = models.PositiveIntegerField(default=0)
    stock_market = models.PositiveIntegerField(default=0)
    biology = models.PositiveIntegerField(default=0)
    chemistry = models.PositiveIntegerField(default=0)
    neuroscience = models.PositiveIntegerField(default=0)
    data_science = models.PositiveIntegerField(default=0)
    economics = models.PositiveIntegerField(default=0)
    sociology = models.PositiveIntegerField(default=0)
    political_science = models.PositiveIntegerField(default=0)
    genetics = models.PositiveIntegerField(default=0)
    anatomy = models.PositiveIntegerField(default=0)
    robotics = models.PositiveIntegerField(default=0)
    nanotechnology = models.PositiveIntegerField(default=0)
    tactics = models.PositiveIntegerField(default=0)
    wilderness_survival = models.PositiveIntegerField(default=0)
    # Fighting Skills
    brawling = models.PositiveIntegerField(default=0)
    evasion = models.PositiveIntegerField(default=0)
    martial_arts = models.PositiveIntegerField(default=0)
    melee = models.PositiveIntegerField(default=0)
    # Performance Skills
    acting = models.PositiveIntegerField(default=0)
    # instrument = models.PositiveIntegerField(default=0) -- requires instrument selection
    # Ranged Weapon Skills
    archery = models.PositiveIntegerField(default=0)
    autofire = models.PositiveIntegerField(default=0)
    handgun = models.PositiveIntegerField(default=0)
    heavy_weapons = models.PositiveIntegerField(default=0)
    shoulder_arms = models.PositiveIntegerField(default=0)
    # Social Skills
    bribery = models.PositiveIntegerField(default=0)
    conversation = models.PositiveIntegerField(default=0)
    human_perception = models.PositiveIntegerField(default=0)
    interrogation = models.PositiveIntegerField(default=0)
    persuasion = models.PositiveIntegerField(default=0)
    streetwise = models.PositiveIntegerField(default=0)
    trading = models.PositiveIntegerField(default=0)
    style = models.PositiveIntegerField(default=0)  # Removed the "personal grooming" skill
    # Technique Skills
    air_vehicle_tech = models.PositiveIntegerField(default=0)
    basic_tech = models.PositiveIntegerField(default=0)
    cybertech = models.PositiveIntegerField(default=0)
    demolitions = models.PositiveIntegerField(default=0)
    electronics = models.PositiveIntegerField(default=0)
    first_aid = models.PositiveIntegerField(default=0)
    forgery = models.PositiveIntegerField(default=0)
    land_vehicle_tech = models.PositiveIntegerField(default=0)
    artistry = models.PositiveIntegerField(default=0)  # for Paint/Draw/Sculpt
    paramedic = models.PositiveIntegerField(default=0)
    photography = models.PositiveIntegerField(default=0)
    pick_lock = models.PositiveIntegerField(default=0)
    pick_pocket = models.PositiveIntegerField(default=0)
    sea_vehicle_tech = models.PositiveIntegerField(default=0)
    weaponstech = models.PositiveIntegerField(default=0)
    # role abilities
    charismatic_impact = models.PositiveIntegerField(default=0)  # rockerboy
    combat_awareness = models.PositiveIntegerField(default=0)  # solo
    interface = models.PositiveIntegerField(default=0)  # netrunner
    maker = models.PositiveIntegerField(default=0)  # tech
    medicine = models.PositiveIntegerField(default=0)  # medtech
    credibility = models.PositiveIntegerField(default=0)  # media
    teamwork = models.PositiveIntegerField(default=0)  # exec
    backup = models.PositiveIntegerField(default=0)  # lawman
    operator = models.PositiveIntegerField(default=0)  # fixer
    moto = models.PositiveIntegerField(default=0)  # nomad

    unarmed_damage_dice = models.IntegerField(default=1)
    unarmed_damage_die_type = models.IntegerField(default=6)  # Changed to d6 as per the rules
    has_cyberarm = models.BooleanField(default=False)

    def calculate_base_unarmed_damage(self):
        if self.body >= 11:
            return 4
        elif self.body >= 7:
            return 3
        elif self.body >= 5 or (self.body >= 1 and self.has_cyberarm):
            return 2
        else:
            return 1

    def add_language(self, language_name, level):
        logger.log_info(f"Adding language: {language_name}, level: {level}")

        # Get or create the Language object
        language, created = Language.objects.get_or_create(
            name__iexact=language_name,
            defaults={
                'name': language_name,
                'local': getattr(next((lang for lang in LANGUAGES if lang.name.lower() == language_name.lower()), None), 'local', False),
                'corporate': getattr(next((lang for lang in LANGUAGES if lang.name.lower() == language_name.lower()), None), 'corporate', False)
            }
        )

        # Get or create the CharacterLanguage object
        char_lang, created = CharacterLanguage.objects.get_or_create(
            character_sheet=self,
            language=language,
            defaults={'level': level}
        )
        
        if not created:
            char_lang.level = level
            char_lang.save()

        logger.log_info(f"Added language {language_name} at level {level}")

    def remove_language(self, language_name):
        try:
            language = Language.objects.get(name__iexact=language_name)
            CharacterLanguage.objects.filter(character_sheet=self, language=language).delete()
            logger.log_info(f"Removed language {language_name} from character sheet")
        except Language.DoesNotExist:
            logger.log_warn(f"Language {language_name} not found, nothing to remove")

    def update_language_level(self, language_name, new_level):
        try:
            language = Language.objects.get(name=language_name)
            char_lang = CharacterLanguage.objects.get(character_sheet=self, language=language)
            char_lang.level = new_level
            char_lang.save()
        except (Language.DoesNotExist, CharacterLanguage.DoesNotExist):
            pass  # Language or character-language relationship not found

    @property
    def active_skills(self):
        """
        Return a dictionary of skills where the value is between 1 and 10.
        """
        skills = {
            "Concentration": self.concentration,
            "Conceal Object": self.conceal_object,
            "Lip Reading": self.lip_reading,
            "Perception": self.perception,
            "Tracking": self.tracking,
            "Athletics": self.athletics,
            "Contortionist": self.contortionist,
            "Dance": self.dance,
            "Endurance": self.endurance,
            "Resist Torture/Drugs": self.resist_torture_drugs,
            "Stealth": self.stealth,
            "Drive Land Vehicle": self.drive_land,
            "Pilot Air Vehicle": self.pilot_air,
            "Pilot Sea Vehicle": self.pilot_sea,
            "Riding": self.riding,
            "Accounting": self.accounting,
            "Animal Handling": self.animal_handling,
            "Bureaucracy": self.bureaucracy,
            "Business": self.business,
            "Composition": self.composition,
            "Criminology": self.criminology,
            "Cryptography": self.cryptography,
            "Deduction": self.deduction,
            "Education": self.education,
            "Gamble": self.gamble,
            # leaving out language as it should allow for multiple.
            "Library Search": self.library_search,
            "Local Expert": self.local_expert,
            # science -- requires field selection
            "Tactics": self.tactics,
            "Wilderness Survival": self.wilderness_survival,
            "Zoology": self.zoology,
            "Stock Market": self.stock_market,
            "Physics": self.physics,
            "Biology": self.biology,
            "Chemistry": self.chemistry,
            "Neuroscience": self.neuroscience,
            "Data Science": self.data_science,
            "Economics": self.economics,
            "Sociology": self.sociology,
            "Political Science": self.political_science,
            "Genetics": self.genetics,
            "Anatomy": self.anatomy,
            "Robotics": self.robotics,
            "Nanotechnology": self.nanotechnology,
            # Fighting Skills
            "Brawling": self.brawling,
            "Evasion": self.evasion,
            "Martial Arts": self.martial_arts,
            "Melee Weapons": self.melee,
            # Performance Skills
            "Acting": self.acting,
            # instrument -- requires instrument selection
            # Ranged Weapon Skills
            "Archery": self.archery,
            "Autofire": self.autofire,
            "Handgun": self.handgun,
            "Heavy Weapons": self.heavy_weapons,
            "Shoulder Arms": self.shoulder_arms,
            # Social Skills
            "Bribery": self.bribery,
            "Conversation": self.conversation,
            "Human Perception": self.human_perception,
            "Interrogation": self.interrogation,
            "Persuasion": self.persuasion,
            "Streetwise": self.streetwise,
            "Trading": self.trading,
            "Style": self.style,
            # Technique Skills
            "Air Vehicle Tech": self.air_vehicle_tech,
            "Basic Tech": self.basic_tech,
            "Cybertech": self.cybertech,
            "Demolitions": self.demolitions,
            "Electronics/Security": self.electronics,
            "First Aid": self.first_aid,
            "Forgery": self.forgery,
            "Land Vehicle Tech": self.land_vehicle_tech,
            "Artistry": self.artistry,
            "Paramedic": self.paramedic,
            "Photography/Film": self.photography,
            "Pick Lock": self.pick_lock,
            "Pick Pocket": self.pick_pocket,
            "Sea Vehicle Tech": self.sea_vehicle_tech,
            "Weaponstech": self.weaponstech,
            # role abilities
            "Charismatic Impact": self.charismatic_impact,
            "Combat Awareness": self.combat_awareness,
            "Interface": self.interface,
            "Maker": self.maker,
            "Medicine": self.medicine,
            "Credibility": self.credibility,
            "Teamwork": self.teamwork,
            "Backup": self.backup,
            "Operator": self.operator,
            "Moto": self.moto
        }

        # Filter skills to include only those with values between 1 and 10
        active_skills = {skill: level for skill, level in skills.items() if 1 <= level <= 10}

        return active_skills

    @property
    def __str__(self):
        return f"Character Sheet for {self.full_name or 'Unknown'}"

    @property
    def role_ability(self):
        role_ability_mapping = {
            'Rockerboy': self.charismatic_impact,
            'Solo': self.combat_awareness,
            'Netrunner': self.interface,
            'Tech': self.maker,
            'Medtech': self.medicine,
            'Media': self.credibility,
            'Exec': self.teamwork,
            'Lawman': self.backup,
            'Fixer': self.operator,
            'Nomad': self.moto
        }
        return role_ability_mapping.get(self.role, 0)

    @property
    def active_skills(self):
     return {field.name.replace('_', ' ').title(): getattr(self, field.name)
            for field in self._meta.get_fields()
            if field.name not in ['id', 'db_object', 'full_name', 'gender']
            and not field.name.startswith('intelligence')
            and isinstance(getattr(self, field.name), int)
            and getattr(self, field.name) > 0}

    def initialize_humanity(self):
        self.humanity = self.empathy * 10
        self.total_cyberware_humanity_loss = 0

    def calculate_humanity_loss(self):
        logger.info("Starting calculate_humanity_loss in CharacterSheet")
        from world.inventory.models import CyberwareInstance
        installed_cyberware = CyberwareInstance.objects.filter(character=self, installed=True)
        total_cyberware_hl = sum(cw.cyberware.humanity_loss for cw in installed_cyberware)
        
        logger.info(f"Total cyberware humanity loss: {total_cyberware_hl}")
        
        # Calculate new humanity
        new_humanity = max(0, self.empathy * 10 - total_cyberware_hl)
        
        logger.info(f"New calculated humanity: {new_humanity}")
        
        # Update humanity
        self.humanity = new_humanity
        
        # Only update empathy if it's been reduced to 0
        if self.empathy * 10 <= total_cyberware_hl:
            self.empathy = max(1, new_humanity // 10)
        
        self.total_cyberware_humanity_loss = total_cyberware_hl
        logger.info("About to recalculate derived stats")
        self.recalculate_derived_stats()
        logger.info("Derived stats recalculated")
        self.save()
        logger.info("CharacterSheet saved")
        
    def recalculate_derived_stats(self):
        self._max_hp = 10 + (5 * ((self.body + self.willpower) // 2))
        self.death_save = self.body
        self.serious_wounds = self.body
        
        total_cyberware_hl = self.calculate_total_cyberware_hl()
        
        # Calculate current humanity
        self.humanity = max(0, self.empathy * 10 - total_cyberware_hl)
        
        # Ensure _current_hp doesn't exceed _max_hp
        if self._current_hp > self._max_hp:
            self._current_hp = self._max_hp
        # If _current_hp is 0, set it to _max_hp
        if self._current_hp == 0:
            self._current_hp = self._max_hp
        # Ensure _current_hp is never negative   
        self._current_hp = max(0, self._current_hp)

        # Save without triggering another recalculation
        self.save(skip_recalculation=True)

    def calculate_total_cyberware_hl(self):
        from world.inventory.models import CyberwareInstance
        installed_cyberware = CyberwareInstance.objects.filter(character=self, installed=True)
        return sum(cw.cyberware.humanity_loss for cw in installed_cyberware)

    def save(self, *args, **kwargs):
        # Add a flag to prevent recursive calls
        if not kwargs.get('skip_recalculation'):
            self.recalculate_derived_stats()
        super().save(*args, **kwargs)

    def clean(self):
                if self._current_hp < 0:
                 self._current_hp = 0
                elif self._current_hp > self._max_hp:
                                  self._current_hp = self._max_hp

    def take_damage(self, amount):
                """
                Inflict damage on the character.
                """
                self._current_hp = max(0, self._current_hp - amount)
                self.save()

    def heal(self, amount):
                """                Heal the character by the specified amount.
                """
                self._current_hp = min(self._current_hp + amount, self._max_hp)
                self.save()
    def spend_luck(self):
                if self.current_luck > 0:
                 self.current_luck -= 1
                self.save()
                return True

    def gain_luck(self, amount):
                self.current_luck = min(self.current_luck + amount, self.luck)
                self.save()
                return self.current_luck

    def add_reputation(self, amount):
                """
                Add reputation points and update rep level if necessary.
                """
                self.reputation_points += amount
                self.update_rep()
                self.save()

    def update_rep(self):
                """
                Update the rep level based on reputation points.
                """
                new_rep = min(self.reputation_points // 100, 10)
                if new_rep != self.rep:
                 self.rep = new_rep
                 self.save()

    def reset(self):
        """Reset all fields to their default values and clear cyberware, languages, and inventory."""
        self.role = ""
        self.chargen_method = ""
        self.full_name = ""
        self.gender = ""
        self.intelligence = 1
        self.reflexes = 1
        self.dexterity = 1
        self.technology = 1
        self.cool = 1
        self.willpower = 1
        self.luck = 1
        self.move = 1
        self.empathy = 1
        self.body = 1
        self.is_approved = False
        
        # Clear existing cyberware
        CyberwareInstance.objects.filter(character=self).delete()
        
        # Clear existing languages
        self.character_languages.all().delete()
        
        # Add default language (Streetslang)
        self.add_language("Streetslang", 4)
        
        # Clear inventory
        if hasattr(self, 'inventory'):
            self.inventory.weapons.clear()
            self.inventory.armor.clear()
            self.inventory.gear.clear()
        else:
            Inventory.objects.create(character=self)
        
        self.save()

    def refresh_from_db(self, using=None, fields=None):
        """
        Reload field values from the database.
        """
        super().refresh_from_db(using=using, fields=fields)

    def save(self, *args, **kwargs):
        skip_recalculation = kwargs.pop('skip_recalculation', False)
        if not skip_recalculation:
            self.recalculate_derived_stats()
        if self.character:
            # Check if this character is already associated with another sheet
            existing_sheet = CharacterSheet.objects.filter(character=self.character).exclude(id=self.id).first()
            if existing_sheet:
                # If so, remove the association from the old sheet
                existing_sheet.character = None
                existing_sheet.save(skip_recalculation=True)
        super().save(*args, **kwargs)

    def recalculate_derived_stats(self):
        self._max_hp = 10 + (5 * ((self.body + self.willpower) // 2))
        self.death_save = self.body
        self.serious_wounds = self.body
        
        total_cyberware_hl = self.calculate_total_cyberware_hl()
        
        # Calculate current humanity
        self.humanity = max(0, self.empathy * 10 - total_cyberware_hl)
        
        # Ensure _current_hp doesn't exceed _max_hp
        if self._current_hp > self._max_hp:
            self._current_hp = self._max_hp
        # If _current_hp is 0, set it to _max_hp
        if self._current_hp == 0:
            self._current_hp = self._max_hp
        # Ensure _current_hp is never negative   
        self._current_hp = max(0, self._current_hp)

    # ... rest of the model ...

@property
def max_hp(self):
        return self._max_hp

@max_hp.setter
def max_hp(self, value):
        self._max_hp = value

@property
def current_hp(self):
        return self._current_hp

@current_hp.setter
def current_hp(self, value):
    self._current_hp = max(0, min(value, self.max_hp))

@property
def death_save(self):
        return self.body

@property
def serious_wounds(self):
        return self.body

@property
def rep_level(self):
        """
        Return the current rep level as a string for display.
        """
        return f"{self.rep} level"
