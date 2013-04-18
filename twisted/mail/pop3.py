# -*- test-case-name: twisted.mail.test.test_pop3 -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Post-office Protocol version 3

@author: Glyph Lefkowitz
@author: Jp Calderone
"""

import base64
import binascii
import warnings
from hashlib import md5

from zope.interface import implements, Interface

from twisted.mail import smtp
from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import task
from twisted.internet import defer
from twisted.internet import interfaces
from twisted.python import log

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials

##
## Authentication
##
class APOPCredentials:
    implements(cred.credentials.IUsernamePassword)

    def __init__(self, magic, username, digest):
        self.magic = magic
        self.username = username
        self.digest = digest

    def checkPassword(self, password):
        seed = self.magic + password
        myDigest = md5(seed).hexdigest()
        return myDigest == self.digest


class _HeadersPlusNLines:
    def __init__(self, f, n):
        self.f = f
        self.n = n
        self.linecount = 0
        self.headers = 1
        self.done = 0
        self.buf = ''

    def read(self, bytes):
        if self.done:
            return ''
        data = self.f.read(bytes)
        if not data:
            return data
        if self.headers:
            df, sz = data.find('\r\n\r\n'), 4
            if df == -1:
                df, sz = data.find('\n\n'), 2
            if df != -1:
                df += sz
                val = data[:df]
                data = data[df:]
                self.linecount = 1
                self.headers = 0
        else:
            val = ''
        if self.linecount > 0:
            dsplit = (self.buf+data).split('\n')
            self.buf = dsplit[-1]
            for ln in dsplit[:-1]:
                if self.linecount > self.n:
                    self.done = 1
                    return val
                val += (ln + '\n')
                self.linecount += 1
            return val
        else:
            return data



class _POP3MessageDeleted(Exception):
    """
    Internal control-flow exception.  Indicates the file of a deleted message
    was requested.
    """


class POP3Error(Exception):
    pass



class _IteratorBuffer(object):
    bufSize = 0

    def __init__(self, write, iterable, memoryBufferSize=None):
        """
        Create a _IteratorBuffer.

        @param write: A one-argument callable which will be invoked with a list
        of strings which have been buffered.

        @param iterable: The source of input strings as any iterable.

        @param memoryBufferSize: The upper limit on buffered string length,
        beyond which the buffer will be flushed to the writer.
        """
        self.lines = []
        self.write = write
        self.iterator = iter(iterable)
        if memoryBufferSize is None:
            memoryBufferSize = 2 ** 16
        self.memoryBufferSize = memoryBufferSize


    def __iter__(self):
        return self


    def next(self):
        try:
            v = self.iterator.next()
        except StopIteration:
            if self.lines:
                self.write(self.lines)
            # Drop some references, in case they're edges in a cycle.
            del self.iterator, self.lines, self.write
            raise
        else:
            if v is not None:
                self.lines.append(v)
                self.bufSize += len(v)
                if self.bufSize > self.memoryBufferSize:
                    self.write(self.lines)
                    self.lines = []
                    self.bufSize = 0



def iterateLineGenerator(proto, gen):
    """
    Hook the given protocol instance up to the given iterator with an
    _IteratorBuffer and schedule the result to be exhausted via the protocol.

    @type proto: L{POP3}
    @type gen: iterator
    @rtype: L{twisted.internet.defer.Deferred}
    """
    coll = _IteratorBuffer(proto.transport.writeSequence, gen)
    return proto.schedule(coll)



def successResponse(response):
    """
    Format the given object as a positive response.
    """
    response = str(response)
    return '+OK %s\r\n' % (response,)



def formatStatResponse(msgs):
    """
    Format the list of message sizes appropriately for a STAT response.

    Yields None until it finishes computing a result, then yields a str
    instance that is suitable for use as a response to the STAT command.
    Intended to be used with a L{twisted.internet.task.Cooperator}.
    """
    i = 0
    bytes = 0
    for size in msgs:
        i += 1
        bytes += size
        yield None
    yield successResponse('%d %d' % (i, bytes))



def formatListLines(msgs):
    """
    Format a list of message sizes appropriately for the lines of a LIST
    response.

    Yields str instances formatted appropriately for use as lines in the
    response to the LIST command.  Does not include the trailing '.'.
    """
    i = 0
    for size in msgs:
        i += 1
        yield '%d %d\r\n' % (i, size)



def formatListResponse(msgs):
    """
    Format a list of message sizes appropriately for a complete LIST response.

    Yields str instances formatted appropriately for use as a LIST command
    response.
    """
    yield successResponse(len(msgs))
    for ele in formatListLines(msgs):
        yield ele
    yield '.\r\n'



def formatUIDListLines(msgs, getUidl):
    """
    Format the list of message sizes appropriately for the lines of a UIDL
    response.

    Yields str instances formatted appropriately for use as lines in the
    response to the UIDL command.  Does not include the trailing '.'.
    """
    for i, m in enumerate(msgs):
        if m is not None:
            uid = getUidl(i)
            yield '%d %s\r\n' % (i + 1, uid)



def formatUIDListResponse(msgs, getUidl):
    """
    Format a list of message sizes appropriately for a complete UIDL response.

    Yields str instances formatted appropriately for use as a UIDL command
    response.
    """
    yield successResponse('')
    for ele in formatUIDListLines(msgs, getUidl):
        yield ele
    yield '.\r\n'



class POP3(basic.LineOnlyReceiver, policies.TimeoutMixin):
    """
    POP3 server protocol implementation.

    @ivar portal: A reference to the L{twisted.cred.portal.Portal} instance we
    will authenticate through.

    @ivar factory: A L{twisted.mail.pop3.IServerFactory} which will be used to
    determine some extended behavior of the server.

    @ivar timeOut: An integer which defines the minimum amount of time which
    may elapse without receiving any traffic after which the client will be
    disconnected.

    @ivar schedule: A one-argument callable which should behave like
    L{twisted.internet.task.coiterate}.
    """
    implements(interfaces.IProducer)

    magic = None
    _userIs = None
    _onLogout = None

    AUTH_CMDS = ['CAPA', 'USER', 'PASS', 'APOP', 'AUTH', 'RPOP', 'QUIT']

    portal = None
    factory = None

    # The mailbox we're serving
    mbox = None

    # Set this pretty low -- POP3 clients are expected to log in, download
    # everything, and log out.
    timeOut = 300

    # Current protocol state
    state = "COMMAND"

    # PIPELINE
    blocked = None

    # Cooperate and suchlike.
    schedule = staticmethod(task.coiterate)

    # Message index of the highest retrieved message.
    _highest = 0

    def connectionMade(self):
        if self.magic is None:
            self.magic = self.generateMagic()
        self.successResponse(self.magic)
        self.setTimeout(self.timeOut)
        if getattr(self.factory, 'noisy', True):
            log.msg("New connection from " + str(self.transport.getPeer()))


    def connectionLost(self, reason):
        if self._onLogout is not None:
            self._onLogout()
            self._onLogout = None
        self.setTimeout(None)


    def generateMagic(self):
        return smtp.messageid()


    def successResponse(self, message=''):
        self.transport.write(successResponse(message))

    def failResponse(self, message=''):
        self.sendLine('-ERR ' + str(message))

#    def sendLine(self, line):
#        print 'S:', repr(line)
#        basic.LineOnlyReceiver.sendLine(self, line)

    def lineReceived(self, line):
#        print 'C:', repr(line)
        self.resetTimeout()
        getattr(self, 'state_' + self.state)(line)

    def _unblock(self, _):
        commands = self.blocked
        self.blocked = None
        while commands and self.blocked is None:
            cmd, args = commands.pop(0)
            self.processCommand(cmd, *args)
        if self.blocked is not None:
            self.blocked.extend(commands)

    def state_COMMAND(self, line):
        try:
            return self.processCommand(*line.split(' '))
        except (ValueError, AttributeError, POP3Error, TypeError), e:
            log.err()
            self.failResponse('bad protocol or server: %s: %s' % (e.__class__.__name__, e))

    def processCommand(self, command, *args):
        if self.blocked is not None:
            self.blocked.append((command, args))
            return

        command = command.upper()
        authCmd = command in self.AUTH_CMDS
        if not self.mbox and not authCmd:
            raise POP3Error("not authenticated yet: cannot do " + command)
        f = getattr(self, 'do_' + command, None)
        if f:
            return f(*args)
        raise POP3Error("Unknown protocol command: " + command)


    def listCapabilities(self):
        baseCaps = [
            "TOP",
            "USER",
            "UIDL",
            "PIPELINE",
            "CELERITY",
            "AUSPEX",
            "POTENCE",
        ]

        if IServerFactory.providedBy(self.factory):
            # Oh my god.  We can't just loop over a list of these because
            # each has spectacularly different return value semantics!
            try:
                v = self.factory.cap_IMPLEMENTATION()
            except NotImplementedError:
                pass
            except:
                log.err()
            else:
                baseCaps.append("IMPLEMENTATION " + str(v))

            try:
                v = self.factory.cap_EXPIRE()
            except NotImplementedError:
                pass
            except:
                log.err()
            else:
                if v is None:
                    v = "NEVER"
                if self.factory.perUserExpiration():
                    if self.mbox:
                        v = str(self.mbox.messageExpiration)
                    else:
                        v = str(v) + " USER"
                v = str(v)
                baseCaps.append("EXPIRE " + v)

            try:
                v = self.factory.cap_LOGIN_DELAY()
            except NotImplementedError:
                pass
            except:
                log.err()
            else:
                if self.factory.perUserLoginDelay():
                    if self.mbox:
                        v = str(self.mbox.loginDelay)
                    else:
                        v = str(v) + " USER"
                v = str(v)
                baseCaps.append("LOGIN-DELAY " + v)

            try:
                v = self.factory.challengers
            except AttributeError:
                pass
            except:
                log.err()
            else:
                baseCaps.append("SASL " + ' '.join(v.keys()))
        return baseCaps

    def do_CAPA(self):
        self.successResponse("I can do the following:")
        for cap in self.listCapabilities():
            self.sendLine(cap)
        self.sendLine(".")

    def do_AUTH(self, args=None):
        if not getattr(self.factory, 'challengers', None):
            self.failResponse("AUTH extension unsupported")
            return

        if args is None:
            self.successResponse("Supported authentication methods:")
            for a in self.factory.challengers:
                self.sendLine(a.upper())
            self.sendLine(".")
            return

        auth = self.factory.challengers.get(args.strip().upper())
        if not self.portal or not auth:
            self.failResponse("Unsupported SASL selected")
            return

        self._auth = auth()
        chal = self._auth.getChallenge()

        self.sendLine('+ ' + base64.encodestring(chal).rstrip('\n'))
        self.state = 'AUTH'

    def state_AUTH(self, line):
        self.state = "COMMAND"
        try:
            parts = base64.decodestring(line).split(None, 1)
        except binascii.Error:
            self.failResponse("Invalid BASE64 encoding")
        else:
            if len(parts) != 2:
                self.failResponse("Invalid AUTH response")
                return
            self._auth.username = parts[0]
            self._auth.response = parts[1]
            d = self.portal.login(self._auth, None, IMailbox)
            d.addCallback(self._cbMailbox, parts[0])
            d.addErrback(self._ebMailbox)
            d.addErrback(self._ebUnexpected)

    def do_APOP(self, user, digest):
        d = defer.maybeDeferred(self.authenticateUserAPOP, user, digest)
        d.addCallbacks(self._cbMailbox, self._ebMailbox, callbackArgs=(user,)
        ).addErrback(self._ebUnexpected)

    def _cbMailbox(self, (interface, avatar, logout), user):
        if interface is not IMailbox:
            self.failResponse('Authentication failed')
            log.err("_cbMailbox() called with an interface other than IMailbox")
            return

        self.mbox = avatar
        self._onLogout = logout
        self.successResponse('Authentication succeeded')
        if getattr(self.factory, 'noisy', True):
            log.msg("Authenticated login for " + user)

    def _ebMailbox(self, failure):
        failure = failure.trap(cred.error.LoginDenied, cred.error.LoginFailed)
        if issubclass(failure, cred.error.LoginDenied):
            self.failResponse("Access denied: " + str(failure))
        elif issubclass(failure, cred.error.LoginFailed):
            self.failResponse('Authentication failed')
        if getattr(self.factory, 'noisy', True):
            log.msg("Denied login attempt from " + str(self.transport.getPeer()))

    def _ebUnexpected(self, failure):
        self.failResponse('Server error: ' + failure.getErrorMessage())
        log.err(failure)

    def do_USER(self, user):
        self._userIs = user
        self.successResponse('USER accepted, send PASS')

    def do_PASS(self, password):
        if self._userIs is None:
            self.failResponse("USER required before PASS")
            return
        user = self._userIs
        self._userIs = None
        d = defer.maybeDeferred(self.authenticateUserPASS, user, password)
        d.addCallbacks(self._cbMailbox, self._ebMailbox, callbackArgs=(user,)
        ).addErrback(self._ebUnexpected)


    def _longOperation(self, d):
        # Turn off timeouts and block further processing until the Deferred
        # fires, then reverse those changes.
        timeOut = self.timeOut
        self.setTimeout(None)
        self.blocked = []
        d.addCallback(self._unblock)
        d.addCallback(lambda ign: self.setTimeout(timeOut))
        return d


    def _coiterate(self, gen):
        return self.schedule(_IteratorBuffer(self.transport.writeSequence, gen))


    def do_STAT(self):
        d = defer.maybeDeferred(self.mbox.listMessages)
        def cbMessages(msgs):
            return self._coiterate(formatStatResponse(msgs))
        def ebMessages(err):
            self.failResponse(err.getErrorMessage())
            log.msg("Unexpected do_STAT failure:")
            log.err(err)
        return self._longOperation(d.addCallbacks(cbMessages, ebMessages))


    def do_LIST(self, i=None):
        if i is None:
            d = defer.maybeDeferred(self.mbox.listMessages)
            def cbMessages(msgs):
                return self._coiterate(formatListResponse(msgs))
            def ebMessages(err):
                self.failResponse(err.getErrorMessage())
                log.msg("Unexpected do_LIST failure:")
                log.err(err)
            return self._longOperation(d.addCallbacks(cbMessages, ebMessages))
        else:
            try:
                i = int(i)
                if i < 1:
                    raise ValueError()
            except ValueError:
                self.failResponse("Invalid message-number: %r" % (i,))
            else:
                d = defer.maybeDeferred(self.mbox.listMessages, i - 1)
                def cbMessage(msg):
                    self.successResponse('%d %d' % (i, msg))
                def ebMessage(err):
                    errcls = err.check(ValueError, IndexError)
                    if errcls is not None:
                        if errcls is IndexError:
                            # IndexError was supported for a while, but really
                            # shouldn't be.  One error condition, one exception
                            # type.
                            warnings.warn(
                                "twisted.mail.pop3.IMailbox.listMessages may not "
                                "raise IndexError for out-of-bounds message numbers: "
                                "raise ValueError instead.",
                                PendingDeprecationWarning)
                        self.failResponse("Invalid message-number: %r" % (i,))
                    else:
                        self.failResponse(err.getErrorMessage())
                        log.msg("Unexpected do_LIST failure:")
                        log.err(err)
                return self._longOperation(d.addCallbacks(cbMessage, ebMessage))


    def do_UIDL(self, i=None):
        if i is None:
            d = defer.maybeDeferred(self.mbox.listMessages)
            def cbMessages(msgs):
                return self._coiterate(formatUIDListResponse(msgs, self.mbox.getUidl))
            def ebMessages(err):
                self.failResponse(err.getErrorMessage())
                log.msg("Unexpected do_UIDL failure:")
                log.err(err)
            return self._longOperation(d.addCallbacks(cbMessages, ebMessages))
        else:
            try:
                i = int(i)
                if i < 1:
                    raise ValueError()
            except ValueError:
                self.failResponse("Bad message number argument")
            else:
                try:
                    msg = self.mbox.getUidl(i - 1)
                except IndexError:
                    # XXX TODO See above comment regarding IndexError.
                    warnings.warn(
                        "twisted.mail.pop3.IMailbox.getUidl may not "
                        "raise IndexError for out-of-bounds message numbers: "
                        "raise ValueError instead.",
                        PendingDeprecationWarning)
                    self.failResponse("Bad message number argument")
                except ValueError:
                    self.failResponse("Bad message number argument")
                else:
                    self.successResponse(str(msg))


    def _getMessageFile(self, i):
        """
        Retrieve the size and contents of a given message, as a two-tuple.

        @param i: The number of the message to operate on.  This is a base-ten
        string representation starting at 1.

        @return: A Deferred which fires with a two-tuple of an integer and a
        file-like object.
        """
        try:
            msg = int(i) - 1
            if msg < 0:
                raise ValueError()
        except ValueError:
            self.failResponse("Bad message number argument")
            return defer.succeed(None)

        sizeDeferred = defer.maybeDeferred(self.mbox.listMessages, msg)
        def cbMessageSize(size):
            if not size:
                return defer.fail(_POP3MessageDeleted())
            fileDeferred = defer.maybeDeferred(self.mbox.getMessage, msg)
            fileDeferred.addCallback(lambda fObj: (size, fObj))
            return fileDeferred

        def ebMessageSomething(err):
            errcls = err.check(_POP3MessageDeleted, ValueError, IndexError)
            if errcls is _POP3MessageDeleted:
                self.failResponse("message deleted")
            elif errcls in (ValueError, IndexError):
                if errcls is IndexError:
                    # XXX TODO See above comment regarding IndexError.
                    warnings.warn(
                        "twisted.mail.pop3.IMailbox.listMessages may not "
                        "raise IndexError for out-of-bounds message numbers: "
                        "raise ValueError instead.",
                        PendingDeprecationWarning)
                self.failResponse("Bad message number argument")
            else:
                log.msg("Unexpected _getMessageFile failure:")
                log.err(err)
            return None

        sizeDeferred.addCallback(cbMessageSize)
        sizeDeferred.addErrback(ebMessageSomething)
        return sizeDeferred


    def _sendMessageContent(self, i, fpWrapper, successResponse):
        d = self._getMessageFile(i)
        def cbMessageFile(info):
            if info is None:
                # Some error occurred - a failure response has been sent
                # already, just give up.
                return

            self._highest = max(self._highest, int(i))
            resp, fp = info
            fp = fpWrapper(fp)
            self.successResponse(successResponse(resp))
            s = basic.FileSender()
            d = s.beginFileTransfer(fp, self.transport, self.transformChunk)

            def cbFileTransfer(lastsent):
                if lastsent != '\n':
                    line = '\r\n.'
                else:
                    line = '.'
                self.sendLine(line)

            def ebFileTransfer(err):
                self.transport.loseConnection()
                log.msg("Unexpected error in _sendMessageContent:")
                log.err(err)

            d.addCallback(cbFileTransfer)
            d.addErrback(ebFileTransfer)
            return d
        return self._longOperation(d.addCallback(cbMessageFile))


    def do_TOP(self, i, size):
        try:
            size = int(size)
            if size < 0:
                raise ValueError
        except ValueError:
            self.failResponse("Bad line count argument")
        else:
            return self._sendMessageContent(
                i,
                lambda fp: _HeadersPlusNLines(fp, size),
                lambda size: "Top of message follows")


    def do_RETR(self, i):
        return self._sendMessageContent(
            i,
            lambda fp: fp,
            lambda size: "%d" % (size,))


    def transformChunk(self, chunk):
        return chunk.replace('\n', '\r\n').replace('\r\n.', '\r\n..')


    def finishedFileTransfer(self, lastsent):
        if lastsent != '\n':
            line = '\r\n.'
        else:
            line = '.'
        self.sendLine(line)


    def do_DELE(self, i):
        i = int(i)-1
        self.mbox.deleteMessage(i)
        self.successResponse()


    def do_NOOP(self):
        """Perform no operation.  Return a success code"""
        self.successResponse()


    def do_RSET(self):
        """Unset all deleted message flags"""
        try:
            self.mbox.undeleteMessages()
        except:
            log.err()
            self.failResponse()
        else:
            self._highest = 0
            self.successResponse()


    def do_LAST(self):
        """
        Return the index of the highest message yet downloaded.
        """
        self.successResponse(self._highest)


    def do_RPOP(self, user):
        self.failResponse('permission denied, sucker')


    def do_QUIT(self):
        if self.mbox:
            self.mbox.sync()
        self.successResponse()
        self.transport.loseConnection()


    def authenticateUserAPOP(self, user, digest):
        """Perform authentication of an APOP login.

        @type user: C{str}
        @param user: The name of the user attempting to log in.

        @type digest: C{str}
        @param digest: The response string with which the user replied.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the login is
        successful, and whose errback will be invoked otherwise.  The
        callback will be passed a 3-tuple consisting of IMailbox,
        an object implementing IMailbox, and a zero-argument callable
        to be invoked when this session is terminated.
        """
        if self.portal is not None:
            return self.portal.login(
                APOPCredentials(self.magic, user, digest),
                None,
                IMailbox
            )
        raise cred.error.UnauthorizedLogin()

    def authenticateUserPASS(self, user, password):
        """Perform authentication of a username/password login.

        @type user: C{str}
        @param user: The name of the user attempting to log in.

        @type password: C{str}
        @param password: The password to attempt to authenticate with.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the login is
        successful, and whose errback will be invoked otherwise.  The
        callback will be passed a 3-tuple consisting of IMailbox,
        an object implementing IMailbox, and a zero-argument callable
        to be invoked when this session is terminated.
        """
        if self.portal is not None:
            return self.portal.login(
                cred.credentials.UsernamePassword(user, password),
                None,
                IMailbox
            )
        raise cred.error.UnauthorizedLogin()


class IServerFactory(Interface):
    """Interface for querying additional parameters of this POP3 server.

    Any cap_* method may raise NotImplementedError if the particular
    capability is not supported.  If cap_EXPIRE() does not raise
    NotImplementedError, perUserExpiration() must be implemented, otherwise
    they are optional.  If cap_LOGIN_DELAY() is implemented,
    perUserLoginDelay() must be implemented, otherwise they are optional.

    @ivar challengers: A dictionary mapping challenger names to classes
    implementing C{IUsernameHashedPassword}.
    """

    def cap_IMPLEMENTATION():
        """Return a string describing this POP3 server implementation."""

    def cap_EXPIRE():
        """Return the minimum number of days messages are retained."""

    def perUserExpiration():
        """Indicate whether message expiration is per-user.

        @return: True if it is, false otherwise.
        """

    def cap_LOGIN_DELAY():
        """Return the minimum number of seconds between client logins."""

    def perUserLoginDelay():
        """Indicate whether the login delay period is per-user.

        @return: True if it is, false otherwise.
        """

class IMailbox(Interface):
    """
    @type loginDelay: C{int}
    @ivar loginDelay: The number of seconds between allowed logins for the
    user associated with this mailbox.  None

    @type messageExpiration: C{int}
    @ivar messageExpiration: The number of days messages in this mailbox will
    remain on the server before being deleted.
    """

    def listMessages(index=None):
        """Retrieve the size of one or more messages.

        @type index: C{int} or C{None}
        @param index: The number of the message for which to retrieve the
        size (starting at 0), or None to retrieve the size of all messages.

        @rtype: C{int} or any iterable of C{int} or a L{Deferred} which fires
        with one of these.

        @return: The number of octets in the specified message, or an iterable
        of integers representing the number of octets in all the messages.  Any
        value which would have referred to a deleted message should be set to 0.

        @raise ValueError: if C{index} is greater than the index of any message
        in the mailbox.
        """

    def getMessage(index):
        """Retrieve a file-like object for a particular message.

        @type index: C{int}
        @param index: The number of the message to retrieve

        @rtype: A file-like object
        @return: A file containing the message data with lines delimited by
        C{\\n}.
        """

    def getUidl(index):
        """Get a unique identifier for a particular message.

        @type index: C{int}
        @param index: The number of the message for which to retrieve a UIDL

        @rtype: C{str}
        @return: A string of printable characters uniquely identifying for all
        time the specified message.

        @raise ValueError: if C{index} is greater than the index of any message
        in the mailbox.
        """

    def deleteMessage(index):
        """Delete a particular message.

        This must not change the number of messages in this mailbox.  Further
        requests for the size of deleted messages should return 0.  Further
        requests for the message itself may raise an exception.

        @type index: C{int}
        @param index: The number of the message to delete.
        """

    def undeleteMessages():
        """
        Undelete any messages which have been marked for deletion since the
        most recent L{sync} call.

        Any message which can be undeleted should be returned to its
        original position in the message sequence and retain its original
        UID.
        """

    def sync():
        """Perform checkpointing.

        This method will be called to indicate the mailbox should attempt to
        clean up any remaining deleted messages.
        """



class Mailbox:
    implements(IMailbox)

    def listMessages(self, i=None):
        return []
    def getMessage(self, i):
        raise ValueError
    def getUidl(self, i):
        raise ValueError
    def deleteMessage(self, i):
        raise ValueError
    def undeleteMessages(self):
        pass
    def sync(self):
        pass


NONE, SHORT, FIRST_LONG, LONG = range(4)

NEXT = {}
NEXT[NONE] = NONE
NEXT[SHORT] = NONE
NEXT[FIRST_LONG] = LONG
NEXT[LONG] = NONE

class POP3Client(basic.LineOnlyReceiver):

    mode = SHORT
    command = 'WELCOME'
    import re
    welcomeRe = re.compile('<(.*)>')

    def __init__(self):
        import warnings
        warnings.warn("twisted.mail.pop3.POP3Client is deprecated, "
                      "please use twisted.mail.pop3.AdvancedPOP3Client "
                      "instead.", DeprecationWarning,
                      stacklevel=3)

    def sendShort(self, command, params=None):
        if params is not None:
            self.sendLine('%s %s' % (command, params))
        else:
            self.sendLine(command)
        self.command = command
        self.mode = SHORT

    def sendLong(self, command, params):
        if params:
            self.sendLine('%s %s' % (command, params))
        else:
            self.sendLine(command)
        self.command = command
        self.mode = FIRST_LONG

    def handle_default(self, line):
        if line[:-4] == '-ERR':
            self.mode = NONE

    def handle_WELCOME(self, line):
        code, data = line.split(' ', 1)
        if code != '+OK':
            self.transport.loseConnection()
        else:
            m = self.welcomeRe.match(line)
            if m:
                self.welcomeCode = m.group(1)

    def _dispatch(self, command, default, *args):
        try:
            method = getattr(self, 'handle_'+command, default)
            if method is not None:
                method(*args)
        except:
            log.err()

    def lineReceived(self, line):
        if self.mode == SHORT or self.mode == FIRST_LONG:
            self.mode = NEXT[self.mode]
            self._dispatch(self.command, self.handle_default, line)
        elif self.mode == LONG:
            if line == '.':
                self.mode = NEXT[self.mode]
                self._dispatch(self.command+'_end', None)
                return
            if line[:1] == '.':
                line = line[1:]
            self._dispatch(self.command+"_continue", None, line)

    def apopAuthenticate(self, user, password, magic):
        digest = md5(magic + password).hexdigest()
        self.apop(user, digest)

    def apop(self, user, digest):
        self.sendLong('APOP', ' '.join((user, digest)))
    def retr(self, i):
        self.sendLong('RETR', i)
    def dele(self, i):
        self.sendShort('DELE', i)
    def list(self, i=''):
        self.sendLong('LIST', i)
    def uidl(self, i=''):
        self.sendLong('UIDL', i)
    def user(self, name):
        self.sendShort('USER', name)
    def pass_(self, pass_):
        self.sendShort('PASS', pass_)
    def quit(self):
        self.sendShort('QUIT')

from twisted.mail.pop3client import POP3Client as AdvancedPOP3Client
from twisted.mail.pop3client import POP3ClientError
from twisted.mail.pop3client import InsecureAuthenticationDisallowed
from twisted.mail.pop3client import ServerErrorResponse
from twisted.mail.pop3client import LineTooLong

__all__ = [
    # Interfaces
    'IMailbox', 'IServerFactory',

    # Exceptions
    'POP3Error', 'POP3ClientError', 'InsecureAuthenticationDisallowed',
    'ServerErrorResponse', 'LineTooLong',

    # Protocol classes
    'POP3', 'POP3Client', 'AdvancedPOP3Client',

    # Misc
    'APOPCredentials', 'Mailbox']
