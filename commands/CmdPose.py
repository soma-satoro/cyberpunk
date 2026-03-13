from evennia import default_cmds
import re

class PoseBreakMixin:
    """
    A mixin to add pose breaks before commands.
    Compatible with both WoD (reality layers) and Cyberpunk (no layers = include all).
    """
    def get_filtered_receivers(self):
        """
        Get receivers who can see/hear the message.
        WoD: filters by reality layer (umbra, material, dreaming).
        Cyberpunk: when neither has reality tags, include everyone (default).
        """
        caller = self.caller
        filtered_receivers = []
        for obj in caller.location.contents:
            if not obj.has_account:
                continue
            # WoD reality layer check
            caller_in_umbra = getattr(caller.tags, 'has', lambda *a, **k: False)("in_umbra", category="state")
            caller_in_material = getattr(caller.tags, 'has', lambda *a, **k: False)("in_material", category="state")
            caller_in_dreaming = getattr(caller.tags, 'has', lambda *a, **k: False)("in_dreaming", category="state")
            obj_in_umbra = getattr(obj.tags, 'has', lambda *a, **k: False)("in_umbra", category="state")
            obj_in_material = getattr(obj.tags, 'has', lambda *a, **k: False)("in_material", category="state")
            obj_in_dreaming = getattr(obj.tags, 'has', lambda *a, **k: False)("in_dreaming", category="state")
            same_layer = (caller_in_umbra and obj_in_umbra) or (caller_in_material and obj_in_material) or (caller_in_dreaming and obj_in_dreaming)
            neither_has_tags = not any([caller_in_umbra, caller_in_material, caller_in_dreaming]) and not any([obj_in_umbra, obj_in_material, obj_in_dreaming])
            if same_layer or neither_has_tags:
                filtered_receivers.append(obj)
        return filtered_receivers

    def receiver_has_universal_language(self, receiver):
        """WoD: Universal Language merit understands all. Cyberpunk: always False."""
        try:
            stats = getattr(receiver.db, 'stats', None) or {}
            merits = stats.get('merits', {}) if isinstance(stats, dict) else {}
            for category in (merits.values() if isinstance(merits, dict) else []):
                if isinstance(category, dict):
                    for merit in category.keys():
                        if str(merit).lower().replace(' ', '') in ('universallanguage', 'universallinguist'):
                            return True
        except (AttributeError, TypeError):
            pass
        return False

    def send_pose_break(self, exclude=None):
        caller = self.caller
        
        # Check if the room is an OOC Area (by roomtype, db.tags, or Evennia tags from +room/tag)
        if hasattr(caller.location, 'db'):
            room_tags = getattr(caller.location.db, 'tags', []) or []
            if 'ooc' in room_tags or getattr(caller.location.db, 'roomtype', None) == 'OOC Area':
                return  # Don't send pose breaks in OOC Areas
        if hasattr(caller.location, 'tags') and getattr(caller.location.tags, 'has', lambda *a, **k: False)('ooc'):
            return  # Don't send pose breaks in OOC Areas (Evennia tag system)
            
        display_name = caller.get_display_name(caller)
        pose_break = f"\n|y{'=' * 30}> |w{display_name}|n |y<{'=' * 30}|n"
        filtered_receivers = self.get_filtered_receivers()
        
        for receiver in filtered_receivers:
            if receiver != caller and (not exclude or receiver not in exclude):
                receiver.msg(pose_break)
        
        # Always send the pose break to the caller
        caller.msg(pose_break)

    def msg_contents(self, message, exclude=None, from_obj=None, **kwargs):
        """
        Custom msg_contents that adds a pose break before the message.
        """
        # Check if the room is an OOC Area (by roomtype or 'ooc' tag from +room/tag)
        if hasattr(self.caller.location, 'db'):
            room_tags = getattr(self.caller.location.db, 'tags', []) or []
            if 'ooc' in room_tags or getattr(self.caller.location.db, 'roomtype', None) == 'OOC Area':
                super().msg_contents(message, exclude=exclude, from_obj=from_obj, **kwargs)
                return
        # Also check Evennia's tag system
        if hasattr(self.caller.location, 'tags') and getattr(self.caller.location.tags, 'has', lambda *a, **k: False)('ooc'):
            super().msg_contents(message, exclude=exclude, from_obj=from_obj, **kwargs)
            return

        # Add the pose break
        self.send_pose_break(exclude=exclude)

        # Call the original msg_contents (pose/emit/say)
        super().msg_contents(message, exclude=exclude, from_obj=from_obj, **kwargs)

class CmdPose(PoseBreakMixin, default_cmds.MuxCommand):
    """
    Pose an action to the room, with support for mixed content and language tags.
    Usage:
      :pose text
      ;pose text
      pose text

    Use "~text" or "text" for language to mark speech in your set language.
    Set your language first with +language <name> (e.g. +language Streetslang).
    
    Examples:
      :waves and says "~Hello!" then "Hello" in English.
      pose tests, "Test" for language.
      pose This is a pose with "~tagged speech" and "untagged speech".
    """

    key = "pose"
    aliases = [";", ":"]
    locks = "cmd:all()"
    arg_regex = None
    help_category = "RP Commands"

    def parse(self):
        """
        Custom parsing to handle different pose prefixes.
        """
        super().parse()
        
        if self.cmdstring == ";":
            # Remove space after semicolon if present
            self.args = self.args.lstrip()

    def process_special_characters(self, message):
        """
        Process %r and %t in the message, replacing them with appropriate ANSI codes.
        """
        message = message.replace('%r', '|/').replace('%t', '|-')
        return message

    def func(self):
        caller = self.caller
        
        # Check if the room is a Quiet Room
        if hasattr(caller.location, 'db') and caller.location.db.roomtype == "Quiet Room":
            caller.msg("|rYou are in a Quiet Room and cannot pose.|n")
            return
            
        if not self.args:
            caller.msg("Pose what?")
            return

        # Normalize "text" for language to "~text" (alternative syntax)
        args_normalized = re.sub(
            r'"([^"]+)"\s+for\s+language\b',
            r'"~\1"',
            self.args,
            flags=re.IGNORECASE
        )

        # Check if there's a language-tagged speech and set speaking language
        if "~" in args_normalized:
            speaking_language = caller.get_speaking_language()
            if not speaking_language:
                caller.msg("You need to set a speaking language first with +language <language>")
                return

        # Send pose break before processing the message
        self.send_pose_break()

        # Process special characters in the message
        processed_args = self.process_special_characters(args_normalized)

        # Determine the name to use (elfname in ELO, gradient_name or key otherwise)
        poser_name = caller.get_display_name(caller)

        # Get the character's speaking language
        speaking_language = caller.get_speaking_language()

        filtered_receivers = self.get_filtered_receivers()

        # Process the pose for each receiver
        for receiver in filtered_receivers:
            # If there's language-tagged speech in the pose, process it
            if "~" in processed_args:
                parts = []
                current_pos = 0
                for match in re.finditer(r'"~([^"]+)"', processed_args):
                    # Add text before the speech
                    parts.append(processed_args[current_pos:match.start()])
                    
                    # Process the speech - pass with ~ prefix so prepare_say recognizes it as language-tagged
                    speech = "~" + match.group(1)
                    _, msg_understand, msg_not_understand, language = caller.prepare_say(speech, language_only=True, skip_english=True)
                    
                    has_universal = self.receiver_has_universal_language(receiver)
                    understands = receiver == caller or has_universal or (speaking_language and speaking_language in receiver.get_languages())
                    if understands:
                        # Add language indicator so it's clear they're hearing another language
                        lang_indicator = f' (in {speaking_language})' if speaking_language else ''
                        # DEBUG: Uncomment to trace - remove after fixing
                        # caller.msg(f"|y[DEBUG] speaking_language={speaking_language!r} lang_indicator={lang_indicator!r}|n")
                        parts.append(f'"{msg_understand}"{lang_indicator}')
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

        if hasattr(caller, 'record_scene_activity'):
            caller.record_scene_activity()