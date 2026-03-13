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
