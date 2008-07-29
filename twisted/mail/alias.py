# -*- test-case-name: twisted.mail.test.test_mail -*-
#
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Support for aliases(5) configuration files

@author: Jp Calderone

TODO::
    Monitor files for reparsing
    Handle non-local alias targets
    Handle maildir alias targets
"""

import os
import tempfile

from twisted.mail import smtp
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import defer
from twisted.python import failure
from twisted.python import log
from zope.interface import implements, Interface


def handle(result, line, filename, lineNo):
    parts = [p.strip() for p in line.split(':', 1)]
    if len(parts) != 2:
        fmt = "Invalid format on line %d of alias file %s."
        arg = (lineNo, filename)
        log.err(fmt % arg)
    else:
        user, alias = parts
        result.setdefault(user.strip(), []).extend(map(str.strip, alias.split(',')))

def loadAliasFile(domains, filename=None, fp=None):
    """Load a file containing email aliases.

    Lines in the file should be formatted like so::

        username: alias1,alias2,...,aliasN

    Aliases beginning with a | will be treated as programs, will be run, and
    the message will be written to their stdin.

    Aliases without a host part will be assumed to be addresses on localhost.

    If a username is specified multiple times, the aliases for each are joined
    together as if they had all been on one line.

    @type domains: C{dict} of implementor of C{IDomain}
    @param domains: The domains to which these aliases will belong.

    @type filename: C{str}
    @param filename: The filename from which to load aliases.

    @type fp: Any file-like object.
    @param fp: If specified, overrides C{filename}, and aliases are read from
    it.

    @rtype: C{dict}
    @return: A dictionary mapping usernames to C{AliasGroup} objects.
    """
    result = {}
    if fp is None:
        fp = file(filename)
    else:
        filename = getattr(fp, 'name', '<unknown>')
    i = 0
    prev = ''
    for line in fp:
        i += 1
        line = line.rstrip()
        if line.lstrip().startswith('#'):
            continue
        elif line.startswith(' ') or line.startswith('\t'):
            prev = prev + line
        else:
            if prev:
                handle(result, prev, filename, i)
            prev = line
    if prev:
        handle(result, prev, filename, i)
    for (u, a) in result.items():
        addr = smtp.Address(u)
        result[u] = AliasGroup(a, domains, u)
    return result

class IAlias(Interface):
    def createMessageReceiver():
        pass

class AliasBase:
    def __init__(self, domains, original):
        self.domains = domains
        self.original = smtp.Address(original)

    def domain(self):
        return self.domains[self.original.domain]

    def resolve(self, aliasmap, memo=None):
        if memo is None:
            memo = {}
        if str(self) in memo:
            return None
        memo[str(self)] = None
        return self.createMessageReceiver()

class AddressAlias(AliasBase):
    """The simplest alias, translating one email address into another."""

    implements(IAlias)

    def __init__(self, alias, *args):
        AliasBase.__init__(self, *args)
        self.alias = smtp.Address(alias)

    def __str__(self):
        return '<Address %s>' % (self.alias,)

    def createMessageReceiver(self):
        return self.domain().startMessage(str(self.alias))

    def resolve(self, aliasmap, memo=None):
        if memo is None:
            memo = {}
        if str(self) in memo:
            return None
        memo[str(self)] = None
        try:
            return self.domain().exists(smtp.User(self.alias, None, None, None), memo)()
        except smtp.SMTPBadRcpt:
            pass
        if self.alias.local in aliasmap:
            return aliasmap[self.alias.local].resolve(aliasmap, memo)
        return None

class FileWrapper:
    implements(smtp.IMessage)

    def __init__(self, filename):
        self.fp = tempfile.TemporaryFile()
        self.finalname = filename

    def lineReceived(self, line):
        self.fp.write(line + '\n')

    def eomReceived(self):
        self.fp.seek(0, 0)
        try:
            f = file(self.finalname, 'a')
        except:
            return defer.fail(failure.Failure())

        f.write(self.fp.read())
        self.fp.close()
        f.close()

        return defer.succeed(self.finalname)

    def connectionLost(self):
        self.fp.close()
        self.fp = None

    def __str__(self):
        return '<FileWrapper %s>' % (self.finalname,)


class FileAlias(AliasBase):

    implements(IAlias)

    def __init__(self, filename, *args):
        AliasBase.__init__(self, *args)
        self.filename = filename

    def __str__(self):
        return '<File %s>' % (self.filename,)

    def createMessageReceiver(self):
        return FileWrapper(self.filename)



class ProcessAliasTimeout(Exception):
    """
    A timeout occurred while processing aliases.
    """



class MessageWrapper:
    """
    A message receiver which delivers content to a child process.

    @type completionTimeout: C{int} or C{float}
    @ivar completionTimeout: The number of seconds to wait for the child
        process to exit before reporting the delivery as a failure.

    @type _timeoutCallID: C{NoneType} or L{IDelayedCall}
    @ivar _timeoutCallID: The call used to time out delivery, started when the
        connection to the child process is closed.

    @type done: C{bool}
    @ivar done: Flag indicating whether the child process has exited or not.

    @ivar reactor: An L{IReactorTime} provider which will be used to schedule
        timeouts.
    """
    implements(smtp.IMessage)

    done = False

    completionTimeout = 60
    _timeoutCallID = None

    reactor = reactor

    def __init__(self, protocol, process=None, reactor=None):
        self.processName = process
        self.protocol = protocol
        self.completion = defer.Deferred()
        self.protocol.onEnd = self.completion
        self.completion.addBoth(self._processEnded)

        if reactor is not None:
            self.reactor = reactor


    def _processEnded(self, result):
        """
        Record process termination and cancel the timeout call if it is active.
        """
        self.done = True
        if self._timeoutCallID is not None:
            # eomReceived was called, we're actually waiting for the process to
            # exit.
            self._timeoutCallID.cancel()
            self._timeoutCallID = None
        else:
            # eomReceived was not called, this is unexpected, propagate the
            # error.
            return result


    def lineReceived(self, line):
        if self.done:
            return
        self.protocol.transport.write(line + '\n')


    def eomReceived(self):
        """
        Disconnect from the child process, set up a timeout to wait for it to
        exit, and return a Deferred which will be called back when the child
        process exits.
        """
        if not self.done:
            self.protocol.transport.loseConnection()
            self._timeoutCallID = self.reactor.callLater(
                self.completionTimeout, self._completionCancel)
        return self.completion


    def _completionCancel(self):
        """
        Handle the expiration of the timeout for the child process to exit by
        terminating the child process forcefully and issuing a failure to the
        completion deferred returned by L{eomReceived}.
        """
        self._timeoutCallID = None
        self.protocol.transport.signalProcess('KILL')
        exc = ProcessAliasTimeout(
            "No answer after %s seconds" % (self.completionTimeout,))
        self.protocol.onEnd = None
        self.completion.errback(failure.Failure(exc))


    def connectionLost(self):
        # Heh heh
        pass


    def __str__(self):
        return '<ProcessWrapper %s>' % (self.processName,)



class ProcessAliasProtocol(protocol.ProcessProtocol):
    """
    Trivial process protocol which will callback a Deferred when the associated
    process ends.

    @ivar onEnd: If not C{None}, a L{Deferred} which will be called back with
        the failure passed to C{processEnded}, when C{processEnded} is called.
    """

    onEnd = None

    def processEnded(self, reason):
        """
        Call back C{onEnd} if it is set.
        """
        if self.onEnd is not None:
            self.onEnd.errback(reason)



class ProcessAlias(AliasBase):
    """
    An alias which is handled by the execution of a particular program.

    @ivar reactor: An L{IReactorProcess} and L{IReactorTime} provider which
        will be used to create and timeout the alias child process.
    """
    implements(IAlias)

    reactor = reactor

    def __init__(self, path, *args):
        AliasBase.__init__(self, *args)
        self.path = path.split()
        self.program = self.path[0]


    def __str__(self):
        """
        Build a string representation containing the path.
        """
        return '<Process %s>' % (self.path,)


    def spawnProcess(self, proto, program, path):
        """
        Wrapper around C{reactor.spawnProcess}, to be customized for tests
        purpose.
        """
        return self.reactor.spawnProcess(proto, program, path)


    def createMessageReceiver(self):
        """
        Create a message receiver by launching a process.
        """
        p = ProcessAliasProtocol()
        m = MessageWrapper(p, self.program, self.reactor)
        fd = self.spawnProcess(p, self.program, self.path)
        return m



class MultiWrapper:
    """
    Wrapper to deliver a single message to multiple recipients.
    """

    implements(smtp.IMessage)

    def __init__(self, objs):
        self.objs = objs

    def lineReceived(self, line):
        for o in self.objs:
            o.lineReceived(line)

    def eomReceived(self):
        return defer.DeferredList([
            o.eomReceived() for o in self.objs
        ])

    def connectionLost(self):
        for o in self.objs:
            o.connectionLost()

    def __str__(self):
        return '<GroupWrapper %r>' % (map(str, self.objs),)



class AliasGroup(AliasBase):
    """
    An alias which points to more than one recipient.

    @ivar processAliasFactory: a factory for resolving process aliases.
    @type processAliasFactory: C{class}
    """

    implements(IAlias)

    processAliasFactory = ProcessAlias

    def __init__(self, items, *args):
        AliasBase.__init__(self, *args)
        self.aliases = []
        while items:
            addr = items.pop().strip()
            if addr.startswith(':'):
                try:
                    f = file(addr[1:])
                except:
                    log.err("Invalid filename in alias file %r" % (addr[1:],))
                else:
                    addr = ' '.join([l.strip() for l in f])
                    items.extend(addr.split(','))
            elif addr.startswith('|'):
                self.aliases.append(self.processAliasFactory(addr[1:], *args))
            elif addr.startswith('/'):
                if os.path.isdir(addr):
                    log.err("Directory delivery not supported")
                else:
                    self.aliases.append(FileAlias(addr, *args))
            else:
                self.aliases.append(AddressAlias(addr, *args))

    def __len__(self):
        return len(self.aliases)

    def __str__(self):
        return '<AliasGroup [%s]>' % (', '.join(map(str, self.aliases)))

    def createMessageReceiver(self):
        return MultiWrapper([a.createMessageReceiver() for a in self.aliases])

    def resolve(self, aliasmap, memo=None):
        if memo is None:
            memo = {}
        r = []
        for a in self.aliases:
            r.append(a.resolve(aliasmap, memo))
        return MultiWrapper(filter(None, r))

