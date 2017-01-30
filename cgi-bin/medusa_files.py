from datetime import datetime
import os
import syslog
import ConfigParser

syslog.openlog(ident='medusa_files')
CONFIG = ConfigParser.SafeConfigParser()
CONFIG.read('constantina.ini')


# Only do opendir once per directory, and store results here
# The other Medusa modules need access to this "globally".
MedusaFiles = {}


def remove_future(dirlisting):
    """For any files named after a Unix timestamp, don't include the
    files in a directory listing if the timestamp-name is in the future.
    Assumes the dirlisting is already sorted in reverse order!"""
    for testpath in dirlisting:
        date = datetime.fromtimestamp(int(testpath)).strftime("%s")
        current = datetime.strftime(datetime.now(), "%s")
        if date > current:
            dirlisting.remove(testpath)
        else:
            break

    return dirlisting


def opendir(ctype, hidden=False):
    """
    Return either cached directory information or open a dir and
    list all the files therein. Used for both searching and for the
    card reading functions, so we manage it outside those.
    """
    directory = CONFIG.get("paths", ctype)
    if hidden is True:
        directory += "/hidden"
        ctype += "/hidden"

    # If the directory wasn't previously cached
    if ctype not in MedusaFiles.keys():
        # Default value. If no files, keep the empty array
        MedusaFiles[ctype] = []

        dirlisting = os.listdir(directory)
        if (dirlisting == []):
            return MedusaFiles[ctype]

        # Any newly-generated list of paths should be weeded out
        # so that subdirectories don't get fopen'ed later
        for testpath in dirlisting:
            if os.path.isfile(os.path.join(directory, testpath)):
                MedusaFiles[ctype].append(testpath)

        # Sort the output. Most directories should use
        # utimes for their filenames, which sort nicely. Use
        # reversed array for newest-first utime files
        MedusaFiles[ctype].sort()
        MedusaFiles[ctype].reverse()

        # For news items, remove any items newer than the current time
        if ctype == "news":
            MedusaFiles[ctype] = remove_future(MedusaFiles[ctype])

    return MedusaFiles[ctype]
