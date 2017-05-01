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

// TODO: block authentication form when HTTP is used
(function() {
	if ( document.url.indexOf("https") != 0 ) {
        login = document.getElementsByClassName("login")[0];
		login.style.display = "none";

		https_error = document.getElementsByClassName("https_error")[0];
		login.style.display = "block";
	}
})