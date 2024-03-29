# Constantina
### A dynamic-content blog platform
##### Justin Cassidy, July 2021

## Overview
Constantina is a single-page static site generator designed to randomize 
content for *grazing*. It's written in Python, and was originally written
to host my music and technology site, [Codaworry](http://www.codaworry.com). 

<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/desktop1.png" width="720" />
<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/mobile1.png" width="320" />


## Changelog

* **0.7.0** - Sunsetting auth and separate app support for easier blog maintenance
* **0.6.0** - Migrated to Python 3 for better performance and pervasive Unicode support
* **0.5.6** - Separated out security-oriented configuration for file monitoring purposes
* **0.5.5** - Forum settings forms and cookies, `X-Sendfile` trampolining for `private` media
* **0.5.3** - For `private` files, added caching headers and fixed paths with spaces
* **0.5.2** - Move images to `private`, make search non-AJAX to better support auth checks
* **0.5.0** - Install from `setup.py`, authentication features test-released
* **0.4.5** - Under-the-hood "sub-application" support, fixed search index generation
* **0.4.0** - First public release


## Features
* Single-page single-column infinite-scroll layout
  * Layout responsive for any screen size or orientation
  * Infinite scroll falls back to a "click to load" for legacy browsers
* Page consists of a series of *cards* 
  * Card content is either short HTML snippets, or raw images/music files
  * Add content to a folder, and it will publish upon the next page load
  * News cards contain Permalinks for external linking
  * Future-dated news only publish after their timestamp
  * Page layout and card types are easily configurable
* Search feature for cards with text emphasis
  * Uses `whoosh` text-search library on the backend
  * Unindexed text cards get indexed any time content is searched
  * Supports keyword searches as well as "#cardtype" searches
  * Supports ''encyclopedia'' cards that only appear in search results 
* Three colorful themes, and straightforward HTML/CSS to make new ones

<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/desktop2.png" width="720" />


## How It Works
Roughly 20 cards are displayed upon initial load, and Constantina considers
this a ''page'' of content. No additional cards are loaded until the reader 
scrolls further in the viewport, or submits a search in the search bar.

Each card presents content stored in one of Constantina's content folders. 
Each content folder has a [file naming convention](https://github.com/wwoast/constantina/blob/master/docs/ADMIN.md)
and specific rules for how the content appears in the Constantina layout.

News items always have unix-timestamp names, and appear in reverse-time order,
newest to oldest. Pictures and interjections are randomly-distributed through
the pages, with guaranteed spacing. Songs and advertisements appear once per 
''page'', randomly distributed. Finally, there are a handful of special cards,
such as headers, footers, and *tombstones* that assist or alert about any
pagination activities or page state.

<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/mobile2.png" width="320" />


## Usage and Lifecycle
Constantina is licensed under the [GNU Affero General Public License](https://github.com/wwoast/constantina/blob/master/LICENSE.md). I've been using it for three years, and if you decide
to use it, I'd love your help in making it better.

Constantina is a Python web application, and running it requires solid knowledge
of Unix tools (`ssh` or `sftp`, Python, `uwsgi`). If you have basic footing in these 
technologies, try setting up an instance yourself!
 * [Installation](https://github.com/wwoast/constantina/blob/master/docs/INSTALL.md)
 * [Configuration](https://github.com/wwoast/constantina/blob/master/docs/CONFIG.md)

