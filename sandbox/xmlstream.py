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
        attributes = ' '.join(['%s="%s"' % (k, v) for (k, v) in 
                                         self.getGlobalAttributes().items()])
        self.transport.write("<stream:stream %s>" % attributes)

    def loseConnection(self):
        self.transport.write("</stream:stream>")
        self.transport.loseConnection()

    def gotTagStart(self, name, attributes):
        if self.first:
            if name != "stream:stream":
                raise BadStream()
            self.first = 0
            self.gotGlobalAttributes(attributes)
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


def parseJID(jid):
    resource = jid.rfind('/')
    if resource != -1:
        jid, resource = jid[:resource], jid[resource+1:]
    else:
        resource = None
    user = jid.find('@')
    if user != -1:
        user, jid = jid[:user], jid[user+1:]
    else:
        user = None
    return user, jid, resource

def makeJID(user, host, resource):
    if user is not None:
        jid = user+'@'+host
    else:
        jid = host
    if resource is not None:
        jid += '/'+resource
    return jid
    

class JabberBasic(XMLStream):

    def gotGlobalAttributes(self, attributes):
        self.gotGlobalFrom(attributes.get('from'))
        self.gotGlobalID(attributes.get('id'))
        self.gotGlobalTo(attributes.get('to'))

    def gotElement(self, element):
        elementName = element.tagName.replace(':', '_')
        m = getattr(self, "gotElement_"+elementName, self.gotUnknownElement)
        m(element)

    def gotElement_stream_error(self, element):
        self.loseConnection()

    def gotUnknownElement(self, element):
        pass # degrade gracefully

    def gotGlobalFrom(self, from_):
        pass # usually we don't care

    def gotGlobalID(self, id):
        self.id = id

    def gotGlobalTo(self, to):
        pass # usually we don't care

    # probably wanna override this for servers
    def getGlobalAttributes(self):
        return {'to': self.getGlobalTo(self)}

    def getGlobalTo(self):
        return ''


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
        id = element.attributes.get('id')
        from_ = element.attributes.get('from')
        to = element.attributes.get('to')
        if type == 'error':
            error = _getElementNamedOrNone(message, 'error')
            code = error.attributes['code']
            text = domhelpers.getNodeText(error)
            return self.gotIQError(type, from_, to, id, code, text)
        query = _getElementNamedOrNone(message, 'query')
        if query is None: # technically, there could be those.
            return
        ns = query.attributes['xmlns']
        pns = type+'_'+ns.replace(':', '_').replace('/', '_')
        m = getattr(self, 'gotIQ_'+pns, self.gotIQUnknown)
        m(type, ns, id, from_, to, query)
         
    def gotIQUnknown(self, type, ns, from_, to, id, query):
        return # ignore unknown IQs by default

    def gotIQError(self, from_, to, id, code, text):
        raise NotImplementedError


class JabberCoreMixin(JabberMessageMixin, JabberPresenceMixin, JabberIQMixin):
    pass
