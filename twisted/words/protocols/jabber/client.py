# -*- test-case-name: twisted.words.test.test_jabbercomponent -*-
#
# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.xish import domish, xpath, utility, xmlstream

DigestAuthQry = xpath.internQuery("/iq/query/digest")
PlaintextAuthQry = xpath.internQuery("/iq/query/password")

def basicClientFactory(jid, secret):
    a = BasicAuthenticator(jid, secret)
    return xmlstream.XmlStreamFactory(a)

class IQ(domish.Element):
    """ Wrapper for a Info/Query packet

    This provides the necessary functionality to send IQs and get notified when
    a result comes back. It's a subclass from L{domish.Element}, so you can use
    the standard DOM manipulation calls to add data to the outbound request.

    @type callbacks: L{utility.CallbackList}
    @cvar callbacks: Callback list to be notified when response comes back
    
    """    
    def __init__(self, xmlstream, type = "set"):
        """
        @type xmlstream: L{xmlstream.XmlStream}
        @param xmlstream: XmlStream to use for transmission of this IQ

        @type type: L{str}
        @param type: IQ type identifier ('get' or 'set')

        """
        domish.Element.__init__(self, ("jabber:client", "iq"))
        self.addUniqueId()
        self["type"] = type
        self._xmlstream = xmlstream
        self.callbacks = utility.CallbackList()

    def addCallback(self, fn, *args, **kwargs):
        """
        Register a callback for notification when the IQ result
        is available.

        """
        self.callbacks.addCallback(True, fn, *args, **kwargs)

    def send(self, to = None):
        """
        Call this method to send this IQ request via the associated XmlStream

        @param to: Jabber ID of the entity to send the request to
        @type to: L{str}

        @returns: Callback list for this IQ. Any callbacks added to this list
                  will be fired when the result comes back.
        """
        if to != None:
            self["to"] = to
        self._xmlstream.addOnetimeObserver("/iq[@id='%s']" % self["id"], \
                                                             self._resultEvent)
        self._xmlstream.send(self)

    def _resultEvent(self, iq):
        self.callbacks.callback(iq)
        self.callbacks = None

class BasicAuthenticator(xmlstream.ConnectAuthenticator):
    """ Authenticates an XmlStream against a Jabber server as a Client

    This only implements non-SASL authentication, per
    U{JEP-0078<http://www.jabber.org/jeps/jep-0078.html>}. Additionally, this
    authenticator provides the ability to perform inline registration, per
    U{JEP-0077<http://www.jabber.org/jeps/jep-0077.html>}.

    Under normal circumstances, the BasicAuthenticator generates the
    L{xmlstream.STREAM_AUTHD_EVENT} once the stream has authenticated. However,
    it can also generate other events, such as:
      - L{INVALID_USER_EVENT} : Authentication failed, due to invalid username
      - L{AUTH_FAILED_EVENT} : Authentication failed, due to invalid password
      - L{REGISTER_FAILED_EVENT} : Registration failed

    If authentication fails for any reason, you can attempt to register by
    calling the L{registerAccount} method. If the registration succeeds, a
    L{xmlstream.STREAM_AUTHD_EVENT} will be fired. Otherwise, one of the above
    errors will be generated (again).
    
    """
    namespace = "jabber:client"

    INVALID_USER_EVENT    = "//event/client/basicauth/invaliduser"
    AUTH_FAILED_EVENT     = "//event/client/basicauth/authfailed"
    REGISTER_FAILED_EVENT = "//event/client/basicauth/registerfailed"

    def __init__(self, jid, password):
        xmlstream.ConnectAuthenticator.__init__(self, jid.host)
        self.jid = jid
        self.password = password

    def streamStarted(self, rootelem):
        # Send request for auth fields
        iq = IQ(self.xmlstream, "get")
        iq.addElement(("jabber:iq:auth", "query"))
        iq.query.addElement("username", content = self.jid.user)
        iq.addCallback(self._authQueryResultEvent)
        iq.send()

    def _authQueryResultEvent(self, iq):
        if iq["type"] == "result":
            # Construct auth request
            reply = IQ(self.xmlstream, "set")
            reply.addElement(("jabber:iq:auth", "query"))
            reply.query.addElement("username", content = self.jid.user)
            reply.query.addElement("resource", content = self.jid.resource)
        
            # Prefer digest over plaintext
            if DigestAuthQry.matches(iq):
                digest = xmlstream.hashPassword(self.xmlstream.sid,
                                                self.password)
                reply.query.addElement("digest", content = digest)
            else:
                reply.query.addElement("password", content = self.password)

            reply.addCallback(self._authResultEvent)
            reply.send()
        else:
            # Check for 401 -- Invalid user
            if iq.error["code"] == "401":
                self.xmlstream.dispatch(iq, self.INVALID_USER_EVENT)
            else:
                self.xmlstream.dispatch(iq, self.AUTH_FAILED_EVENT)

    def _authResultEvent(self, iq):
        if iq["type"] == "result":
            self.xmlstream.dispatch(self.xmlstream,
                                    xmlstream.STREAM_AUTHD_EVENT)
        else:
            self.xmlstream.dispatch(iq, self.AUTH_FAILED_EVENT)

    def registerAccount(self, username = None, password = None):
        if username:
            self.jid.user = username
        if password:
            self.password = password
            
        iq = IQ(self.xmlstream, "set")
        iq.addElement(("jabber:iq:register", "query"))
        iq.query.addElement("username", content = self.jid.user)
        iq.query.addElement("password", content = self.password)

        iq.addCallback(self._registerResultEvent)

        iq.send()

    def _registerResultEvent(self, iq):
        if iq["type"] == "result":
            # Registration succeeded -- go ahead and auth
            self.streamStarted(None)
        else:
            # Registration failed
            self.xmlstream.dispatch(iq, self.REGISTER_FAILED_EVENT)
            
