# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Dropin module defining all of the plugins provided by Twisted core.
"""

import sys, warnings

from zope.interface import implements

from twisted.trial.itrial import IReporter
from twisted.plugin import IPlugin
from twisted.application.service import ServiceMaker
from twisted.application.reactors import Reactor, NoSuchReactor
from twisted.internet import defer
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.strcred import ICheckerFactory
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.checkers import FilePasswordDB
from twisted.cred.checkers import AllowAnonymousAccess
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import IAnonymous
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.credentials import IUsernameHashedPassword




def verifyCryptedPassword(crypted, pw):
    if crypted[0] == '$': # md5_crypt encrypted
        salt = '$1$' + crypted.split('$')[2]
    else:
        salt = crypted[:2]
    try:
        import crypt
    except ImportError:
        crypt = None

    if crypt is None:
        raise NotImplementedError("cred_unix not supported on this platform")
    return crypt.crypt(pw, salt) == crypted



class UNIXChecker(object):
    """
    A credentials checker for a UNIX server. This will check that
    an authenticating username/password is a valid user on the system.

    Does not work on Windows.

    Right now this supports Python's pwd and spwd modules, if they are
    installed. It does not support PAM.
    """
    implements(ICredentialsChecker)
    credentialInterfaces = (IUsernamePassword,)


    def checkPwd(self, pwd, username, password):
        try:
            cryptedPass = pwd.getpwnam(username)[1]
        except KeyError:
            return defer.fail(UnauthorizedLogin())
        else:
            if cryptedPass in ('*', 'x'):
                # Allow checkSpwd to take over
                return None
            elif verifyCryptedPassword(cryptedPass, password):
                return defer.succeed(username)


    def checkSpwd(self, spwd, username, password):
        try:
            cryptedPass = spwd.getspnam(username)[1]
        except KeyError:
            return defer.fail(UnauthorizedLogin())
        else:
            if verifyCryptedPassword(cryptedPass, password):
                return defer.succeed(username)


    def requestAvatarId(self, credentials):
        username, password = credentials.username, credentials.password

        try:
            import pwd
        except ImportError:
            pwd = None

        if pwd is not None:
            checked = self.checkPwd(pwd, username, password)
            if checked is not None:
                return checked

        try:
            import spwd
        except ImportError:
            spwd = None

        if spwd is not None:
            checked = self.checkSpwd(spwd, username, password)
            if checked is not None:
                return checked
        # TODO: check_pam?
        # TODO: check_shadow?
        return defer.fail(UnauthorizedLogin())



unixCheckerFactoryHelp = """
This checker will attempt to use every resource available to
authenticate against the list of users on the local UNIX system.
(This does not support Windows servers for very obvious reasons.)

Right now, this includes support for:

  * Python's pwd module (which checks /etc/passwd)
  * Python's spwd module (which checks /etc/shadow)

Future versions may include support for PAM authentication.
"""



class UNIXCheckerFactory(object):
    """
    A factory for L{UNIXChecker}.
    """
    implements(ICheckerFactory, IPlugin)
    authType = 'unix'
    authHelp = unixCheckerFactoryHelp
    argStringFormat = 'No argstring required.'
    credentialInterfaces = UNIXChecker.credentialInterfaces

    def generateChecker(self, argstring):
        """
        This checker factory ignores the argument string. Everything
        needed to generate a user database is pulled out of the local
        UNIX environment.
        """
        return UNIXChecker()



theUnixCheckerFactory = UNIXCheckerFactory()



inMemoryCheckerFactoryHelp = """
A checker that uses an in-memory user database.

This is only of use in one-off test programs or examples which
don't want to focus too much on how credentials are verified. You
really don't want to use this for anything else. It is a toy.
"""



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
    authHelp = inMemoryCheckerFactoryHelp
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



theInMemoryCheckerFactory = InMemoryCheckerFactory()

fileCheckerFactoryHelp = """
This checker expects to receive the location of a file that
conforms to the FilePasswordDB format. Each line in the file
should be of the format 'username:password', in plain text.
"""

invalidFileWarning = 'Warning: not a valid file'

class FileCheckerFactory(object):
    """
    A factory for instances of L{FilePasswordDB}.
    """
    implements(ICheckerFactory, IPlugin)
    authType = 'file'
    authHelp = fileCheckerFactoryHelp
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
            self.errorOutput.write('%s: %s\n' % (invalidFileWarning, argstring))
        return FilePasswordDB(argstring)



theFileCheckerFactory = FileCheckerFactory()
anonymousCheckerFactoryHelp = """
This allows anonymous authentication for servers that support it.
"""


class AnonymousCheckerFactory(object):
    """
    Generates checkers that will authenticate an anonymous request.
    """
    implements(ICheckerFactory, IPlugin)
    authType = 'anonymous'
    authHelp = anonymousCheckerFactoryHelp
    argStringFormat = 'No argstring required.'
    credentialInterfaces = (IAnonymous,)

    def generateChecker(self, argstring=''):
        return AllowAnonymousAccess()

theAnonymousCheckerFactory = AnonymousCheckerFactory()



class _Reporter(object):
    implements(IPlugin, IReporter)

    def __init__(self, name, module, description, longOpt, shortOpt, klass):
        self.name = name
        self.module = module
        self.description = description
        self.longOpt = longOpt
        self.shortOpt = shortOpt
        self.klass = klass


Tree = _Reporter("Tree Reporter",
                 "twisted.trial.reporter",
                 description="verbose color output (default reporter)",
                 longOpt="verbose",
                 shortOpt="v",
                 klass="TreeReporter")

BlackAndWhite = _Reporter("Black-And-White Reporter",
                          "twisted.trial.reporter",
                          description="Colorless verbose output",
                          longOpt="bwverbose",
                          shortOpt="o",
                          klass="VerboseTextReporter")

Minimal = _Reporter("Minimal Reporter",
                    "twisted.trial.reporter",
                    description="minimal summary output",
                    longOpt="summary",
                    shortOpt="s",
                    klass="MinimalReporter")

Classic = _Reporter("Classic Reporter",
                    "twisted.trial.reporter",
                    description="terse text output",
                    longOpt="text",
                    shortOpt="t",
                    klass="TextReporter")

Timing = _Reporter("Timing Reporter",
                   "twisted.trial.reporter",
                   description="Timing output",
                   longOpt="timing",
                   shortOpt=None,
                   klass="TimingTextReporter")


default = Reactor(
    'default', 'twisted.internet.default',
    'The best reactor for the current platform.')

select = Reactor(
    'select', 'twisted.internet.selectreactor', 'select(2)-based reactor.')
wx = Reactor(
    'wx', 'twisted.internet.wxreactor', 'wxPython integration reactor.')
gtk = Reactor(
    'gtk', 'twisted.internet.gtkreactor', 'Gtk1 integration reactor.')
gtk2 = Reactor(
    'gtk2', 'twisted.internet.gtk2reactor', 'Gtk2 integration reactor.')
glib2 = Reactor(
    'glib2', 'twisted.internet.glib2reactor',
    'GLib2 event-loop integration reactor.')
glade = Reactor(
    'debug-gui', 'twisted.manhole.gladereactor',
    'Semi-functional debugging/introspection reactor.')
win32er = Reactor(
    'win32', 'twisted.internet.win32eventreactor',
    'Win32 WaitForMultipleObjects-based reactor.')
poll = Reactor(
    'poll', 'twisted.internet.pollreactor', 'poll(2)-based reactor.')
epoll = Reactor(
    'epoll', 'twisted.internet.epollreactor', 'epoll(4)-based reactor.')
cf = Reactor(
    'cf' , 'twisted.internet.cfreactor',
    'CoreFoundation integration reactor.')
kqueue = Reactor(
    'kqueue', 'twisted.internet.kqreactor', 'kqueue(2)-based reactor.')
iocp = Reactor(
    'iocp', 'twisted.internet.iocpreactor',
    'Win32 IO Completion Ports-based reactor.')

wikiURL = 'http://twistedmatrix.com/trac/wiki/QTReactor'
errorMessage = ('qtreactor is no longer a part of Twisted due to licensing '
                'issues. Please see %s for details.' % (wikiURL,))

class QTStub(Reactor):
    """
    Reactor plugin which emits a deprecation warning on the successful
    installation of its reactor or a pointer to further information if an
    ImportError occurs while attempting to install it.
    """
    def __init__(self):
        super(QTStub, self).__init__(
            'qt', 'qtreactor', 'QT integration reactor')


    def install(self):
        """
        Install the Qt reactor with a deprecation warning or try to point
        the user to further information if it cannot be installed.
        """
        try:
            super(QTStub, self).install()
        except (ValueError, ImportError):
            raise NoSuchReactor(errorMessage)
        else:
            warnings.warn(
                "Please use -r qt3 to import qtreactor",
                category=DeprecationWarning)


qt = QTStub()


TwistedFTP = ServiceMaker(
    "Twisted FTP",
    "twisted.tap.ftp",
    "An FTP server.",
    "ftp")

TwistedPortForward = ServiceMaker(
    "Twisted Port-Forwarding",
    "twisted.tap.portforward",
    "A simple port-forwarder.",
    "portforward")

TwistedTelnet = ServiceMaker(
    "Twisted Telnet Shell Server",
    "twisted.tap.telnet",
    "A simple, telnet-based remote debugging service.",
    "telnet")

TwistedSOCKS = ServiceMaker(
    "Twisted SOCKS",
    "twisted.tap.socks",
    "A SOCKSv4 proxy service.",
    "socks")
