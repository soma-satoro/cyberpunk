from evennia.commands.default.muxcommand import MuxCommand
from commands.commonmux.CmdPose import PoseBreakMixin
from utils.text import process_special_characters

class CmdSay(PoseBreakMixin, MuxCommand):
    """
    speak as your character

    Usage:
      say <message>
      say ~<message>     (to speak in your set language)
      "<message>
      '~<message>    (to speak in your set language)

    Talk to those in your current location.
    """

    key = "say"
    aliases = ['"', "'"]
    locks = "cmd:all()"
    help_category = "Roleplaying Tools"
    arg_regex = r""

    def func(self):
        """
        This is where the language handling happens.
        """
        caller = self.caller

        # Check if the room is a Quiet Room (by tag or roomtype)
        if hasattr(caller.location, 'db'):
            room_tags = getattr(caller.location.db, 'tags', []) or []
            if 'quiet' in room_tags or caller.location.db.roomtype == "Quiet Room":
                caller.msg("|rYou are in a Quiet Room and cannot speak.|n")
                return

        if not self.args:
            caller.msg("Say what?")
            return

        speech = self.args

        # Handle the case where the alias " or ' is used
        if self.cmdstring in ['"', "'"]:
            speech = speech
        else:
            # For the 'say' command, we need to preserve leading whitespace
            # to differentiate between 'say ~message' and 'say ~ message'
            speech = speech.rstrip()

        # Process special characters in the speech
        speech = process_special_characters(speech)

        # Send pose break before the message
        self.send_pose_break()

        # Prepare the say messages
        msg_self, msg_understand, msg_not_understand, language = caller.prepare_say(speech)

        # Filter receivers based on reality layers
        filtered_receivers = []
        for obj in caller.location.contents:
            if not obj.has_account:
                continue
            
            # Check reality layer tags
            caller_in_umbra = caller.tags.get("in_umbra", category="state")
            caller_in_material = caller.tags.get("in_material", category="state")
            caller_in_dreaming = caller.tags.get("in_dreaming", category="state")
            
            obj_in_umbra = obj.tags.get("in_umbra", category="state")
            obj_in_material = obj.tags.get("in_material", category="state")
            obj_in_dreaming = obj.tags.get("in_dreaming", category="state")
            
            # Check if they share the same reality layer
            # If neither has any tags, assume they're both in normal reality
            if (caller_in_umbra and obj_in_umbra) or \
               (caller_in_material and obj_in_material) or \
               (caller_in_dreaming and obj_in_dreaming) or \
               (not any([caller_in_umbra, caller_in_material, caller_in_dreaming]) and 
                not any([obj_in_umbra, obj_in_material, obj_in_dreaming])):
                filtered_receivers.append(obj)

        # Send messages to receivers
        for receiver in filtered_receivers:
            if receiver != caller:
                # Check for Universal Language merit
                has_universal = any(
                    merit.lower().replace(' ', '') == 'universallanguage'
                    for category in receiver.db.stats.get('merits', {}).values()
                    for merit in category.keys()
                )

                # Get the languages the receiver knows
                receiver_languages = receiver.get_languages()

                # If they have Universal Language, know the language, or it's not a language-tagged message
                if has_universal or not language or (language and language in receiver_languages):
                    _, msg_understand, _, _ = caller.prepare_say(speech, viewer=receiver, skip_english=True)
                    receiver.msg(msg_understand)
                else:
                    _, _, msg_not_understand, _ = caller.prepare_say(speech, viewer=receiver, skip_english=True)
                    receiver.msg(msg_not_understand)
            else:
                # The speaker always understands their own speech
                msg_self, _, _, _ = caller.prepare_say(speech, viewer=receiver, skip_english=True)
                receiver.msg(msg_self)

        # Record scene activity
        caller.record_scene_activity()

