"THIS DOESN'T WORK"

from twisted.web import microdom, domhelpers

class BadStream(Exception):
     pass

class XMLStream(microdom.MicroDOMParser):

    first = 1

    # if we get an exception in dataReceived we must send tag end before
    # losing connection

    def connectionMade(self):
        microdom.MicroDOMParser.connectionMade(self)
        self.transport.write("<stream:stream>")

    def loseConnection(self):
        self.transport.write("</stream:stream>")
        self.transport.loseConnection()

    def gotTagStart(self, name, attributes):
        if self.first:
            if name != "stream:stream":
                raise BadStream()
            self.first = 0
        else:
            microdom.MicroDOMParser.gotTagStart(self, name, attributes)

    def gotTagEnd(self, name):
        if not self.elementstack and name=="stream:stream":
            self.transport.loseConnection()
            return
        microdom.MicroDOMParser.gotTagEnd(self, name)
        if self.documents:
            self.gotElement(self.documents[0])
            self.documents.pop()

    def gotElement(self, element):
        raise NotImplementedError("what to do with element")

    def writeElement(self, element):
        element.writexml(self)

class JabberBasic(XMLStream):

    def gotElement(self, element):
        elementName = element.tagName
        m = getattr(self, "gotElement_"+elementName, self.gotUnknownElement)
        m(element)

    def gotUnknownElement(self, element):
        pass # degrade gracefully

def _getElementNamedOrNone(self, element, name):
    return (microdom.getElementsByTagName(element, name) or [None])[0]

class JabberCoreMixin:

    def gotElement_message(self, message):
        type = message.attributes.get('type')
        if type:
            m = getattr(self, "gotMessage_"+type, self.gotMessageUnknown)
        else:
            m = self.gotMessageUnknown
        m(message, type)

    def gotMessage_error(self, message, type):
        error = _getElementNamedOrNone(message, 'error')
        from_ = message.attributes.get('from')
        to = message.attributes.get('to')
        code = error.attributes['code']
        text = domhelpers.getNodeText(error)
        self.gotMessageError(code, text, from_, to)

    def gotMessageUnknown(self, message, type):
        body = _getElementNamedOrNone(message, 'body')
        subject = _getElementNamedOrNone(message, 'subject')
        from_ = message.attributes.get('from')
        to = message.attributes.get('to')
        id = message.attributes.get('id')
        thread = _getElementNamedOrNone(message, 'thread')
        self.gotMessageDefault(type, from, to, subject, body, id, thread)

    def gotElement_presence(self, element):
        type = message.attributes.get('type')
        if type:
            m = getattr(self, "gotPresence_"+type, self.gotPresence_available)
        else:
            m = self.gotPresence_available
        m(message, type)

    def gotPresence_error(self, element, type):
        error = _getElementNamedOrNone(message, 'error')
        from_ = message.attributes.get('from')
        to = message.attributes.get('to')
        code = error.attributes['code']
        text = domhelpers.getNodeText(error)
        self.gotPresenceError(code, text, from_, to)

    def gotPresence_available(self, element, type):
        pass # graceful degradation

    def gotPresence_unavailable(self, element, type):
        pass # implement

    def gotPresence_unavailable(self, element, type):
        pass # implement

"""
The Presence Element

   The <presence/> is used to express an entity's current availability
   status (offline or online, along with various sub-states of the
   latter) and communicate that status to other entities. It is also used
   to negotiate and manage subscriptions to the presence of other
   entities.

   A presence chunk MAY possess the following attributes:
     * to - Specifies the intended recipient of the presence chunk (if
       any).
     * from - Specifies the sender of the presence chunk.
     * id - A unique identifier for the purpose of tracking presence. The
       sender of the presence chunk sets this attribute, which may be
       returned in any replies.
     * type - Describes the availability state, subscription request,
       presence request, or error. No 'type' attribute, or inclusion of a
       type not specified here, implies that the resource is available.
       The type SHOULD be one of the following:
          + unavailable - Signals that the entity is no longer available
            for communication.
          + subscribe - The sender wishes to subscribe to the recipient's
            presence.
          + subscribed - The sender has allowed the recipient to receive
            their presence.
          + unsubscribe - A notification that an entity is unsubscribing
            from another entity's presence.
          + unsubscribed - The subscription request has been denied or a
            previously-granted subscription has been cancelled.
          + probe - A request for an entity's current presence.
          + error - An error has occurred regarding processing or
            delivery of a previously-sent presence chunk.

   A presence chunk may contain zero or one of each of the following
   child elements:
     * show - Describes the availability status of an entity or specific
       resource. The value SHOULD be one of the following (values other
       than these four are typically ignored; additional availability
       types could be defined through a properly-namespaced element of
       the presence chunk):
          + away - Entity or resource is temporarily away.
          + chat - Entity or resource is free to chat.
          + xa - Entity or resource is away for an extended period (xa =
            "eXtended Away").
          + dnd - Entity or resource is busy (dnd = "Do Not Disturb").
     * status - An optional natural-language description of availability
       status. Normally used in conjunction with the show element to
       provide a detailed description of an availability state (e.g., "In
       a meeting").
     * priority - A non-negative integer representing the priority level
       of the connected resource, with zero as the lowest priority.
     * error - If the presence is of type="error", the <presence/> chunk
       MUST include an <error/> child, which in turn MUST have a 'code'
       attribute corresponding to one of the standard error codes and MAY
       also contain PCDATA corresponding to a natural-language
       description of the error.

   A presence chunk MAY also contain any properly-namespaced child
   element (other than the common data elements, stream elements, or
   defined children thereof).

The IQ Element

   Info/Query, or IQ, is a simple request-response mechanism. Just as
   HTTP is a request-response medium, the iq element enables an entity to
   make a request of, and receive a response from, another entity. The
   data content of the request and response is defined by the namespace
   declaration of a direct child element of the iq element.

   Most IQ interactions follow a common pattern of structured data
   exchange such as get/result or set/result:

Requesting               Responding
  Entity                   Entity
----------               ----------
    |                        |
    |    <iq type="get">     |
    | ---------------------> |
    |                        |
    |   <iq type="result">   |
    | <--------------------- |
    |                        |
    |    <iq type="set">     |
    | ---------------------> |
    |                        |
    |   <iq type="result">   |
    | <--------------------- |
    |                        |



   An IQ chunk MAY possess the following attributes:
     * to - Specifies the intended recipient of the IQ chunk.
     * from - Specifies the sender of the IQ chunk.
     * id - An optional unique identifier for the purpose of tracking the
       request-response interaction. The sender of the IQ chunk sets this
       attribute, which may be returned in any replies.
     * type - The required 'type' attribute specifies a distinct step
       within a request-response interaction. The value SHOULD be one of
       the following (all other values are ignored):
          + get - The chunk is a request for information.
          + set - The chunk contains data intended to provide required
            data, set new values, or replace existing values.
          + result - The chunk is a response to a successful get or set
            request.
          + error - An error has occurred regarding processing or
            delivery of a previously-sent get or set.

   In the strictest terms, the iq element contains no children since it
   is a vessel for XML in another namespace. An IQ chunk MAY contain any
   properly-namespaced child element (other than the common data
   elements, stream elements, or defined children thereof).

   If the IQ is of type="error", the <iq/> chunk MUST include an <error/>
   child, which in turn MUST have a 'code' attribute corresponding to one
   of the standard error codes and MAY also contain PCDATA corresponding
   to a natural-language description of the error.
"""

    def gotMessageError(self, code, text, from_, to):
        raise NotImplementedError

    def gotPresenceError(self, code, text, from_, to):
        raise NotImplementedError

    def gotMessageDefault(self, type, from_, to, subject, body, id, thread):
        raise NotImplementedError

