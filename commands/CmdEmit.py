from evennia import default_cmds
from commands.CmdPose import PoseBreakMixin
from utils.text import process_special_characters
import re

class CmdEmit(PoseBreakMixin, default_cmds.MuxCommand):
    """
    @emit - Send a message to the room without your name attached.

    Usage:
      @emit <message>
      @emit/language <message>

    Switches:
      /language - Use this to emit a message in your set language.

    Examples:
      @emit A cool breeze blows through the room.
      @emit "~Bonjour, mes amis!" A voice calls out in French.
      @emit/language The entire message is in the set language.

    Use quotes with a leading tilde (~) for speech in your set language.
    This will be understood only by those who know the language.
    """

    key = "@emit"
    aliases = ["\\\\", "emit"]
    locks = "cmd:all()"
    help_category = "RP Commands"

    def func(self):
        """Execute the @emit command"""
        caller = self.caller
        
        # Check if the room is a Quiet Room
        if hasattr(caller.location, 'db') and caller.location.db.roomtype == "Quiet Room":
            caller.msg("|rYou are in a Quiet Room and cannot emit messages.|n")
            return

        if not self.args:
            caller.msg("Usage: @emit <message>")
            return

        # Normalize "text" for language to "~text" (alternative syntax)
        args_normalized = re.sub(
            r'"([^"]+)"\s+for\s+language\b',
            r'"~\1"',
            self.args,
            flags=re.IGNORECASE
        )

        # Process special characters in the message
        processed_args = process_special_characters(args_normalized)

        # Check if there's a language-tagged speech and set speaking language
        if "~" in processed_args or 'language' in self.switches:
            speaking_language = caller.get_speaking_language()
            if not speaking_language:
                caller.msg("You need to set a speaking language first with +language <language>")
                return

        # Get receivers (Cyberpunk: all in room; WoD: same reality layer)
        filtered_receivers = self.get_filtered_receivers()

        # Send pose break before the message
        self.send_pose_break()

        if 'language' in self.switches:
            # The entire emit is in the set language
            speaking_language = caller.get_speaking_language()
            _, msg_understand, msg_not_understand, language = caller.prepare_say(processed_args, language_only=True, skip_english=True)

            for receiver in filtered_receivers:
                # WoD Universal Language merit (no-op in Cyberpunk)
                has_universal = self.receiver_has_universal_language(receiver)
                if receiver == caller or has_universal or speaking_language in receiver.get_languages():
                    lang_name = str(speaking_language) if speaking_language else ''
                    lang_indicator = f' (in {lang_name})' if lang_name else ''
                    receiver.msg(msg_understand + lang_indicator)
                else:
                    receiver.msg(msg_not_understand)
        else:
            # Handle mixed language content
            for receiver in filtered_receivers:
                if "~" in processed_args:
                    parts = []
                    current_pos = 0
                    for match in re.finditer(r'"~([^"]+)"', processed_args):
                        # Add text before the speech
                        parts.append(processed_args[current_pos:match.start()])
                        
                        # Process the speech - pass with ~ prefix so prepare_say recognizes it as language-tagged
                        speech = "~" + match.group(1)
                        _, msg_understand, msg_not_understand, language = caller.prepare_say(speech, language_only=True, skip_english=True)
                        
                        # WoD Universal Language merit (no-op in Cyberpunk)
                        has_universal = self.receiver_has_universal_language(receiver)
                        speaking_language = caller.get_speaking_language()
                        if receiver == caller or has_universal or (speaking_language and speaking_language in receiver.get_languages()):
                            lang_indicator = f' (in {speaking_language})' if speaking_language else ''
                            parts.append(f'"{msg_understand}"{lang_indicator}')
                        else:
                            parts.append(f'"{msg_not_understand}"')
                        
                        current_pos = match.end()
                    
                    # Add any remaining text
                    parts.append(processed_args[current_pos:])
                    
                    # Send the final message
                    receiver.msg(''.join(parts))
                else:
                    # No language-tagged content, send as is
                    receiver.msg(processed_args)

        if hasattr(caller, 'record_scene_activity'):
            caller.record_scene_activity()
