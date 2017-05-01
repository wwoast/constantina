(function() {
	if ( navigator.platform === "iPad" ) {
		var scale = 1.2;
		document.write('<meta name="viewport" content="width=device-width; initial-scale='+scale+'; minimum-scale='+scale+'; maximum-scale='+scale+'; user-scalable=0;" />');

	} else if ( navigator.platform === "iPhone" ) {
		var scale = 1.0;
		document.write('<meta name="viewport" content="width=device-width; initial-scale='+scale+'; minimum-scale='+scale+'; maximum-scale='+scale+'; user-scalable=0;" />');

	} else if ( navigator.userAgent.indexOf("Android") != -1 ) {
		var scale = 1.2;
		document.write('<meta name="viewport" content="width=device-width; initial-scale-'+scale+'; minimum-scale='+scale+'; maximum-scale='+scale+'; user-scalable=0; target-densitydpi="device-dpi"; />');
	} else {
		return;
	}
})(); 


var clickMore = false;

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
                  cardToggle(last_element.id);
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
      // Remove or escape any search processing characters here like commas
      $(".container").empty();

      // Create a now-searching div
      var loadingText = ''
      if ( query == '' ) {
         loadingText = document.createTextNode('Reshuffling...');
      } else {
         loadingText = document.createTextNode('Searching...');
      }
      var loading = document.createElement('div');
      loading.className = "card heading";
      loading.id = "search_waiting";
      var loadingContents = document.createElement('p');
      loadingContents.id = "loadButton";
      loadingContents.appendChild(loadingText);
      loading.appendChild(loadingContents);
      $(".container").append(loading);

      // Allow searches using special characters like #
      query = escape(query);

      // Load more data
      $("#searchForm").action = "/?xs" + query;
      $.get(
         "/?xs" + query,
          function (data) {
             // hack hack hack (length check)
             if ( data.length <= 200 ) {
                var failedText = document.createTextNode('No results.');
                loadingContents.removeChild(loadingText);
                loadingContents.appendChild(failedText);
             } else {
                $(".container").empty();
                $(".container").append(data);
             }
          }
      );
   });
});


function activateTopicLinks() { 
   var linkList = document.getElementsByClassName('topicLink');
   for (var i = 0; i < linkList.length; i++ ) {
      linkList[i].addEventListener('click', function() {
         $('#searchEntry').val(this.text);
         $('#searchForm').submit();
      }, false);
   }
}

function cardToggle(id) {
   var card = document.getElementById(id);
   var largeImgs = card.querySelectorAll('#imgExpand')
   var expandLink = card.querySelector('.showShort')
   var expandDiv = card.querySelector('.divExpand')
   var todo = expandLink.style.display;

   if ( todo !== "none" ) {
      expandLink.style.display = "none";
      expandDiv.style.display = "block";
      for ( var i = 0; i < largeImgs.length; i++ ) {
         largeImgs[i].style.display = "block";
      }
   }
   else {
      expandLink.style.display = "inline";
      expandDiv.style.display = "none";
      for ( var i = 0; i < largeImgs.length; i++ ) {
         largeImgs[i].style.display = "none";
      }
   }   
}
