function woven_eventHandler(eventName, node) {
    var input = document.getElementById('woven_inputConduit')
    var eventTarget = node.getAttribute('id')
    var additionalArguments = ''
    for (i = 2; i<arguments.length; i++) {
        additionalArguments += '&woven_clientSideEventArguments='
        additionalArguments += escape(eval(arguments[i]))
    }
    var source = '?woven_clientSideEventName=' + eventName + '&woven_clientSideEventTarget=' + eventTarget + additionalArguments

    input.src = source
}

function onkeyevent(theEvent)
{ 	
    if (!theEvent) {
        theEvent = event
    }
	code = theEvent.keyCode;
	if (code==13) {
		send()
	}
}

function send() {
    var inputText = document.getElementById('inputText')
    document.getElementById("woven_inputConduit").src = "?wovenLivePageInput=" + escape(inputText.value)
    recv("-> " + inputText.value)
    inputText.value = ""
    inputText.focus()
}

function woven_replaceElement(theId, htmlStr) {
    var oldNode = document.getElementById(theId)
    var r = oldNode.ownerDocument.createRange();
    r.setStartBefore(oldNode);
    var parsedHTML = r.createContextualFragment(htmlStr);
    oldNode.parentNode.replaceChild(parsedHTML, oldNode);
}


function recv(stuff) {
    var output = document.getElementById("content")
// Works on ie mac and mozilla but not as well on ie win
    output.appendChild(document.createTextNode(unescape(stuff)))
    output.appendChild(document.createElement("br"))
// Works on ie win & mac, and mozilla, but is a bit slower
    //output.innerHTML = output.innerHTML + unescape(stuff) + '<br \>'
    window.scrollBy(0, window.innerHeight)
}

function focusInput() {
    document.getElementById('inputText').focus()
}

document.onkeypress = onkeyevent
