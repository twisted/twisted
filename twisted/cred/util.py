# -*- test-case-name: twisted.test.test_newcred -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Outdated, deprecated functionality related to challenge-based authentication.

Seek a solution to your problem elsewhere.  This module is deprecated.
"""

# System Imports
import random, warnings

from twisted.python.hashlib import md5
from twisted.cred.error import Unauthorized


def respond(challenge, password):
    """Respond to a challenge.
    This is useful for challenge/response authentication.
    """
    warnings.warn(
        "twisted.cred.util.respond is deprecated since Twisted 8.3.",
        category=PendingDeprecationWarning,
        stacklevel=2)
    m = md5()
    m.update(password)
    hashedPassword = m.digest()
    m = md5()
    m.update(hashedPassword)
    m.update(challenge)
    doubleHashedPassword = m.digest()
    return doubleHashedPassword

def challenge():
    """I return some random data.
    """
    warnings.warn(
        "twisted.cred.util.challenge is deprecated since Twisted 8.3.",
        category=PendingDeprecationWarning,
        stacklevel=2)
    crap = ''
    for x in range(random.randrange(15,25)):
        crap = crap + chr(random.randint(65,90))
    crap = md5(crap).digest()
    return crap
