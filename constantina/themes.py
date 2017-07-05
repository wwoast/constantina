import syslog

from random import randint, seed
from shared import GlobalConfig

syslog.openlog(ident='constantina.themes')


class ConstantinaTheme:
    """
    Constantina Theme tracking.

    With the non-cookie State, the forum-cookie State, as well as website
    template loading all doing checks of theme information, it made sense
    to manage theme settings in a single place, and even a single Global
    object.
    """
    def __init__(self):
        """
        Read the theme settings from a file, and set any defaults.
        desired_theme is either a numeric index into the array of themes, or
        'default' to allow for either default-config or random choice.

        self.theme is the directory path to the theme.
        self.index is which Nth value in the config has our theme.
           self.index and preferences.thm should be the same
        """
        self.index = None
        self.theme = None
        self.default = GlobalConfig.get("themes", "default")
        self.count = len(GlobalConfig.items("themes")) - 1
        self.random = False

    def set(self, desired_theme=None):
        """
        The Global Theme is set during state loading, but we manage the
        attempted/imported values here, in case we need to deconflict between
        state-cookie theme settings and preferences theme settings.
        """
        if desired_theme is None:
            # Choose the plain default value
            self.theme = self.default
        elif desired_theme == -1:
            # Random choice selected from the menu
            self.__random_choice()
        else:
            # Choose based on user input, mod'ing to the number of themes
            # if the user input was some out-of-range number
            self.index = int(desired_theme) % self.count
            self.theme = GlobalConfig.get("themes", str(self.index))
            self.random = False

        # Do we have a default set to 'random'?
        if desired_theme is None and self.theme == "random":
            self.__random_choice()
        # Otherwise, the index is whatever matches the theme value
        else:
            self.index = [int(x[0]) for x in GlobalConfig.items("themes")[1:]
                          if x[1] == self.theme][0]

    def __random_choice(self):
        # If the configuration supports a random theme, and we didn't have a
        # theme provided in the initial state, let's choose one randomly
        seed()   # Enable non-seeded choice
        self.index = randint(0, self.count - 1)
        self.theme = GlobalConfig.get("themes", str(self.index))
        self.random = True


GlobalTheme = ConstantinaTheme()