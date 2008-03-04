# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Paul, why didn't you check in an error.py?

"""
An error to represent bad things happening in Conch.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

class ConchError(Exception):
    def __init__(self, value, data = None):
        Exception.__init__(self, value, data)
        self.value = value
        self.data = data

class NotEnoughAuthentication(Exception):
    """This is thrown if the authentication is valid, but is not enough to
    successfully verify the user.  i.e. don't retry this type of
    authentication, try another one.
    """

class ValidPublicKey(Exception):
    """This is thrown during the authentication process if the public key
    is valid for the user.
    """

class IgnoreAuthentication(Exception):
    """This is thrown to let the UserAuthServer know it doesn't need to handle
    the authentication anymore.
    """
