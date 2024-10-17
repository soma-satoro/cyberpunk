from evennia.commands.cmdhandler import cmdhandler
import re

def custom_cmdhandler(session, raw_string, **kwargs):
    # Check if the input starts with a colon followed immediately by a non-space character
    if re.match(r'^:\S', raw_string):
        # Treat it as a pose command, inserting a space after the colon
        raw_string = "pose " + raw_string[1:]
    
    # Call the original cmdhandler with the possibly modified raw_string
    return cmdhandler(session, raw_string, **kwargs)