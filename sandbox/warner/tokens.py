#! /usr/bin/python

from twisted.python.failure import Failure
from twisted.python.components import Interface

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

    sendOpen = """True if an OPEN/CLOSE token pair should be sent around the
    Slicer's body tokens. Only special-purpose Slicers (like the RootSlicer)
    should use False."""

    trackReferences = """True if the object we slice is referenceable: i.e.
    it is useful or necessary to send multiple copies as a single instance
    and a bunch of References, rather than as separate copies. Instances are
    referenceable, as are mutable containers like lists."""

    def slice(self, streamable, banana):
        """Return an iterator which provides Index Tokens and the Body
        Tokens of the object's serialized form. This is frequently
        implemented with a generator (i.e. 'yield' appears in the body of
        this function). Do not yield the OPEN or the CLOSE token, those will
        be handled elsewhere.

        If a Violation exception is raised, slicing will cease. An ABORT
        token followed by a CLOSE token will be emitted."""

    def registerReference(self, refid, obj):
        """Register the relationship between 'refid' (a number taken from
        the cumulative count of OPEN tokens sent over our connection: 0 is
        the object described by the very first OPEN sent over the wire) and
        the object. If the object is sent a second time, a Reference may be
        used in its place.

        Slicers usually delgate this function upwards to the RootSlicer, but
        it can be handled at any level to allow local scoping of references
        (they might only be valid within a single RPC invocation, for
        example)."""

    def childAborted(self):
        """Notify the Slicer that one of its child tokens (as produced by
        its .slice iterator) emitted an ABORT token, terminating their token
        stream. The corresponding Unslicer (receiving this token stream)
        will get an UnbananaFailure and is likely to ignore any remaining
        tokens from us, so it may be reasonable to emit an ABORT of our own
        here.
        """

    def slicerForObject(self, obj):
        """Get a new Slicer for some child object. Slicers usually delegate
        this method up to the RootSlicer. References are handled by
        producing a ReferenceSlicer here. These references can have various
        scopes.

        If something on the stack does not want the object to be sent, it can
        raise a Violation exception. This is the 'taster' function."""


class IReferenceable(Interface):
    # TODO: really?
    """This object is remotely referenceable. This means it defines some
    remote_* methods and may have a schema which describes how those methods
    may be invoked.
    """
