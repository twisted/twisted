# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""Cred errors."""

class Unauthorized(Exception):
    """Standard unauthorized error."""

class DuplicateIdentity(KeyError):
    """There already exists an identity with that name."""
    # Descends from KeyError for backwards compatibility: That's what
    # DefaultAuthorizer.addIdentity used to raise.
    def __init__(self, name):
        KeyError.__init__(self, name)
        self.name = name

    def __repr__(self):
        return "<%s name %s>" % (self.__class__.__name__,
                                 repr(self.name))

    def __str__(self):
        return "There is already an identity named %s." % (self.name,)

class KeyNotFound(KeyError, Unauthorized):
    """None of the keys on your keyring seem to fit here."""
    def __init__(self, serviceName, perspectiveName):
        KeyError.__init__(self, (serviceName, perspectiveName))
        self.serviceName = serviceName
        self.perspectiveName = perspectiveName

    def __repr__(self):
        return "<%s (%r, %r)>" % (self.__class__.__name__,
                                  repr(self.serviceName),
                                  repr(self.perspectiveName))

    def __str__(self):
        return "No key for service %r, perspective %r." % (
            repr(self.serviceName), repr(self.perspectiveName))

### "New Cred" objects

class LoginFailed(Exception):
    """
    The user's request to log in failed for some reason.
    """

class UnauthorizedLogin(LoginFailed, Unauthorized):
    """The user was not authorized to log in.
    """

class UnhandledCredentials(LoginFailed):
    """A type of credentials were passed in with no knowledge of how to check
    them.  This is a server configuration error - it means that a protocol was
    connected to a Portal without a CredentialChecker that can check all of its
    potential authentication strategies.
    """

class LoginDenied(LoginFailed):
    """
    The realm rejected this login for some reason.
    
    Examples of reasons this might be raised include an avatar logging in
    too frequently, a quota having been fully used, or the overall server
    load being too high.
    """
