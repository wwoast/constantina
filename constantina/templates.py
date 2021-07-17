from string import Template

from constantina.themes import GlobalTheme

def template_contents(raw):
    """
    Anything involving template generation on server-side for Constantina
    is here. Currently it's just the $theme_directory to use.
    """
    template = Template(raw)
    replacements = {}
    replacements['theme_directory'] = GlobalTheme.theme
    # Returned output is the template transform
    output = template.safe_substitute(replacements)
    return output
