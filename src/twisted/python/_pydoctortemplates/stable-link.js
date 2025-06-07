// If the documentation isn't stable or latest, insert a stable link
const HTML_BASE_URL = "https://docs.twisted.org/en/stable/api/";

if ((window.location.pathname.indexOf('/stable/') == -1) && (window.location.pathname.indexOf('/latest/') == -1)) {
    // Give the user a link to this page, but in the stable version of the docs.
    var link = document.getElementById('current-docs-link');
    var url = window.location.pathname;
    var filename = url.substring(url.lastIndexOf('/')+1);
    // And make it visible
    var container = document.getElementById('current-docs-container');
    container.style.display = "block";
    link.href = HTML_BASE_URL + filename;
    delete link;
    delete container;
    delete url;
    delete filename;
    
}