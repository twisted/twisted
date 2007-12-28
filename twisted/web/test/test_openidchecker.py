from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, maybeDeferred, gatherResults
from twisted.internet.threads import deferToThread
from twisted.internet.task import LoopingCall, Clock
from twisted.cred.error import UnauthorizedLogin
from twisted.web.server import Request, Site, Session
from twisted.web.resource import Resource

from twisted.web.openidchecker import (OpenIDChecker, OpenIDCredentials,
                                       OpenIDCallbackHandler,
                                       IOpenIDSession,
                                       IRequestAvatarIDDeferred,
                                       IDestinationURL)

from openid.consumer.consumer import SUCCESS, FAILURE, Consumer
from openid.store.memstore import MemoryStore


class DummySession(Session):
    """
    A session that won't use the reactor for scheduling.

    The only reason this class exists is to avoid pending timed call errors in
    trial.
    """

    def loopFactory(self, interval):
        """
        Return a L{LoopingCall} that will run at C{interval}.

        The C{LoopingCall}'s clock will be set to its own L{Clock}.
        """
        call = LoopingCall(interval)
        call.clock = Clock()
        return call



class DummyRequest(Request):
    """
    A request which can be used for testing.

    @ivar redirectDeferred: A Deferred which will be fired back when this
        request is redirected.
    @ivar finishDeferred: '' '' '' '' '' '' '' '' '' '' '' finished.
    """

    def __init__(self):
        Request.__init__(self, None, True)
        self.redirectDeferred = Deferred()
        self.finishDeferred = Deferred()
        self.args = {}
        self.sitepath = []
        self.site = Site(Resource())
        self.site.sessionFactory = DummySession


    def redirect(self, url):
        self.redirectDeferred.callback(url)

    def finish(self):
        self.finishDeferred.callback(None)



class StoreMismatchError(Exception):
    """
    Raised when you haven't got your stores straight.
    """



class FakeConsumerFactory(object):
    """
    A configurable fake implementation of L{Consumer}'s interface.

    @ivar redirects: A list of two-tuples of realm and callback URL. This will
        be populated by calls to C{redirectURL} on the auth request.
    @ivar completions: A list of two-tuples of arguments and callback URL. This
        will be populated by calls to C{complete} on the consumer.
    """

    def __init__(self, store):
        """
        @param store: Only used for assertion purposes. The store passed to
            L{__call__} must be the same as this store.
        """
        self.identities = {}
        self.brokenIdentities = set()
        self.store = store
        self.redirects = []
        self.completions = []


    def addIdentity(self, identity, provider, status):
        """
        Add an identity for which authentication will be successful.
        """
        self.identities[identity] = (provider, status)


    def addBrokenIdentity(self, identity):
        """
        Add an identity for which looking up the provider will raise an
        exception.
        """
        self.brokenIdentities.add(identity)


    def __call__(self, session, store):
        """
        Instantiate and return a L{FakeConsumer} which will act in the
        configured way.

        If the passed store is not the same as the preconfigured one,
        L{StoreMismatchError} will be raised.
        """
        if store is not self.store:
            raise StoreMismatchError(
                "%r is not the same store as the configured %r"
                % (store, self.store))
        return FakeConsumer(self, session, store)



class FakeConsumer(object):
    """
    An object which looks a lot like L{Consumer}.
    """

    def __init__(self, consumerFactory, session, store):
        self.consumerFactory = consumerFactory
        self.session = session
        self.store = store


    def begin(self, openid):
        """
        - Set up session state so that L{complete} can be called later and
          return a L{FakeAuthRequest}, OR
        - raise a ZeroDivisionError if the specified C{openid} was configured
          for brokenness with L{FakeConsumerFactory.addBrokenIdentity}.
        """
        if openid in self.consumerFactory.brokenIdentities:
            1 / 0
        self.session["openid"] = openid
        return FakeAuthRequest(self.consumerFactory, openid)


    def complete(self, args, callbackURL):
        """
        Record arguments to the consumer factory's C{completions} list, and
        return a L{Response} with data appropriate for the way this openid was
        configured on the L{FakeConsumerFactory}.
        """
        self.consumerFactory.completions.append((args, callbackURL))
        openid = self.session["openid"]
        if openid in self.consumerFactory.identities:
            status = self.consumerFactory.identities[openid][1]
            return Response(status, self.session["openid"])



class FakeAuthRequest(object):
    """
    An L{AuthRequest}-like object.
    """

    def __init__(self, consumerFactory, openid):
        """
        @param consumerFactory: The L{FakeConsumerFactory} to record input URLs
            to.
        """
        self.consumerFactory = consumerFactory
        self.openid = openid


    def redirectURL(self, realm, callbackURL):
        """
        Record the arguments to the consumer factory's C{redirects} list, and
        return the provider URL that was associated with the identity with the
        consumer factory's C{addItentity}.
        """
        self.consumerFactory.redirects.append((realm, callbackURL))
        return self.consumerFactory.identities[self.openid][0]



class Response(object):
    """
    A thing that looks like an openid response.

    @ivar status: The status.
    @ivar identity_url: The identity URL.
    """
    def __init__(self, status, identityURL):
        self.status = status
        self.identity_url = identityURL



class OpenIDCheckerTest(TestCase):
    """
    Tests for L{twisted.web.openidchecker}.
    """
    def setUp(self):
        self.oidStore = MemoryStore()
        # Some handy sample data
        self.openID = "http://radix.example/"
        self.realm = "http://unittest.local/"
        self.returnURL = "http://unittest.local/return/"
        self.destination = "http://unittest.local/destination/"
        self.provider = "http//openid.provider/"
        self.factory = FakeConsumerFactory(self.oidStore)
        self.checker = OpenIDChecker(self.realm, self.returnURL, self.oidStore,
                                     asynchronize=maybeDeferred,
                                     consumerFactory=self.factory)


    def setupRequestForCallback(self, request):
        sessionData = {}
        avatarIDDeferred = Deferred()

        session = request.getSession()
        session.setComponent(IOpenIDSession, sessionData)
        session.setComponent(IRequestAvatarIDDeferred, avatarIDDeferred)
        session.setComponent(IDestinationURL, self.destination)

        # Do a begin() on our fake consumer to set up some data which the
        # complete() that OpenIDCallbackHandler does will need.
        self.factory(sessionData, self.oidStore).begin(self.openID)
        return avatarIDDeferred


    def test_defaultAsynchronize(self):
        """
        The default asynchronizer should be L{deferToThread}, so that
        authenticating with python-openid does not block the reactor.
        """
        checker = OpenIDChecker("foo", "bar", None)
        self.assertIdentical(checker._asynchronize, deferToThread)


    def test_defaultConsumerFactory(self):
        """
        The default consumer factory should be
        L{Consumer}, so that we actually authenticate
        for real.
        """
        checker = OpenIDChecker("foo", "bar", None)
        self.assertIdentical(checker._consumerFactory, Consumer)


    def test_success(self):
        """
        When requestAvatarId is called, it

        1. redirects the user to the openID provider based on interaction with
           the Consumer object
        2. returns a Deferred which will be fired when the user is redirected
           back to an L{OpenIDCallbackHandler},
        3. fire said deferred with the identity URL as the result, if the
           authentication was successful.

        This is the integration test between the L{OpenIDChecker} and
        L{OpenIDCallbackHandler}.
        """
        request = DummyRequest()
        self.factory.addIdentity(self.openID, self.provider, SUCCESS)

        credentials = OpenIDCredentials(request, self.openID, self.destination)
        result = self.checker.requestAvatarId(credentials)

        def pingBack(redirectedURL):
            """
            The redirect to the provider has been done. Simulate the user being
            redirected back.
            """
            # Did the checker pass the correct arguments to redirectURL?
            self.assertEquals(self.factory.redirects,
                              [(self.realm, self.returnURL)])
            # Did the checker redirect to the URL returned from redirectURL?
            self.assertEquals(redirectedURL, self.provider)

            # Now let's trigger the callback handler.
            responseRequest = DummyRequest()
            responseRequest.session = request.session
            responseRequest.args = {"WHAT": ["foo"]}
            resource = OpenIDCallbackHandler(self.oidStore, self.checker,
                                             consumerFactory=self.factory)
            resource.render_GET(responseRequest)
            # Did the callback handler pass reasonable arguments to complete?
            self.assertEquals(self.factory.completions,
                              [({"WHAT": "foo"}, self.returnURL)])
            # The callback handler should redirect the request to the
            # destination as specified by the credentials.
            return responseRequest.redirectDeferred.addCallback(
                self.assertEquals, self.destination)

        request.redirectDeferred.addCallback(pingBack)

        # The avatar ID is the OpenID.
        result.addCallback(self.assertEquals, self.openID)

        # The login() Defered must fire, the request must be redirected, and
        # the request must finish:
        return gatherResults([result,
                              request.redirectDeferred,
                              request.finishDeferred])

    def test_beginAuthentication(self):
        """
        When requestAvatarId is called, the user will be redirected to the
        OpenID provider and session data will be set up to allow the callback
        handler to later finish the authentication.
        """
        request = DummyRequest()
        self.factory.addIdentity(self.openID, self.provider, SUCCESS)

        credentials = OpenIDCredentials(request, self.openID, self.destination)
        result = self.checker.requestAvatarId(credentials)
        def redirected(result):
            self.assertEquals(result, self.provider)
            # The session data here comes from the fake consumer's begin().
            self.assertEquals(request.getSession(IOpenIDSession),
                              {"openid": self.openID})
            self.assertEquals(request.getSession(IDestinationURL),
                              self.destination)
            deferred = request.getSession(IRequestAvatarIDDeferred)
            self.assertTrue(isinstance(deferred, Deferred))

        request.redirectDeferred.addCallback(redirected)


    def test_callbackHandler(self):
        """
        When the callback handler is triggered, the Deferred which was returned
        from requestAvatarId (and placed in the session) will be fired and user
        will be redirected to the destination URL as specified by the
        credentials.
        """
        self.factory.addIdentity(self.openID, self.provider, SUCCESS)

        request = DummyRequest()
        request.args = {"WHAT": ["foo"]}

        avatarIDDeferred = self.setupRequestForCallback(request)

        resource = OpenIDCallbackHandler(self.oidStore, self.checker,
                                         consumerFactory=self.factory)
        resource.render_GET(request)

        # Did the callback handler pass reasonable arguments to complete?
        self.assertEquals(self.factory.completions,
                          [({"WHAT": "foo"}, self.returnURL)])

        # Did the callback handler fire the avatarId deferred with the identity
        # URL?
        avatarIDDeferred.addCallback(self.assertEquals, self.openID)

        # Did the callback handler redirect the user to the ultimate
        # destination?
        request.redirectDeferred.addCallback(self.assertEquals,
                                             self.destination)
        return gatherResults([avatarIDDeferred, request.redirectDeferred])


    def test_failedAuthentication(self):
        """
        If any result status other than SUCCESS is returned from the consumer
        library, the authentication should fail.
        """
        self.factory.addIdentity(self.openID, self.provider, FAILURE)
        request = DummyRequest()
        avatarIDDeferred = self.setupRequestForCallback(request)
        resource = OpenIDCallbackHandler(self.oidStore, self.checker,
                                         consumerFactory=self.factory)
        resource.render_GET(request)
        self.assertFailure(avatarIDDeferred, UnauthorizedLogin)
        return avatarIDDeferred


    def test_openIDLookupError(self):
        """
        If an error occurs trying to find a user's OpenID provider,
        UnauthorizedLogin will be fired.
        """
        request = DummyRequest()
        self.factory.addBrokenIdentity(self.openID)
        credentials = OpenIDCredentials(request, self.openID, self.destination)

        result = self.checker.requestAvatarId(credentials)
        self.assertFailure(result, UnauthorizedLogin)
        result.addCallback(
            lambda ignored: self.flushLoggedErrors(ZeroDivisionError))
        return result

    # XXX Test timeouts
