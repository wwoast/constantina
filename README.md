# Constantina
### A dynamic-content blog platform
##### Justin Cassidy, February 2017

## Overview
Constantina is a single-page static site generator designed to randomize 
content for "grazing". To get a basic idea, visit http://www.codaworry.com,
and refresh the page a few times.


## Changelog

* **0.4.0** - First public release


## Features
* Single-page single-column infinite-scroll layout
 * Bundled with `zepto.js` and light supporting Javascript
 * Layout responsive at any screen size
 * Actively tested on mobile, landscape and portrait
 * Infinite scroll falls back to a "click to load" for legacy browsers
* Page consists of a series of cards 
 * Card content is either short HTML snippets, or raw images/music files
 * Add content to a folder, and it will publish upon the next page load
 * Each card type has unique distribution and layout rules
* Search feature for any cards with text content
 * Uses `whoosh` text-search library on the backend
 * Supports ''encyclopedia'' cards that only appear in search results
* News cards contain Permalinks for external linking
* Future-dated news only publish after their timestamp


## How It Works
Roughly 20 cards are displayed upon initial load, and Constantina considers
this a ''page'' of content. No additional cards are loaded until the reader 
scrolls further in the viewport, or submits a search in the search bar.

Each card presents content stored in one of Constantina's content folders. 
Each content folder has a file naming convention and specific rules for how 
the content appears in the Constantina layout.

News items always have unix-timestamp names, and appear in reverse-time order,
newest to oldest. Pictures and interjections are randomly-distributed through
the pages, with guaranteed spacing. Songs and advertisements appear once per 
''page'', randomly distributed. Finally, there are a handful of special cards,
such as headers, footers, and ''tombstones'' that assist or alert about any
pagination activities or page state.


##Card Layout Rules
Card types are listed below, as well as their default path below the ROOT_DIR,
whether card placement on the page is random or not, and whether the order
of cards in the page is randomly determined or not. Not all card types are
indexed for searching, but we make note which types are. 

Finally, the cards per page values are listed, all of which can be adjusted
by an admin. The card spacing rules are not shown below, but those values are
adjustable as well.

   Card Type	Path		Layout	Order		Indexed	Cards/Page
   ---------	----		------	-----		-------	----------
   news		news/		Fixed	Reverse-Time	Yes	10
   images	pictures/	Random	Random		No*	4
   songs	songs/		Random	Reverse-Time	No*	1
   quotes	interjections/	Random	Random		Yes	3
   ads		gracias/	Random	Random		No	0**
   media	embedded/	Random	Random		No	0**
   features	features/	Random	Random		Yes	0**
   heading	heading/	Fixed	Predetermined	No	1***
   topics	encyclopedia/	Fixed	Predetermined	Yes	1****

   * 	= May index metadata for these in the future
   ** 	= Admin will likely want to adjust these upward
   ***	= Just header and footer cards on the first and/or last pages
   ****	= Only returned when using the search bar


##Installing Constantina

### List of Python dependencies
TOWRITE

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
