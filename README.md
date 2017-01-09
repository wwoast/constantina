# Constantina
### A dynamic-content blog platform
##### Justin Cassidy, July 2014

## Overview
Constantina is a single-page static site generator designed to randomize 
content. To get a basic idea, visit http://www.codaworry.com, and refresh the 
page a few times.


## Features
* Single-page single-column infinite-scroll layout
 * Bundled with `zepto.js` and light supporting Javascript
 * Layout responsive at any screen size
 * Well supported and tested on mobile, landscape and portrait
 * Infinite scroll falls back to a "click to load" for legacy browsers
* Page consists of a simple series of cards 
 * Card content is either a prescribed file type or a short HTML snippet
 * Each card type is stored in a separate folder
 * Add content to a folder, and it will publish upon the next page load
 * Each card type has unique distribution and layout rules
* Search feature for any cards with text content
 * Uses `whoosh` text-search library on the backend
 * Supports ''encyclopedia'' cards that only appear in search results
* News cards contain Permalinks for external linking
* Future-dated news only publish after their timestamp


## Usage
Constantina is an infinite-scrolling layout containing a series of "cards". 
Roughly 20 cards are displayed upon initial load, and no additional cards are 
loaded until the reader scrolls further in the viewport. We'll call each set of
20 cards a ''page''.

Each card presents content stored in one of Constantina's content folders. 
Finally, each content folder has rules for how the content appears in the 
Constantina layout.

News items always have unix-timestamp names, and appear in reverse-time order,
newest to oldest. Pictures and interjections are randomly-distributed through
the pages, with guaranteed spacing. Songs and advertisements appear once per 
''page'', randomly distributed. Finally, there are a handful of special cards,
such as headers, footers, and "tombstones" that assist or alert about any
pagination activities or page state.


## Architecture
`constantina.py` is a single Python script on the backend, which loads a series
of static webpages, javascript, and content on the frontend.

The backend script pulls files from subdirectories in a single ROOT_DIR folder.
Some of these subdirectories store files that appear in set reverse-time
order, like news entries. Other subdirectories store media that appear with
random spacing and random ordering, such as pictures, songs, and quotes. A
MAX_ITEMS variable defines the total size of the page -- once MAX_ITEMS is
reached, the page must trigger an AJAX event to load further content. 

The front end defines a single-column responsive layout for nearly any screen
size. This column will display "cards" of content in an infinitely-scrolling
list. A clickable event and a scroll-height event will both trigger AJAX calls
to load further content into the page.


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
