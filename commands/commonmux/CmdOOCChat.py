from evennia.commands.default.muxcommand import MuxCommand
from utils.text import process_special_characters


class CmdOOCChat(MuxCommand):
    """
    Out-of-character communication in the current room.

    Usage:
      ooc <message>          - Say something OOC
      ooc :<action>          - Pose an action OOC
      ooc ;<action>          - Pose an action OOC (no space)

    Examples:
      ooc Hi everyone!
      > <OOC> Soma says, "Hi everyone!"

      ooc :waves to the group.
      > <OOC> Soma waves to the group.

      ooc ;grins.
      > <OOC> Soma grins.

    This command allows you to communicate out-of-character with others
    in your current location. Unlike IC speech, OOC messages are always
    understood by everyone regardless of language settings, and they
    ignore IC restrictions like Quiet Rooms.
    """

    key = "ooc"
    locks = "cmd:all()"
    help_category = "Comms"
    arg_regex = r""

    def func(self):
        """Execute the OOC chat command"""
        caller = self.caller

        if not self.args:
            caller.msg("Usage: ooc <message> or ooc :<action>")
            return

        # Check if caller has a location
        if not caller.location:
            caller.msg("You don't have a location to speak in.")
            return

        message = self.args.strip()

        # Process special characters
        message = process_special_characters(message)

        # Determine if this is a pose or a say
        is_pose = message.startswith(':') or message.startswith(';')

        if is_pose:
            # Remove the pose prefix
            if message.startswith(':'):
                action = message[1:].lstrip()
            else:  # starts with ;
                action = message[1:]

            # Format as pose
            name = caller.attributes.get('gradient_name', default=caller.key)
            formatted_message = f"|y<OOC>|n {name} {action}"
        else:
            # Format as say
            name = caller.attributes.get('gradient_name', default=caller.key)
            formatted_message = f"|y<OOC>|n {name} says, \"{message}\""

        # Get all objects in the room that can receive messages
        # OOC bypasses reality layer filtering - everyone can see it
        receivers = []
        for obj in caller.location.contents:
            if obj.has_account:
                receivers.append(obj)

        # Send the message to all receivers
        for receiver in receivers:
            receiver.msg(formatted_message)

        # Record scene activity if the method exists
        if hasattr(caller, 'record_scene_activity'):
            caller.record_scene_activity()


class CmdUnpuppet(MuxCommand):
    """
    Stop controlling your current character.

    Usage:
      unpuppet

    This command allows you to stop puppeting your current character
    and return to the account level. This is useful for switching
    between characters or logging out.

    This command was previously called 'ooc' in default Evennia,
    but has been renamed to avoid conflicts with the OOC chat command.
    """

    key = "unpuppet"
    aliases = ["unpuppet"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        """Execute the unpuppet command"""
        caller = self.caller

        if not caller.account:
            caller.msg("You are not currently puppeting a character.")
            return

        account = caller.account
        character = caller

        # Use Evennia's built-in unpuppet functionality
        try:
            account.unpuppet_object(caller.sessions.get())
            account.msg(f"You stop puppeting {character.name}.")
        except Exception as e:
            caller.msg(f"Error unpuppeting: {e}")

