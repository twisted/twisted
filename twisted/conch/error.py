# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Paul, why didn't you check in an error.py?

"""An error to represent bad things happening in Conch.

This module is unstable.

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
