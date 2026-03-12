from evennia import default_cmds
from evennia.commands.default.muxcommand import MuxCommand
import re
from utils.text import process_special_characters

class PoseBreakMixin:
    """
    A mixin to add pose breaks before commands.
    """
    def send_pose_break(self, exclude=None):
        caller = self.caller
        
        # Check if the room is an OOC Area (by tag or roomtype)
        if hasattr(caller.location, 'db'):
            room_tags = getattr(caller.location.db, 'tags', []) or []
            if 'ooc' in room_tags or caller.location.db.roomtype == 'OOC Area':
                return  # Don't send pose breaks in OOC Areas
            
        pose_break = f"\n|y{'=' * 30}> |w{caller.name}|n |y<{'=' * 30}|n"
        
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
        
        for receiver in filtered_receivers:
            if receiver != caller and (not exclude or receiver not in exclude):
                receiver.msg(pose_break)
        
        # Always send the pose break to the caller
        caller.msg(pose_break)

    def msg_contents(self, message, exclude=None, from_obj=None, **kwargs):
        """
        Custom msg_contents that adds a pose break before the message.
        """
        # Check if the room is an OOC Area (by tag or roomtype)
        if hasattr(self.caller.location, 'db'):
            room_tags = getattr(self.caller.location.db, 'tags', []) or []
            if 'ooc' in room_tags or self.caller.location.db.roomtype == 'OOC Area':
                # Call the original msg_contents without pose break
                super().msg_contents(message, exclude=exclude, from_obj=from_obj, **kwargs)
                return
            
        # Add the pose break
        self.send_pose_break(exclude=exclude)

        # Call the original msg_contents (pose/emit/say)
        super().msg_contents(message, exclude=exclude, from_obj=from_obj, **kwargs)

class CmdPose(PoseBreakMixin, MuxCommand):
    """
    Pose an action to the room, with support for mixed content and language tags.
    Usage:
      :pose text
      ;pose text
      pose text

    Use "~text" for language-tagged speech.
    
    Example:
      :waves and says "~Hello!" in French, then "Hello" in English.
      ;grins and whispers, "~We meet again!"
      pose This is a regular pose with "~tagged speech" and "untagged speech".
    """

    key = "pose"
    aliases = [";", ":"]
    locks = "cmd:all()"
    arg_regex = None
    help_category = "Roleplaying Tools"

    def parse(self):
        """
        Custom parsing to handle different pose prefixes.
        """
        super().parse()
        
        if self.cmdstring == ";":
            # Remove space after semicolon if present
            self.args = self.args.lstrip()

    def func(self):
        caller = self.caller
        
        # Check if the room is a Quiet Room (by tag or roomtype)
        if hasattr(caller.location, 'db'):
            room_tags = getattr(caller.location.db, 'tags', []) or []
            if 'quiet' in room_tags or caller.location.db.roomtype == "Quiet Room":
                caller.msg("|rYou are in a Quiet Room and cannot pose.|n")
                return
            
        if not self.args:
            caller.msg("Pose what?")
            return

        # Check if there's a language-tagged speech and set speaking language
        if "~" in self.args:
            speaking_language = caller.get_speaking_language()
            if not speaking_language:
                caller.msg("You need to set a speaking language first with +language <language>")
                return

        # Send pose break before processing the message
        self.send_pose_break()

        # Process special characters in the message
        processed_args = process_special_characters(self.args)

        # Determine the name to use
        poser_name = caller.attributes.get('gradient_name', default=caller.key)

        # Get the character's speaking language
        speaking_language = caller.get_speaking_language()

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

        # Process the pose for each receiver
        for receiver in filtered_receivers:
            # If there's language-tagged speech in the pose, process it
            if "~" in processed_args:
                parts = []
                current_pos = 0
                for match in re.finditer(r'"~([^"]+)"', processed_args):
                    # Add text before the speech
                    parts.append(processed_args[current_pos:match.start()])
                    
                    # Process the speech
                    speech = match.group(1)
                    _, msg_understand, msg_not_understand, _ = caller.prepare_say(speech, language_only=True, skip_english=True)
                    
                    # Check for Universal Language merit
                    has_universal = any(
                        merit.lower().replace(' ', '') == 'universallinguist'
                        for category in receiver.db.stats.get('merits', {}).values()
                        for merit in category.keys()
                    )
                    
                    if receiver == caller or has_universal or (speaking_language and speaking_language in receiver.get_languages()):
                        parts.append(f'"{msg_understand}"')
                    else:
                        parts.append(f'"{msg_not_understand}"')
                    
                    current_pos = match.end()
                
                # Add any remaining text
                parts.append(processed_args[current_pos:])
                
                # Construct final message
                final_message = f"{poser_name} {''.join(parts)}"
                receiver.msg(final_message)
            else:
                # No language-tagged speech, send normal pose
                receiver.msg(f"{poser_name} {processed_args}")

        # Record scene activity
        caller.record_scene_activity()
