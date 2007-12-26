from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, maybeDeferred, gatherResults
from twisted.internet.task import LoopingCall, Clock
from twisted.cred.error import UnauthorizedLogin
from twisted.web.server import Request, Site, Session
from twisted.web.resource import Resource

from mocker import MockerTestCase, ARGS, KWARGS, ANY
from twisted.web.openidchecker import (OpenIDChecker, OpenIDCredentials,
                                       OpenIDCallbackHandler, IOpenIDSessionTag)

from openid.consumer.consumer import SUCCESS
from openid.store.memstore import MemoryStore


def replaceFunction(mocker, originalName, replacement):
    """
    Given the FQPN of the original function, replace it with C{replacement}.

    @param mocker: The mocker
    @param originalName: The name of the original function, like
        C{twisted.internet.threads.deferToThread}.
    @param replacement: The function to replace it with.
    """
    originalMock = mocker.replace(originalName, passthrough=False)
    originalMock(ARGS, KWARGS)
    mocker.call(replacement)
    mocker.count(0, None) # allow any number of calls to the function



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



class OpenIDCheckerTest(MockerTestCase, TestCase):
    def setUp(self):
        self.oidStore = MemoryStore()
        replaceFunction(self.mocker,
                        "twisted.internet.threads.deferToThread", maybeDeferred)
        # Some handy sample data
        self.openID = "http://radix.example/"
        self.realm = "http://unittest.local/"
        self.returnURL = "http://unittest.local/return/"
        self.destination = "http://unittest.local/destination/"
        self.openIDProviderURL = "http://unittest.provider/"

    def mockConsumer(self, sessionData, openID, realm, returnURL,
                     openIDProviderURL, completeArgument, completeResult):
        consumerFactory = self.mocker.replace(
            "openid.consumer.consumer.Consumer", passthrough=False)
        consumerMock = consumerFactory(ANY, self.oidStore)

        authRequest = consumerMock.begin(openID)
        authRequest.redirectURL(realm, returnURL)
        self.mocker.result(openIDProviderURL)

        secondConsumer = consumerFactory(ANY, self.oidStore)
        secondConsumer.complete(completeArgument, returnURL)
        self.mocker.result(completeResult)

    def test_success(self):
        request = DummyRequest()
        class Response(object):
            status = SUCCESS
            identity_url = self.openID
        completeResult = Response()
        self.mockConsumer({}, self.openID, self.realm,
                          self.returnURL, self.openIDProviderURL,
                          {"WHAT": "foo"}, completeResult)
        self.mocker.replay()

        checker = OpenIDChecker(self.realm, self.returnURL, self.oidStore)
        credentials = OpenIDCredentials(request, self.openID, self.destination)
        result = checker.requestAvatarId(credentials)

        def pingBack(providerURL):
            self.assertEquals(providerURL, self.openIDProviderURL)
            response_request = DummyRequest()
            response_request.session = request.session
            response_request.args = {"WHAT": ["foo"]}
            resource = OpenIDCallbackHandler(self.oidStore, checker)
            resource.render_GET(response_request)

        request.redirectDeferred.addCallback(pingBack)
        result.addCallback(self.assertEquals, self.openID)
        return gatherResults([result, request.redirectDeferred])

    def test_openIDLookupError(self):
        """
        If an error occurs trying to find a user's OpenID provider,
        UnauthorizedLogin will be fired.
        """
        request = DummyRequest()
        checker = OpenIDChecker(self.realm, self.returnURL, self.oidStore)
        credentials = OpenIDCredentials(request, self.openID, self.destination)

        consumerFactory = self.mocker.replace(
            "openid.consumer.consumer.Consumer", passthrough=False)
        consumerMock = consumerFactory(ANY, self.oidStore)
        consumerMock.begin(ARGS, KWARGS)
        self.mocker.throw(ZeroDivisionError)

        self.mocker.replay()

        result = checker.requestAvatarId(credentials)
        self.assertFailure(result, UnauthorizedLogin)
        result.addCallback(
            lambda ignored: self.flushLoggedErrors(ZeroDivisionError))
        return result

    # XXX Test timeouts
    # XXX Test a FailureResponse
    # XXX Test a CancelResponse
    # XXX Test a SetupNeededResponse
