from random import randint
from string import Template
from shared import GlobalConfig

# Anything involving template generation on server-side for Constantina
# is here, including the preferences form menu and things to do with
# selecting new themes.


def template_themes(desired_theme):
    """
    Server side rendering of the theme selection menu.
    """
    theme_range = len(GlobalConfig.items('themes')) - 1
    valid_theme = (desired_theme in xrange(0, theme_range))
    chosen_theme = desired_theme
    if valid_theme is False:
        # Account for random=-1, and out-of-range values
        chosen_theme = randint(0, theme_range)

    menu = ""
    option = Template("""
  <label>
     <input type="radio" name="thm" value="$theme_index" $theme_selected />
     <img src="$theme_directory/theme.png" />
  </label>
""")

    for theme in xrange(0, theme_range):
        replacements = {}
        replacements['theme_index'] = str(theme)
        replacements['theme_directory'] = GlobalConfig.get('themes', str(theme))
        if theme == desired_theme and valid_theme is True:
            replacements['theme_selected'] = 'chosen="chosen"'
        else:
            replacements['theme_selected'] = ''
        menu += option.safe_substitute(replacements)

    random = {}
    random['theme_index'] = -1
    random['theme_directory'] = GlobalConfig.get('themes', str(chosen_theme))
    random_option = Template("""
  <label>
     <input type="radio" name="thm" value="$theme_index" $theme_selected />
     <img src="$theme_directory/random-theme.jpg" />
  </label>
""")
    if valid_theme is False:
        random['theme_selected'] = 'chosen="chosen"'
    else:
        random['theme_selected'] = ''
    menu += random_option.safe_substitute(random)

    return [menu, random['theme_directory']]


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
    replacements = {}

    if prefs is None:
        # Replace page variables with defaults
        for field in missing.keys():
            replacements[field] = missing[field]
        [replacements['theme_menu'],
         replacements['theme_directory']] = template_themes(-1)

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
        [replacements['theme_menu'],
         replacements['theme_directory']] = template_themes(int(prefs.thm))

    # Returned output is the template transform
    output = template.safe_substitute(replacements)
    return output