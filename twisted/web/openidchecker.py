"""
OpenID support for twisted.web.

The Cred integration in this module assumes that the user's application is a
web application that uses twisted.web. It is strongly bound to twisted.web's
idea of a request.
"""

from zope.interface import Interface, implements, Attribute

from twisted.web.resource import Resource
from twisted.internet.threads import deferToThread
from twisted.internet.defer import Deferred
from twisted.python import log
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import ICredentials

from openid.consumer.consumer import Consumer, SUCCESS


class IOpenIDCredentials(ICredentials):
    """
    An object representing OpenID credentials.

    Some extra data is required in this object which isn't necessarily related
    to user authentication data, to deal with the very webby nature of OpenID.
    """
    request = Attribute(
        "A request. It must have a redirect method and a getSession method.")
    openID = Attribute("The user's OpenID")
    destinationURL = Attribute("""
        The URL that the user should ultimately be redirected to, assuming
        authentication succeeds.
        """)

class IOpenIDSessionTag(Interface):
    """
    An empty interface that will point to a dict object associated with a
    session.
    """

class IOpenIDSessionResultTag(Interface):
    """
    An empty interface that will point to a Deferred object.
    """


class OpenIDCredentials(object):
    """
    Basic, obvious implementation of L{IOpenIDCredentials}.
    """
    implements(IOpenIDCredentials)

    def __init__(self, request, openID, destinationURL):
        """
        @param request: The L{IOpenIDCredentials.session}
        @param openid: The L{IOpenIDCredentials.openID}
        @param destinationURL: The L{OpenIDCredentials.destinationURL}
        """
        self.request = request
        self.openID = openID


class OpenIDChecker(object):
    """A Cred Checker which is able to authenticate OpenID credentials.

    An important thing to note about using a Portal that is configured with
    OpenID as a checker is that you cannot rely on the Deferred returned from
    C{portal.login} to fire before the request is complete. Callers of
    C{portal.login} should forget about their web request after that point.
    """
    implements(ICredentialsChecker)

    # XXX This line is untested
    credentialInterfaces = [IOpenIDCredentials]

    def __init__(self, myURL, callbackURL, store, asynchronize=deferToThread):
        """
        @param myURL: The URL that this site is hosted at. This will be used to
            identify this site to the OpenID provider and end-user.
        @param callbackURL: A URL which should ultimately resolve to a
            L{OpenIDCallbackHandler} resource object. The provider will be
            directed to redirect the user to this URL in order to complete the
            authentication procedure.
        @param store: A python-openid Store. See L{openid.store}.
        @param asynchronize: A callable which takes a blocking function and
            argumenst and makes it magically non-blocking.
        """
        self._myURL = myURL
        self._callbackURL = callbackURL
        self._store = store
        self._asynchronize = asynchronize

    def requestAvatarId(self, credentials):
        """
        Kick off the OpenID authentication process.

        @type credentials: L{IOpenIDCredentials}
        """
        session = {}
        credentials.request.getSession().setComponent(IOpenIDSessionTag,
                                                      session)
        consumer = Consumer(session, self._store)

        def errorDuringBegin(failure):
            """
            An error occured during L{Consumer.begin}; log it and raise an
            UnauthorizedLogin.
            """
            log.err(failure, "Error looking up OpenID Provider for OpenID %r"
                    % (credentials.openID,))
            raise UnauthorizedLogin()

        def waitForCallback(ignored):
            """
            Return a Deferred which will fire when the user agent hits our
            callback URL with authentication data.

            The Deferred will fire with the OpenID.
            """
            avatarID = Deferred()
            credentials.request.getSession().setComponent(
                IOpenIDSessionResultTag, avatarID)
            return avatarID

        def redirect(authRequest):
            url = authRequest.redirectURL(self._myURL, self._callbackURL)
            credentials.request.redirect(url)
            # UNTESTED!
            credentials.request.finish()

        # XXX: Timeouts
        authRequest = self._asynchronize(consumer.begin, credentials.openID)
        authRequest.addCallback(redirect)
        authRequest.addErrback(errorDuringBegin)
        authRequest.addCallback(waitForCallback)
        return authRequest


class OpenIDCallbackHandler(Resource):
    """
    A resource which should be placed somewhere on your site to handle
    redirects from OpenID providers.

    The URL at which you place this resource should be passed to
    L{OpenIDChecker} as the C{callbackURL} argument.
    """
    def __init__(self, store, checker):
        Resource.__init__(self)
        self._store = store
        self._checker = checker

    def render_GET(self, request):
        """
        Complete the OpenID authentication procedure.

        This will fire the deferred returned from
        L{OpenIDChecker.requestAvatarId} with the OpenID or
        L{UnauthorizedLogin}.
        """
        args = {}
        for k, v in request.args.items():
            args[k] = v[0]
        sessionData = request.getSession(IOpenIDSessionTag)
        consumer = Consumer(sessionData, self._store)
        result = consumer.complete(args, self._checker._callbackURL)
        d = request.getSession(IOpenIDSessionResultTag)
        if result.status == SUCCESS:
            d.callback(result.identity_url)
        else:
            d.errback(UnauthorizedLogin())
        # XXX Untested
        
