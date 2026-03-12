"""
Text Processing Utilities

Universal text processing functions for consistent handling of
special characters and formatting across the game.
"""

from django.conf import settings


def process_special_characters(text):
    """
    Process special character substitutions in text input.
    
    Uses settings.ENABLE_SPECIAL_CHAR_SUBSTITUTIONS and 
    settings.SPECIAL_CHAR_SUBSTITUTIONS to determine what
    substitutions to apply.
    
    Default substitutions:
    - %r = newline/carriage return
    - %r%r = paragraph break (double newline) 
    - %t = tab (5 spaces of padding)
    
    Args:
        text (str): The input text to process
        
    Returns:
        str: The processed text with substitutions applied
        
    Example:
        >>> process_special_characters("Line 1%rLine 2%r%rNew paragraph%tIndented text")
        "Line 1\nLine 2\n\nNew paragraph     Indented text"
    """
    if not text:
        return text
        
    # Check if substitutions are enabled
    if not getattr(settings, 'ENABLE_SPECIAL_CHAR_SUBSTITUTIONS', True):
        return text
    
    # Get substitutions from settings with fallback defaults
    substitutions = getattr(settings, 'SPECIAL_CHAR_SUBSTITUTIONS', {
        '%r%r': '\n\n',  # Paragraph break (must be processed first)
        '%r': '\n',      # Newline/carriage return
        '%t': '     ',   # Tab (5 spaces)
    })
    
    # Apply substitutions in the order they appear in the dict
    # This ensures %r%r is processed before %r
    for old, new in substitutions.items():
        text = text.replace(old, new)
    
    return text


def apply_text_formatting(text, apply_substitutions=True):
    """
    Apply all text formatting including special character substitutions.
    
    This is the main function that should be called for all user input
    that needs text processing.
    
    Args:
        text (str): The input text to format
        apply_substitutions (bool): Whether to apply special character substitutions
        
    Returns:
        str: The fully formatted text
    """
    if not text:
        return text
        
    if apply_substitutions:
        text = process_special_characters(text)
        
    return text 
