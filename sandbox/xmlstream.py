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


class JabberMessageMixin:

    def gotElement_message(self, message):
        type = message.attributes.get('type')
        from_ = message.attributes.get('from')
        to = message.attributes.get('to')
        id = message.attributes.get('id')
        if type:
            m = getattr(self, "gotMessage_"+type, self.gotMessageUnknown)
        else:
            m = self.gotMessageUnknown
        m(type, from_, to, id, message)

    def gotMessage_error(self, type, from_, to, id, message):
        error = _getElementNamedOrNone(message, 'error')
        code = error.attributes['code']
        text = domhelpers.getNodeText(error)
        self.gotMessageError(from_, to, id, code, text)

    def gotMessageUnknown(self, type, from_, to, id, message):
        body = _getElementNamedOrNone(message, 'body')
        subject = _getElementNamedOrNone(message, 'subject')
        thread = _getElementNamedOrNone(message, 'thread')
        self.gotMessageDefault(type, from, to, id, subject, body, thread)

    def gotMessageError(self, from_, to, id, code, text):
        raise NotImplementedError

    def gotMessageDefault(self, type, from_, to, id, subject, body, thread):
        raise NotImplementedError


class JabberPresenceMixin:

    def gotElement_presence(self, element):
        type = message.attributes.get('type')
        from_ = message.attributes.get('from')
        to = message.attributes.get('to')
        id = message.attributes.get('id')
        if type:
            m = getattr(self, "gotPresence_"+type, self.gotPresence_available)
        else:
            m = self.gotPresence_available
        m(type, from_, to, id, message)

    def gotPresence_error(self, type, from_, to, id, message):
        error = _getElementNamedOrNone(message, 'error')
        code = error.attributes['code']
        text = domhelpers.getNodeText(error)
        self.gotPresenceError(from_, to, id, code, text)

    def gotPresence_available(self, type, from_, to, id, message):
        show = _getElementNamedOrNone(message, 'show')
        status = _getElementNamedOrNone(message, 'status')
        priority = _getElementNamedOrNone(message, 'priority')
        return self.gotPresenceNotification(from_, to, id, show, status,
                                            priority)

    def gotPresenceError(self, from_, to, id, code, text):
        raise NotImplementedError

    def gotPresenceNotification(self, from_, to, id, show, status, priority):
        raise NotImplementedError

    def gotPresence_unavailable(self, type, from_, to, id, message):
        pass # implement

    def gotPresence_subscribe(self, type, from_, to, id, message):
        pass # implement

    def gotPresence_subscribed(self, type, from_, to, id, message):
        pass # implement

    def gotPresence_probe(self, type, from_, to, id, message):
        pass # implement


class JabberIQMixin:

    def gotElement_iq(self, element):
        type = element.attributes['type']
        m = getattr(self, 'gotIQ_'+type, None)
        if not m:
            return # unrecognized types must be ignored as per spec
        id = element.attributes.get('id')
        from_ = element.attributes.get('from')
        to = element.attributes.get('to')
        m(type, from_, to, id, element)

    def gotIQ_error(self, type, from_, to, id, element):
        error = _getElementNamedOrNone(message, 'error')
        code = error.attributes['code']
        text = domhelpers.getNodeText(error)
        self.gotIQError(from_, to, id, code, text)

    def gotIQ_get(self, type, from_, to, id, element):
        pass # implemented in implementation-dependent manner

    def gotIQ_set(self, type, from_, to, id, element):
        pass # implemented in implementation-dependent manner

    def gotIQ_result(self, type, from_, to, id, element):
        pass # implemented in implementation-dependent manner

    def gotIQError(self, from_, to, id, code, text):
        raise NotImplementedError


class JabberCoreMixin(JabberMessageMixin, JabberPresenceMixin, JabberIQMixin):
    pass

