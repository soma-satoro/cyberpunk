"""
Text processing utilities for pose, emit, say and other commands.
"""


def process_special_characters(message):
    """
    Process %r and %t in the message, replacing them with appropriate ANSI codes.
    %r -> newline (|/)
    %t -> tab (|-)
    """
    if not message:
        return message
    return message.replace('%r', '|/').replace('%t', '|-')
