
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Utility functions for authorization.

These are currently for challenge-response shared secret authentication.

Maintainer: Glyph Lefkowitz
"""

# System Imports
import md5
import random

from twisted.cred.error import Unauthorized

def respond(challenge, password):
    """Respond to a challenge.
    This is useful for challenge/response authentication.
    """
    m = md5.new()
    m.update(password)
    hashedPassword = m.digest()
    m = md5.new()
    m.update(hashedPassword)
    m.update(challenge)
    doubleHashedPassword = m.digest()
    return doubleHashedPassword

def challenge():
    """I return some random data.
    """
    crap = ''
    for x in range(random.randrange(15,25)):
        crap = crap + chr(random.randint(65,90))
    crap = md5.new(crap).digest()
    return crap
