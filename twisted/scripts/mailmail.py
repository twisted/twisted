
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
#

"""
Implementation module for the `newtexaco` command.

The name is preliminary and subject to change.
"""

import os
import sys
import rfc822
import socket
import getpass
from ConfigParser import ConfigParser

try:
    import cStringIO as StringIO
except:
    import StringIO

from twisted.internet import reactor
from twisted.protocols import smtp
from twisted.mail import bounce

GLOBAL_CFG = "/etc/mailmail"
LOCAL_CFG = os.path.expanduser("~/.twisted/mailmail")
SMARTHOST = '127.0.0.1'

ERROR_FMT = """\
Subject: Failed Message Delivery

  Message delivery failed.  The following occurred:
  
  %s
-- 
The Twisted sendmail application.
"""

def log(message, *args):
    sys.stderr.write(str(message) % args + '\n')

class Options:
    """
    @type to: C{list} of C{str}
    @ivar to: The addresses to which to deliver this message.
    
    @type sender: C{str}
    @ivar sender: The address from which this message is being sent.
    
    @type body: C{file}
    @ivar body: The object from which the message is to be read.
    """

class JointFile:
    def __init__(self, files, terminateOnPeriod = True):
        self.files = files
        self.files.reverse()
        self.used = []
    
    def read(self, bytes=None):
        r = ''
        while self.files:
            r = self.files[-1].read(bytes)
            if r != '':
                return self.filter(r)
            self.used.append(self.files.pop())
        return ''

    def readline(self):
        if not self.files:
            return ''
        while self.files:
            r = self.files[-1].readline()
            if r != '':
                return self.filter(r)
            self.used.append(self.files.pop())
        return ''
    
    def readlines(self, bytes=None):
        if not self.files:
            return []
        while self.files:
            r = self.files[-1].readlines(bytes)
            if r != []:
                r[-1] == self.filter(r[-1])
                if not r[-1]:
                    del r[-1]
                return r
            self.used.append(self.files.pop())
        return []
    
    def filter(self, s):
        i = s.find('\n.\r')
        if i == -1:
            i = s.find('\n.\n')
        if i == -1:
            return s
        while self.files:
            self.used.append(self.files.pop())
        return s[:i + 1]
    
    def fileno(self):
        return self.files and self.files[-1].fileno() or self.used[-1].fileno()
    
    def close(self):
        for f in self.used:
            f.close()
        for f in self.files:
            f.close()

def getlogin():
    try:
        return os.getlogin()
    except:
        return getpass.getuser()
        

def parseOptions(argv):
    o = Options()
    o.to = [e for e in argv if not e.startswith('-')]
    o.sender = '@'.join((getlogin(), socket.gethostname()))
    
    # Just be very stupid

    # Skip -bm -- it is the default
    
    # -bp lists queue information.  Screw that.
    if '-bp' in argv:
        raise ValueError, "Unsupported option"
    
    # -bs makes sendmail use stdin/stdout as its transport.  Screw that.
    if '-bs' in argv:
        raise ValueError, "Unsupported option"
    
    # -F sets who the mail is from, but is overridable by the From header
    if '-F' in argv:
        o.sender = argv[argv.index('-F') + 1]
        o.to.remove(o.sender)
    
    # -i and -oi makes us ignore lone "."
    if ('-i' in argv) or ('-oi' in argv):
        o.ignoreDot = True
    else:
        o.ignoreDot = False
    
    # -odb is background delivery
    if '-odb' in argv:
        o.background = True
    else:
        o.background = False
    
    # -odf is foreground delivery
    if '-odf' in argv:
        o.background = False
    else:
        o.background = True
    
    # -oem and -em cause errors to be mailed back to the sender.
    # It is also the default.
    
    # -oep and -ep cause errors to be printed to stderr
    if ('-oep' in argv) or ('-ep' in argv):
        o.printErrors = True
    else:
        o.printErrors = False
    
    # -om causes a copy of the message to be sent to the sender if the sender
    # appears in an alias expansion.  We do not support aliases.
    if '-om' in argv:
        raise ValueError, "Unsupported option"

    # -t causes us to pick the recipients of the message from the To, Cc, and Bcc
    # headers, and to remove the Bcc header if present.
    if '-t' in argv:
        o.recipientsFromHeaders = True
        o.excludeAddresses = o.to
        o.to = []
    else:
        o.recipientsFromHeaders = False
        o.exludeAddresses = []
    
    headers = []
    buffer = StringIO.StringIO()
    while 1:
        write = 1
        line = sys.stdin.readline()
        if not line.strip():
            break
        
        hdrs = line.split(': ', 1)
        
        hdr = hdrs[0].lower()
        if o.recipientsFromHeaders and hdr in ('to', 'cc', 'bcc'):
            o.to.extend([
                a[1] for a in rfc822.AddressList(hdrs[1]).addresslist
            ])
            if hdr != 'bcc':
                write = 0
        elif hdr == 'from':
            o.sender = rfc822.parseaddr(hdrs[1])[1]
        
        if write:
            buffer.write(line)
    buffer.write(line)

    if o.recipientsFromHeaders:
        for a in o.excludeAddresses:
            try:
                o.to.remove(a)
            except:
                pass

    buffer.seek(0, 0)
    o.body = JointFile([buffer, sys.stdin], not o.ignoreDot)
    return o

class Configuration:
    """
    @ivar allowUIDs
    @ivar allowGIDs
    @ivar denyUIDs
    @ivar denyGIDs
    @ivar useraccess
    @ivar groupaccess
    @ivar identities
    @ivar smarthost
    @ivar domain
    @ivar defaultAccess
    """
    def __init__(self):
        self.allowUIDs = []
        self.denyUIDs = []
        self.allowGIDs = []
        self.denyGIDs = []
        self.useraccess = 'deny'
        self.groupaccess= 'deny'
        
        self.identities = {}
        self.smarthost = None
        self.domain = None
        
        self.defaultAccess = True

def loadConfig(path):
    # [useraccess]
    # allow=uid1,uid2,...
    # deny=uid1,uid2,...
    # order=allow,deny
    # [groupaccess]
    # allow=gid1,gid2,...
    # deny=gid1,gid2,...
    # order=deny,allow
    # [identity]
    # host1=username:password
    # host2=username:password
    # [addresses]
    # smarthost=a.b.c.d
    # default_domain=x.y.z
    
    c = Configuration()
    
    if not os.access(path, os.R_OK):
        return c

    p = ConfigParser()
    p.read(path)
    
    au = c.allowUIDs
    du = c.denyUIDs
    ag = c.allowGIDs
    dg = c.denyGIDs
    for (section, a, d) in (('useraccess', au, du), ('groupaccess', ag, dg)):
        if p.has_section(section):
            for (mode, L) in (('allow', a), ('deny', d)):
                for id in p.get(section, mode).split(','):
                    try:
                        id = int(id)
                    except ValueError:
                        log("Illegal %sID in [%s] section: %s", section[0].upper(), section, id)
                    else:
                        L.append(id)
            order = p.get(section, 'order')
            order = map(str.split, map(str.lower, order.split(',')))
            if order[0] == 'allow':
                setattr(c, section, 'allow')
            else:
                setattr(c, section, 'deny')

    if p.has_section('identity'):
        for (host, up) in p.items('identity'):
            parts = up.split(':', 1)
            if len(parts) != 2:
                log("Illegal entry in [identity] section: %s", up)
                continue
            p.identities[host] = parts

    if p.has_section('addresses'):
        c.smarthost = p.get('addresses', 'smarthost')
        c.domain = p.get('addresses', 'default_domain')

    return c

def success(result):
    reactor.stop()

failed = None
def failure(f):
    global failed
    reactor.stop()
    failed = f

def sendmail(host, options, ident):
    from twisted.protocols.smtp import sendmail
    d = sendmail(host, options.sender, options.to, options.body)
    d.addCallbacks(success, failure)
    reactor.run()

def senderror(failure, options):
    recipient = [options.sender]
    sender = 'Internally Generated Message (%s)' % (sys.argv[0],)
    error = StringIO.StringIO()
    failure.printTraceback(file=error)
    body = StringIO.StringIO(ERROR_FMT % error.getvalue())

    from twisted.protocols.smtp import sendmail
    d = sendmail('localhost', sender, recipient, body)
    d.addBoth(lambda _: reactor.stop())

def deny(conf):
    uid = os.getuid()
    gid = os.getgid()
    
    if conf.useraccess == 'deny':
        if uid in conf.denyUIDs:
            return True
        if uid in conf.allowUIDs:
            return False
    else:
        if uid in conf.allowUIDs:
            return False
        if uid in conf.denyUIDs:
            return True

    if conf.groupaccess == 'deny':
        if gid in conf.denyGIDs:
            return True
        if gid in conf.allowGIDs:
            return False
    else:
        if gid in conf.allowGIDs:
            return False
        if gid in conf.denyGIDs:
            return True
    
    return not conf.defaultAccess

def run():
    o = parseOptions(sys.argv[1:])
    gConf = loadConfig(GLOBAL_CFG)
    lConf = loadConfig(LOCAL_CFG)
    
    if deny(gConf) or deny(lConf):
        log("Permission denied")
        return

    host = lConf.smarthost or gConf.smarthost or SMARTHOST
    
    ident = gConf.identities.copy()
    ident.update(lConf.identities)
    
    if lConf.domain:
        smtp.DNSNAME = lConf.domain
    elif gConf.domain:
        smtp.DNSNAME = gConf.domain

    sendmail(host, o, ident)

    if failed:
        if o.printErrors:
            failed.printTraceback(file=sys.stderr)
            raise SystemExit(1)
        else:
            senderror(failed, o)
