#! /usr/bin/python

import types, struct

from twisted.internet import protocol, error
from twisted.python.failure import Failure

from slicer import RootSlicer, RootUnslicer, \
     UnbananaFailure, VocabSlicer, SimpleTokens
from tokens import Violation, SIZE_LIMIT, STRING, LIST, INT, NEG, \
     LONGINT, LONGNEG, VOCAB, FLOAT, OPEN, CLOSE, ABORT, tokenNames, \
     BananaError, BananaError2

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

class Banana(protocol.Protocol):
    slicerClass = RootSlicer
    unslicerClass = RootUnslicer
    hangupOnLengthViolation = False
    debug = False

    def __init__(self):
        self.initSend()
        self.initReceive()

    # output side
    def initSend(self):
        self.rootSlicer = self.slicerClass()
        self.rootSlicer.protocol = self
        self.slicerStack = [self.rootSlicer]
        self.openCount = 0
        self.outgoingVocabulary = {}

    def send(self, obj):
        assert(len(self.slicerStack) == 1)
        assert(isinstance(self.slicerStack[0], self.slicerClass))
        if type(obj) in SimpleTokens:
            self.sendToken(obj)
            return
        self.doSlice(obj)

    def setOutgoingVocabulary(self, vocabDict):
        # build a VOCAB message, send it, then set our outgoingVocabulary
        # dictionary to start using the new table
        for key,value in vocabDict.items():
            assert(isinstance(key, types.IntType))
            assert(isinstance(value, types.StringType))
        s = VocabSlicer()
        s.protocol = self
        self.slicerStack.append(s)
        self.doSlice(vocabDict)
        self.slicerStack.pop(-1)
        self.outgoingVocabulary = dict(zip(vocabDict.values(),
                                           vocabDict.keys()))

    def doSlice(self, obj):
        slicer = self.slicerStack[-1]
        slicer.start(obj)
        slicer.slice(obj)
        slicer.finish(obj)

    # slicers require the following methods on their .banana object:

    def slice(self, obj):
        # let everybody taste it
        #for i in range(len(self.stack)-1, -1, -1):
        #    self.stack[i].taste(obj)
        # find the Slicer object
        child = None
        for i in range(len(self.slicerStack)-1, -1, -1):
            child = self.slicerStack[i].newSlicer(obj)
            if child:
                break
        if child == None:
            raise "nothing to send for obj '%s' (type '%s')" % (obj, type(obj))
        self.slice2(child, obj)

    def slice2(self, child, obj):
        child.protocol = self
        self.slicerStack.append(child)
        self.doSlice(obj)
        self.slicerStack.pop(-1)

    def setRefID(self, obj, refid):
        for i in range(len(self.slicerStack)-1, -1, -1):
            self.slicerStack[i].setRefID(obj, refid)
    def getRefID(self, refid):
        # this definitely needs to be optimized
        for i in range(len(self.slicerStack)-1, -1, -1):
            obj = self.slicerStack[i].getRefID(refid)
            if obj is not None:
                return obj
        return None

    # and these methods define how they emit low-level tokens

    def sendOpen(self, opentype):
        openID = self.openCount
        self.openCount += 1
        int2b128(openID, self.transport.write)
        self.transport.write(OPEN)
        self.sendToken(opentype)
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

    # they also require the slicerStack list, which they will manipulate


    # input side

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


    def getLimit(self, typebyte):
        # the purpose here is to limit the memory consumed by the body of a
        # STRING, OPEN, LONGINT, or LONGNEG token (i.e., the size of a
        # primitive type). This will never be called with ABORT or CLOSE
        # types.
        top = self.receiveStack[-1]
        if self.inOpen:
            limit = top.openerCheckToken(typebyte, self.opentype)
        else:
            limit = top.checkToken(typebyte) # might raise Violation
        if self.debug: print "getLimit(0x%x)=%s" % (ord(typebyte), limit)
        return limit


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
            sizelimit = SIZE_LIMIT # default limit is 1k

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

            if not rejected:
                # CLOSE and ABORT are always legal. All others (including
                # OPEN) can be rejected by the schema: for example, a list
                # of integers would reject STRING, VOCAB, and OPEN
                if typebyte not in (ABORT, CLOSE):
                    try:
                        sizelimit = self.getLimit(typebyte)
                    except Violation:
                        where = self.describe()
                        e = BananaError("schema rejected %s token" % \
                                        tokenNames[typebyte],
                                        where + "<checkToken>")
                        rejected = True
                        gotItem(UnbananaFailure(self.describe(), e))
                    except BananaError, e:
                        where = self.describe()
                        e.where = where
                        raise e
                    except:
                        # TODO: I think BananaError2 can go away, since we
                        # can modify a Failure and then re-raise it
                        e = BananaError2(Failure(),
                                         self.describe() + "<checkToken>")
                        raise e

            header = buffer[:pos]
            rest = buffer[pos+1:]
            if len(header) > 64:
                raise BananaError("token prefix is limited to 64 bytes")

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
                #header = b1282int(header)
                #if header > SIZE_LIMIT:
                #    raise BananaError("Security precaution: List too long.")
                #listStack.append((header, []))
                #buffer = rest

            elif typebyte == STRING:
                strlen = b1282int(header)
                if not rejected and sizelimit != None and strlen > sizelimit:
                    if self.hangupOnLengthViolation:
                        raise BananaError("String too long.")
                    else:
                        # need to skip 'strlen' bytes and feed a BananaFailure
                        # to the current unslicer
                        rejected = True
                        e = BananaError("String too long.")
                        gotItem(UnbananaFailure(self.describe(), e))
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
                        self.skipBytes = strlen - len(rest)
                        self.buffer = ""
                    return

            elif typebyte == INT:
                buffer = rest
                header = b1282int(header)
                obj = int(header)
            elif typebyte == NEG:
                buffer = rest
                header = b1282int(header)
                obj = -int(header)
            elif typebyte == LONGINT or typebyte == LONGNEG:
                strlen = b1282int(header)
                if not rejected and sizelimit != None and strlen > sizelimit:
                    if self.hangupOnLengthViolation:
                        raise BananaError("Longint too long.")
                    else:
                        # need to skip 'strlen' bytes and feed a
                        # BananaFailure to the current unslicer
                        rejected = True
                        e = BananaError("Longint too long.")
                        gotItem(UnbananaFailure(self.describe(), e))
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
                header = b1282int(header)
                obj = self.incomingVocabulary[header]

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
                self.openCount = b1282int(header)
                if rejected:
                    # either 1) we are discarding everything, or 2) we
                    # rejected the OPEN token. In either case, discard
                    # everything until the matching CLOSE token.
                    self.discardCount += 1
                else:
                    if self.inOpen:
                        raise BananaError("OPEN token followed by OPEN")
                    self.inOpen = True
                    self.opentype = []
                continue

            elif typebyte == CLOSE:
                buffer = rest
                count = b1282int(header)
                if self.discardCount:
                    self.discardCount -= 1
                else:
                    self.handleClose(count)
                continue

            elif typebyte == ABORT:
                buffer = rest
                count = b1282int(header)
                self.discardCount += 1
                # TODO: this isn't really a BananaError, but we need
                # *something* to describe it
                e = BananaError("ABORT received")
                gotItem(UnbananaFailure(self.describe(), e))
                continue

            else:
                raise BananaError(("Invalid Type Byte 0x%x" % ord(typebyte)))

            if not rejected:
                if self.inOpen:
                    self.handleOpen(self.openCount, obj)
                    # handleOpen might push a new unslicer and clear
                    # .inOpen, or leave .inOpen true and append the object
                    # to .indexOpen
                else:
                    gotItem(obj)
            else:
                pass # drop the object

            #while listStack and (len(listStack[-1][1]) == listStack[-1][0]):
            #    item = listStack.pop()[1]
            #    gotItem(item)
        self.buffer = ''


    def handleOpen(self, openCount, indexToken):
        self.opentype.append(indexToken)
        opentype = tuple(self.opentype)
        if self.debug:
            print "handleOpen(%d,%s)" % (openCount, indexToken)
        objectCount = self.objectCounter
        top = self.receiveStack[-1]
        try:
            # obtain a new Unslicer to handle the object
            child = top.doOpen(opentype)
            if not child:
                if self.debug:
                    print " doOpen wants more index tokens"
                return # they want more index tokens, leave .inOpen=True
            if self.debug:
                print " opened[%d] with %s" % (openCount, child)
        except Violation:
            # must discard the rest of the child object. There is no new
            # unslicer pushed yet, so we don't use abandonUnslicer
            self.discardCount += 1
            self.inOpen = False

            # and give an UnbananaFailure to the parent who rejected it
            where = self.describe() + ".<OPEN(%s)>" % (opentype,)
            failure = UnbananaFailure(where, Failure())
            top.receiveChild(failure)
            return
        except BananaError:
            raise
        except:
            # blow up, but make a note of which object caused the problem
            where = self.describe() + ".<OPEN(%s)>" % (opentype,)
            raise BananaError2(Failure(), where)

        self.objectCounter += 1
        self.inOpen = False
        child.protocol = self
        child.openCount = openCount
        self.receiveStack.append(child)
        try:
            child.start(objectCount)
        except Violation:
            # the child is now on top, so use abandonUnslicer to discard the
            # rest of the child
            where = self.describe() + ".<START>"
            f = UnbananaFailure(where, Failure())
            self.abandonUnslicer(f, child)
        except BananaError:
            raise
        except:
            where = self.describe() + ".<START>"
            raise BananaError2(Failure(), where)

    def handleToken(self, token):
        top = self.receiveStack[-1]
        if self.debug: print "handleToken(%s)" % token
        try:
            top.receiveChild(token)
        except Violation:
            # this is how the child says "I've been contaminated". If they
            # want to handle bad input better, they should deal with
            # whatever they get (and have the ability to restrict that
            # earlier, with checkToken and doOpen). At this point we have to
            # give up on them.
            #
            # It is not valid for a child to do both
            # 'self.protocol.abandonUnslicer()' and 'raise Violation'

            f = UnbananaFailure(self.describe(), Failure())
            self.abandonUnslicer(f, top)
        except BananaError:
            raise
        except:
            where = self.describe() + ".<receiveChild(%s)>" % (token,)
            raise BananaError2(Failure(), where)

    def handleClose(self, closeCount):
        if self.debug:
            print "handleClose(%d)" % closeCount
        if self.receiveStack[-1].openCount != closeCount:
            print "LOST SYNC"
            self.printStack()
            assert(0)

        child = self.receiveStack[-1] # don't pop yet: describe() needs it

        try:
            obj = child.receiveClose()
        except Violation:
            # the child is contaminated. However, they're finished, so we
            # don't have to discard anything. Just give an UnbananaFailure
            # to the parent.
            where = self.describe() + ".<CLOSE>"
            obj = UnbananaFailure(where, Failure())
        except BananaError:
            raise
        except:
            where = self.describe() + ".<CLOSE>"
            raise BananaError2(Failure(), where)

        if self.debug: print "receiveClose returned", obj

        try:
            child.finish()
        except Violation:
            # .finish could raise a Violation if an object that references
            # the child is just now deciding that they don't like it
            # (perhaps their TupleConstraint couldn't be asserted until the
            # tuple was complete and referenceable). In this case, the child
            # has produced a valid object, but an earlier (incomplete)
            # object is not valid. So we treat this as if this child itself
            # raised the Violation. The .where attribute will point to this
            # child, which is the node that caused somebody problems, but
            # will be marked <FINISH>, which indicates that it wasn't the
            # child itself which raised the Violation.
            #
            # TODO: it would be more useful if the UF could also point to
            # the completing object (the one which raised Violation).

            where = self.describe() + ".<FINISH>"
            obj = UnbananaFailure(where, Failure())
        except BananaError:
            raise
        except:
            where = self.describe() + ".<FINISH>"
            raise BananaError2(Failure(), where)

        self.receiveStack.pop()

        parent = self.receiveStack[-1]
        try:
            if self.debug: print "receiveChild()"
            if isinstance(obj, UnbananaFailure):
                if self.debug: print "%s .childFinished for UF" % parent
                self.startDiscarding(obj, parent)
            parent.receiveChild(obj)
        except Violation:
            # the parent didn't like the child object and is now
            # contaminated. This is just like receiveToken failing
            f = UnbananaFailure(self.describe(), Failure())
            self.abandonUnslicer(f, parent)
        except BananaError:
            raise
        except:
            where = self.describe() + ".<receiveChild(%s)>" % (obj,)
            raise BananaError2(Failure(), where)

    def abandonUnslicer(self, failure, leaf=None):
        """The top-most Unslicer has decided to give up. We must discard all
        tokens until the matching CLOSE is received. The UnbananaFailure
        must be delivered to the late unslicer's parent.

        leaf is a paranoia debug check, used to make sure abandonUnslicer is
        called by the slicer that is currently in control.
        """

        if self.debug:
            print "## abandonUnslicer called"
            if isinstance(failure, UnbananaFailure):
                print "##  while decoding '%s'" % failure.where
            print "## current stack leading up to abandonUnslicer:"
            import traceback
            traceback.print_stack()
            if not isinstance(failure, UnbananaFailure) and failure.failure:
                print "## exception that triggered abandonUnslicer:"
                print failure.failure.getBriefTraceback()

        old = self.receiveStack.pop()
        try:
            old.finish() # ??
        except Violation:
            # they've already failed once
            pass
        # let other exceptions pop up here, because the .where argument
        # isn't really useful (TODO: really?)

        assert leaf == old

        if not self.receiveStack:
            # uh oh, the RootUnslicer broke. have to drop the connection
            # now
            print "RootUnslicer broken! hang up or else"
            raise RuntimeError, "RootUnslicer broken: hang up or else"

        self.discardCount += 1 # throw out everything until matching CLOSE
        top = self.receiveStack[-1]
        try:
            top.receiveChild(failure)
        except Violation:
            # they didn't like it either. This is like receiveToken failing.
            # Propogate it up. The RootUnslicer is expected to log the
            # UnbananaFailure and not raise another Violation, so this
            # shouldn't go all the way up to the top.

            # note that simplistic Unslicers who deal with UF by raising
            # Violation allows a mild recursion attack: we have a stack here
            # that is as deep as the object tree was when the Violation took
            # place.

            # TODO: need a mechanism to chain the UnbananaFailures
            self.abandonUnslicer(failure, top)
        except BananaError:
            raise
        except:
            where = self.describe() + \
                    ".<abandonUnslicer-receiveChild(%s)>" % failure
            raise BananaError2(Failure(), where)

    def describe(self):
        where = []
        for i in self.receiveStack:
            try:
                piece = i.describeSelf()
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

