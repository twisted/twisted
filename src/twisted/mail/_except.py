# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Exceptions in L{twisted.mail}.
"""

from __future__ import absolute_import, division


class IMAP4Exception(Exception):
    pass


class IllegalClientResponse(IMAP4Exception):
    pass



class IllegalOperation(IMAP4Exception):
    pass



class IllegalMailboxEncoding(IMAP4Exception):
    pass
