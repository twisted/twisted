#! /usr/bin/python

from twisted.python.failure import Failure
from zope.interface import Attribute, Interface

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

tokenNames = {
    LIST: "LIST",
    INT: "INT",
    STRING: "STRING",
    NEG: "NEG",
    FLOAT: "FLOAT",
    LONGINT: "LONGINT",
    LONGNEG: "LONGNEG",
    VOCAB: "VOCAB",
    OPEN: "OPEN",
    CLOSE: "CLOSE",
    ABORT: "ABORT",
    }

SIZE_LIMIT = 1000 # default limit on the body length of long tokens (STRING,
                  # LONGINT, LONGNEG)

class Violation(Exception):
    """This exception is raised in response to a schema violation. It
    indicates that the incoming token stream has violated a constraint
    imposed by the recipient. The current Unslicer is abandoned and the
    error is propagated upwards to the enclosing Unslicer parent by
    providing an UnbananaFailure object to the parent's .receiveChild
    method. All remaining tokens for the current Unslicer are to be dropped.
    """

    """.failure: when a child raises a Violation, the parent's
    .receiveChild() will get a UnbananaFailure() that wraps it. If the
    parent wants to propagate the failure up towards the root, it should
    take that UbF and raise a Violation(failure=ubf). This tells the
    unbanana code to use the original UbF instead of creating a nest of
    Violation/UbFs as deep as the current serialization stack.
    """

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args)
        self.failure = kwargs.get("failure", None)



class BananaError(Exception):
    """This exception is raised in response to a fundamental protocol
    violation. The connection should be dropped immediately.

    .why is a string that describes what kind of violation occurred
    
    .where is an optional string that describes the node of the object graph
    where the failure was noticed.
    """

    def __init__(self, why, where=None):
        self.why = why
        self.where = where

    def __str__(self):
        if self.where:
            return "BananaError(in %s): %s" % (self.where, self.why)
        else:
            return "BananaError: %s" % (self.where,)

class UnbananaFailure(Failure):
    """This subclass of Failure adds a .where attribute which records the
    object-graph pathname where the problem occurred. It indicates a
    recoverable failure (one which will cause the containing sub-tree to be
    discarded but which does not require the connection be dropped).
    """

    def __init__(self, exc, where):
        self.where = where
        Failure.__init__(self, exc)

    def __str__(self):
        return "[UnbananaFailure in %s: %s]" % (self.where,
                                                self.getBriefTraceback())

class ISlicer(Interface):
    """I know how to slice objects into tokens."""

    sendOpen = Attribute("True if an OPEN/CLOSE token pair should be sent around the Slicer's body tokens. Only special-purpose Slicers (like the RootSlicer) should use False.")

    trackReferences = Attribute("True if the object we slice is referenceable: i.e. it is useful or necessary to send multiple copies as a single instance and a bunch of References, rather than as separate copies. Instances are referenceable, as are mutable containers like lists.")

    def slice(streamable, banana):
        """Return an iterator which provides Index Tokens and the Body
        Tokens of the object's serialized form. This is frequently
        implemented with a generator (i.e. 'yield' appears in the body of
        this function). Do not yield the OPEN or the CLOSE token, those will
        be handled elsewhere.

        If a Violation exception is raised, slicing will cease. An ABORT
        token followed by a CLOSE token will be emitted."""

    def registerReference(refid, obj):
        """Register the relationship between 'refid' (a number taken from
        the cumulative count of OPEN tokens sent over our connection: 0 is
        the object described by the very first OPEN sent over the wire) and
        the object. If the object is sent a second time, a Reference may be
        used in its place.

        Slicers usually delgate this function upwards to the RootSlicer, but
        it can be handled at any level to allow local scoping of references
        (they might only be valid within a single RPC invocation, for
        example)."""

    def childAborted(v):
        """Notify the Slicer that one of its child tokens (as produced by
        its .slice iterator) emitted an ABORT token, terminating their token
        stream. The corresponding Unslicer (receiving this token stream)
        will get an UnbananaFailure and is likely to ignore any remaining
        tokens from us, so it may be reasonable to emit an ABORT of our own
        here.
        """

    def slicerForObject(obj):
        """Get a new Slicer for some child object. Slicers usually delegate
        this method up to the RootSlicer. References are handled by
        producing a ReferenceSlicer here. These references can have various
        scopes.

        If something on the stack does not want the object to be sent, it can
        raise a Violation exception. This is the 'taster' function."""


class IUnslicer(Interface):
    # .parent

    # start/receiveChild/receiveClose/finish are
    # the main "here are some tokens, make an object out of them" entry
    # points used by Unbanana.

    # start/receiveChild can call self.protocol.abandonUnslicer(failure,
    # self) to tell the protocol that the unslicer has given up on life and
    # all its remaining tokens should be discarded. The failure will be
    # given to the late unslicer's parent in lieu of the object normally
    # returned by receiveClose.
    
    # start/receiveChild/receiveClose/finish may raise a Violation
    # exception, which tells the protocol that this object is contaminated
    # and should be abandoned. An UnbananaFailure will be passed to its
    # parent.

    # Note, however, that it is not valid to both call abandonUnslicer *and*
    # raise a Violation. That would discard too much.

    def setConstraint(constraint):
        """Add a constraint for this unslicer. The unslicer will enforce
        this constraint upon all incoming data. The constraint must be of an
        appropriate type (a ListUnslicer will only accept a ListConstraint,
        etc.). It must not be None. To leave us unconstrained, do not call
        this method.

        If this method is not called, the Unslicer will accept any valid
        banana as input, which probably means there is no limit on the
        number of bytes it will accept (and therefore on the memory it could
        be made to consume) before it finally accepts or rejects the input.
        """

    def start(count):
        """Called to initialize the new slice. The 'count' argument is the
        reference id: if this object might be shared (and therefore the
        target of a 'reference' token), it should call
        self.protocol.setObject(count, obj) with the object being created.
        If this object is not available yet (tuples), it should save a
        Deferred there instead.
        """

    def checkToken(typebyte, size):
        """Check to see if the given token is acceptable (does it conform to
        the constraint?). It will not be asked about ABORT or CLOSE tokens,
        but it *will* be asked about OPEN. It should enfore a length limit
        for long tokens (STRING and LONGINT/LONGNEG types). If STRING is
        acceptable, then VOCAB should be too. It should return None if the
        token and the size are acceptable. Should raise Violation if the
        schema indiates the token is not acceptable. Should raise
        BananaError if the type byte violates the basic Banana protocol. (if
        no schema is in effect, this should never raise Violation, but might
        still raise BananaError).
        """

    def openerCheckToken(typebyte, size, opentype):
        """'typebyte' is the type of an incoming index token. 'size' is the
        value of header associated with this typebyte. 'opentype' is a list
        of open tokens that we've received so far, not including the one
        that this token hopes to create.

        This method should ask the current opener if this index token is
        acceptable, and is used in lieu of checkToken() when the receiver is
        in the index phase. Usually implemented by calling
        self.opener.openerCheckToken, thus delegating the question to the
        RootUnslicer.
        """

    def doOpen(opentype):
        """opentype is a tuple. Return None if more index tokens are
        required. Check to see if this kind of child object conforms to the
        constraint, raise Violation if not. Create a new Unslicer (usually
        by delegating to self.parent.doOpen, up to the RootUnslicer). Set a
        constraint on the child unslicer, if any.
        """

    def receiveChild(childobject):
        """'childobject' is being handed to this unslicer. It may be a
        primitive type (number or string), or a composite type produced by
        another Unslicer. It might be an UnbananaFailure if something went
        wrong, in which case it may be appropriate to do
        self.protocol.abandonUnslicer(failure, self). It might also be a
        Deferred, in which case you should add a callback that will fill in
        the appropriate object later."""

    def receiveClose(self):
        """Called when the Close token is received. Should return the object
        just created, or an UnbananaFailure if something went wrong. If
        necessary, unbanana.setObject should be called, then the Deferred
        created in start() should be fired with the new object."""

    def finish(self):
        """Called when the unslicer is popped off the stack. This is called
        even if the pop is because of an exception. The unslicer should
        perform cleanup, including firing the Deferred with an
        UnbananaFailure if the object it is creating could not be created.

        TODO: can receiveClose and finish be merged? Or should the child
        object be returned from finish() instead of receiveClose?
        """

    def describeSelf(self):
        """Return a short string describing where in the object tree this
        unslicer is sitting, relative to its parent. These strings are
        obtained from every unslicer in the stack, and joined to describe
        where any problems occurred."""

    def where(self):
        """This returns a string that describes the location of this
        unslicer, starting at the root of the object tree."""

class IReferenceable(Interface):
    # TODO: really?
    """This object is remotely referenceable. This means it defines some
    remote_* methods and may have a schema which describes how those methods
    may be invoked.
    """
