"""

Lockfuncs

Lock functions are functions available when defining lock strings,
which in turn limits access to various game systems.

All functions defined globally in this module are assumed to be
available for use in lockstrings to determine access. See the
Evennia documentation for more info on locks.

A lock function is always called with two arguments, accessing_obj and
accessed_obj, followed by any number of arguments. All possible
arguments should be handled with *args, **kwargs. The lock function
should handle all eventual tracebacks by logging the error and
returning False.

Lock functions in this module extend (and will overload same-named)
lock functions from evennia.locks.lockfuncs.

"""

# def myfalse(accessing_obj, accessed_obj, *args, **kwargs):
#    """
#    called in lockstring with myfalse().
#    A simple logger that always returns false. Prints to stdout
#    for simplicity, should use utils.logger for real operation.
#    """
#    print "%s tried to access %s. Access denied." % (accessing_obj, accessed_obj)
#    return False

def role(accessing_obj, accessed_obj, *args, **kwargs):
    """
    Check if the accessing object has a specific role.
    
    Args:
        accessing_obj (Object): The object trying to access.
        accessed_obj (Object): The object being accessed.
        args (str): The role to check for.
    
    Returns:
        bool: True if the accessing object has the specified role, False otherwise.
    """
    if not args:
        return False
    
    required_role = args[0]
    
    if hasattr(accessing_obj, 'character_sheet'):
        return accessing_obj.character_sheet.role == required_role
    
    return False