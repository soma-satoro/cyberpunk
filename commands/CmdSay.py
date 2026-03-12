from evennia.commands.default.muxcommand import MuxCommand
from commands.CmdPose import PoseBreakMixin
from utils.text import process_special_characters
import re


class CmdSay(PoseBreakMixin, MuxCommand):
    """
    speak as your character

    Usage:
      say <message>
      say ~<message>     (to speak in your set language)
      say "text" for language
      "<message>
      '~<message>    (to speak in your set language)

    Set your language first with +language <name>. Talk to those in your current location.
    """

    key = "say"
    aliases = ['"', "'"]
    locks = "cmd:all()"
    help_category = "RP Commands"
    arg_regex = r""

    def func(self):
        """
        This is where the language handling happens.
        """
        caller = self.caller

        # Check if the room is a Quiet Room
        if hasattr(caller.location, 'db') and caller.location.db.roomtype == "Quiet Room":
            caller.msg("|rYou are in a Quiet Room and cannot speak.|n")
            return

        if not self.args:
            caller.msg("Say what?")
            return

        speech = self.args

        # Normalize "text" for language to ~text (alternative syntax)
        match = re.match(r'"([^"]+)"\s+for\s+language\b', speech, re.IGNORECASE)
        if match:
            speech = "~" + match.group(1)

        # When using " or ' alias with a speaking language set, treat as language-tagged
        if self.cmdstring in ['"', "'"] and not speech.strip().startswith('~'):
            if caller.get_speaking_language():
                speech = '~' + speech.strip()
        elif self.cmdstring not in ['"', "'"]:
            # For the 'say' command, we need to preserve leading whitespace
            # to differentiate between 'say ~message' and 'say ~ message'
            speech = speech.rstrip()

        # Process special characters
        speech = process_special_characters(speech)

        # Send pose break before the message
        self.send_pose_break()

        # Prepare the say messages
        msg_self, msg_understand, msg_not_understand, language = caller.prepare_say(speech)

        # Get receivers (Cyberpunk: all in room; WoD: same reality layer)
        filtered_receivers = self.get_filtered_receivers()

        # Send messages to receivers (match pose/emit logic for language masking)
        speaking_language = caller.get_speaking_language()
        for receiver in filtered_receivers:
            if receiver != caller:
                # WoD Universal Language merit (no-op in Cyberpunk)
                has_universal = self.receiver_has_universal_language(receiver)
                # Receiver understands if: no language tag, has universal, or knows the language
                try:
                    receiver_langs = receiver.get_languages()
                    receiver_langs_lower = [str(l).lower() for l in (receiver_langs or [])]
                    # Use language (from prepare_say) to match prepare_say's internal check
                    knows_language = (
                        language
                        and str(language).lower() in receiver_langs_lower
                    )
                except (AttributeError, TypeError):
                    knows_language = False
                understands = not language or has_universal or knows_language
                _, msg_understand, msg_not_understand, _ = caller.prepare_say(speech, viewer=receiver, skip_english=True)
                if understands:
                    # Only add language indicator when we had language-tagged speech (~)
                    lang_indicator = f' (in {speaking_language})' if language and speaking_language and str(speaking_language).lower() != 'english' else ''
                    receiver.msg(msg_understand + lang_indicator)
                else:
                    receiver.msg(msg_not_understand)
            else:
                # The speaker always understands their own speech
                msg_self, _, _, _ = caller.prepare_say(speech, viewer=receiver, skip_english=True)
                receiver.msg(msg_self)

        if hasattr(caller, 'record_scene_activity'):
            caller.record_scene_activity()
