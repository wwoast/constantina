(function() {
	if ( navigator.platform === "iPad" ) {
		var scale = 1.2;
		document.write('<meta name="viewport" content="width=device-width, initial-scale='+scale+', minimum-scale='+scale+', maximum-scale='+scale+', user-scalable=0" />');

	} else if ( navigator.platform === "iPhone" ) {
		var scale = 1.0;
		document.write('<meta name="viewport" content="width=device-width, initial-scale='+scale+', minimum-scale='+scale+', maximum-scale='+scale+', user-scalable=0" />');

	} else if ( navigator.userAgent.indexOf("Android") != -1 ) {
		var scale = 1.0;
		document.write('<meta name="viewport" content="width=device-width, initial-scale='+scale+', minimum-scale='+scale+', maximum-scale='+scale+', user-scalable=0, target-densitydpi="device-dpi" />');
	} else {
		return;
	}
})(); 


var clickMore = false;
var wasFresh = [];

// The last headingCard in the page is a hidden marker. If it can't be hidden
// by Javascript, it will display a "load more content" link that can be
// clicked to load additional content into the page, based on the state
// variable, which opening the page will change. If clicked, provide a
// "true" argument. Otherwise provide "false" to the function.
function addMoreContent(was_clicked) {
   clickMore = was_clicked;

   // Heading card named for the "tombstone" needs to get replaced
   var tombstone = document.getElementById('tombstone');

   // Replace tombstone with page contents
   var state = tombstone.querySelector('#state').innerHTML;

   // Add content into the page
   $.get(
      "/?" + state,
       function (data) {
          $(".container").append(data);
       }
   );

   tombstone.id = "old_tombstone";
}


// Make all loading buttons show a "Loading..." state
function loadingButton() {
   // And add a listener to set the loading text for this and others
   document.getElementById('loadButton').addEventListener('click', function() {
      document.getElementById('loadButton').style.display = "none";
      document.getElementById('inProgress').style.display = "block";
   }, false);
}


// Once page has loaded, add new event listeners. When new cards are added to
// the page, run this code to regenerate tombstones and scrollstones that
// manage the loading of new content
$(function() {
   if ( document.getElementById('loadButton') != null ) {
      loadingButton();
   }

   // Add the search text pre-populated into the search bar
   document.getElementById("searchEntry").placeholder = searchPlaceholderText();

   // Detect when we loaded more content, and scroll to it if it was done via
   // a button click at the bottom of the page. Need a timeout value so that 
   // we scrollIntoView() only when all divs are finally rendered
   document.getElementById('container').addEventListener( 'DOMNodeInserted', function () {
      // If the bottom-of-page button was actually clicked, do a page-shift
      // so that it's clear the new content is finished loading.
      setTimeout(function () {
         var old_tombstone = document.getElementById('old_tombstone');
         if( clickMore == true ) {
            clickMore = false;
            // Go to an element next to the previous tombstone
            last_element = old_tombstone.previousElementSibling;
            // If last element was expanded, shrink it 
            shortener = last_element.querySelector('.showShort');
            if ( shortener ) { 
               if ( shortener.style.display == "none" ) {
                  revealToggle(last_element.id);
               }
            }
            last_element.scrollIntoView();
         }
         // Any old tombstones should be removed
         $("#old_tombstone").remove();
         $("#old_scrollstone").remove();
         // Any new divs should get topic links that are clickable
         activateTopicLinks();
         loadingButton();
      }, 200);
   }, false );

   // If we scrolled past the scrollstone itself, start adding new content
   window.addEventListener( 'scroll', function() {
      var scrollstone = document.getElementById('scrollstone');
      // If scrolled past the scrollstone, start loading data
      if ( document.body.scrollTop >= scrollstone.offsetTop ) {
         scrollstone.id = "old_scrollstone";
         addMoreContent(false);

         document.getElementById('loadButton').style.display = "none";
         document.getElementById('inProgress').style.display = "block";
      }
   });      

   // Make new topic links clickable and populate the search bar
   activateTopicLinks();

   // Process input into the search form
   $('#searchForm').submit(function() {
      $('#searchEntry').blur();   // Make iOS keyboard disappear after submitting
      var query = $('#searchEntry').val().trim();
      // TODO: Remove or escape any search processing characters here like commas
      // Allow searches using special characters like #. The escape function doesn't
      // support unicode, so use encodeURI instead.
      query = encodeURI(query);

      // Load more data
      window.location.assign("/?xs" + query);
   });

   // If the cancel button is clicked, close the settings window
   $("#closeSettings").click(function(){
      revealMenu('zooSettings');
   })
});

function searchPlaceholderText() { 
   if (window.location.href.indexOf("?xs") != -1) {
       var placeholder = window.location.href.split("?")[1].slice(2);
       return unescape("\u27A4") + decodeURI(placeholder);
   } else {
       return unescape("Search \u27A4");
   }
}

function activateTopicLinks() { 
   var linkList = document.getElementsByClassName('topicLink');
   for (var i = 0; i < linkList.length; i++ ) {
      linkList[i].addEventListener('click', function() {
         $('#searchEntry').val(this.text);
         $('#searchForm').submit();
      }, false);
   }
}

function revealToggle(id) {
   var card = document.getElementById(id);
   var largeImgs = card.querySelectorAll('.imgExpand')
   var expandLink = card.querySelector('.showShort')
   var expandDiv = card.querySelector('.divExpand')
   var todo = expandLink.style.display;

   if ( todo !== "none" ) {
      expandLink.style.display = "none";
      expandDiv.style.display = "block";
      for ( var i = 0; i < largeImgs.length; i++ ) {
         largeImgs[i].style.display = "block";
      }
      // If a card is color-highlighted (fresh), remove
      // the highlight once it's expanded. This preserves
      // the look of the gradient effect for smaler items.
      if ( card.classList.contains("fresh") ) {
         wasFresh.push(id);
         card.classList.remove("fresh");
      }
   }
   else {
      expandLink.style.display = "inline";
      expandDiv.style.display = "none";
      for ( var i = 0; i < largeImgs.length; i++ ) {
         largeImgs[i].style.display = "none";
      }
      // If a card was color-highlighted, add the 
      // freshness back once shrunk.
      if ( wasFresh.indexOf(id) != -1) {
         wasFresh.splice(wasFresh.indexOf(id), 1);
         card.classList.add("fresh");
      }
   }
}

function revealMenu(id) {
   // Logic for the Zoo menu buttons
   var button_id = id.replace("zoo", "button");
   var button_ids = ['buttonSettings', 'buttonDocs'];
   var menu_ids = ['zooSettings', 'zooDocs'];
   var card = document.getElementById(id);
   var button = document.getElementById(button_id);
   var todo = card.style.display;
   if ( todo !== "none" ) {
      card.style.display = "none";
      button.style.background = "rgba(255, 255, 255, 0.0)";
   } else {
      for ( var i = 0; i < menu_ids.length; i++ ) {
          var menu = document.getElementById(menu_ids[i]);
          var menu_button = document.getElementById(button_ids[i]);
          menu.style.display = "none";
          menu_button.style.background = "rgba(255, 255, 255, 0.0)";
      }
      card.style.display = "block";
      button.style.background = "rgba(255, 255, 255, 0.2)";
   }
}

function modifyPostBox(card, nextCard, mode) {
    // Switching between quote and reply mode in the text areas.
    // If a reply was already typed, and quote is clicked, just change 
    // the class of the existing box and add quote to the top of it.
    //
    // If a quote box is open and either reply or quote links are clicked,
    // the box will be hidden but not removed. Quote text won't be added 
    // after it first appears in the text box.
    //
    // Returns [need-to-create-card, need-to-add-quote-text]
    createCard = true;
    addText = false;

    if (nextCard.classList.contains("newPost")) {
        // Click Reply or Quote twice? Card disappears, but is not destroyed
        if (nextCard.classList.contains(mode)) {
            createCard = false;
        }
        // Turning on a quote? Add contents to the textarea
        else if ((nextCard.classList.contains("reply")) && (mode === "quote")) {
            addText = true;
            createCard = false;
        }
        else if ((nextCard.classList.contains("quote")) && (mode === "reply")) {
            createCard = false;
        }
    }
    if ((createCard == true) && (mode === "quote")) {
        // Just adding a quote card where none existed.
        addText = true;
    }
    return [createCard, addText];
}

function createPost(id, mode) {
   var card = document.getElementById(id);
   var reply = document.createElement('textarea');
   reply.className = "newThread";
   reply.required = true;

   var nextCard = card.nextElementSibling;
   var [createCard, addText] = modifyPostBox(card, nextCard, mode)

   reply.name = mode;
   if ( addText == true ) {
      // Get body of the earlier message, and format it without nested
      // quotes. Only basic paragraphs (avoid pre/code/friends) 
      quotetext = card.childNodes[3].getElementsByClassName('postBody');
      // Munge all paragraphs, and put it in a [QUOTE] tag.
      quotecode = "[QUOTE]" + quotetext[0].textContent + "[/QUOTE]";
      if (createCard == true) {
         reply.defaultValue = quotecode;
      } else {
         // Is there a quote in there already? If so, don't add any more
         existing = nextCard.firstElementChild.defaultValue;
         if (existing.indexOf("[QUOTE]") == -1) { 
            nextCard.firstElementChild.defaultValue = quotecode + "\n" + existing;
         }
      }
      // Once it gets a quote, give it the "quote" class, since we just added quote text.
      nextCard.classList.remove('reply');
      nextCard.classList.add('quote');

   } else if ((nextCard.classList.contains('reply')) || (nextCard.classList.contains('quote'))) {
       if (nextCard.style.display == "none") {
           nextCard.style.display = "block";
       } else {
           nextCard.style.display = "none";
       }
   } else {
      reply.placeholder = "Add Your Reply!";
   }

   // Append edit menu afterwards
   if ( createCard == true) {
      var newPostCard = document.createElement('div');
      newPostCard.className = 'card newPost';
      newPostCard.classList.add(mode);

      var replyFooter = document.createElement('div');
      // TODO: not newthread class?
      replyFooter.className = "rolldown newthread";
      var attachmentButton = document.createElement('input');
      attachmentButton.className = "threadFileInput";
      attachmentButton.type = "file";
      attachmentButton.name = "attachment";
      var submitButton = document.createElement('input');
      submitButton.className = "threadSubmit";
      submitButton.type = "submit";
      submitButton.name = "submit";
      replyFooter.appendChild(attachmentButton);
      replyFooter.appendChild(submitButton);

      newPostCard.appendChild(reply);
      newPostCard.appendChild(replyFooter);

      card.insertAdjacentElement('afterEnd', newPostCard);
   }
}
