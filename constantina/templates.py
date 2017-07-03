from random import randint
from string import Template
from shared import GlobalConfig


def template_contents(raw, prefs):
    """
    Given the values in the preferences form, adjust the contents page
    to match the metadata relevant to the currently logged-in user.

    If not in Forum mode, do replacements that would make sense as
    defaults.
    """
    template = Template(raw)
    missing = {
        'username': 'guest',
        'post_count': 'yet to make',
        'registration_date': 'any given moment',
        'default_topic': 'general',
        'default_expand': 'expandAll',
        'default_revise': '120'
    }
    theme_range = len(GlobalConfig.items('themes')) - 1
    theme_enabled = 'checked="checked"'
    theme_chosen = -1
    replacements = {}

    if prefs is None:
        # Replace page variables with defaults
        for field in missing.keys():
            replacements[field] = missing[field]
        for theme in xrange(0, theme_range):
            replacements['theme_state_' + str(theme)] = ''
        replacements['theme_state_random'] = theme_enabled

    else:
        # Replace page variables with preferences
        replacements = {
            'username': prefs.username,
            'post_count': missing['post_count'],   # TODO
            'registration_date': missing['registration_date'],   # TODO
            'default_topic': prefs.top,
            'default_expand': str(prefs.gro),
            'default_revise': str(prefs.rev)
        }
        theme_chosen = int(prefs.thm)
        if theme_chosen not in xrange(0, theme_range):
            replacements['theme_state_random'] = theme_enabled
        else:
            for theme in xrange(0, theme_range):
                if theme_chosen == theme:
                    replacements['theme_state_' + str(theme)] = theme_enabled
                else:
                    replacements['theme_state_' + str(theme)] = ''

    # Based on the theme value, actually replace stylesheet theme data
    if theme_chosen not in xrange(0, theme_range):
        theme_chosen = randint(0, theme_range)
    theme_directory = GlobalConfig.get("themes", str(theme_chosen))
    replacements['theme_directory'] = theme_directory

    # Returned output is the template transform
    output = template.safe_substitute(replacements)
    return output
