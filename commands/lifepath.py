from evennia import Command
from evennia.utils import evmenu
from evennia.utils.evtable import EvTable
from world.utils.formatting import header, footer, divider
from world.utils.ansi_utils import wrap_ansi
from world.cyberpunk_sheets.models import CharacterSheet
from world.lifepath_dictionary import CULTURAL_ORIGINS, PERSONALITIES, CLOTHING_STYLES, HAIRSTYLES, AFFECTATIONS, MOTIVATIONS, LIFE_GOALS, ROLE_SPECIFIC_LIFEPATHS, VALUED_PERSON, VALUED_POSSESSION, FAMILY_BACKGROUND, ENVIRONMENT, FAMILY_CRISIS

class CmdLifepath(Command):
    """
    Start the lifepath creation process.

    Usage:
      lifepath
    """
    key = "lifepath"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
       evmenu.EvMenu(self.caller, 
               "commands.lifepath_functions",
               startnode="start_lifepath",
               cmdset_mergetype="Replace",
               cmdset_priority=1,
               auto_quit=True,
               cmd_on_exit=None)

class CmdViewLifepath(Command):
    """
    View your character's lifepath details.

    Usage:
      sheet/lifepath
    """
    key = "sheet/lifepath"
    locks = "cmd:all()"
    help_category = "Character"

    def wrap_field(self, title, value, width=80, title_width=30):
        wrapped_title = wrap_ansi(title, width=title_width)
        wrapped_value = wrap_ansi(value, width=width-title_width-1)
        
        title_lines = wrapped_title.split('\n')
        value_lines = wrapped_value.split('\n')
        
        output = ""
        for i in range(max(len(title_lines), len(value_lines))):
            title_line = title_lines[i] if i < len(title_lines) else ""
            value_line = value_lines[i] if i < len(value_lines) else ""
            
            if i == 0:
                output += f"|c{title_line:<{title_width}}|n {value_line}\n"
            else:
                output += f"|c{title_line:<{title_width}}|n {value_line}\n"
        
        return output


    def func(self):
        try:
            cs = self.caller.account.character_sheet
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet yet. Use the 'lifepath' command to create one.")
            return

        if not cs:
            self.caller.msg("You don't have a character sheet yet. Use the 'lifepath' command to create one.")
            return

        width = 80
        title_width = 30
        output = ""

        # Main header
        output += header(f"Character Sheet for {cs.full_name}", width=width, fillchar="|m-|n") + "\n"

        # Present Section
        output += divider("|yPresent|n", width=width, fillchar="|m=|n") + "\n"
        present_fields = [
            ("Cultural Origin", "cultural_origin"),
            ("Personality", "personality"),
            ("Clothing Style", "clothing_style"),
            ("Hairstyle", "hairstyle"),
            ("Affectation", "affectation"),
            ("Motivation", "motivation"),
            ("Life Goal", "life_goal"),
            ("Most Valued Person", "valued_person"),
        ]
        for title, field in present_fields:
            value = getattr(cs, field, "Not set")
            output += self.wrap_field(title, value, width, title_width)
        output += "\n"

        # Past Section
        output += divider("|yPast|n", width=width, fillchar="|m=|n") + "\n"
        past_fields = [
            ("Valued Possession", "valued_possession"),
            ("Family Background", "family_background"),
            ("Origin Environment", "environment"),
            ("Family Crisis", "family_crisis")
        ]
        for title, field in past_fields:
            value = getattr(cs, field, "Not set")
            output += self.wrap_field(title, value, width, title_width)
        output += "\n"

        # Role Section
        if cs.role:
            output += divider(f"|yRole: {cs.role}|n", width=width, fillchar="|m=|n") + "\n"
            role_specific_fields = {
                "Rockerboy": [
                    "what_kind_of_rockerboy_are_you",
                    "whos_gunning_for_you_your_group",
                    "where_do_you_perform"
                ],
                "Solo": [
                    "what_kind_of_solo_are_you",
                    "whats_your_moral_compass_like",
                    "whos_gunning_for_you",
                    "whats_your_operational_territory"
                ],
                "Netrunner": [
                    "what_kind_of_runner_are_you",
                    "who_are_some_of_your_other_clients",
                    "where_do_you_get_your_programs",
                    "whos_gunning_for_you"
                ],
                "Tech": [
                    "what_kind_of_tech_are_you",
                    "whats_your_workspace_like",
                    "who_are_your_main_clients",
                    "where_do_you_get_your_supplies"
                ],
                "Medtech": [
                    "what_kind_of_medtech_are_you",
                    "who_are_your_main_clients",
                    "where_do_you_get_your_supplies"
                ],
                "Media": [
                    "what_kind_of_media_are_you",
                    "how_does_your_work_reach_the_public",
                    "how_ethical_are_you",
                    "what_types_of_stories_do_you_want_to_tell"
                ],
                "Exec": [
                    "what_kind_of_corp_do_you_work_for",
                    "what_division_do_you_work_in",
                    "how_good_bad_is_your_corp",
                    "where_is_your_corp_based",
                    "current_state_with_your_boss"
                ],
                "Lawman": [
                    "what_is_your_position_on_the_force",
                    "how_wide_is_your_groups_jurisdiction",
                    "how_corrupt_is_your_group",
                    "who_is_your_groups_major_target"
                ],
                "Fixer": [
                    "what_kind_of_fixer_are_you",
                    "who_are_your_side_clients",
                    "whos_gunning_for_you"
                ],
                "Nomad": [
                    "how_big_is_your_pack",
                    "what_do_you_do_for_your_pack",
                    "whats_your_packs_overall_philosophy",
                    "is_your_pack_based_on_land_air_or_sea"
                ]
            }

            for field in role_specific_fields.get(cs.role, []):
                value = getattr(cs, field, None)
                if value:
                    title = field.replace('_', ' ').title()
                    output += self.wrap_field(title, value, width, title_width)
            output += "\n"

        output += footer(width=width, fillchar="|m-|n")
        
        # Send the formatted output to the caller
        self.caller.msg(output)