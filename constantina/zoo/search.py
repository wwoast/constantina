import os
from whoosh import index
from whoosh.fields import Schema, ID, TEXT
from whoosh.qparser import QueryParser
import re
from defusedxml.ElementTree import fromstring, tostring
import syslog
import configparser

from constantina.shared import GlobalConfig, BaseFiles, opendir, unroll_newlines

syslog.openlog(ident='constantina.zoo.search')


class ZooSearch:
    """
    Constantina search object -- but for zoo posts, they work different.
    """
    # TODO: Modify this from the MedusaSearch in more than just a hack way! :)
    # TODO: No cardtype filtering here. Zoo filter will either apply this search or not
    def __init__(self, page, resultcount, unsafe_query_terms):
        self.config = configparser.SafeConfigParser()
        self.config.read('zoo.ini')

        # Upper limit on the permitted number of searchable items.
        # Since we use this as an array slice, add one to support N-1 elements
        self.max_query_count = GlobalConfig.getint("miscellaneous", "max_state_parameters") + 1

        # List of symbols to filter out in the unsafe input
        self.ignore_symbols = []
        # Regex of words that won't be indexed
        self.ignore_words = ''
        # After processing unsafe_query, save it in the object
        # Assume we're searching for all terms, unless separated by pluses
        self.query_string = ''
        # The contents of the last file we read
        self.content = ''
        # Notes on what was searched for. This will either be an error
        # message, or provide context on the search results shown.
        # Array of ctypes, each with an array of filename hits
        self.hits = {}

        # Whoosh object defaults
        self.schema = ''
        self.index = ''
        self.query = ''
        self.parser = ''
        self.searcher = ''
        self.results = ''

        # Max search results per page is equal to the number of cards that would
        # be shown on a normal news page. And while whoosh expects pages starting
        # at one, the page state counting will be from zero
        self.page = page + 1
        self.resultcount = resultcount

        # File paths for loading things
        card_root = GlobalConfig.get("paths", "data_root") + "/private"
        self.index_dir = card_root + "/" + self.config.get('search', 'index_dir')
        self.words_file = card_root + "/" + self.config.get('search', 'ignore_words')
        self.symobls_file = card_root + "/" + self.config.get('search', 'ignore_symbols')
        self.search_types = card_root + "/" + self.config.get("card_properties", "search").replace(" ", "").split(",")

        # Define the indexing schema. Include the mtime to track updated
        # content in the backend, ctype so that we can manage the distribution
        # of returned search results similar to the normal pages, and the
        # filename itself as a unique identifier (most filenames are utimes).
        self.schema = Schema(file=ID(stored=True, unique=True, sortable=True), ctype=ID(stored=True), mtime=ID(stored=True), content=TEXT)

        # If index doesn't exist, create it
        if index.exists_in(self.index_dir):
            self.index = index.open_dir(self.index_dir)
            # syslog.syslog("Index exists")
        else:
            self.index = index.create_in(self.index_dir, schema=self.schema)
            # syslog.syslog("Index not found -- creating one")
        # Prepare for query searching (mtime update, search strings)
        self.searcher = self.index.searcher()

        for ctype in self.search_types:
            # Prior to processing input, prepare the results arrays.
            # Other functions will expect this to exist regardless.
            self.hits[ctype] = []

        # Double check if the query terms exist or not
        if unsafe_query_terms is None:
            self.searcher.close()
            return

        # If the query string is null after processing, don't do anything else.
        # Feed our input as a space-delimited set of terms. NOTE that we limit
        # this in the __import_state function in MedusaState.
        if not self.__process_input(' '.join(unsafe_query_terms[0:self.max_query_count])):
            self.searcher.close()
            return

        for ctype in self.search_types:
            # Now we have good safe input, but we don't know if our index is
            # up-to-date or not. If have changed since their last-modified date,
            # reindex all the modified files
            self.__add_ctype_to_index(ctype)

        # Return only up to CARD_COUNT items per page for each type of returned
        # search result query. We calculate the max sum of all returned items,
        # and then we'll later determine which of these results we'll display
        # on the returned search results page.
        self.__search_index()
        self.searcher.close()


    def __process_input(self, unsafe_input, returning="query"):
        """Squeeze out ignore-characters, and modify the incoming query
        string to not search for things we don't index. This can set either
        self.query (search processing) or self.content (adding to index).
        Return values:
            0: word list and symbol erasing ate all the search terms
            1: valid query
        """
        # Make a or-regex of all the words in the wordlist
        if self.ignore_words == '':
            with open(self.words_file, 'r', encoding='utf-8') as wfile:
                words = wfile.read().splitlines()
                remove = '|'.join(words)
                self.ignore_words = re.compile(r'\b('+remove+r')\b', flags=re.IGNORECASE)

        # Then remove them from whatever input we're processing
        safe_input = self.ignore_words.sub("", unsafe_input)
        if safe_input == '':
            return 0

        # Get rid of symbol instances in whatever input we're processing
        # Note this only works on ASCII symbol characters, not the special
        # double-quote characters &ldquo; and &rdquo;, as well as other
        # defusedxml.ElementTree converted &-escaped HTML characters
        if self.ignore_symbols == '':
            with open(self.symbols_file, 'r', encoding='utf-8') as sfile:
                for character in sfile.read().splitlines():
                    self.ignore_symbols.push(character)
                    safe_input = safe_input.replace(character, " ")
        else:
            for character in self.ignore_symbols:
                safe_input = safe_input.replace(character, " ")

        # Did we sanitize a query, or a round of content? Infer by what
        # we're setting in the object itself.
        if safe_input != '':
            if returning == "query":
                self.query_string = safe_input
            else:
                self.content = safe_input
            return 1

        else:
            return 0


    def __add_file_to_index(self, fnmtime, filename, ctype="news"):
        """
        Reads in a file, processes it into lines, ElementTree grabs
        text out of the tags, processes the input to remove banal words
        and symbols, and then adds it to the index.
        """
        # Enable writing to our chosen index. To limit the index
        # locking, this is the only function that writes to the index.
        writer = self.index.writer()
        card_root = GlobalConfig.get("paths", "data_root") + "/private"
        card_path = card_root + "/" + self.config.get("paths", ctype)

        with open(card_path + "/" + filename, 'r', encoding='utf-8') as indexfh:
            body = ""
            lines = indexfh.read().splitlines()
            unrolled = unroll_newlines(lines)
            for line in unrolled:
                e = fromstring(line)
                if (e.tag == 'p'):
                    body += e.text + " "
            self.__process_input(body, returning="contents")
            # Update wraps add if the document hasn't been inserted, and
            # replaces current indexed data if it has been inserted. This
            # requires the file parameter to be set "unique" in the Schema
            writer.update_document(file=unicode(filename), ctype=unicode(ctype), mtime=unicode(fnmtime), content=unicode(self.content))

        # Finish by commiting the updates
        writer.commit()


    def __add_ctype_to_index(self, ctype):
        """Take a file type, list all the files there, and add all the
        body contents to the index."""
        # Make sure BaseFiles is populated
        opendir(self.config, ctype)
        card_root = GlobalConfig.get("paths", "data_root") + "/private"
        card_path = card_root + "/" + self.config.get("paths", ctype)

        for filename in BaseFiles[ctype]:
            try:
                fnmtime = int(os.path.getmtime(card_path + "/" + filename))
            except os.error:
                syslog.syslog("Failed to get \"" + filename + "\" mtime for indexing.")
                return   # File has been removed, nothing to index

            lastmtime = ''
            try:
                lastmtime = int(float(self.searcher.document(file=unicode(filename))['mtime']))
            except index.IndexError:
                lastmtime = 0   # File hasn't been indexed
            # If small revisions were made after the fact, the indexes won't
            # be accurate unless we reindex this file now
            if lastmtime < fnmtime:
                self.__add_file_to_index(fnmtime, filename, ctype)


    def __search_index(self):
        """
        Given a list of search paramters, look for any of them in the
        indexes. Don't return the Nth pge of resultcount hits.
        """
        self.parser = QueryParser("content", self.schema)
        self.query = self.parser.parse(unicode(self.query_string))
        self.results = self.searcher.search_page(self.query, self.page, sortedby="file", reverse=True, pagelen=self.resultcount)

        # Just want the utime filenames themselves? Here they are, in
        # reverse-utime order just like we want for insert into the page
        for result in self.results:
            ctype = result['ctype']
            self.hits[ctype].append(result['file'])
