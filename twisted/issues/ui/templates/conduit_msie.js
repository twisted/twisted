// JAVASCRIPT FOR MSIE

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
//function scrollTextFrame()
//{
//        document.getElementById("initialtextFrame").contentDocument.defaultView.scroll(0, 50000);
//}

function recv(stuff) {
    var output = document.getElementById("content")
// Works on ie mac and mozilla but not as well on ie win
    output.document.documentElement.appendChild(output.document.createTextNode(unescape(stuff)))
//    output.appendChild(document.createElement("br"))
//    output.contentDocument.defaultView.scrollBy(0, 5000)
// Works on ie win & mac, and mozilla, but is a bit slower
    alert(stuff)
//    output.document.innerHTML = output.document.documentElement.innerHTML + unescape(stuff) + '<br \>'
    output.contentWindow.scrollBy(0, output.innerHeight)
}

function focusInput() {
    foo = document.getElementById('inputText')
    foo.focus()
    foo.onkeypress = onkeyevent
}

