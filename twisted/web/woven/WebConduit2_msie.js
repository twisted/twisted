var InternetExplorer = navigator.appName.indexOf('Microsoft') != 1
function FlashConduit_swf_DoFSCommand(command, args) {
	eval(args)
}

if (InternetExplorer) {
	if (navigator.userAgent.indexOf('Windows') != -1) {
		document.write('<SCRIPT LANGUAGE=VBScript\>\n')
		document.write('on error resume next\n')
		document.write('Sub FlashConduit_swf_FSCommand(ByVal command, ByVal args)\n')
		document.write('call FlashConduit_swf_DoFSCommand(command, args)\n')
		document.write('end sub\n')
		document.write('</SCRIPT\>\n')
	}
	
}

var woven_eventQueue = []
woven_eventQueueBusy = 0
woven_clientSideEventNum = 0

function woven_eventHandler(eventName, node) {
    var eventTarget = node.getAttribute('id')
    var additionalArguments = ''
    for (i = 2; i<arguments.length; i++) {
        additionalArguments += '&woven_clientSideEventArguments='
        additionalArguments += escape(eval(arguments[i]))
    }
    var source = '?woven_clientSideEventName=' + eventName + '&woven_clientSideEventTarget=' + eventTarget + additionalArguments + '&woven_clientSideEventNum=' + woven_clientSideEventNum
    woven_clientSideEventNum += 1
    
    woven_eventQueue = woven_eventQueue.concat(source)
    if (!woven_eventQueueBusy) {
        woven_sendTopEvent()
    }
    return false
}

function woven_sendTopEvent() {
    woven_eventQueueBusy = 1
    var url = woven_eventQueue[0]
    woven_eventQueue = woven_eventQueue.slice(1)
    var input = document.getElementById('woven_inputConduit')
    
    input.src = url
}

function woven_clientToServerEventComplete() {
    if (this.woven_eventQueue.length) {
        this.woven_sendTopEvent()
    } else {
        this.woven_eventQueueBusy = 0
    }
    var focus = document.getElementById('woven_firstResponder')
    if (focus) {
        focus.focus()
        if (focus.getAttribute('clearOnFocus')) {
            focus.value=''
        }
    }
    document.scrollTop = 999999999
}

function woven_attemptFocus(theNode) {
    // focus the first input element in the new node
    if (theNode.tagName == 'INPUT') {
        theNode.focus()
        return 1
    } else {
/*         for (i=0; i<theNode.childNodes.length; i++) { */
/*             if(woven_attemptFocus(theNode.childNodes[i])) { */
/*                 return 1 */
/*             } */
/*         } */
        return 0
    }
}

function woven_replaceElement(theId, htmlStr) {
    //alert(woven_eventQueue.length)
    var oldNode = document.getElementById(theId)
    if (oldNode) {
        if (oldNode.parentNode) {
            var created = document.createElement('span')
            created.innerHTML = htmlStr
            if (created.firstChild) {
                oldNode.parentNode.replaceChild(created.firstChild, oldNode)
                var newNode = document.getElementById(theId)
                //woven_attemptFocus(newNode)
            }
        }
    }
}
 
function woven_appendChild(theId, htmlStr) {
    var container = document.getElementById(theId)
    var newNode = document.createElement('span')
    newNode.innerHTML = htmlStr
    container.appendChild(newNode.firstChild)
}

function woven_removeChild(theId) {
    var theElement = document.getElementById(theId)
    theElement.parentNode.removeChild(theElement)
}
