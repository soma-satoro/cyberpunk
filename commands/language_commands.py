from evennia import Command
from world.languages.models import Language, CharacterLanguage
from world.languages.language_dictionary import LANGUAGES
from evennia.commands.default.muxcommand import MuxCommand
import re

class CmdLanguage(MuxCommand):
    """
    Set or view language for quoted text in pose, emit, and say commands.

    Usage:
      language [<language_name>]
      language list

    Examples:
      language Spanish
      language list
    """

    key = "language"
    aliases = ["lang"]
    locks = "cmd:all()"

    def func(self):
        if not self.args:
            # Display current language
            current_lang = self.caller.attributes.get("current_language", "None")
            self.caller.msg(f"Your current language is set to: {current_lang}")
            return
        
        if self.args.lower() == "list":
            # List all known languages
            character_sheet = self.caller.db.character_sheet
            if not character_sheet:
                self.caller.msg("You don't have a character sheet.")
                return
            
            languages = character_sheet.language_list
            if not languages:
                self.caller.msg("You don't know any languages.")
            else:
                self.caller.msg("Known languages:")
                for lang in languages:
                    self.caller.msg(f"- {lang['name']} (Level {lang['level']})")
            return
        
        language_name = self.args.strip().capitalize()
        try:
            language = Language.objects.get(name=language_name)
        except Language.DoesNotExist:
            self.caller.msg(f"Language '{language_name}' not found. Use 'language list' to see available languages.")
            return

        character_language = CharacterLanguage.objects.filter(character=self.caller.db.character_sheet, language=language).first()
        if not character_language:
            self.caller.msg(f"You don't know the language '{language_name}'. Learn it first.")
            return

        self.caller.db.selected_language = language_name
        self.caller.msg(f"Language set to: {language_name}")

    def list_languages(self):
        known_languages = CharacterLanguage.objects.filter(character=self.caller.db.character_sheet)
        if not known_languages:
            self.caller.msg("You don't know any languages yet.")
            return

        table = self.styled_table("Language", "Level", "Local", "Corporate")
        for cl in known_languages:
            lang_info = next((l for l in LANGUAGES if l["name"] == cl.language.name), None)
            if lang_info:
                table.add_row(
                    cl.language.name,
                    cl.level,
                    "Yes" if lang_info["local"] else "No",
                    "Yes" if lang_info["corporate"] else "No"
                )
        
        self.caller.msg(table)

class LanguageMixin:
    def mask_text(self, text):
        return "".join("*" if c.isalnum() else c for c in text)

    def understands_language(self, player, language):
        if player == self.caller:
            return True
        character_sheet = player.db.character_sheet
        if not character_sheet:
            return False
        return CharacterLanguage.objects.filter(character=character_sheet, language__name=language).exists()

    def process_message(self, message, language=None):
        language = language or "English"
        if language:
            masked_message = re.sub(r'"([^"]*)"', lambda m: f'"{self.mask_text(m.group(1))}"', message)
            full_message = f"(in {language}) {message}"
            masked_full_message = f"(in {language}) {masked_message}"

            for player in self.caller.location.contents:
                if player.has_account:
                    if self.understands_language(player, language):
                        player.msg(full_message)
                    else:
                        player.msg(masked_full_message)
        else:
            self.caller.location.msg_contents(message)


class CmdMaskedSay(Command, LanguageMixin):
    """
    Speak with quoted text masked for those who don't understand the selected language.

    Usage:
      say <message>
    """

    key = "say"
    locks = "cmd:all()"

    def func(self):
        if not self.args:
            self.caller.msg("Say what?")
            return

        message = f"{self.caller.name} says: {self.args}"
        language = self.caller.db.selected_language
        self.process_message(message, language)

class CmdMaskedPose(Command, LanguageMixin):
    """
    Pose with quoted text masked for those who don't understand the selected language.

    Usage:
      pose <message>
    """

    key = "pose"
    aliases = [":", "emote"]
    locks = "cmd:all()"

    def func(self):
        if not self.args:
            self.caller.msg("Pose what?")
            return

        message = f"{self.caller.name} {self.args}"
        language = self.caller.db.selected_language
        self.process_message(message, language)

class CmdMaskedEmit(Command, LanguageMixin):
    """
    Emit with quoted text masked for those who don't understand the selected language.

    Usage:
      emit <message>
    """

    key = "emit"
    aliases = ["\\"]
    locks = "cmd:all()"

    def func(self):
        if not self.args:
            self.caller.msg("Emit what?")
            return

        message = self.args
        language = self.caller.db.selected_language
        self.process_message(message, language)