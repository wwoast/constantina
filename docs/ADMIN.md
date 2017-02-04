# Constantina
### A dynamic-content blog platform
##### Justin Cassidy, February 2017

##Summary
[Constantina](https://github.com/wwoast/constantina) is a static site generator designed for *grazing*. It is licensed under the [GNU Affero General Public License](https://github.com/wwoast/constantina/blobs/master/docs/LICENSE.md).

##Installing Constantina

### List of Python dependencies
You can grab these either from your distro or Python package manager, with the
exception of `python-magic` where Debian's distro version has a totally different
API than the version in `pip`.

 * `pymad` for MP3 parsing. Unfortunately, this requires some C compiling.
 * `pillow` for image operations. Successor to the older `PIL`
 * `python-magic` for file type checks
 * `lxml` for occasions where you need to parse HTML files
 * `configparser` for implementing the configuration files
 * `whoosh` for reverse-index word searching
 * `wsgiref` if you need to use Apache and `mod_cgi`

### uwsgi+nginx on a private server
The best performing way to install Constantina is with a dedicated
application server such as `gunicorn` or `uwsgi`, with a more general
web server like `nginx` sitting in front and serving static assets.

`/etc/nginx/sites-available/constantina.conf`:
```
server {
        # Port, config, SSL, and other details here

        # Just proxy the exact location on your webserver that you
        # want Constantina to load within. All other locations are 
        # static files that shouldn't be proxied.
        location = / {
                proxy_pass        http://localhost:9090/;
                proxy_set_header  X-Real-IP $remote_addr;
        }
}
```

`uwsgi.constantina.ini`:
```
[uwsgi]
http-socket  = :9090
plugin       = python
wsgi-file    = /path/to/constantina.py
processes    = 3
procname     = constantina
max-requests = 5
master
close-on-exec
```

At the command line, you can test Constantina by running:
```
uwsgi --ini uwsgi.constantina.ini --daemonize=/path/to/constantina.log
```

### Apache + mod_cgi on Shared Hosting
For those of you still on shared hosting, Constantina will run behind `mod_cgi`
with the included `constantina.cgi` helper script. In the folder where you want
Constantina to treat as your web root folder (i.e. your `public_html` folder),
add a brief Apache config snippet file named `.htaccess`:

```
RewriteEngine on

# All root not directed at files should be processed through CGI
# Replace /cgi-bin/ with your hosting provider's specified scripts folder
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^(.*)$ /cgi-bin/constantina.cgi
```


##Configuration Settings
`cgi-bin/constantina.ini` stores all operational configuration for Constantina.

 * `[paths].root` is the root of your public HTML directory where files are hosted
  * The other values in this section are paths for each card type, under `[paths].root`
   * You shouldn't need to change these
 * The `[card_counts]` section enforces the number of cards per page, per card-type
 * The `[card_spacing]` section similarly enforces the spacing on the page
 * `[card_filters]` define equivalent "card type" terms for searching
  * Normally if you want to search for news cards you type *#news*
  * However, the `[card_filters]` section defines alternatives such as *#updates*
 * `[card_properties]` defines logic for how state functions when cards are present
  * *This section should not be changed*
 * `[authentication]` is not used yet, and should just be set to `blog`.
 * `[search]` defines paths and wordlists for Whoosh's search indexing
 * `[themes]` defines where Constantina's themes are located
  * Any themes you add must be listed by number, aside from the `default` entry
  * If the default theme is set to `random`, one of the numbered options is used
 * `[special_states]` should only be modified if new card types are added
  * New text-card types should get a new `_permalink` special state
 * `[miscellaneous].max_state_parameters` is the limit on search terms that will be processed.
  * The default here is 10, so you can't process more than 10 search terms and 10 filter terms
  * Constantina itself won't process more than 512 characters from any `QUERY_STRING`


##How Cards Work
Cards are the basis of Constantina. News cards are shown in reverse-time
order, while images, quotes, and ordering of cards are all randomized on
the server.


###Card Naming Standards
| Card Type | Path                 | File Naming Standard     | File Formats   |
|-----------|----------------------|--------------------------|----------------|
| news      | cards/news/          | unix-time (`date +%s`)   | Limited HTML   |
| images    | cards/pictures/      | any filename OK          | `.jpg`, `.png` |
| songs	    | cards/songs/         | playlist plus subfolder  | `.mp3`, `.m3u` |
| quotes    | cards/interjections/ | any filename OK          | Limited HTML   |
| heading   | cards/heading/       | any filename OK          | Limited HTML   |
| topics    | cards/encyclopedia/  | search-term string match | Limited HTML   |

For news cards, name these files a unix timestamp and the date that timestamp
corresponds to will be the stated publishing date of that card. `vim $(date +%s)` 
will create a file with the current unix timestamp as the filename.


###Text Card Format: Limited HTML
**Limited HTML** format is a HTML format with two lines at the beginning, one 
for the post title, and the other for searchable keywords. The rest is basic
paragraph tags with light use of nested images where necessary. Keeping the
text cards simplified is crucial for readable mobile single-column layouts.

```
Example Post
Education, Demonstration

<img class="InlineNewsLeft" src="/images/news/wingkey.png" alt="Example image" />
<p>The Limited HTML format is generally restricted to display logic that easily displays on both large screens and single-column portrait mobile displays. While Constantina itself does not restrict your HTML content, you should stick to simple layout designs, using just basic anchors, paragraphs, images, and subheadings.</p>
```

###Image Card Format: PNG/JPG Images
Picture cards interleaved into the page are relatively large size, so you
should be open to using high-quality JPG or PNG images, so they appear sharp
on both Retina (Hi-DPI) and normal PC displays.


###Song Card Format: MP3 folders and M3U Playlists
Song cards will package all the songs in a playlist into a single block. The
playlist should point at songs in a subfolder of `cards/songs`, and `.m3u`
files are just a simple list of those song files (including the containing
directory), one per line:

```
Evergreen Jazz/Toadstools.mp3
Evergreen Jazz/Bug Catchers.mp3
Evergreen Jazz/Nowhere Bells.mp3
Evergreen Jazz/Blue Mormon.mp3
```


##Card Layout Rules
Card types are listed below, as well as their default path below the `ROOT_DIR`,
whether card placement on the page is random or not, and whether the order
of cards in the page is randomly determined or not. Not all card types are
indexed for searching, but we make note which types are. 

Finally, the cards per page values are listed, all of which can be adjusted
by an admin. The card spacing rules are not shown below, but those values are
adjustable as well.

| Card Type | Path                 | Layout | Order         | Indexed | Cards/Page |
|-----------|----------------------|--------|---------------|---------|------------|
| news      | cards/news/          | Fixed  | Reverse-Time  | Yes     | 10         |
| images    | cards/pictures/      | Random | Random        | No*     | 4          |
| songs	    | cards/songs/         | Random | Reverse-Time  | No*     | 1          |
| quotes    | cards/interjections/ | Random | Random        | Yes     | 3          |
| heading   | cards/heading/       | Fixed  | Predetermined | No      | 1**        |
| topics    | cards/encyclopedia/  | Fixed  | Predetermined | Yes     | 1+         |

  * `*`  : May index metadata for these in the future
  * `**` : Just header and footer cards on the first and/or last pages
  * `+`	 : Only returned when using the search bar


##Creating Themes
Constantina themes consist of themes subfolder, and at least a `content.html`
page and a `style.css` stylesheet. The `content.html` file has a single
comment that gets replaced with all the card content generated by Constantina.
Other than this replacement step, there's no limit to what you can do with
the stylesheet and HTML design.

All of Constantina's responsive layout focus comes from the stylesheets
and content design, so I'll describe some of the guidelines I use. Firstly,
the Constantina themes are aggressively single-column page layouts, so that
portrait-mode on mobile is naturally supported. Secondly, to account for
the sparseness of the single-column layouts on PCs, I try and leverage the
wallpaper itself for texture and color.

On mobile, wallpapers must be able to vertically tile to be visually 
consistent with the fixed-background wallpapers on the desktop. For years,
mobile browsers have failed to support fixed wallpapers, and there are
typically problems with scrolling tiled wallpapers. If you scroll the page
prior to the content fully loading, it will leave a "hole" in the
wallpaper the length of your first scroll event. iOS 10 seems to have
reduced the odds of "holes" occuring in your scrolling, but it's not perfect.
