
# miscellaneous helper classes for debugging and testing, not needed for
# normal use

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from twisted.pb import banana, slicer, tokens, storage
Banana = banana.Banana
StorageBanana = storage.StorageBanana

class LoggingBananaMixin:
    # this variant prints a log of tokens sent and received, if you set the
    # .doLog attribute to a string (like 'tx' or 'rx')
    doLog = None

    ### send logging

    def sendOpen(self):
        if self.doLog: print "[%s] OPEN(%d)" % (self.doLog, self.openCount)
        return Banana.sendOpen(self)
    def sendToken(self, obj):
        if self.doLog:
            if type(obj) == str:
                print "[%s] \"%s\"" % (self.doLog, obj)
            elif type(obj) == int:
                print "[%s] %s" % (self.doLog, obj)
            else:
                print "[%s] ?%s?" % (self.doLog, obj)
        return Banana.sendToken(self, obj)
    def sendClose(self, openID):
        if self.doLog: print "[%s] CLOSE(%d)" % (self.doLog, openID)
        return Banana.sendClose(self, openID)
    def sendAbort(self, count):
        if self.doLog: print "[%s] ABORT(%d)" % (self.doLog, count)
        return Banana.sendAbort(self, count)


    ### receive logging

    def rxStackSummary(self):
        return ",".join([s.__class__.__name__ for s in self.receiveStack])

    def handleOpen(self, openCount, indexToken):
        if self.doLog:
            stack = self.rxStackSummary()
            print "[%s] got OPEN(%d,%s) %s" % \
                  (self.doLog, openCount, indexToken, stack)
        return Banana.handleOpen(self, openCount, indexToken)
    def handleToken(self, token, ready_deferred=None):
        if self.doLog:
            if type(token) == str:
                s = '"%s"' % token
            elif type(token) == int:
                s = '%s' % token
            elif isinstance(token, tokens.BananaFailure):
                s = 'UF:%s' % (token,)
            else:
                s = '?%s?' % (token,)
            print "[%s] got %s %s" % (self.doLog, s, self.rxStackSummary())
        return Banana.handleToken(self, token, ready_deferred)
    def handleClose(self, closeCount):
        if self.doLog:
            stack = self.rxStackSummary()
            print "[%s] got CLOSE(%d): %s" % (self.doLog, closeCount, stack)
        return Banana.handleClose(self, closeCount)

class LoggingBanana(LoggingBananaMixin, Banana):
    pass

class LoggingStorageBanana(LoggingBananaMixin, StorageBanana):
    pass

class TokenTransport:
    disconnectReason = None
    def loseConnection(self):
        pass

class TokenBananaMixin:
    # this class accumulates tokens instead of turning them into bytes

    def __init__(self):
        self.tokens = []
        self.connectionMade()
        self.transport = TokenTransport()

    def sendOpen(self):
        openID = self.openCount
        self.openCount += 1
        self.sendToken(("OPEN", openID))
        return openID

    def sendToken(self, token):
        #print token
        self.tokens.append(token)

    def sendClose(self, openID):
        self.sendToken(("CLOSE", openID))

    def sendAbort(self, count=0):
        self.sendToken(("ABORT",))

    def sendError(self, msg):
        #print "TokenBanana.sendError(%s)" % msg
        pass

    def getTokens(self):
        self.produce()
        assert(len(self.slicerStack) == 1)
        assert(isinstance(self.slicerStack[0][0], slicer.RootSlicer))
        return self.tokens

    # TokenReceiveBanana

    def processTokens(self, tokens):
        self.object = None
        for t in tokens:
            self.receiveToken(t)
        return self.object
        
    def receiveToken(self, token):
        # insert artificial tokens into receiveData. Once upon a time this
        # worked by directly calling the commented-out functions, but schema
        # checking and abandonUnslicer made that unfeasible.

        #if self.debug:
        #    print "receiveToken(%s)" % (token,)

        if type(token) == type(()):
            if token[0] == "OPEN":
                count = token[1]
                assert count < 128
                b = ( chr(count) + tokens.OPEN )
                self.injectData(b)
                #self.handleOpen(count, opentype)
            elif token[0] == "CLOSE":
                count = token[1]
                assert count < 128
                b = chr(count) + tokens.CLOSE
                self.injectData(b)
                #self.handleClose(count)
            elif token[0] == "ABORT":
                if len(token) == 2:
                    count = token[1]
                else:
                    count = 0
                assert count < 128
                b = chr(count) + tokens.ABORT
                self.injectData(b)
                #self.handleAbort(count)
        elif type(token) == int:
            assert 0 <= token < 128
            b = chr(token) + tokens.INT
            self.injectData(b)
        elif type(token) == str:
            assert len(token) < 128
            b = chr(len(token)) + tokens.STRING + token
            self.injectData(b)
        else:
            raise NotImplementedError, "hey, this is just a quick hack"

    def injectData(self, data):
        if not self.transport.disconnectReason:
            self.dataReceived(data)

    def receivedObject(self, obj):
        self.object = obj

    def reportViolation(self, why):
        self.violation = why

class TokenBanana(TokenBananaMixin, Banana):
    def __init__(self):
        Banana.__init__(self)
        TokenBananaMixin.__init__(self)

    def reportReceiveError(self, f):
        Banana.reportReceiveError(self, f)
        self.transport.disconnectReason = BananaFailure()

class TokenStorageBanana(TokenBananaMixin, StorageBanana):
    def __init__(self):
        StorageBanana.__init__(self)
        TokenBananaMixin.__init__(self)

    def reportReceiveError(self, f):
        StorageBanana.reportReceiveError(self, f)
        self.transport.disconnectReason = tokens.BananaFailure()

def encodeTokens(obj, debug=0):
    from twisted.trial.util import deferredResult
    b = TokenStorageBanana()
    b.debug = debug
    d = b.send(obj)
    deferredResult(d)
    return b.tokens
def decodeTokens(tokens, debug=0):
    b = TokenStorageBanana()
    b.debug = debug
    obj = b.processTokens(tokens)
    return obj

def encode(obj):
    b = LoggingStorageBanana()
    b.transport = StringIO.StringIO()
    b.send(obj)
    return b.transport.getvalue()
def decode(string):
    b = LoggingStorageBanana()
    b.dataReceived(string)
    return b.object
