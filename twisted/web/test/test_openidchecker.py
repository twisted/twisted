from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, maybeDeferred, gatherResults
from twisted.internet.threads import deferToThread
from twisted.internet.task import LoopingCall, Clock
from twisted.cred.error import UnauthorizedLogin
from twisted.web.server import Request, Site, Session
from twisted.web.resource import Resource

from twisted.web.openidchecker import (OpenIDChecker, OpenIDCredentials,
                                       OpenIDCallbackHandler, IOpenIDSessionTag)

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
    """

    def __init__(self):
        Request.__init__(self, None, True)
        self.redirectDeferred = Deferred()
        self.sitepath = []
        self.site = Site(Resource())
        self.site.sessionFactory = DummySession


    def redirect(self, url):
        self.redirectDeferred.callback(url)



class FakeConsumer(object):

    def __init__(self, session, store):
        self.session = session
        self.store = store

    def begin(self, openid):
        self.session["openid"] = openid
        return FakeAuthRequest()

    def complete(self, args, callbackURL):
        self.completePostData = args
        self.callbackURL = callbackURL
        return Response(SUCCESS, self.session["openid"])



class BrokenBeginConsumer(FakeConsumer):
    def begin(self, openid):
        1 / 0



class FakeAuthRequest(object):
    def redirectURL(self, myURL, callbackURL):
        self.myURL = myURL
        self.callbackURL = callbackURL
        return "URL"



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
        self.openIDProviderURL = "http://unittest.provider/"

#     def mockConsumer(self, sessionData, openID, realm, returnURL,
#                      openIDProviderURL, completeArgument, completeResult):
#         consumerFactory = self.mocker.replace(
#             "openid.consumer.consumer.Consumer", passthrough=False)
#         consumerMock = consumerFactory(ANY, self.oidStore)

#         authRequest = consumerMock.begin(openID)
#         authRequest.redirectURL(realm, returnURL)
#         self.mocker.result(openIDProviderURL)

#         secondConsumer = consumerFactory(ANY, self.oidStore)
#         secondConsumer.complete(completeArgument, returnURL)
#         self.mocker.result(completeResult)

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


#         self.mockConsumer({}, self.openID, self.realm,
#                           self.returnURL, self.openIDProviderURL,
#                           {"WHAT": "foo"}, completeResult)
#         self.mocker.replay()

        checker = OpenIDChecker(self.realm, self.returnURL, self.oidStore,
                                asynchronize=maybeDeferred,
                                consumerFactory=FakeConsumer)
        credentials = OpenIDCredentials(request, self.openID, self.destination)
        result = checker.requestAvatarId(credentials)

        def pingBack(providerURL):
            self.assertEquals(providerURL, "URL")
            responseRequest = DummyRequest()
            responseRequest.session = request.session
            responseRequest.args = {"WHAT": ["foo"]}
            resource = OpenIDCallbackHandler(
                self.oidStore, checker,
                consumerFactory=FakeConsumer)
            resource.render_GET(responseRequest)

        request.redirectDeferred.addCallback(pingBack)
        result.addCallback(self.assertEquals, self.openID)
        return gatherResults([result, request.redirectDeferred])

    def test_openIDLookupError(self):
        """
        If an error occurs trying to find a user's OpenID provider,
        UnauthorizedLogin will be fired.
        """
        request = DummyRequest()
        checker = OpenIDChecker(self.realm, self.returnURL, self.oidStore,
                                asynchronize=maybeDeferred,
                                consumerFactory=BrokenBeginConsumer)
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
