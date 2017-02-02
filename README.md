# Constantina
### A dynamic-content blog platform
##### Justin Cassidy, February 2017

## Overview
Constantina is a single-page static site generator designed to randomize 
content for *grazing*. It's written in Python, and was originally written
to host my music and technology site, [Codaworry](http://www.codaworry.com). 

![mobile1](https://raw.githubusercontent.com/wwoast/constantina/master/docs/mobile1.png)
![mobile2](https://raw.githubusercontent.com/wwoast/constantina/master/docs/mobile2.png)
![desktop1](https://raw.githubusercontent.com/wwoast/constantina/master/docs/desktop1.png)
![desktop2](https://raw.githubusercontent.com/wwoast/constantina/master/docs/desktop2.png)


## Changelog

* **0.4.0** - First public release


## Features
* Single-page single-column infinite-scroll layout
 * Layout responsive at any screen size or orientation
 * Infinite scroll falls back to a "click to load" for legacy browsers
* Page consists of a series of *cards* 
 * Card content is either short HTML snippets, or raw images/music files
 * Add content to a folder, and it will publish upon the next page load
 * Each card type has unique distribution and layout rules
* Search feature for cards with text emphasis
 * Uses `whoosh` text-search library on the backend
 * Unindexed text cards get indexed any time content is searched
 * Supports ''encyclopedia'' cards that only appear in search results
* News cards contain Permalinks for external linking
* Future-dated news only publish after their timestamp
* Three colorful themes, and straightforward HTML/CSS to make new ones
* Page layout and card types are easily configurable


## How It Works
Roughly 20 cards are displayed upon initial load, and Constantina considers
this a ''page'' of content. No additional cards are loaded until the reader 
scrolls further in the viewport, or submits a search in the search bar.

Each card presents content stored in one of Constantina's content folders. 
Each content folder has a [file naming convention](https://raw.githubusercontent.com/wwoast/constantina/docs/ADMIN.md)
and specific rules for how the content appears in the Constantina layout.

News items always have unix-timestamp names, and appear in reverse-time order,
newest to oldest. Pictures and interjections are randomly-distributed through
the pages, with guaranteed spacing. Songs and advertisements appear once per 
''page'', randomly distributed. Finally, there are a handful of special cards,
such as headers, footers, and *tombstones* that assist or alert about any
pagination activities or page state.


## Usage and Lifecycle
Constantina is licensed under the [GNU Affero General Public License](https://raw.githubusercontent.com/wwoast/constantina/docs/LICENSE.md). I've been using it for three years, and if you decide
to use it, I'd love your help in making it better.

Constantina is a Python web application, and running it requires solid knowledge
of Unix tools (`ssh` or `sftp`, Python, `uwsgi`). If you have basic footing in these 
technologies, read the [installation and configuration notes](https://raw.githubusercontent.com/wwoast/constantina/docs/ADMIN.md) to get started!

While this is currently a blog engine, I intend Constantina to be a platform
for small online communities. Eventually I intend to implement authentication,
a web forum, a basic webdav calendar, and an IMAP webmail client, all as part of 
the existing system of cards and config.




##Card Format and Naming Standards

| Card Type | Path                 | File Naming Standard     | File Formats   |
|-----------|----------------------|--------------------------|----------------|
| news      | cards/news/          | unix-time (`date +%s`)   | Limited HTML   |
| images    | cards/pictures/      | any filename OK          | `.jpg`, `.png` |
| songs	    | cards/songs/         | playlist plus subfolder  | `.mp3`, `.m3u` |
| quotes    | cards/interjections/ | any filename OK          | Limited HTML   |
| heading   | cards/heading/       | any filename OK          | Limited HTML   |
| topics    | cards/encyclopedia/  | search-term string match | Limited HTML   |

There are a handful of other untested card types defined. ''Limited HTML'' 
format is a HTML format with two lines at the beginning, one for the post 
title, and the other for searchable keywords:

```
Example Post
Education, Demonstration

<img class="InlineNewsLeft" src="/images/news/wingkey.png" alt="Example image" />
<p>The Limited HTML format is generally restricted to display logic that easily displays on both large screens and single-column portrait mobile displays. Anchors, paragraphs, images, and other basic layout info is recommended.</p>
```

For news cards, name these files a unix timestamp and the date that timestamp
corresponds to will be the stated publishing date of that card. `vim $(date +%s)` 
will create a file with the current unix timestamp as the filename.

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
| heading   | cards/heading/       | Fixed  | Predetermined | No      | 1**       |
| topics    | cards/encyclopedia/  | Fixed  | Predetermined | Yes     | 1***      |

   * 	= May index metadata for these in the future
   **	= Just header and footer cards on the first and/or last pages
   ***	= Only returned when using the search bar


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
