var woven_eventQueue = []
woven_eventQueueBusy = 0
woven_clientSideEventNum = 0
woven_requestingEvent = 0

function woven_eventHandler(eventName, node) {
    var eventTarget = node.getAttribute('id')
    var additionalArguments = ''
    for (i = 2; i<arguments.length; i++) {
        additionalArguments += '&woven_clientSideEventArguments='
        additionalArguments += escape(eval(arguments[i]))
    }
    var source = '?woven_clientSideEventName=' + eventName + '&woven_clientSideEventTarget=' + eventTarget + additionalArguments + '&woven_clientSideEventNum=' + woven_clientSideEventNum
    woven_clientSideEventNum += 1
    
    woven_eventQueue.unshift(source)
    if (!woven_eventQueueBusy) {
        woven_sendTopEvent()
    }
    return false
}

function woven_sendTopEvent() {
    woven_eventQueueBusy = 1
    var url = woven_eventQueue.shift()
    var input = document.getElementById('woven_inputConduit')
    
    input.src = url
}

function woven_requestNextEvent() {
    var output = document.getElementById('woven_outputConduit')

    if (output) { output.src = '?woven_hookupOutputConduitToThisFrame=1&woven_clientSideEventNum=' + woven_clientSideEventNum.toString()}
}

function woven_clientToServerEventComplete() {
    woven_requestNextEvent()

    if (woven_eventQueue.length) {
        woven_sendTopEvent()
    } else {
        woven_eventQueueBusy = 0
    }
    var focus = document.getElementById('woven_firstResponder')
    focus.focus()
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

    var oldNode = document.getElementById(theId)
    var newNode = document.createElement('span')
    newNode.innerHTML = htmlStr
    oldNode.parentNode.replaceChild(newNode.firstChild, oldNode)
    //woven_attemptFocus(newNode)
    woven_requestNextEvent()
    //alert('blah')
}

function woven_appendChild(theId, htmlStr) {
    woven_requestNextEvent()

    var container = document.getElementById(theId)
    var newNode = document.createElement('span')
    newNode.innerHTML = htmlStr
    container.appendChild(newNode.firstChild)
}
