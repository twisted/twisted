// Old Moz JS

function onkeyevent(theEvent)
{ 	
    if (!theEvent) {
        theEvent = event
    }
	code = theEvent.keyCode;
	if (code==13 || code==10) {
		var inputText = document.getElementById('inputText')
		send('None', inputText.value)
	}
        
}

document.onkeypress = onkeyevent

function send(recipient, text) {
    if (text) {
      document.getElementById("input").src = "?input=" + escape(text) + "&recipient=" + escape(recipient)
        // what would be really cool is if we did it roman here and 
        // and changed it to italics on receive :D
        var inputText = document.getElementById("inputText")
        inputText.value = ""
        focusInput() // inputText.focus()
    }
}

function recv(stuff) {
    var output = document.getElementById("content")
// Works on ie mac and mozilla but not as well on ie win
//    output.appendChild(document.createTextNode(unescape(stuff)))
//    output.appendChild(document.createElement("br"))
// Works on ie win & mac, and mozilla, but is a bit slower
    output.contentDocument.documentElement.innerHTML = output.contentDocument.documentElement.innerHTML + unescape(stuff) + '<br \>'
    output.contentWindow.scrollBy(0, output.contentWindow.innerHeight)
}

function focusInput() {
    foo = document.getElementById('inputText')
    foo.focus()
    foo.onkeypress = onkeyevent
}

