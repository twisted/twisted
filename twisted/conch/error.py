# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An error to represent bad things happening in Conch.

Maintainer: Paul Swartz
"""


class ConchError(Exception):
    def __init__(self, value, data = None):
        Exception.__init__(self, value, data)
        self.value = value
        self.data = data



class NotEnoughAuthentication(Exception):
    """
    This is thrown if the authentication is valid, but is not enough to
    successfully verify the user.  i.e. don't retry this type of
    authentication, try another one.
    """



class ValidPublicKey(Exception):
    """
    This is thrown during the authentication process if the public key is valid
    for the user.
    """



class IgnoreAuthentication(Exception):
    """
    This is thrown to let the UserAuthServer know it doesn't need to handle the
    authentication anymore.
    """



class MissingKeyStoreError(Exception):
    """
    Raised if an SSHAgentServer starts receiving data without its factory
    providing a keys dict on which to read/write key data.
    """



class UserRejectedKey(Exception):
    """
    The user interactively rejected a key.
    """



class InvalidEntry(Exception):
    """
    An entry in a known_hosts file could not be interpreted as a valid entry.
    """



class HostKeyChanged(Exception):
    """
    The host key of a remote host has changed.

    @ivar offendingEntry: The entry which contains the persistent host key that
    disagrees with the given host key.

    @type offendingEntry: L{twisted.conch.interfaces.IKnownHostEntry}

    @ivar path: a reference to the known_hosts file that the offending entry
    was loaded from

    @type path: L{twisted.python.filepath.FilePath}

    @ivar lineno: The line number of the offending entry in the given path.

    @type lineno: L{int}
    """
    def __init__(self, offendingEntry, path, lineno):
        Exception.__init__(self)
        self.offendingEntry = offendingEntry
        self.path = path
        self.lineno = lineno
