from evennia.utils.ansi import ANSIString
from collections import defaultdict

def format_stat(name: str, value: int, default: int = 0, tempvalue: int = None, width: int = 25, allow_zero: bool = False) -> str:
    """
    Format a stat for display on a character sheet.
    
    Args:
        name: The name of the stat
        value: The permanent value of the stat
        default: The default value if none is set
        tempvalue: The temporary value of the stat (if different from permanent)
        width: The width to pad the output to
        allow_zero: Whether to allow zero values (default False)
        
    Returns:
        A formatted string representing the stat
    """
    # Handle None values
    if value is None:
        value = default
    if tempvalue is None:
        tempvalue = value

    # Format the value part
    if not allow_zero and value == 0:
        value_str = "0"
    else:
        value_str = str(value)

    # If temporary value differs from permanent, show both
    if tempvalue != value:
        value_str = f"{value}({tempvalue})"
        # Add yellow highlighting for boosted stats
        return f"|y {name}|x{'.' * (width - len(name) - len(value_str) - 2)} |y{value_str}|n"

    # Format the full string with padding
    return f" {name}{'.' * (width - len(name) - len(value_str) - 2)} {value_str}"

def header(title, width=78, color="|y", fillchar="-", bcolor="|b"):
    """Create a header with consistent width."""
    # Ensure the title has proper spacing
    title = f" {title} "
    left_dashes = bcolor + fillchar * ((width - len(ANSIString(title).clean()) - 2) // 2) + "|n"
    right_dashes = bcolor + fillchar * (width - len(ANSIString(title).clean()) - 2 - len(ANSIString(left_dashes).clean())) + "|n"
    return f"{left_dashes}{color}{title}|n{right_dashes}\n"

def footer(width=78, fillchar="-"):
    """Create a footer with consistent width."""
    return "|b" + fillchar * width + "|n\n"


def footer_with_right_text(width=78, right_text="", fillchar="-", color="|m"):
    """
    Create a footer line with right-aligned text (e.g. for room resource display).
    Used for: ------------------------------[Res: Very Expensive]---
    """
    if isinstance(fillchar, ANSIString):
        fillchar = "-"
    elif not fillchar or fillchar == "|m" or len(str(fillchar)) > 1:
        fillchar = "-"
    clean_right = str(ANSIString(right_text).clean()) if right_text else ""
    padding = max(0, width - len(clean_right))
    return color + (fillchar * padding) + "|n" + right_text + "\n"


def sheet_header(title, width=80):
    """Character sheet header: '-------- Character Sheet for {name} --------' (80 chars)."""
    from evennia.utils.ansi import ANSIString
    clean_title = str(ANSIString(title).clean())
    fill_len = max(0, width - len(clean_title) - 2)
    half = fill_len // 2
    return "|b" + "-" * half + "|n " + "|y" + clean_title + "|n " + "|b" + "-" * (fill_len - half) + "|n\n"


def sheet_section(title, width=80):
    """Character sheet section: '=====> Title <============...' (80 chars, blue/magenta)."""
    from evennia.utils.ansi import ANSIString
    clean_title = str(ANSIString(title).clean())
    pattern = f"=====> {clean_title} <"
    fill_len = max(0, width - len(pattern))
    return "|b" + pattern + "|m" + "=" * fill_len + "|n\n"


def inv_info_centered_title(title, width=78, dash_color="|m", title_color="|y"):
    """
    ``inv/info`` item header: centered title between horizontal rules.

    Uses plain ``-`` only for rules (no ANSI embedded in the filler), so total visible
    width is exactly ``width`` and the title stays centered.
    """
    clean = str(ANSIString(title).clean()).strip()
    core = f" {clean} "  # spaces around name, matching book-style blocks
    if len(core) >= width:
        return f"{title_color}{clean}|n\n"
    remaining = width - len(core)
    left = remaining // 2
    right = remaining - left
    return f"{dash_color}{'-' * left}|n{title_color}{core}|n{dash_color}{'-' * right}|n\n"


def inv_info_section_rule(label, width=78, dash_color="|m", label_color="|y"):
    """
    ``inv/info`` section line: ``----- Description -----`` with centered label.
    """
    clean_label = str(ANSIString(label).clean()).strip()
    core = f" {clean_label} "
    if len(core) >= width:
        return f"{label_color}{clean_label}|n\n"
    remaining = width - len(core)
    left = remaining // 2
    right = remaining - left
    return f"{dash_color}{'-' * left}|n {label_color}{clean_label}|n {dash_color}{'-' * right}|n\n"


def inv_info_footer(width=78, dash_color="|m"):
    """``inv/info`` closing rule: one full line of hyphens at visible width ``width``."""
    return f"{dash_color}{'-' * width}|n\n"


# ASCII ellipsis only (avoid Unicode "..." in MUD column truncation)
INV_ELLIPSIS_ASCII = "..."


def inv_visible_cell(value, width: int, *, ellipsis: str = INV_ELLIPSIS_ASCII) -> str:
    """
    Format one inventory table cell: visible width ``width``, left-aligned,
    truncated with ASCII ``...`` when needed (ANSI in ``value`` is measured as-clean).
    """
    if width < 1:
        return ""
    raw = "" if value is None else str(value)
    clean = str(ANSIString(raw).clean())
    elen = len(ellipsis)
    if len(clean) <= width:
        return clean + " " * (width - len(clean))
    if width <= elen:
        return (ellipsis[:width]).ljust(width)
    body = clean[: width - elen] + ellipsis
    return body + " " * (width - len(body))


def divider(title, width=78, fillchar="-", color="|b", text_color="|y"):
    """Create a divider with consistent width.

    ``fillchar`` may be a single character or an Evennia ANSI segment repeated as one
    logical unit (e.g. ``|m-|n`` for a magenta dash). Do **not** use only the first
    character of multi-char strings -- that turns valid codes into spurious ``|`` runs.
    """
    if isinstance(fillchar, ANSIString):
        fillchar = str(fillchar)
    if not fillchar:
        fillchar = "-"

    # Visible width contributed by one repetition of fillchar (usually 1 for "-" or "|m-|n")
    unit_vis = max(1, len(ANSIString(fillchar).clean()))

    if title:
        # Calculate the width of the title text without color codes
        title_width = len(ANSIString(title).clean())

        # For column headers, center the title
        if width <= 25:  # Column headers
            padding = (width - title_width) // 2
            title_str = title.center(width)
            return f"{color}{title_str}|n"
        else:  # Full-width dividers
            # Padding on each side of the title (spaces around title are separate)
            padding = (width - title_width - 2) // 2  # -2 for spaces around the title
            right_slots = width - padding - title_width - 2
            left_units = max(0, padding // unit_vis)
            right_units = max(0, right_slots // unit_vis)

            left_part = color + fillchar * left_units + "|n"
            right_part = color + fillchar * right_units + "|n"
            return f"{left_part} {text_color}{title}|n {right_part}"
    else:
        line_units = max(0, width // unit_vis)
        return color + fillchar * line_units + "|n"


section_header = divider  # Alias for backward compatibility


def format_key_value(name: str, value: str, width: int = 40) -> str:
    """
    Format a key-value pair for display (e.g. rental info, status tables).
    Produces: "  Name....... Value"
    """
    val_str = str(value) if value is not None else "None"
    name_clean = str(ANSIString(name).clean())
    val_clean = str(ANSIString(val_str).clean())
    dots = max(0, width - len(name_clean) - len(val_clean) - 2)
    return f" |w{name}|n{'.' * dots} {val_str}"