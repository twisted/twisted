
// JAVASCRIPT FOR MSIE

function onkeyevent(theEvent)
{
  if (!theEvent) {
    theEvent = event;
  }
  code = theEvent.keyCode;
  if (code==13 || code==10) {
    var inputText = document.getElementById('inputText');
    send('None', inputText.value);
  }
}

document.onkeypress = onkeyevent

function send(recipient, text) {
  if (text) {
    document.getElementById("input").src = "?input=" + escape(text) + "&recipient=" + escape(recipient);
    // what would be really cool is if we did it roman here and
      // and changed it to italics on receive :D
        var inputText = document.getElementById("inputText");
    inputText.value = "";
    focusInput(); // inputText.focus()
  }
}

function recv(stuff) {
  var output = document.getElementById("content");

  var fc = frames.content;
  var fcd = fc.document;
  var fcdb = fcd.body;
  fcdb.insertAdjacentHTML("beforeEnd", stuff + "<br/>");
  output.contentWindow.scrollBy(0, 5000); //output.innerHeight
}

function focusInput() {
  foo = document.getElementById('inputText');
  foo.focus();
  foo.onkeypress = onkeyevent;
}

