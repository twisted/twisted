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
    //var focus = document.getElementById('woven_firstResponder')
    //focus.focus()
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
    oldNode.outerHTML = htmlStr
    var newNode = document.getElementById(theId)
    woven_attemptFocus(newNode)
}
