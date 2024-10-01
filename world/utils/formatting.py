from evennia.utils.ansi import ANSIString

def format_stat(stat, value, width=25, default=None, tempvalue=None):
    # if there's no value and the default value is greater than 0 then use the default value.
    if default is not None and value is None or value == 0 or value == "":
        value = default

    if not value or value == "" or value == 0 and not tempvalue:
        value = default
    
    if not tempvalue:
        tempvalue = value
    # compare two strings
    if  ANSIString(f"{value}").strip() != ANSIString(f"{tempvalue}").strip():
        value = ANSIString(f"|h{value}|n(|w{tempvalue}|n)")

    # A regex to see if the string starts with a bscktick

    if ANSIString(f"{stat}").startswith("`"):
        return ANSIString(f"|n|y {stat}").ljust(width -  len(ANSIString(value).strip()), ANSIString('|y.|n')) + f"|n|y{value}|n"
    else:
        if value == default and default == 0 or value == default and default == "":
            value = ANSIString(f"|n{value}|n")
            stat = ANSIString(f"|n{stat}|n")
        else :
            value = ANSIString(f"|w{value}|n")
            stat = ANSIString(f"|w{stat}|n")

        return ANSIString(f" |w{stat}").ljust(width -  len(ANSIString(value).strip()), ANSIString('|h|x.|n')) + value


def header(title, width=78,  color="|y", fillchar=ANSIString("|b-|n"), bcolor="|b"):
    return ANSIString.center(ANSIString(f"{bcolor}<|n {color} {title} |n{bcolor}>|n"), width=width, fillchar=ANSIString(fillchar)) + "\n"

def footer(width=78, fillchar=ANSIString("|b-|n")):
    return ANSIString(fillchar) * width + "\n"


def divider(title, width=78, color="|y", fillchar="|b-|n"):
    fillchar = ANSIString(fillchar)
    title_ansi = ANSIString(f"{color} {title} |n")
    fill_width = width - len(title_ansi)
    left_fill = fillchar * ((fill_width + 1) // 2)  # Add 1 to round up
    right_fill = fillchar * (fill_width - len(left_fill))
    return left_fill + title_ansi + right_fill
