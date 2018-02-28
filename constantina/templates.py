from random import randint
from string import Template
import syslog

from constantina.shared import GlobalConfig
from constantina.themes import GlobalTheme

syslog.openlog(ident='constantina.templates')


# Anything involving template generation on server-side for Constantina
# is here, including the preferences form menu and things to do with
# selecting new themes.


def template_themes(desired_theme):
    """
    Server side rendering of the theme selection menu.
    """
    menu = ""
    option = Template("""
  <label>
     <input type="radio" name="thm" value="$theme_index" $theme_selected />
     <img src="$theme_directory/theme.png" />
  </label>
""")

    for index in range(0, GlobalTheme.count):
        replacements = {}
        replacements['theme_index'] = str(index)
        replacements['theme_directory'] = GlobalConfig.get('themes', str(index))
        if index == desired_theme and GlobalTheme.random is False:
            replacements['theme_selected'] = 'checked="checked"'
        else:
            replacements['theme_selected'] = ''
        menu += option.safe_substitute(replacements)

    random = {}
    random['theme_index'] = -1
    random['theme_directory'] = GlobalTheme.theme
    random_option = Template("""
  <label>
     <input type="radio" name="thm" value="$theme_index" $theme_selected />
     <img src="$theme_directory/random-theme.jpg" />
  </label>
""")
    if GlobalTheme.random is True:
        random['theme_selected'] = 'checked="checked"'
    else:
        random['theme_selected'] = ''
    menu += random_option.safe_substitute(random)

    return [menu, random['theme_directory']]


def template_selectoptions(default_value, **kwargs):
    """
    Set the select attribute on the text entry box based on what's in the
    preferences. Used for "Expand Posts" logic and TODO: the default topic
    form (waiting on a topic registry)
    """
    output = ""
    selected = 'selected="selected"'
    options = Template("""
    <option value="$key" $selected>$value</option>
""")
    for key in kwargs.keys():
        replacements = {
            'key': key,
            'value': kwargs[key],
            'selected': ''
        }
        if key == default_value:
            replacements['selected'] = selected
        output += options.safe_substitute(replacements)

    return output


def default_template_values(missing):
    """
    For cases where no authentication happens, return default template values
    """
    # Replace page variables with defaults
    replacements = {}
    for field in missing.keys():
        replacements[field] = missing[field]
    [replacements['theme_menu'],
     replacements['theme_directory']] = template_themes(GlobalTheme.index)
    return replacements


def replace_template_values(missing, prefs):
    """
    If authentication and forums are happening, replace any template strings
    with the necessary user or content data.
    """
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
    # syslog.syslog("Theme in cookie: " + str(prefs.thm))
    return replacements


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
        'default_expand': '0',
        'default_revise': '120'
    }
    replacements = {}

    expand_options = {
        '0': 'Expand All Posts',
        '1': 'Show Only The Latest 10 Posts'
    }

    if prefs is None:
        replacements = default_template_values(missing)
    elif prefs.valid is False:
        replacements = default_template_values(missing)
    else:
        replacements = replace_template_values(missing, prefs)

    # Expand Threads form
    replacements['expand_options'] = template_selectoptions(replacements['default_expand'], **expand_options)

    # Returned output is the template transform
    output = template.safe_substitute(replacements)
    return output
