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

class IReferenceable(Interface):
    # TODO: really?
    """This object is remotely referenceable. This means it defines some
    remote_* methods and may have a schema which describes how those methods
    may be invoked.
    """
