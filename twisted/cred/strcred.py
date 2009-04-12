# -*- test-case-name: twisted.test.test_strcred -*-
#
# Copyright (c) 2007-2008 Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""
Support for resolving command-line strings that represent different
checkers available to cred.

Examples:
 - passwd:/etc/passwd
 - memory:admin:asdf:user:lkj
 - unix
"""

import sys

from zope.interface import Interface, Attribute, implements

from twisted.plugin import IPlugin, getPlugins
from twisted.python import usage
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.checkers import UNIXChecker, FilePasswordDB, AllowAnonymousAccess
from twisted.cred.credentials import IAnonymous, IUsernamePassword, IUsernameHashedPassword


class ICheckerFactory(Interface):
    """
    A factory for objects which provide
    L{twisted.cred.checkers.ICredentialsChecker}.

    It's implemented by twistd plugins creating checkers.
    """

    authType = Attribute(
        'A tag that identifies the authentication method.')


    authHelp = Attribute(
        'A detailed (potentially multi-line) description of precisely '
        'what functionality this CheckerFactory provides.')


    argStringFormat = Attribute(
        'A short (one-line) description of the argument string format.')


    credentialInterfaces = Attribute(
        'A list of credentials interfaces that this factory will support.')


    def generateChecker(argstring):
        """
        Return an L{ICredentialChecker} provider using the supplied
        argument string.
        """



class StrcredException(Exception):
    """
    Base exception class for strcred.
    """



class InvalidAuthType(StrcredException):
    """
    Raised when a user provides an invalid identifier for the
    authentication plugin (known as the authType).
    """



class InvalidAuthArgumentString(StrcredException):
    """
    Raised by an authentication plugin when the argument string
    provided is formatted incorrectly.
    """



class UnsupportedInterfaces(StrcredException):
    """
    Raised when an application is given a checker to use that does not
    provide any of the application's supported credentials interfaces.
    """



# This will be used to warn the users whenever they view help for an
# authType that is not supported by the application.
notSupportedWarning = ("WARNING: This authType is not supported by "
                       "this application.")



def findCheckerFactories():
    """
    Find all plugin objects that provide L{ICheckerFactory}.
    """
    return getPlugins(ICheckerFactory)



def findCheckerFactory(authType):
    """
    Find the first checker factory that supports the given authType.
    """
    for factory in findCheckerFactories():
        if factory.authType == authType:
            return factory
    raise InvalidAuthType(authType)



def makeChecker(description):
    """
    Returns an L{twisted.cred.checkers.ICredentialsChecker} based on the
    contents of a descriptive string. Similar to
    L{twisted.application.strports}.
    """
    if ':' in description:
        authType, argstring = description.split(':', 1)
    else:
        authType = description
        argstring = ''
    return findCheckerFactory(authType).generateChecker(argstring)



class AuthOptionMixin:
    """
    Defines helper methods that can be added on to any
    L{usage.Options} subclass that needs authentication.

    This mixin implements three new options methods:

    The opt_auth method (--auth) will write two new values to the
    'self' dictionary: C{credInterfaces} (a dict of lists) and
    C{credCheckers} (a list).

    The opt_help_auth method (--help-auth) will search for all
    available checker plugins and list them for the user; it will exit
    when finished.

    The opt_help_auth_type method (--help-auth-type) will display
    detailed help for a particular checker plugin.

    @cvar supportedInterfaces: An iterable object that returns
       credential interfaces which this application is able to support.

    @cvar authOutput: A writeable object to which this options class
        will send all help-related output. Default: L{sys.stdout}
    """

    supportedInterfaces = None
    authOutput = sys.stdout


    def supportsInterface(self, interface):
        """
        Returns whether a particular credentials interface is supported.
        """
        return (self.supportedInterfaces is None
                or interface in self.supportedInterfaces)


    def supportsCheckerFactory(self, factory):
        """
        Returns whether a checker factory will provide at least one of
        the credentials interfaces that we care about.
        """
        for interface in factory.credentialInterfaces:
            if self.supportsInterface(interface):
                return True
        return False


    def addChecker(self, checker):
        """
        Supply a supplied credentials checker to the Options class.
        """
        # First figure out which interfaces we're willing to support.
        supported = []
        if self.supportedInterfaces is None:
            supported = checker.credentialInterfaces
        else:
            for interface in checker.credentialInterfaces:
                if self.supportsInterface(interface):
                    supported.append(interface)
        if not supported:
            raise UnsupportedInterfaces(checker.credentialInterfaces)
        # If we get this far, then we know we can use this checker.
        if 'credInterfaces' not in self:
            self['credInterfaces'] = {}
        if 'credCheckers' not in self:
            self['credCheckers'] = []
        self['credCheckers'].append(checker)
        for interface in supported:
            self['credInterfaces'].setdefault(interface, []).append(checker)


    def opt_auth(self, description):
        """
        Specify an authentication method for the server.
        """
        try:
            self.addChecker(makeChecker(description))
        except UnsupportedInterfaces, e:
            raise usage.UsageError(
                'Auth plugin not supported: %s' % e.args[0])
        except InvalidAuthType, e:
            raise usage.UsageError(
                'Auth plugin not recognized: %s' % e.args[0])
        except Exception, e:
            raise usage.UsageError('Unexpected error: %s' % e)


    def _checkerFactoriesForOptHelpAuth(self):
        """
        Return a list of which authTypes will be displayed by --help-auth.
        This makes it a lot easier to test this module.
        """
        for factory in findCheckerFactories():
            for interface in factory.credentialInterfaces:
                if self.supportsInterface(interface):
                    yield factory
                    break


    def opt_help_auth(self):
        """
        Show all authentication methods available.
        """
        self.authOutput.write("Usage: --auth AuthType[:ArgString]\n")
        self.authOutput.write("For detailed help: --help-auth-type AuthType\n")
        self.authOutput.write('\n')
        # Figure out the right width for our columns
        firstLength = 0
        for factory in self._checkerFactoriesForOptHelpAuth():
            if len(factory.authType) > firstLength:
                firstLength = len(factory.authType)
        formatString = '  %%-%is\t%%s\n' % firstLength
        self.authOutput.write(formatString % ('AuthType', 'ArgString format'))
        self.authOutput.write(formatString % ('========', '================'))
        for factory in self._checkerFactoriesForOptHelpAuth():
            self.authOutput.write(
                formatString % (factory.authType, factory.argStringFormat))
        self.authOutput.write('\n')
        raise SystemExit(0)


    def opt_help_auth_type(self, authType):
        """
        Show help for a particular authentication type.
        """
        try:
            cf = findCheckerFactory(authType)
        except InvalidAuthType:
            raise usage.UsageError("Invalid auth type: %s" % authType)
        self.authOutput.write("Usage: --auth %s[:ArgString]\n" % authType)
        self.authOutput.write("ArgString format: %s\n" % cf.argStringFormat)
        self.authOutput.write('\n')
        for line in cf.authHelp.strip().splitlines():
            self.authOutput.write('  %s\n' % line.rstrip())
        self.authOutput.write('\n')
        if not self.supportsCheckerFactory(cf):
            self.authOutput.write('  %s\n' % notSupportedWarning)
            self.authOutput.write('\n')
        raise SystemExit(0)



class UNIXCheckerFactory(object):
    """
    A factory for L{UNIXChecker}.
    """
    implements(ICheckerFactory, IPlugin)
    authType = 'unix'
    authHelp = """
This checker will attempt to use every resource available to
authenticate against the list of users on the local UNIX system.
(This does not support Windows servers for very obvious reasons.)

Right now, this includes support for:

  * Python's pwd module (which checks /etc/passwd)
  * Python's spwd module (which checks /etc/shadow)

Future versions may include support for PAM authentication.
"""
    argStringFormat = 'No argstring required.'
    credentialInterfaces = UNIXChecker.credentialInterfaces

    def generateChecker(self, argstring):
        """
        This checker factory ignores the argument string. Everything
        needed to generate a user database is pulled out of the local
        UNIX environment.
        """
        return UNIXChecker()



class InMemoryCheckerFactory(object):
    """
    A factory for in-memory credentials checkers.

    This is only of use in one-off test programs or examples which don't
    want to focus too much on how credentials are verified.

    You really don't want to use this for anything else.  It is, at best, a
    toy.  If you need a simple credentials checker for a real application,
    see L{cred_passwd.PasswdCheckerFactory}.
    """
    implements(ICheckerFactory, IPlugin)
    authType = 'memory'
    authHelp = """
A checker that uses an in-memory user database.

This is only of use in one-off test programs or examples which
don't want to focus too much on how credentials are verified. You
really don't want to use this for anything else. It is a toy.
"""
    argStringFormat = 'A colon-separated list (name:password:...)'
    credentialInterfaces = (IUsernamePassword, IUsernameHashedPassword)

    def generateChecker(self, argstring):
        """
        This checker factory expects to get a list of
        username:password pairs, with each pair also separated by a
        colon. For example, the string 'alice:f:bob:g' would generate
        two users, one named 'alice' and one named 'bob'.
        """
        checker = InMemoryUsernamePasswordDatabaseDontUse()
        if argstring:
            pieces = argstring.split(':')
            if len(pieces) % 2:
                from twisted.cred.strcred import InvalidAuthArgumentString
                raise InvalidAuthArgumentString(
                    "argstring must be in format U:P:...")
            for i in range(0, len(pieces), 2):
                username, password = pieces[i], pieces[i+1]
                checker.addUser(username, password)
        return checker


_invalidFileWarning = 'Warning: not a valid file'

class FileCheckerFactory(object):
    """
    A factory for instances of L{FilePasswordDB}.
    """
    implements(ICheckerFactory, IPlugin)
    authType = 'file'
    authHelp = """
This checker expects to receive the location of a file that
conforms to the FilePasswordDB format. Each line in the file
should be of the format 'username:password', in plain text.
"""
    argStringFormat = 'Location of a FilePasswordDB-formatted file.'
    # Explicitly defined here because FilePasswordDB doesn't do it for us
    credentialInterfaces = (IUsernamePassword, IUsernameHashedPassword)

    errorOutput = sys.stderr

    def generateChecker(self, argstring):
        """
        This checker factory expects to get the location of a file.
        The file should conform to the format required by
        L{FilePasswordDB} (using defaults for all
        initialization parameters).
        """
        from twisted.python.filepath import FilePath
        if not argstring.strip():
            raise ValueError, '%r requires a filename' % self.authType
        elif not FilePath(argstring).isfile():
            self.errorOutput.write('%s: %s\n' % (_invalidFileWarning, argstring))
        return FilePasswordDB(argstring)



class AnonymousCheckerFactory(object):
    """
    Generates checkers that will authenticate an anonymous request.
    """
    implements(ICheckerFactory, IPlugin)
    authType = 'anonymous'
    authHelp = """
This allows anonymous authentication for servers that support it.
"""
    argStringFormat = 'No argstring required.'
    credentialInterfaces = (IAnonymous,)

    def generateChecker(self, argstring=''):
        return AllowAnonymousAccess()
