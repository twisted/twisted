# -*- test-case-name: twisted.test.test_mail -*-
#
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

"""Support for aliases(5) configuration files

API Stability: Unstable

@author: U{Jp Calderone<exarkun@twistedmatrix.com>}

TODO: Monitor files for reparsing
      Handle non-local alias targets
      Handle maildir alias targets
"""

import os
import tempfile

from twisted.protocols import smtp
from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import error
from twisted.python import components
from twisted.python import failure
from twisted.python import log

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
    
    Lines in the file should be formatted like so:
    
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

class IAlias(components.Interface):
    def createMessageReceiver(self):
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

    __implements__ = (IAlias,)

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
    __implements__ = (smtp.IMessage,)
    
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

    __implements__ = (IAlias,)

    def __init__(self, filename, *args):
        AliasBase.__init__(self, *args)
        self.filename = filename

    def __str__(self):
        return '<File %s>' % (self.filename,)
    
    def createMessageReceiver(self):
        return FileWrapper(self.filename)

class MessageWrapper:
    __implements__ = (smtp.IMessage,)
    
    done = False
    
    def __init__(self, protocol, process=None):
        self.processName = process
        self.protocol = protocol
        self.completion = defer.Deferred()
        self.protocol.onEnd = self.completion
        self.completion.addCallback(self._processEnded)
    
    def _processEnded(self, result, err=0):
        self.done = True
        if err:
            raise result.value
    
    def lineReceived(self, line):
        if self.done:
            return
        self.protocol.transport.write(line + '\n')
    
    def eomReceived(self):
        if not self.done:
            self.protocol.transport.loseConnection()
            self.completion.setTimeout(60)
        return self.completion
    
    def connectionLost(self):
        # Heh heh
        pass
    
    def __str__(self):
        return '<ProcessWrapper %s>' % (self.processName,) 

class ProcessAliasProtocol(protocol.ProcessProtocol):
    def processEnded(self, reason):
        if reason.check(error.ProcessDone):
            self.onEnd.callback("Complete")
        else:
            self.onEnd.errback(reason)

class ProcessAlias(AliasBase):
    """An alias for a program."""

    __implements__ = (IAlias,)

    def __init__(self, path, *args):
        AliasBase.__init__(self, *args)
        self.path = path.split()
        self.program = self.path[0]
    
    def __str__(self):
        return '<Process %s>' % (self.path,)
    
    def createMessageReceiver(self):
        from twisted.internet import reactor
        p = ProcessAliasProtocol()
        m = MessageWrapper(p, self.program)
        fd = reactor.spawnProcess(p, self.program, self.path)
        return m

class MultiWrapper:
    """Wrapper to deliver a single message to multiple recipients"""

    __implements__ = (smtp.IMessage,)

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
    """An alias which points to more than one recipient"""

    __implements__ = (IAlias,)

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
                self.aliases.append(ProcessAlias(addr[1:], *args))
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
