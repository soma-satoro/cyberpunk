"""
Utility functions for searching and validating characters.
"""
from evennia.utils.search import search_object
from typeclasses.characters import Character


def _get_aliases(character):
    """
    Collect all known aliases for a character.

    Supports both Evennia's alias-handler and the custom `alias` Attribute
    used elsewhere in this codebase.
    """
    aliases = []

    # Evennia alias-handler aliases (obj.aliases)
    try:
        aliases.extend(character.aliases.all())
    except Exception:
        pass

    # Custom Attribute alias (obj.db.alias / obj.attributes.get("alias"))
    custom_alias = character.attributes.get("alias", default=None)
    if custom_alias:
        if isinstance(custom_alias, (list, tuple, set)):
            aliases.extend(str(alias) for alias in custom_alias if alias)
        else:
            aliases.append(str(custom_alias))

    return [str(alias).strip().lower() for alias in aliases if str(alias).strip()]


def search_character(searcher, search_string, global_search=True, quiet=False):
    """
    Search for a character, ensuring only Character objects are returned.
    
    Args:
        searcher (Object): The object performing the search
        search_string (str): The string to search for
        global_search (bool): Whether to search globally or just in the current location
        quiet (bool): Whether to suppress error messages
        
    Returns:
        Character or None: The found character object, or None if not found
    """
    query = (search_string or "").strip()
    if not query:
        if not quiet:
            searcher.msg("You must provide a character name to search for.")
        return None

    query_lc = query.lower()

    def _location_filter(results):
        if global_search:
            return results
        searcher_location = getattr(searcher, "location", None)
        if not searcher_location:
            return []
        return [obj for obj in results if getattr(obj, "location", None) == searcher_location]

    # 1) Exact key/dbref match first.
    exact_matches = search_object(query, typeclass=Character, exact=True)
    exact_matches = _location_filter(exact_matches)
    if exact_matches:
        return exact_matches[0]

    # 2) Broader search and deterministic best-match selection.
    broad_matches = search_object(query, typeclass=Character)
    broad_matches = _location_filter(broad_matches)

    if broad_matches:
        # Prefer exact case-insensitive key match.
        for char in broad_matches:
            if char.key.lower() == query_lc:
                return char

        # Then match on aliases (both alias-handler and custom alias Attribute).
        for char in broad_matches:
            if query_lc in _get_aliases(char):
                return char

        # Fallback to first candidate from Evennia search ranking.
        return broad_matches[0]

    # 3) No valid character was found.
    if not quiet:
        searcher.msg(f"Could not find a character named '{query}'.")
    return None