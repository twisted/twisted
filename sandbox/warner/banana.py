#! /usr/bin/python

import types, struct

from twisted.internet import protocol, error, defer
from twisted.python.failure import Failure
from twisted.python import log

import slicer, tokens
from tokens import SIZE_LIMIT, STRING, LIST, INT, NEG, \
     LONGINT, LONGNEG, VOCAB, FLOAT, OPEN, CLOSE, ABORT, \
     BananaError, UnbananaFailure, Violation

def int2b128(integer, stream):
    if integer == 0:
        stream(chr(0))
        return
    assert integer > 0, "can only encode positive integers"
    while integer:
        stream(chr(integer & 0x7f))
        integer = integer >> 7

def b1282int(st):
    # NOTE that this is little-endian
    oneHundredAndTwentyEight = 128
    i = 0
    place = 0
    for char in st:
        num = ord(char)
        i = i + (num * (oneHundredAndTwentyEight ** place))
        place = place + 1
    return i

# long_to_bytes and bytes_to_long taken from PyCrypto: Crypto/Util/number.py

def long_to_bytes(n, blocksize=0):
    """long_to_bytes(n:long, blocksize:int) : string
    Convert a long integer to a byte string.

    If optional blocksize is given and greater than zero, pad the front of
    the byte string with binary zeros so that the length is a multiple of
    blocksize.
    """
    # after much testing, this algorithm was deemed to be the fastest
    s = ''
    n = long(n)
    pack = struct.pack
    while n > 0:
        s = pack('>I', n & 0xffffffffL) + s
        n = n >> 32
    # strip off leading zeros
    for i in range(len(s)):
        if s[i] != '\000':
            break
    else:
        # only happens when n == 0
        s = '\000'
        i = 0
    s = s[i:]
    # add back some pad bytes. this could be done more efficiently w.r.t. the
    # de-padding being done above, but sigh...
    if blocksize > 0 and len(s) % blocksize:
        s = (blocksize - len(s) % blocksize) * '\000' + s
    return s

def bytes_to_long(s):
    """bytes_to_long(string) : long
    Convert a byte string to a long integer.

    This is (essentially) the inverse of long_to_bytes().
    """
    acc = 0L
    unpack = struct.unpack
    length = len(s)
    if length % 4:
        extra = (4 - length % 4)
        s = '\000' * extra + s
        length = length + extra
    for i in range(0, length, 4):
        acc = (acc << 32) + unpack('>I', s[i:i+4])[0]
    return acc

HIGH_BIT_SET = chr(0x80)

# Banana is a big class. It is split up into three sections: sending,
# receiving, and connection setup. These used to be separate classes, but
# the __init__ functions got too weird.

class Banana(protocol.Protocol):

    def __init__(self):
        self.initSend()
        self.initReceive()

    ### connection setup

    def connectionMade(self):
        if self.debugSend:
            print "Banana.connectionMade"
        # prime the pump
        self.produce()
        # TODO: do setup/negotiation
        # now tell anybody who cares that the connection is ready
        self.connectionReady()

    def connectionReady(self):
        pass

    ### SendBanana
    # called by .send()
    # calls transport.write() and transport.loseConnection()

    slicerClass = slicer.RootSlicer
    paused = False
    streamable = True # this is only checked during __init__
    debugSend = False

    def initSend(self):
        self.rootSlicer = self.slicerClass(self)
        self.rootSlicer.allowStreaming(self.streamable)
        assert tokens.ISlicer.providedBy(self.rootSlicer)
        assert tokens.IRootSlicer.providedBy(self.rootSlicer)

        itr = self.rootSlicer.slice()
        next = iter(itr).next
        top = (self.rootSlicer, next, None)
        self.slicerStack = [top]

        self.openCount = 0
        self.outgoingVocabulary = {}

    def send(self, obj):
        if self.debugSend: print "Banana.send(%s)" % obj
        return self.rootSlicer.send(obj)

    def produce(self, dummy=None):
        # optimize: cache 'next' because we get many more tokens than stack
        # pushes/pops
        while self.slicerStack and not self.paused:
            if self.debugSend: print "produce.loop"
            try:
                slicer, next, openID = self.slicerStack[-1]
                obj = next()
                if self.debugSend: print " produce.obj=%s" % obj
                if isinstance(obj, defer.Deferred):
                    for s,n,o in self.slicerStack:
                        if not s.streamable:
                            raise Violation("parent not streamable")
                    obj.addCallback(self.produce)
                    obj.addErrback(self.sendFailed) # what could cause this?
                    # this is the primary exit point
                    break
                elif type(obj) in (int, long, float, str):
                    # sendToken raises a BananaError for weird tokens
                    self.sendToken(obj)
                else:
                    # newSlicerFor raises a Violation for unsendable types
                    # pushSlicer calls .slice, which can raise Violation
                    try:
                        slicer = self.newSlicerFor(obj)
                        self.pushSlicer(slicer, obj)
                    except Violation, v:
                        if self.debugSend:
                            print " violation in newSlicerFor"
                            print Failure()
                        v.setLocation(self.describeSend())
                        # no child tokens have been sent yet, the Slicer has
                        # not yet been pushed. Inform the parent
                        topSlicer = self.slicerStack[-1][0]
                        # .childAborted might re-raise the exception, which
                        # is handled below where it can propogate all the
                        # way up to the root
                        topSlicer.childAborted(v)

                        # the parent wants to forge ahead

            except StopIteration:
                if self.debugSend: print "StopIteration"
                self.popSlicer()
            except Violation, v1:
                # Violations that occur because of Constraints are caught
                # before the Slicer is pushed. A Violation that is caught
                # here was either raised inside .next() or re-raised by
                # .childAborted(). Either case indicates that the Slicer
                # should be abandoned.

                # the parent .childAborted might re-raise the Violation, so
                # we have to loop this until someone stops complaining
                v1.setLocation(self.describeSend())
                v = v1
                if self.debugSend: print " violation in loop:", v

                while True:
                    # should we send an ABORT? Only if an OPEN has been
                    # sent, which happens in pushSlicer (if at all).
                    lastOpenID = self.slicerStack[-1][2]
                    if lastOpenID is not None:
                        self.sendAbort()

                    # should we pop the Slicer? yes
                    self.popSlicer()
                    if not self.slicerStack:
                        if self.debugSend: print "RootSlicer died!"
                        raise BananaError("Hey! You killed the RootSlicer!")

                    # now inform the parent. If they also give up, we will
                    # loop, popping more Slicers off the stack until the
                    # RootSlicer ignores the error

                    # The Violation is tagged with a location the first time
                    # it is handled. Later Slicers have the option of
                    # re-raising it (which means it will retain that
                    # original location description) or creating a new
                    # Violation (in which case they are responsible for
                    # describing it).
                    topSlicer = self.slicerStack[-1][0]
                    try:
                        if self.debugSend:
                            print "  notifying parent", topSlicer
                        topSlicer.childAborted(v)
                    except Violation, v2:
                        v = v2 # not sure this is necessary
                        continue
                    else:
                        break
            except:
                print "exception in produce"
                self.sendFailed(Failure())
                # there is no point to raising this again. The Deferreds are
                # all errbacked in sendFailed(). This function was called
                # inside a Deferred which errbacks to sendFailed(), and
                # we've already called that once. The connection will be
                # dropped by sendFailed(), and the error is logged, so there
                # is nothing left to do.
                return

        assert self.slicerStack # should never be empty

    def newSlicerFor(self, obj):
        if tokens.ISlicer.providedBy(obj):
            return obj
        topSlicer = self.slicerStack[-1][0]
        # slicerForObject could raise a Violation, for unserializeable types
        return topSlicer.slicerForObject(obj)

    def pushSlicer(self, slicer, obj):
        if self.debugSend: print "push", slicer
        assert len(self.slicerStack) < 10000 # failsafe

        # if this method raises a Violation, it means that .slice failed,
        # and neither the OPEN nor the stack-push has occurred

        topSlicer = self.slicerStack[-1][0]
        slicer.parent = topSlicer

        # we start the Slicer (by getting its iterator) first, so that if it
        # fails we can refrain from sending the OPEN (hence we do not have
        # to send an ABORT and CLOSE, which simplifies the send logic
        # considerably). slicer.slice is the only place where a Violation
        # can be raised: it is caught and passed cleanly to the parent. If
        # it happens anywhere else, or if any other exception is raised, the
        # connection will be dropped.

        # the downside to this approach is that .slice happens before
        # .registerReference, so any late-validation being done in .slice
        # will not be able to detect the fact that this object has already
        # begun serialization. Validation performed in .next is ok.

        # also note that if .slice is a generator, any exception it raises
        # will not occur until .next is called, which happens *after* the
        # slicer has been pushed. This check is only useful for .slice
        # methods which are *not* generators.

        itr = slicer.slice(topSlicer.streamable, self)
        next = iter(itr).next

        # we are now committed to sending the OPEN token, meaning that
        # failures after this point will cause an ABORT/CLOSE to be sent

        openID = None
        if slicer.sendOpen:
            openID = self.sendOpen()
            if slicer.trackReferences:
                topSlicer.registerReference(openID, obj)
            # note that the only reason to hold on to the openID here is for
            # the debug/optional copy in the CLOSE token. Consider ripping
            # this code out if we decide to stop sending that copy.

        slicertuple = (slicer, next, openID)
        self.slicerStack.append(slicertuple)

    def popSlicer(self):
        slicertuple = self.slicerStack.pop()
        openID = slicertuple[2]
        if openID is not None:
            self.sendClose(openID)
        if self.debugSend: print "pop", slicertuple[0]

    def describeSend(self):
        where = []
        for i in self.slicerStack:
            try:
                piece = i[0].describe()
            except:
                log.err()
                piece = "???"
            where.append(piece)
        return ".".join(where)
        

    def setOutgoingVocabulary(self, vocabDict):
        # build a VOCAB message, send it, then set our outgoingVocabulary
        # dictionary to start using the new table
        for key,value in vocabDict.items():
            assert(isinstance(key, types.IntType))
            assert(isinstance(value, types.StringType))
        s = slicer.VocabSlicer(vocabDict)
        # insure the VOCAB message does not use vocab tokens itself. This
        # would be legal (sort of a differential compression), but
        # confusing, and it would enhance the bugginess of the race
        # condition.
        self.outgoingVocabulary = {}
        self.send(s)
        # TODO: race condition between this being pushed on the stack and it
        # taking effect for our own transmission. Don't set
        # .outgoingVocabulary until it finishes being sent.
        self.outgoingVocabulary = dict(zip(vocabDict.values(),
                                           vocabDict.keys()))

    # these methods define how we emit low-level tokens

    def sendOpen(self):
        openID = self.openCount
        self.openCount += 1
        int2b128(openID, self.transport.write)
        self.transport.write(OPEN)
        return openID

    def sendToken(self, obj):
        write = self.transport.write
        if isinstance(obj, types.IntType) or isinstance(obj, types.LongType):
            if obj >= 2**31:
                s = long_to_bytes(obj)
                int2b128(len(s), write)
                write(LONGINT)
                write(s)
            elif obj >= 0:
                int2b128(obj, write)
                write(INT)
            elif -obj > 2**31: # NEG is [-2**31, 0)
                s = long_to_bytes(-obj)
                int2b128(len(s), write)
                write(LONGNEG)
                write(s)
            else:
                int2b128(-obj, write)
                write(NEG)
        elif isinstance(obj, types.FloatType):
            write(FLOAT)
            write(struct.pack("!d", obj))
        elif isinstance(obj, types.StringType):
            if self.outgoingVocabulary.has_key(obj):
                symbolID = self.outgoingVocabulary[obj]
                int2b128(symbolID, write)
                write(VOCAB)
            else:
                if len(obj) > SIZE_LIMIT:
                    raise BananaError, \
                          "string is too long to send (%d)" % len(obj)
                int2b128(len(obj), write)
                write(STRING)
                write(obj)
        else:
            raise BananaError, "could not send object: %s" % repr(obj)

    def sendClose(self, openID):
        int2b128(openID, self.transport.write)
        self.transport.write(CLOSE)

    def sendAbort(self, count=0):
        int2b128(count, self.transport.write)
        self.transport.write(ABORT)

    def sendFailed(self, f):
        # call this if an exception is raised in transmission. The Failure
        # will be logged and the connection will be dropped. This is
        # suitable for use as an errback handler.
        print "SendBanana.sendFailed:", f
        log.err(f)
        try:
            if self.transport:
                self.transport.loseConnection(f)
        except:
            print "exception during transport.loseConnection"
            log.err()
        try:
            self.rootSlicer.connectionLost(f)
        except:
            print "exception during rootSlicer.connectionLost"
            log.err()

    ### ReceiveBanana
    # called with dataReceived()
    # calls self.receivedObject()

    unslicerClass = slicer.RootUnslicer
    debugReceive = False
    logViolations = False
    logDiscardCount = False

    def initReceive(self):
        self.rootUnslicer = self.unslicerClass()
        self.rootUnslicer.protocol = self
        self.receiveStack = [self.rootUnslicer]
        self.objectCounter = 0
        self.objects = {}

        self.inOpen = False # set during the Index Phase of an OPEN sequence
        self.opentype = [] # accumulates Index Tokens

        self.incomingVocabulary = {}
        self.buffer = ''
        self.skipBytes = 0 # used to discard a single long token
        self.discardCount = 0 # used to discard non-primitive objects
        self.exploded = None # last-ditch error catcher

    def printStack(self, verbose=0):
        print "STACK:"
        for s in self.receiveStack:
            if verbose:
                d = s.__dict__.copy()
                del d['protocol']
                print " %s: %s" % (s, d)
            else:
                print " %s" % s

    def setObject(self, count, obj):
        for i in range(len(self.receiveStack)-1, -1, -1):
            self.receiveStack[i].setObject(count, obj)

    def getObject(self, count):
        for i in range(len(self.receiveStack)-1, -1, -1):
            obj = self.receiveStack[i].getObject(count)
            if obj is not None:
                return obj
        raise ValueError, "dangling reference '%d'" % count


    def setIncomingVocabulary(self, vocabDict):
        # maps small integer to string, should be called in response to a
        # OPEN(vocab) sequence.
        self.incomingVocabulary = vocabDict

    def checkToken(self, typebyte, size):
        # the purpose here is to limit the memory consumed by the body of a
        # STRING, OPEN, LONGINT, or LONGNEG token (i.e., the size of a
        # primitive type). If the sender wants to feed us more data than we
        # want to accept, the checkToken() method should raise a Violation.
        # This will never be called with ABORT or CLOSE types.
        top = self.receiveStack[-1]
        if self.inOpen:
            top.openerCheckToken(typebyte, size, self.opentype)
        else:
            top.checkToken(typebyte, size) # might raise Violation

    def dataReceived(self, chunk):
        # buffer, assemble into tokens
        # call self.receiveToken(token) with each
        if self.skipBytes:
            if len(chunk) < self.skipBytes:
                # skip the whole chunk
                self.skipBytes -= len(chunk)
                return
            # skip part of the chunk, and stop skipping
            chunk = chunk[self.skipBytes:]
            self.skipBytes = 0
        buffer = self.buffer + chunk
        gotItem = self.handleToken

        # Loop through the available input data, extracting one token per
        # pass.

        while buffer:
            assert self.buffer != buffer, "This ain't right: %s %s" % (repr(self.buffer), repr(buffer))
            self.buffer = buffer
            pos = 0
            for ch in buffer:
                if ch >= HIGH_BIT_SET:
                    break
                pos = pos + 1
                # TODO: the 'pos > 64' test should probably move here. If
                # not, a huge chunk will consume more CPU than it needs to.
                # On the other hand, the test would consume extra CPU all
                # the time.
            else:
                if pos > 64:
                    # drop the connection
                    raise BananaError("token prefix is limited to 64 bytes")
                return # still waiting for header to finish

            # At this point, the header and type byte have been received.
            # The body may or may not be complete.

            typebyte = buffer[pos]
            if pos > 64:
                # redundant?
                raise BananaError("token prefix is limited to 64 bytes")
            if pos:
                header = b1282int(buffer[:pos])
            else:
                header = 0

            # rejected is set as soon as a violation is detected. The
            # appropriate UnbananaFailure will be delivered to the parent
            # unslicer at the same time, so rejected is also a flag that
            # indicates further violation-checking should be skipped. Don't
            # deliver multiple UnbananaFailures.

            rejected = False
            if self.discardCount:
                rejected = True
                self.inOpen = False


            # determine if this token will be accepted, and if so, how large
            # it is allowed to be (for STRING and LONGINT/LONGNEG)

            if (not rejected) and (typebyte not in (ABORT, CLOSE)):
                # CLOSE and ABORT are always legal. All others (including
                # OPEN) can be rejected by the schema: for example, a list
                # of integers would reject STRING, VOCAB, and OPEN because
                # none of those will produce integers. If the unslicer's
                # .checkToken rejects the tokentype, its .receiveChild will
                # immediately get an UnbananaFailure
                try:
                    self.checkToken(typebyte, header)
                except Violation, v:
                    rejected = True
                    if typebyte == OPEN or self.inOpen:
                        # need to discard the rest of this new sequence
                        self.discardCount += 1
                        if self.logDiscardCount:
                            print "discardCount+++++ now", self.discardCount
                    gotItem(UnbananaFailure(v, self.describeReceive()))

            rest = buffer[pos+1:]

            # determine what kind of token it is. Each clause finishes in
            # one of four ways:
            #
            #  raise BananaError: the protocol was violated so badly there is
            #                     nothing to do for it but hang up abruptly
            #
            #  return: if the token is not yet complete (need more data)
            #
            #  continue: if the token is complete but no object (for
            #            handleToken) was produced, e.g. OPEN, CLOSE, ABORT
            #
            #  obj=foo: the token is complete and an object was produced
            #
            # note that if rejected==True, the object is dropped instead of
            # being passed up to the current Unslicer

            if typebyte == LIST:
                raise BananaError("oldbanana peer detected, " +
                                  "compatibility code not yet written")
                #listStack.append((header, []))
                #buffer = rest

            elif typebyte == STRING:
                strlen = header
                if len(rest) >= strlen:
                    # the whole string is available
                    buffer = rest[strlen:]
                    obj = rest[:strlen]
                    # although it might be rejected
                else:
                    # there is more to come
                    if rejected:
                        # drop all we have and note how much more should be
                        # dropped
                        if self.logDiscardCount:
                            print "DROPPED some string bits"
                        self.skipBytes = strlen - len(rest)
                        self.buffer = ""
                    return

            elif typebyte == INT:
                buffer = rest
                obj = int(header)
            elif typebyte == NEG:
                buffer = rest
                obj = -int(header)
            elif typebyte == LONGINT or typebyte == LONGNEG:
                strlen = header
                if len(rest) >= strlen:
                    # the whole number is available
                    buffer = rest[strlen:]
                    obj = bytes_to_long(rest[:strlen])
                    if typebyte == LONGNEG:
                        obj = -obj
                    # although it might be rejected
                else:
                    # there is more to come
                    if rejected:
                        # drop all we have and note how much more should be
                        # dropped
                        self.skipBytes = strlen - len(rest)
                        self.buffer = ""
                    return

            elif typebyte == VOCAB:
                buffer = rest
                obj = self.incomingVocabulary[header]
                # TODO: bail if expanded string is too big
                # this actually means doing self.checkToken(VOCAB, len(obj))
                # but we have to make sure we handle the rejection properly

            elif typebyte == FLOAT:
                if len(rest) >= 8:
                    buffer = rest[8:]
                    obj = struct.unpack("!d", rest[:8])[0]
                else:
                    # this case is easier than STRING, because it is only 8
                    # bytes. We don't bother skipping anything.
                    return

            elif typebyte == OPEN:
                buffer = rest
                self.inboundOpenCount = header
                if rejected:
                    # either 1) we are discarding everything, or 2) we
                    # rejected the OPEN token. In either case, discard
                    # everything until the matching CLOSE token.
                    self.discardCount += 1
                    if self.logDiscardCount:
                        print "discardCount++ now", self.discardCount
                else:
                    if self.inOpen:
                        raise BananaError("OPEN token followed by OPEN")
                    self.inOpen = True
                    self.opentype = []
                continue

            elif typebyte == CLOSE:
                buffer = rest
                count = header
                if self.discardCount:
                    self.discardCount -= 1
                    if self.logDiscardCount:
                        print "discardCount-- now", self.discardCount
                else:
                    self.handleClose(count)
                continue

            elif typebyte == ABORT:
                buffer = rest
                count = header
                # TODO: this isn't really a Violation, but we need something
                # to describe it. It does behave identically to what happens
                # when receiveChild raises a Violation. The .handleViolation
                # will pop the now-useless Unslicer and start discarding
                # tokens just as if the Unslicer had made the decision.
                v = Violation("ABORT received")
                self.handleViolation(v, "receive-abort", True)
                continue

            else:
                raise BananaError(("Invalid Type Byte 0x%x" % ord(typebyte)))

            if not rejected:
                if self.inOpen:
                    self.handleOpen(self.inboundOpenCount, obj)
                    # handleOpen might push a new unslicer and clear
                    # .inOpen, or leave .inOpen true and append the object
                    # to .indexOpen
                else:
                    gotItem(obj)
            else:
                if self.logDiscardCount:
                    print "DROP", obj
                pass # drop the object

            #while listStack and (len(listStack[-1][1]) == listStack[-1][0]):
            #    item = listStack.pop()[1]
            #    gotItem(item)
        self.buffer = ''


    def handleOpen(self, openCount, indexToken):
        self.opentype.append(indexToken)
        opentype = tuple(self.opentype)
        if self.debugReceive:
            print "handleOpen(%d,%s)" % (openCount, indexToken)
        objectCount = self.objectCounter
        top = self.receiveStack[-1]
        try:
            # obtain a new Unslicer to handle the object
            child = top.doOpen(opentype)
            if not child:
                if self.debugReceive:
                    print " doOpen wants more index tokens"
                return # they want more index tokens, leave .inOpen=True
            if self.debugReceive:
                print " opened[%d] with %s" % (openCount, child)
        except Violation, v:
            # must discard the rest of the child object. There is no new
            # unslicer pushed yet, so we don't use abandonUnslicer
            self.discardCount += 1
            if self.logDiscardCount:
                print "discardCount++++ now", self.discardCount
            self.inOpen = False
            self.handleViolation(v, "doOpen", False)
            return

        assert tokens.IUnslicer.providedBy(child), "child is %s" % child
        self.objectCounter += 1
        self.inOpen = False
        child.protocol = self
        child.openCount = openCount
        child.parent = top
        self.receiveStack.append(child)
        try:
            child.start(objectCount)
        except Violation, v:
            # the child is now on top, so use abandonUnslicer to discard the
            # rest of the child
            self.handleViolation(v, "start", True)

    def handleToken(self, token):
        top = self.receiveStack[-1]
        if self.debugReceive: print "handleToken(%s)" % token
        try:
            top.receiveChild(token)
        except Violation, v:
            # this is how the child says "I've been contaminated". If they
            # want to handle bad input better, they should deal with
            # whatever they get (and they have the ability to restrict that
            # earlier, with checkToken and doOpen). At this point we have to
            # give up on them.
            self.handleViolation(v, "receiveChild", True)

    def handleClose(self, closeCount):
        if self.debugReceive:
            print "handleClose(%d)" % closeCount
        if self.receiveStack[-1].openCount != closeCount:
            print "LOST SYNC"
            self.printStack()
            assert(0)

        child = self.receiveStack[-1] # don't pop yet: describe() needs it

        try:
            obj = child.receiveClose()
        except Violation, v:
            # the child is contaminated. However, they're finished, so we
            # don't have to discard anything. Just give an UnbananaFailure
            # to the parent instead of the object they would have returned.
            self.handleViolation(v, "receiveClose", True, discard=False)
            return

        if self.debugReceive: print "receiveClose returned", obj

        try:
            child.finish()
        except Violation, v:
            # .finish could raise a Violation if an object that references
            # the child is just now deciding that they don't like it
            # (perhaps their TupleConstraint couldn't be asserted until the
            # tuple was complete and referenceable). In this case, the child
            # has produced a valid object, but an earlier (incomplete)
            # object is not valid. So we treat this as if this child itself
            # raised the Violation. The .where attribute will point to this
            # child, which is the node that caused somebody problems, but
            # will be marked <FINISH>, which indicates that it wasn't the
            # child itself which raised the Violation. TODO: not true
            #
            # TODO: it would be more useful if the UF could also point to
            # the completing object (the one which raised Violation).

            self.handleViolation(v, "finish", True, discard=False)
            return

        self.receiveStack.pop()

        # now deliver the object (or the UbF) to the parent)
        self.handleToken(obj)

    def handleViolation(self, v, methname, doPop, discard=True):
        """An Unslicer has decided to give up, or we have given up on it
        (because we received an ABORT token). 
        """

        if v.failure:
            # this is a nested failure. Use the UnbananaFailure inside
            f = v.failure
            assert isinstance(f, UnbananaFailure)
        else:
            where = self.describeReceive()
            f = UnbananaFailure(v, where)
            if self.logViolations:
                log.msg("Violation in %s at %s" % (methname, where))
                log.err()
        top = self.receiveStack[-1]
        f = top.reportViolation(f)
        assert isinstance(f, UnbananaFailure)

        if doPop:
            if self.debugReceive:
                print "## abandonUnslicer called"
                print "##  while decoding '%s'" % f.where
                print "## current stack leading up to abandonUnslicer:"
                import traceback
                traceback.print_stack()
                print "## exception that triggered abandonUnslicer:"
                print f

            old = self.receiveStack.pop()
            if discard:
                # throw out everything until matching CLOSE
                self.discardCount += 1
                if self.logDiscardCount:
                    print "discardCount+++ now", self.discardCount

            try:
                # TODO: if handleClose encountered a Violation in .finish,
                # we will end up calling it a second time
                old.finish() # ??
            except Violation:
                pass # they've already failed once

            if not self.receiveStack:
                # Oh my god, you killed the RootUnslicer! You bastard!
                # now there's nobody left to create new Unslicers, so we
                # must drop the connection
                raise BananaError("we abandoned the RootUnslicer!")

        # and give the UnbananaFailure to the (new) parent
        self.handleToken(f)


    def describeReceive(self):
        where = []
        for i in self.receiveStack:
            try:
                piece = i.describe()
            except:
                piece = "???"
                #raise
            where.append(piece)
        return ".".join(where)

    def receivedObject(self, obj):
        """Decoded objects are delivered here, unless you use a RootUnslicer
        variant which does something else in its .childFinished method.
        """
        raise NotImplementedError


class StorageBanana(Banana):
    # this is "unsafe", in that it will do import() and create instances of
    # arbitrary classes. It is also scoped at the root, so each
    # StorageBanana should be used only once.
    slicerClass = slicer.StorageRootSlicer
    unslicerClass = slicer.StorageRootUnslicer

    # it also stashes top-level objects in .obj, so you can retrieve them
    # later
    def receivedObject(self, obj):
        self.object = obj
