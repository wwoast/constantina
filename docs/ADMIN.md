# Constantina
### A dynamic-content blog platform
##### Justin Cassidy, February 2017

## Summary
[Constantina](https://github.com/wwoast/constantina) is a static site generator designed for *grazing*. It is licensed under the [GNU Affero General Public License](https://github.com/wwoast/constantina/blobs/master/LICENSE.md).

## Installing Constantina

### List of Linux dependencies

There are a handful of Linux packages needed (Debian/Ubuntu) to support the ones
installed by Python:

 * `apt-get install libjpeg-dev libffi-dev libssl-dev`

 For use with uwsgi application servers, also install:

 * `apt-get install uwsgi uwsgi-plugin-python`


### List of Python dependencies
You can grab these either from your distro or Python package manager, with the
exception of `python-magic` where Debian's distro version has a totally different
API than the version in `pip`.

Install the Python dependencies manually or from `pip`:

 * `pip install -r requirements.txt`
  * `argon2`, `argon2_cffi`, and `argon2pure` for password hashing
  * `jwcrypto` for managing JWT and JWE session token formats
  * `lxml` for occasions where you need to parse HTML files
  * `mutagen` for MP3 length parsing
  * `passlib` as a wrapper for password hashing
  * `pillow` for image operations. Successor to the older `PIL`
  * `python-magic` for file type checks
  * `whoosh` for reverse-index word searching
  * `wsgiref` if you need to use Apache and `mod_cgi`


### Installing Constantina
`python setup.py install -h` describes the options for installing Constantina.
The setup script attempts to install all files necessary for running the 
application, aside from the webserver configuration.

A typical install includes the webserver's username and group that it hosts
files for, the hostname the site will be accessed through, and a port number
that the application will listen on:

```
`python ./setup.py install -u www-data -g www-data \
   --hostname codaworry.com --port 9090
```

Although Constantina tries to choose useful defaults when running the install
script, it's a good idea to include at least the values above, so that you
are installing on your system in a consistent way. Since Constantina doesn't
manage webserver configuration, it's important that subsequent installations
use the same port and hostname, to be consistent with an existing Nginx or
Apache configuration.

Once you've installed Constantina, you'll need to choose how the application
will run on your webserver. But first, a couple of relevant details:


#### Instances
Constantina uses an idea of *instances*, in case you want to run a staging
copy of the application on the same server as the production copy. This is
a good way to test configuration changes prior to making them on your live
site. Every static resource and configuration for an instance is separated
from the others.

If no instance is specified when running `python ./setup.py install`, the
instance name is called `default`. You'll see that reflected in the paths
to the installed file locations.

Here's an example of installing Constantina twice, under two different
locations and ports, using the *instances* feature:

```
python ./setup.py install -i default --port 9090 \
   --hostname codaworry.com -u www-data -g www-data
python ./setup.py install -i staging --port 9091 \
   --hostname codaworry.com -u www-data -g www-data \
```

#### File Locations
Post-installation, files are installed in the following locations:
 * static HTML: `/var/www/constantina/default`
 * config files: `/etc/constantina/default`
 * Python files: (your system or local Python directories)
 * CGI scripts: `/var/cgi-bin/constantina/default`


### uwsgi+nginx on a private server
The best performing way to install Constantina is with a dedicated
application server such as `gunicorn` or `uwsgi`, with a more general
web server like `nginx` sitting in front and serving static assets out
of its root directory.

`/etc/nginx/sites-available/constantina.conf`:
```
server {
        # Port, config, SSL, and other details here
        listen  localhost:8080;
        root  /var/www/constantina/default;

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
http-socket  = localhost:9090
plugin       = python
module       = constantina.constantina
processes    = 3
procname     = constantina-default
chdir        = /var/www/constantina/default
max-requests = 5
master
close-on-exec
```

At the command line, you can test Constantina by running:
```
uwsgi --ini /etc/constantina/default/uwsgi.ini --daemonize=/path/to/constantina.log
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
SetEnv INSTANCE default
```


## Configuration Settings
`/etc/constantina/<INSTANCE>/constantina.ini` stores all operational configuration for Constantina.

 * `[paths].data_root` is the root of public (HTML) and private (card) data
 * `[authentication]` is not used yet, and should just be set to `blog`.
 * `[themes]` defines where Constantina's themes are located
  * Any themes you add must be listed by number, aside from the `default` entry
  * If the default theme is set to `random`, one of the numbered options is used
 * `[special_states]` should only be modified if new Constantina functionality is added
 * `[miscellaneous].max_state_parameters` is the limit on search terms that will be processed.
  * The default here is 10, so you can't process more than 10 search terms and 10 filter terms
  * Constantina itself won't process more than 512 characters from any `QUERY_STRING`

`/etc/constantina/<INSTANCE>/medusa.ini` stores configuration related to Constantina's blog functionality.

 * `[paths]` values describe where each type of card is stored
  * You shouldn't need to change these
 * The `[card_counts]` section enforces the number of cards per page, per card-type
 * The `[card_spacing]` section similarly enforces the spacing on the page
 * `[card_filters]` define equivalent "card type" terms for searching
  * Normally if you want to search for news cards you type *#news*
  * However, the `[card_filters]` section defines alternatives such as *#updates*
 * `[card_properties]` defines logic for how state functions when cards are present
  * *This section should not be changed*
 * `[search]` defines paths and wordlists for Whoosh's search indexing
 * `[special_states]` should only be modified if new card types are added
  * New blog text-card types should get a new `_permalink` special state


## How Cards Work
Cards are the basis of Constantina. News cards are shown in reverse-time
order, while images, quotes, and ordering of cards are all randomized on
the server.


### Card Naming Standards
| Card Type | Path                  | File Naming Standard     | File Formats   |
|-----------|-----------------------|--------------------------|----------------|
| news      | medusa/news/          | unix-time (`date +%s`)   | Limited HTML   |
| images    | medusa/pictures/      | any filename OK          | `.jpg`, `.png` |
| songs	    | medusa/songs/         | playlist plus subfolder  | `.mp3`, `.m3u` |
| quotes    | medusa/interjections/ | any filename OK          | Limited HTML   |
| heading   | medusa/heading/       | any filename OK          | Limited HTML   |
| topics    | medusa/encyclopedia/  | search-term string match | Limited HTML   |

For news cards, name these files a unix timestamp and the date that timestamp
corresponds to will be the stated publishing date of that card. `vim $(date +%s)` 
will create a file with the current unix timestamp as the filename.


### Text Card Format: Limited HTML
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

### Image Card Format: PNG/JPG Images
Picture cards interleaved into the page are relatively large size, so you
should be open to using high-quality JPG or PNG images, so they appear sharp
on both Retina (Hi-DPI) and normal PC displays.


### Song Card Format: MP3 folders and M3U Playlists
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


## Card Layout Rules
Card types are listed below, as well as their default path below the `ROOT_DIR`,
whether card placement on the page is random or not, and whether the order
of cards in the page is randomly determined or not. Not all card types are
indexed for searching, but we make note which types are. 

Finally, the cards per page values are listed, all of which can be adjusted
by an admin. The card spacing rules are not shown below, but those values are
adjustable as well.

| Card Type | Path                  | Layout | Order         | Indexed | Cards/Page |
|-----------|-----------------------|--------|---------------|---------|------------|
| news      | medusa/news/          | Fixed  | Reverse-Time  | Yes     | 10         |
| images    | medusa/pictures/      | Random | Random        | No*     | 4          |
| songs	    | medusa/songs/         | Random | Reverse-Time  | No*     | 1          |
| quotes    | medusa/interjections/ | Random | Random        | Yes     | 3          |
| heading   | medusa/heading/       | Fixed  | Predetermined | No      | 1**        |
| topics    | medusa/encyclopedia/  | Fixed  | Predetermined | Yes     | 1+         |

  * `*`  : May index metadata for these in the future
  * `**` : Just header and footer cards on the first and/or last pages
  * `+`	 : Only returned when using the search bar


## Creating Themes
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


## Authentication
**Constantina Authentication is currently a work in progress, and is documented
for both testing and for input from peers.**


### Enabling Authentication and Configuring Accounts 
Constantina supports username and password-based authentication in version 
0.5.0, but there are no enrollment flows through the web interface yet.
However, a Python CLI script called `constantina_configure.py` lets you 
configure Constantina users.

To create a user and be interactively prompted for a new password:
`constantina_configure.py -a <login_name>`

To create a user and set an initial password in one step:
`constantina_configure.py -a <login_name> -p <initial_password>`

Enabling authentication in Constantina is a matter of setting `authentication`
to `forum` in your instance's `constantina.ini`.


### How Authentication and Sessions Work
If Authentication is enabled, relevant settings for users and session cookies
will appear in your instance's `/etc/constantina/<instance>/shadow.ini` file.

On the backend, Constantina uses *Argon2* password hashing for modern and 
tunable security of sensitive password hashes. All aspects of the Argon 
hashing algorithm are configurable in the `shadow.ini` file, including:

 * `v`: The version of the *Argon2* hash format (*19 is fine*)
 * `m`: The memory cost of checking a hash, in kilobytes
 * `t`: The time cost of checking a hash, in hash-iterations
 * `p`: The parallelization parameter (set based on your CPU/thread count)

Session cookies are JWE tokens, a format for encrypted JSON data. Inside
the JWE is a signed JWT that indicates a user, instance, and validity period.
The `shadow.ini` file, after a user first loads Constantina in a browser, contains
two encryption keys and two signing keys using the HMAC-SHA256 algorithm. One key
is labelled "current" and the other is labelled "last".

Each signing and encryption key has a two-day validity period by default, and is 
sunsetted after one day. Sunsetting is where existing older tokens are still valid,
but the key is no longer used for encrypting or signing new tokens. The validity
and sunsetting timeframes are configurable in the `key_settings` section of `shadow.ini`.

Each instance of Constantina has an opaque ID that it addes to its JWE tokens. A
given instance will only validate the cookie that contains the correct opaque ID in
its cookie name. The opaque instance ID is stored in `constantina.ini` along with 
the other `hostname` and `port` information.