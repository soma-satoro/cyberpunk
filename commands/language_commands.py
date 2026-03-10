from django.core.exceptions import ObjectDoesNotExist
from evennia import Command
from world.languages.models import Language, CharacterLanguage
from world.languages.language_dictionary import LANGUAGES
from evennia.commands.default.muxcommand import MuxCommand
import re
from world.cyberpunk_sheets.models import CharacterSheet
from world.utils.formatting import sheet_header, sheet_section, footer
from evennia.utils import logger

def parse_language_segments(message, known_languages):
    pattern = r'\+(\w+)(?:\s*,?\s*"([^"]*)"|\s*([^+]+?)(?=\+\w+|$))'
    segments = []
    last_end = 0
    current_lang = "default"
    
    for match in re.finditer(pattern, message):
        if match.start() > last_end:
            segments.append((current_lang, message[last_end:match.start()].strip()))
        
        lang = match.group(1).lower()
        text = match.group(2) or match.group(3)
        
        if text:
            text = text.strip()
            if match.group(2):  # If it's quoted text, preserve the quotes
                text = f'"{text}"'
        
        if lang in known_languages or lang == "english":  # Always allow English
            if lang != current_lang:
                segments.append(("language_change", lang))
            if text:
                segments.append((lang, text))
            current_lang = lang
        else:
            segments.append(("unknown", f"+{lang}" + (f' {text}' if text else "")))
        
        last_end = match.end()
    
    if last_end < len(message):
        segments.append((current_lang, message[last_end:].strip()))
    
    return segments

class CmdLanguage(MuxCommand):
    """
    Set or view language for quoted text in pose, emit, and say commands.

    Usage:
      language [<language_name>]
      language list
      language all

    Examples:
      language Spanish
      language list
      language all
    """

    key = "language"
    aliases = ["lang", "+language", "+lang", "+languages"]
    locks = "cmd:all()"

    def func(self):
        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet

        if not self.args:
            # Display current language
            current_lang = self.caller.attributes.get("selected_language", "None")
            self.caller.msg(f"Your current language is set to: {current_lang}")
            return
        
        if self.args.lower() == "list":
            self.list_languages(sheet)
            return
        
        if self.args.lower() == "all":
            self.list_all_languages()
            return

        if self.args.lower() == "none":
            try:
                self.caller.set_speaking_language(None)
                self.caller.msg("You are no longer speaking in any specific language.")
            except (ValueError, AttributeError):
                self.caller.attributes.add("selected_language", "None")
                self.caller.msg("You are no longer speaking in any specific language.")
            return
        
        language_name = self.args.strip().capitalize()
        try:
            language = Language.objects.get(name__iexact=language_name)
        except Language.DoesNotExist:
            self.caller.msg(f"Language '{language_name}' not found. Use 'language all' to see all available languages.")
            return

        character_language = CharacterLanguage.objects.filter(character_sheet=sheet, language=language).first()
        if not character_language:
            self.caller.msg(f"You don't know the language '{language_name}'. Learn it first.")
            return

        # Use character's set_speaking_language for pose/emit/say compatibility
        try:
            self.caller.set_speaking_language(language.name)
        except ValueError:
            self.caller.attributes.add("selected_language", language.name)
        self.caller.msg(f"Language set to: {language.name}")

    def list_languages(self, sheet):
        known_languages = CharacterLanguage.objects.filter(character_sheet=sheet).select_related('language').order_by('language__name')
        W = 80
        display_name = getattr(self.caller.db, 'full_name', None) or self.caller.name

        output = sheet_header(f"Languages for {display_name}", width=W)
        output += sheet_section("Your Known Languages", width=W)

        if not known_languages:
            output += "|wYou don't know any languages yet.|n\n"
        else:
            output += f"|y{'Language':<30}{'Level':<15}|n\n"
            for cl in known_languages:
                output += f"|w{cl.language.name:<30}{cl.level:<15}|n\n"

        output += footer(width=W, fillchar="-")
        self.caller.msg(output)

    def list_all_languages(self):
        all_languages = sorted(LANGUAGES, key=lambda lang: lang.name)
        W = 80

        output = sheet_header("All Available Languages", width=W)
        output += sheet_section("Languages", width=W)

        if not all_languages:
            output += "|wNo languages are available in the game world.|n\n"
        else:
            output += f"|y{'Language':<25}{'Local':<15}{'Corporate':<15}|n\n"
            for lang in all_languages:
                output += f"|w{lang.name:<25}{'Yes' if lang.local else 'No':<15}{'Yes' if lang.corporate else 'No':<15}|n\n"
        output += "\n|wUse 'language <name>' to set your speaking language.|n\n"
        output += footer(width=W, fillchar="-")
        self.caller.msg(output)


class LanguageMixin:
    def mask_text(self, text):
        return "".join("*" if c.isalnum() else c for c in text)

    def understands_language(self, player, language):
        if player == self.caller:
            return True
        try:
            return player.knows_language(language)
        except AttributeError:
            character_sheet_id = player.db.character_sheet_id
            
            if not character_sheet_id:
                return False
            
            character_sheet = CharacterSheet.objects.get(id=character_sheet_id)
            
            character_language = CharacterLanguage.objects.filter(
                character_sheet=character_sheet, 
                language__name__iexact=language
            ).first()
            
            if character_language:
                return character_language.level > 0
            return False
        except ObjectDoesNotExist:
            return False
        except Exception as e:
            logger.log_err(f"Error in understands_language for {player.name}: {str(e)}")
            return False

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

    def process_multi_language_message(self, message):
        try:
            character_sheet_id = self.caller.db.character_sheet_id
            if not character_sheet_id:
                return

            character_sheet = CharacterSheet.objects.filter(id=character_sheet_id).first()
            if not character_sheet:
                return

            known_languages = [cl.language.name.lower() for cl in character_sheet.sheet_language_proficiencies.all()]
            known_languages.append("english")  # Always include English
            default_language = self.caller.attributes.get("selected_language", "English").lower()
            
            segments = parse_language_segments(message, known_languages)
            
            for player in self.caller.location.contents:
                if player.has_account:
                    player_message = self.process_player_message(player, segments, default_language)
                    player.msg(player_message.strip())
        except AttributeError:
            self.caller.msg("Error: Character sheet not found.")
        except Exception as e:
            logger.log_err(f"Error in process_multi_language_message for {self.caller.name}: {str(e)}")

    def process_player_message(self, player, segments, default_language):
        player_message = ""
        try:
            sheet_id = player.db.character_sheet_id
            if not sheet_id:
                return player_message

            current_lang = default_language
            for i, (lang, text) in enumerate(segments):
                if lang == "default":
                    lang = current_lang
                elif lang == "language_change":
                    current_lang = text
                    player_message += f"|y[{text.capitalize()}] |n"
                    continue
                
                understands = self.understands_language(player, lang)
                
                if lang != current_lang:
                    if understands:
                        player_message += f"|g[{lang.capitalize()}] |n"
                    else:
                        player_message += f"|r[{lang.capitalize()}] |n"
                    current_lang = lang
                
                if understands:
                    player_message += text
                else:
                    masked_text = self.mask_text(text)
                    player_message += masked_text
                
                if text and text[-1] not in ",.;:!?" and (i == len(segments) - 1 or not segments[i+1][1].startswith((".", ",", ";", ":", "!", "?"))):
                    player_message += " "
        except Exception as e:
            logger.log_err(f"Error processing message for {player.name}: {str(e)}")
        
        return player_message

class PoseBreakMixin:
    """
    A mixin to add pose breaks before commands.
    """
    def send_pose_break(self, exclude=None):
        pose_break = f"\n|m{'=' * 30}> |w{self.caller.name}|n |m<{'=' * 30}|n"
        self.caller.location.msg_contents(pose_break, exclude=exclude)

class LanguagePoseBreakMixin(LanguageMixin, PoseBreakMixin):
    """
    A mixin that combines language processing and pose breaks.
    """
    def process_multi_language_message(self, message):
        try:
            # Send pose break before processing the message
            self.send_pose_break()

            character_sheet_id = self.caller.db.character_sheet_id
            if not character_sheet_id:
                return

            character_sheet = CharacterSheet.objects.filter(id=character_sheet_id).first()
            if not character_sheet:
                return

            known_languages = [cl.language.name.lower() for cl in character_sheet.sheet_language_proficiencies.all()]
            known_languages.append("english")  # Always include English
            default_language = self.caller.attributes.get("selected_language", "English").lower()
            
            segments = parse_language_segments(message, known_languages)
            
            for player in self.caller.location.contents:
                if player.has_account:
                    player_message = self.process_player_message(player, segments, default_language)
                    player.msg(player_message.strip())
            
        except AttributeError:
            self.caller.msg("Error: Character sheet not found.")
        except Exception as e:
            logger.log_err(f"Error in process_multi_language_message for {self.caller.name}: {str(e)}")

class CmdMaskedSay(Command, LanguagePoseBreakMixin):
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
        self.process_multi_language_message(message)

class CmdMaskedEmit(Command, LanguagePoseBreakMixin):
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

        self.process_multi_language_message(self.args)

class CmdMaskedPose(MuxCommand, LanguagePoseBreakMixin):
    """
    Pose with quoted text masked for those who don't understand the selected language.

    Usage:
      pose <message>
      :<message>
    """

    key = "pose"
    aliases = [":", "emote"]
    locks = "cmd:all()"
    arg_regex = None  # Allow pose without space after command

    def parse(self):
        args = self.args
        if args and not args[0] in ["'", ",", ":"]:
            args = " %s" % args.strip()
        self.args = args

    def func(self):
        if not self.args:
            self.caller.msg("What do you want to do?")
            return

        message = f"{self.caller.name}{self.args}"
        self.process_multi_language_message(message)