#! /usr/bin/python

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
    pass


class BananaError(Exception):
    """This exception is raised in response to a fundamental protocol
    violation. The connection should be dropped immediately.

    .why is a string that describes what kind of violation occurred
    
    .where is an optional string that describes the node of the object graph
    where the failure was noticed.
    """

    def __init__(self, why, where="?"):
        self.why = why
        self.where = where

    def __str__(self):
        return "BananaError(in %s): %s" % (self.where, self.why)

class BananaError2(BananaError):
    """This exception is raised when something else goes wrong during the
    unserialization process. This catches arbitrary exceptions in Unslicer
    methods.

    This exists solely to add the .where attribute to the raised exception.
    """

    def __str__(self):
        return "BananaError2(in %s): %s" % (self.where, self.why)

class IReferenceable(Interface):
    # TODO: really?
    """This object is remotely referenceable. This means it defines some
    remote_* methods and may have a schema which describes how those methods
    may be invoked.
    """
