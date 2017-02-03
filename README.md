# Constantina
### A dynamic-content blog platform
##### Justin Cassidy, February 2017

## Overview
Constantina is a single-page static site generator designed to randomize 
content for *grazing*. It's written in Python, and was originally written
to host my music and technology site, [Codaworry](http://www.codaworry.com). 

<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/desktop1.png" width="720" />
<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/mobile1.png" width="320" />


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
 * Supports keyword searches as well as "#cardtype" searches
 * Supports ''encyclopedia'' cards that only appear in search results
* News cards contain Permalinks for external linking
* Future-dated news only publish after their timestamp
* Three colorful themes, and straightforward HTML/CSS to make new ones
* Page layout and card types are easily configurable

<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/desktop2.png" width="720" />


## How It Works
Roughly 20 cards are displayed upon initial load, and Constantina considers
this a ''page'' of content. No additional cards are loaded until the reader 
scrolls further in the viewport, or submits a search in the search bar.

Each card presents content stored in one of Constantina's content folders. 
Each content folder has a [file naming convention](https://github.com/wwoast/constantina/docs/ADMIN.md)
and specific rules for how the content appears in the Constantina layout.

News items always have unix-timestamp names, and appear in reverse-time order,
newest to oldest. Pictures and interjections are randomly-distributed through
the pages, with guaranteed spacing. Songs and advertisements appear once per 
''page'', randomly distributed. Finally, there are a handful of special cards,
such as headers, footers, and *tombstones* that assist or alert about any
pagination activities or page state.

<img src="https://raw.githubusercontent.com/wwoast/constantina/master/docs/mobile2.png" width="320" />


## Usage and Lifecycle
Constantina is licensed under the [GNU Affero General Public License](https://github.com/wwoast/constantina/docs/LICENSE.md). I've been using it for three years, and if you decide
to use it, I'd love your help in making it better.

Constantina is a Python web application, and running it requires solid knowledge
of Unix tools (`ssh` or `sftp`, Python, `uwsgi`). If you have basic footing in these 
technologies, read the [installation and configuration notes](https://github.com/wwoast/constantina/docs/ADMIN.md) to get started!

While this is currently a blog engine, I intend Constantina to be a platform
for small online communities. Eventually I intend to implement authentication,
a web forum, a basic webdav calendar, and an IMAP webmail client, all as part of 
the existing system of cards and config.
