#! /usr/bin/python

from slicer import RootSlicer, RootUnslicer, DiscardUnslicer, \
     UnbananaFailure, VocabSlicer, SimpleTokens
from twisted.internet import protocol
from twisted.python.failure import Failure

import types, struct


class BananaError(Exception):
    pass

def int2b128(integer, stream):
    if integer == 0:
        stream(chr(0))
        return
    assert integer > 0, "can only encode positive integers"
    while integer:
        stream(chr(integer & 0x7f))
        integer = integer >> 7

def b1282int(st):
    oneHundredAndTwentyEight = 128
    i = 0
    place = 0
    for char in st:
        num = ord(char)
        i = i + (num * (oneHundredAndTwentyEight ** place))
        place = place + 1
    return i

# delimiter characters.
LIST     = chr(0x80) # old
INT      = chr(0x81)
STRING   = chr(0x82)
NEG      = chr(0x83)
FLOAT    = chr(0x84)
# "optional" -- these might be refused by a low-level implementation.
LONGINT  = chr(0x85) # old
LONGNEG  = chr(0x86) # old
# really optional; this is is part of the 'pb' vocabulary
VOCAB    = chr(0x87)
# newbanana tokens
OPEN     = chr(0x88)
CLOSE    = chr(0x89)
ABORT    = chr(0x8A)

HIGH_BIT_SET = chr(0x80)

SIZE_LIMIT = 640 * 1024   # 640k is all you'll ever need :-)

class Banana(protocol.Protocol):
    slicerClass = RootSlicer
    unslicerClass = RootUnslicer
    debug = 0

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
            if obj >= 0:
                int2b128(obj, write)
                write(INT)
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
        root = self.unslicerClass()
        root.protocol = self
        self.receiveStack = [root]
        self.objectCounter = 0
        self.objects = {}
        self.inOpen = 0
        self.incomingVocabulary = {}
        self.buffer = ''

    def setIncomingVocabulary(self, vocabDict):
        # maps small integer to string, should be called in response to a
        # OPEN(vocab) sequence.
        self.incomingVocabulary = vocabDict

    def startDiscarding(self, failure, leaf):
        """Begin discarding everything in the current node. When the node is
        complete, the given failure is handed to the parent. This is
        implemented by replacing the current node with a DiscardUnslicer.
        
        Slices call startDiscarding in response to an ABORT token or when
        their receiveChild() method is handed a failure object. The Unslicer
        will do startDiscarding when a slice raises an exception.

        The 'leaf' argument is just for development paranoia and will go
        away soon.
        """
        if self.debug:
            print "## startDiscarding called while decoding '%s'" % failure.where
            print "## current stack leading up to startDiscarding:"
            import traceback
            traceback.print_stack()
            if failure.failure:
                print "## exception that triggered startDiscarding:"
                print failure.failure.getBriefTraceback()
        if len(self.receiveStack) == 1:
            # uh oh, the RootUnslicer broke. have to drop the connection now
            print "RootUnslicer broken! hang up or else"
            raise RuntimeError, "RootUnslicer broken: hang up or else"
        assert(self.receiveStack[-1] == leaf)
        d = DiscardUnslicer(failure)
        d.protocol = self
        old = self.receiveStack.pop()
        d.openCount = old.openCount
        old.finish()
        self.receiveStack.append(d)
        if self.debug:
            self.printStack()


    def setObject(self, count, obj):
        for i in range(len(self.receiveStack)-1, -1, -1):
            self.receiveStack[i].setObject(count, obj)

    def getObject(self, count):
        for i in range(len(self.receiveStack)-1, -1, -1):
            obj = self.receiveStack[i].getObject(count)
            if obj is not None:
                return obj
        raise ValueError, "dangling reference '%d'" % count


    def printStack(self, verbose=0):
        print "STACK:"
        for s in self.receiveStack:
            if verbose:
                d = s.__dict__.copy()
                del d['protocol']
                print " %s: %s" % (s, d)
            else:
                print " %s" % s


    def handleOpen(self, openCount, opentype):
        objectCount = self.objectCounter
        self.objectCounter += 1
        try:
            # ask openers what to use
            child = None
            for i in range(len(self.receiveStack)-1, -1, -1):
                child = self.receiveStack[i].doOpen(opentype)
                if child:
                    break
            if child == None:
                raise "nothing to open"
            if self.debug:
                print "opened[%d] with %s" % (openCount, child)
        except:
            if self.debug:
                print "failed to open anything, pushing DiscardUnslicer"
            where = self.describe() + ".<OPEN%s>" % opentype
            uf = UnbananaFailure(where, Failure())
            child = DiscardUnslicer(uf)
        child.protocol = self
        child.openCount = openCount
        self.receiveStack.append(child)
        try:
            child.start(objectCount)
        except:
            where = self.describe() + ".<START>"
            f = UnbananaFailure(where, Failure())
            self.startDiscarding(f, child)

    def handleClose(self, closeCount):
        if self.receiveStack[-1].openCount != closeCount:
            print "LOST SYNC"
            self.printStack()
            assert(0)
        try:
            if self.debug:
                print "receiveClose()"
            obj = self.receiveStack[-1].receiveClose()
        except:
            where = self.describe() + ".<CLOSE>"
            obj = UnbananaFailure(where, Failure())
        if self.debug: print "receiveClose returned", obj
        old = self.receiveStack.pop()
        old.finish()
        try:
            if self.debug: print "receiveChild()"
            self.receiveStack[-1].childFinished(old, obj)
        except:
            where = self.describe()
            # this is just like receiveToken failing
            f = UnbananaFailure(where, Failure())
            self.startDiscarding(f, self.receiveStack[-1])

    def handleAbort(self, count=None):
        # let the unslicer decide what to do. The default is to do
        # self.startDiscarding()
        if self.debug: print "receiveAbort()"
        self.receiveStack[-1].receiveAbort()
        return

    def handleToken(self, token):
        top = self.receiveStack[-1]
        if self.debug: print "receivetoken(%s)" % token
        try:
            top.receiveToken(token)
        except:
            # need to give up on the current stack top
            f = UnbananaFailure(self.describe(), Failure())
            self.startDiscarding(f, top)
            return

    def dataReceived(self, chunk):
        # buffer, assemble into tokens
        # call self.receiveToken(token) with each
        buffer = self.buffer + chunk
        gotItem = self.handleToken
        while buffer:
            assert self.buffer != buffer, "This ain't right: %s %s" % (repr(self.buffer), repr(buffer))
            self.buffer = buffer
            pos = 0
            for ch in buffer:
                if ch >= HIGH_BIT_SET:
                    break
                pos = pos + 1
            else:
                if pos > 64:
                    raise BananaError("Security precaution: more than 64 bytes of prefix")
                return
            header = buffer[:pos]
            typebyte = buffer[pos]
            rest = buffer[pos+1:]
            if len(header) > 64:
                raise BananaError("Security precaution: longer than 64 bytes worth of prefix")
            if typebyte == LIST:
                raise BananaError("oldbanana peer detected, compatibility code not yet written")
                #header = b1282int(header)
                #if header > SIZE_LIMIT:
                #    raise BananaError("Security precaution: List too long.")
                #listStack.append((header, []))
                #buffer = rest
            elif typebyte == STRING:
                header = b1282int(header)
                if header > SIZE_LIMIT:
                    raise BananaError("Security precaution: String too long.")
                if len(rest) >= header:
                    buffer = rest[header:]
                    if self.inOpen:
                        self.inOpen = 0
                        self.handleOpen(self.openCount, rest[:header])
                    else:
                        gotItem(rest[:header])
                else:
                    return
            elif typebyte == INT:
                buffer = rest
                header = b1282int(header)
                gotItem(int(header))
            elif typebyte == LONGINT:
                # OLD: remove this code
                buffer = rest
                header = b1282int(header)
                gotItem(long(header))
            elif typebyte == LONGNEG:
                # OLD: remove this code
                buffer = rest
                header = b1282int(header)
                gotItem(-long(header))
            elif typebyte == NEG:
                buffer = rest
                header = -b1282int(header)
                gotItem(header)
            elif typebyte == VOCAB:
                buffer = rest
                header = b1282int(header)
                str = self.incomingVocabulary[header]
                if self.inOpen:
                    self.inOpen = 0
                    self.handleOpen(self.openCount, str)
                else:
                    gotItem(str)
            elif typebyte == FLOAT:
                if len(rest) >= 8:
                    buffer = rest[8:]
                    gotItem(struct.unpack("!d", rest[:8])[0])
                else:
                    return
            elif typebyte == OPEN:
                buffer = rest
                self.openCount = b1282int(header)
                assert not self.inOpen
                self.inOpen = 1
            elif typebyte == CLOSE:
                buffer = rest
                count = b1282int(header)
                self.handleClose(count)
            elif typebyte == ABORT:
                buffer = rest
                count = b1282int(header)
                self.handleAbort(count)
                
            else:
                raise NotImplementedError(("Invalid Type Byte %s" % typebyte))
            #while listStack and (len(listStack[-1][1]) == listStack[-1][0]):
            #    item = listStack.pop()[1]
            #    gotItem(item)
        self.buffer = ''



    def describe(self):
        where = []
        for i in self.receiveStack:
            try:
                piece = i.describe()
            except:
                piece = "???"
            where.append(piece)
        return ".".join(where)

    def receivedObject(self, obj):
        """Decoded objects are delivered here, unless you use a RootUnslicer
        variant which does something else in its .childFinished method.
        """
        raise NotImplementedError

