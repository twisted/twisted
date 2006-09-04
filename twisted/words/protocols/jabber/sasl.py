import base64
from twisted.internet import defer
from twisted.words.protocols.jabber import sasl_mechanisms, xmlstream
from twisted.words.xish import domish

NS_XMPP_SASL = 'urn:ietf:params:xml:ns:xmpp-sasl'


def get_mechanisms(xs):
    """
    Parse the SASL feature to extract the available mechanism names.
    """
    mechanisms = []
    for element in xs.features[(NS_XMPP_SASL, 'mechanisms')].elements():
        if element.name == 'mechanism':
            mechanisms.append(str(element))

    return mechanisms


class SASLError(Exception):
    """
    SASL base exception.
    """



class SASLNoAcceptableMechanism(SASLError):
    """
    The server did not present an acceptable SASL mechanism.
    """



class SASLAuthError(SASLError):
    """
    SASL Authentication failed.
    """
    def __init__(self, condition=None):
        self.condition = condition


    def __str__(self):
        return "SASLAuthError with condition %r" % self.condition



class SASLInitiatingInitializer(xmlstream.BaseFeatureInitiatingInitializer):
    """
    Stream initializer that performs SASL authentication.

    The supported mechanisms by this initializer are C{DIGEST-MD5} and C{PLAIN}
    which are attemped in that order.
    """
    feature = (NS_XMPP_SASL, 'mechanisms')
    _deferred = None

    def start(self):
        """
        Start SASL authentication exchange.

        Used the authenticator's C{jid} and C{password} attribute for the
        authentication credentials. If no supported SASL mechanisms are
        advertized by the receiving party, a failing deferred is returned with
        a L{SASLNoAcceptableMechanism} exception.
        """

        jid = self.xmlstream.authenticator.jid
        password = self.xmlstream.authenticator.password

        mechanisms = get_mechanisms(self.xmlstream)
        if 'DIGEST-MD5' in mechanisms:
            self.mechanism = sasl_mechanisms.DigestMD5('xmpp', jid.host, None,
                                                       jid.user, password)
        elif 'PLAIN' in mechanisms:
            self.mechanism = sasl_mechanisms.Plain(None, jid.user, password)
        else:
            return defer.fail(SASLNoAcceptableMechanism)

        self._deferred = defer.Deferred()
        self.xmlstream.addObserver('/challenge', self.onChallenge)
        self.xmlstream.addOnetimeObserver('/success', self.onSuccess)
        self.xmlstream.addOnetimeObserver('/failure', self.onFailure)
        self.sendAuth(self.mechanism.getInitialResponse())
        return self._deferred


    def sendAuth(self, data=None):
        """
        Initiate authentication protocol exchange.

        If an initial client response is given in C{data}, it will be
        sent along.

        @param data: initial client response.
        @type data: L{str} or L{None}.
        """
        auth = domish.Element((NS_XMPP_SASL, 'auth'))
        auth['mechanism'] = self.mechanism.name
        if data is not None:
            auth.addContent(base64.b64encode(data) or '=')
        self.xmlstream.send(auth)


    def sendResponse(self, data=''):
        """
        Send response to a challenge.

        @param data: client response.
        @type data: L{str}.
        """
        response = domish.Element((NS_XMPP_SASL, 'response'))
        if data:
            response.addContent(base64.b64encode(data))
        self.xmlstream.send(response)


    def onChallenge(self, element):
        """
        Parse challenge and send response from the mechanism.

        @param element: the challenge protocol element.
        @type element: L{domish.Element}.
        """
        challenge = base64.b64decode(str(element))
        self.sendResponse(self.mechanism.getResponse(challenge))


    def onSuccess(self, success):
        """
        Clean up observers, reset the XML stream and send a new header.

        @param success: the success protocol element. For now unused, but
                        could hold additional data.
        @type success: L{domish.Element}
        """
        self.xmlstream.removeObserver('/challenge', self.onChallenge)
        self.xmlstream.removeObserver('/failure', self.onFailure)
        self.xmlstream.reset()
        self.xmlstream.sendHeader()
        self._deferred.callback(xmlstream.Reset)


    def onFailure(self, failure):
        """
        Clean up observers, parse the failure and errback the deferred.

        @param failure: the failure protocol element. Holds details on
                        the error condition.
        @type failure: L{domish.Element}
        """
        self.xmlstream.removeObserver('/challenge', self.onChallenge)
        self.xmlstream.removeObserver('/success', self.onSuccess)
        try:
            condition = failure.firstChildElement().name
        except AttributeError:
            condition = None
        self._deferred.errback(SASLAuthError(condition))
