from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, maybeDeferred, gatherResults
from twisted.internet.threads import deferToThread
from twisted.internet.task import LoopingCall, Clock
from twisted.cred.error import UnauthorizedLogin
from twisted.web.server import Request, Site, Session
from twisted.web.resource import Resource

from twisted.web.openidchecker import (OpenIDChecker, OpenIDCredentials,
                                       OpenIDCallbackHandler)

from openid.consumer.consumer import SUCCESS, Consumer
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


    def addSuccessfulIdentity(self, identity, provider):
        """
        Add an identity for which authentication will be successful.
        """
        self.identities[identity] = provider


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

    def __init__(self, consumerFactory, session, store):
        self.consumerFactory = consumerFactory
        self.session = session
        self.store = store


    def begin(self, openid):
        if openid in self.consumerFactory.brokenIdentities:
            1 / 0
        self.session["openid"] = openid
        return FakeAuthRequest(self.consumerFactory, openid)


    def complete(self, args, callbackURL):
        self.consumerFactory.completions.append((args, callbackURL))
        self.completePostData = args
        self.callbackURL = callbackURL
        openid = self.session["openid"]
        if openid in self.consumerFactory.identities:
            return Response(SUCCESS, self.session["openid"])



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
        consumer factory's C{addSuccessfulIdentity}.
        """
        self.consumerFactory.redirects.append((realm, callbackURL))
        return self.consumerFactory.identities[self.openid]



class Response(object):
    def __init__(self, status, identityURL):
        self.status = status
        self.identity_url = identityURL



class OpenIDCheckerTest(TestCase):
    def setUp(self):
        self.oidStore = MemoryStore()
        # Some handy sample data
        self.openID = "http://radix.example/"
        self.realm = "http://unittest.local/"
        self.returnURL = "http://unittest.local/return/"
        self.destination = "http://unittest.local/destination/"
        self.openIDProvider = "http//openid.provider/"


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
        L{openid.consumer.consumer.Consumer}, so that we actually authenticate
        for real.
        """
        checker = OpenIDChecker("foo", "bar", None)
        self.assertIdentical(checker._consumerFactory, Consumer)


    def test_success(self):
        request = DummyRequest()
        factory = FakeConsumerFactory(self.oidStore)
        factory.addSuccessfulIdentity(self.openID, self.openIDProvider)

        checker = OpenIDChecker(self.realm, self.returnURL, self.oidStore,
                                asynchronize=maybeDeferred,
                                consumerFactory=factory)
        credentials = OpenIDCredentials(request, self.openID, self.destination)
        result = checker.requestAvatarId(credentials)

        def pingBack(redirectedURL):
            """
            The redirect to the provider has been done. Simulate the user being
            redirected back.
            """
            # Did the checker pass the correct arguments to redirectURL?
            self.assertEquals(factory.redirects,
                              [(self.realm, self.returnURL)])
            # Did the checker redirect to the URL returned from redirectURL?
            self.assertEquals(redirectedURL, self.openIDProvider)

            # Now let's trigger the callback handler.
            responseRequest = DummyRequest()
            responseRequest.session = request.session
            responseRequest.args = {"WHAT": ["foo"]}
            resource = OpenIDCallbackHandler(
                self.oidStore, checker,
                consumerFactory=factory)
            resource.render_GET(responseRequest)
            # Did the callback handler pass reasonable arguments to complete?
            self.assertEquals(factory.completions, [({"WHAT": "foo"},
                                                     self.returnURL)])
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


    def test_openIDLookupError(self):
        """
        If an error occurs trying to find a user's OpenID provider,
        UnauthorizedLogin will be fired.
        """
        request = DummyRequest()
        factory = FakeConsumerFactory(self.oidStore)
        factory.addBrokenIdentity(self.openID)
        checker = OpenIDChecker(self.realm, self.returnURL, self.oidStore,
                                asynchronize=maybeDeferred,
                                consumerFactory=factory)
        credentials = OpenIDCredentials(request, self.openID, self.destination)

        result = checker.requestAvatarId(credentials)
        self.assertFailure(result, UnauthorizedLogin)
        result.addCallback(
            lambda ignored: self.flushLoggedErrors(ZeroDivisionError))
        return result

    # XXX Test timeouts
    # XXX Test a FailureResponse
    # XXX Test a CancelResponse
    # XXX Test a SetupNeededResponse
