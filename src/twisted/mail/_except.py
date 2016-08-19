"""
Exceptions in L{twisted.mail}.
"""

from __future__ import absolute_import, division

class IMAP4Exception(Exception):
    def __init__(self, *args):
        Exception.__init__(self, *args)

class IllegalClientResponse(IMAP4Exception): pass

class IllegalOperation(IMAP4Exception): pass

class IllegalMailboxEncoding(IMAP4Exception): pass
