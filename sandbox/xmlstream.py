"THIS DOESN'T WORK"
from __future__ import nested_scopes

import cgi
from twisted.web import microdom, domhelpers
from twisted.python import reflect
from twisted import copyright
from twisted.internet import defer


class BadStream(Exception):
     pass


class ElementWithText(microdom.Element):                                        
    def __init__(self, tagName, text, attributes=None, parentNode=None,
                 filename=None, markpos=None):
        microdom.Element.__init__(self, tagName, attributes, parentNode,
                                  filename, markpos)                            
        self.text = microdom.Text(text)
        self.appendChild(self.text)


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

    def connectionMade(self):
        XMLStream.connectionMade(self)

    def gotGlobalAttributes(self, attributes):
        self.gotGlobalFrom(attributes.get('from'))
        self.gotGlobalID(attributes.get('id'))
        self.gotGlobalTo(attributes.get('to'))
        # Only notify of the connection after the stream-level connection
        # started
        methods = reflect.prefixedMethods(self, 'notifyConnectionMade_')
        for m in methods:
            m()

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
        #print "got global id"
        self.id = id

    def gotGlobalTo(self, to):
        pass # usually we don't care

    # probably wanna override this for servers
    def getGlobalAttributes(self):
        return {'to': self.getGlobalTo()}

    def getGlobalTo(self):
        return ''


def _getElementNamedOrNone(element, name):
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
        self.gotMessageDefault(type, from_, to, id, subject, body, thread)

    def gotMessageError(self, from_, to, id, code, text):
        raise NotImplementedError

    def gotMessageDefault(self, type, from_, to, id, subject, body, thread):
        raise NotImplementedError

    def sendM(self, to_, subject, thread, body):
        id = str(self.lastID)
        self.lastID += 1
        deferred = defer.Deferred()
        query = microdom.Element("message", { "to": to })
	if subject_:
	    subject = ElementWithText("subject", subject)
	    query.appendChild(subject)
	if thread_:
	    thread = ElementWithText("thread", thread)
	    query.appendChild(thread)
	body = ElementWithText("body", body)
	query.appendChild(body)
        query.writexml(self.transport)
        self.requests[id] = deferred
        return id, deferred


class JabberPresenceMixin:

    def sendP(self, type, ashow, astatus):
        id = str(self.lastID)
        self.lastID += 1
        deferred = defer.Deferred()
        query = microdom.Element("presence", { "type": type, "id": id })
        show = ElementWithText("show", ashow)
        status = ElementWithText("status", astatus)
        priority = ElementWithText("priority", "5")
        query.appendChild(show)
        query.appendChild(status)
        query.appendChild(priority)  
        query.writexml(self.transport)
        self.requests[id] = deferred
        return id, deferred

    def gotElement_presence(self, element):
        message=element
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


class IQFailure(Exception):
    pass


class JabberIQMixin:

    def notifyConnectionMade_IQ(self):
        self.lastID = 0
        self.requests = {}

    def sendIQ(self, type, from_, to, query):
        id = str(self.lastID)
        self.lastID += 1
        deferred = defer.Deferred()
        attributes = []
        for k, v in [('from', from_), ('to', to), ('type', type), ('id', id)]:
            if v:
                attributes.append('%s="%s"' % (k, v))
        attributes = " ".join(attributes)
        self.transport.write("<iq %s>" % attributes)
        query.writexml(self.transport)
        self.transport.write('</iq>')
        self.requests[id] = deferred
        return id, deferred

    def gotElement_iq(self, element):
        type = element.attributes['type']
        id = element.attributes.get('id')
        from_ = element.attributes.get('from')
        to = element.attributes.get('to')
        message=element
        if type == 'result' or type == 'error':
            if not self.requests.has_key(id):
                return # ignore results for cancelled/non-existing requests
            if type == 'result':
                query = _getElementNamedOrNone(message, 'query')
                self.requests[id].callback(query)
            else:
                error = _getElementNamedOrNone(message, 'error')
                code = error.attributes['code']
                text = domhelpers.getNodeText(error)
                self.requests[id].errback(IQFailure(code, text))
            del self.requests[id]
        elif type == 'get' or type == 'set': # a remote method call!
             query = _getElementNamedOrNone(message, 'query')
             ns = query.attributes['xmlns']
             d = self.methodCalled(type, ns, id, from_, to, query)
             def _(query):
                 myTo, myFrom = from_, to
                 e = microdom.Element('iq', {'id': id, 'from': to,
                                             'to': from_, type: 'error'})
                 e.appendChild(query)
                 self.writeElement(e)
             d.addCallback(_)
             def _(failure):
                 failure.trap(IQFailure)
                 code, text = failure.value
                 myTo, myFrom = from_, to
                 e = microdom.Element('iq', {'id': id, 'from': to,
                                             'to': from_, type: 'result'})
                 error = microdom.Element('error', {'code': code})
                 error.appendChild(microdom.Text(cgi.escape(text)))
                 e.appendChild(error)
                 self.writeElement(e)
             d.addErrback(_)

    def methodCalled(self, type, ns, from_, to, id, query):
        if ns.startswith("http://"):
            return self.methodCalledURL(type, ns, from_, to, id, query)
        else:
            n = ns.replace(":", "_")
            m = getattr(self, "methodCalled_"+n, self.methodCalledUnknown)
            return m(type, ns, from_, to, id, query)

    def methodCalledUnknown(self, type, ns, from_, to, id, query):
        return defer.fail(IQFailure(502, "I am a silly monkey"))

    methodCalledURL = methodCalledUnknown


class JabberIQAdMixin:

    "Free advertisement is fun"

    def methodCalled_jabber_iq_version(self, type, ns, from_, to, id, query):
        e = microdom.Element(query, {'xmlns': ns})
        name = microdom.Element('name')
        name.appendChild(microdom.Text("TwistedJabber"))
        e.appendChild(name)
        version = microdom.Element('version')
        version.appendChild(microdom.Text(copyright.version))
        e.appendChild(version)
        return defer.succeed(e)


class JabberIQLoggingInMixin(JabberIQMixin):

    def notifyConnectionMade_IQ(self):
        JabberIQMixin.notifyConnectionMade_IQ(self)
        query = microdom.Element('query', {'xmlns':"jabber:iq:auth"})
        username = microdom.Element('username')
        username.appendChild(microdom.Text(cgi.escape(self.getUsername())))
        digest = microdom.Element('digest')
        digest.appendChild(microdom.Text(cgi.escape(self.getDigest())))
        resource = microdom.Element('resource')
        resource.appendChild(microdom.Text(cgi.escape(self.getResource())))
	query.appendChild(username)
	query.appendChild(digest)
	query.appendChild(resource)
        self.sendIQ(type='set', from_=None, to=None,
                    query=query)[1].addCallbacks(
            self.loginSuccess,
            self.loginFailure
        )

    def getDigest(self):
        import sha
        return sha.new(self.id+self.getPassword()).hexdigest()

    def getResource(self):
        return ''

    def getUsername(self):
        raise NotImplementedError

    def getPassword(self):
        raise NotImplementedError

    def loginSuccess(self, arg):
        raise NotImplementedError

    def loginFailure(self, arg):
        raise NotImplementedError


class JabberCoreMixin(JabberMessageMixin, JabberPresenceMixin, JabberIQMixin):
    pass

class JabberCoreClientMixin(JabberMessageMixin, JabberPresenceMixin,
                            JabberIQLoggingInMixin, JabberIQAdMixin):
    pass
