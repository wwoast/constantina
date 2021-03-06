# Constantina
### A dynamic-content blog platform

## Configuration Settings
`/etc/constantina/<INSTANCE>/constantina.ini` stores all operational configuration for Constantina.

 * `[paths].data_root` is the root of `public` (HTML and themes) and `private` (card) data
 * `[authentication]` should just be set to `blog` for normal use, or `forum` for auth-testing
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
the server. In authentication situations, card access is only permitted with
a successful login, so all cards are found in `[paths].data_root`/`private`.


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

Constantina does some tricks server-side to hide images or cards that have more than three paragraphs
of text inside them. The tricks aren't very clever yet however, so as a result the **Limited HTML**
format only supports the following tags at the beginning of a line:

 * `<p>`
 * `<img>`
 * `<ul>`
 * `<ol>`
 * `<div>`
 * `<h5>`


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
  * `+`	 : Only returned when using the search bar for the *exact name* of the page.
    * The page contents for *topics* cards are not search-indexed
    * These pages are intended to be semi-secret, not appearing in the normal feed


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
