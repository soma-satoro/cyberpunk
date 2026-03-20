"""
Permission checks for staff/builder/admin operations.

Used by netrunning staff commands, BBS, and other privileged operations.
"""


def check_builder_permission(caller):
    """
    Check if the caller has Builder or higher permissions (including Admin, Developer).

    Args:
        caller: Character or Account to check.

    Returns:
        bool: True if caller has Builder+, False otherwise.
    """
    if not caller:
        return False
    acct = getattr(caller, "account", caller)
    if not acct:
        return False
    return (
        getattr(acct, "is_superuser", False)
        or (hasattr(acct, "check_permstring") and acct.check_permstring("Builder"))
    )


def check_admin_permission(caller):
    """
    Check if the caller has Admin permissions.

    Args:
        caller: Character or Account to check.

    Returns:
        bool: True if caller has Admin, False otherwise.
    """
    if not caller:
        return False
    acct = getattr(caller, "account", caller)
    if not acct:
        return False
    return (
        getattr(acct, "is_superuser", False)
        or (hasattr(acct, "check_permstring") and acct.check_permstring("Admin"))
    )


def format_permission_error(caller, action="perform this action"):
    """Return a user-friendly message when permission is denied."""
    return f"You do not have permission to {action}."


def check_storyteller_plot_access(caller):
    """
    True if caller may use plot-runner tools (e.g. NPCs, some mission actions).

    Requires the Storyteller account permission and an approved character, same
    gate as +npc for non-staff.
    """
    if not caller or not hasattr(caller, "check_permstring"):
        return False
    if not caller.check_permstring("storyteller"):
        return False
    from world.utils.character_utils import is_character_approved

    return bool(is_character_approved(caller))
