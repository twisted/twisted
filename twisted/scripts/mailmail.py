
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

try:
    import cStringIO as StringIO
except:
    import StringIO

from twisted.internet import reactor
from twisted.mail import bounce

ERROR_FMT = """\
Subject: Failed Message Delivery

  Message delivery failed.  The following occurred:
  
  %s
-- 
The Twisted sendmail application.
"""

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
        for a in o.excludeAddress:
            try:
                o.to.remove(a)
            except:
                pass

    buffer.seek(0, 0)
    o.body = JointFile([buffer, sys.stdin], not o.ignoreDot)
    return o

def success(result):
    reactor.stop()

failed = None
def failure(f):
    global failed
    reactor.stop()
    failed = f

def sendmail(options):
    from twisted.protocols.smtp import sendmail
    d = sendmail('localhost', options.sender, options.to, options.body)
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

def run():
    o = parseOptions(sys.argv[1:])
    sendmail(o)
    if failed:
        if o.printErrors:
            failed.printTraceback(file=sys.stderr)
            raise SystemExit(1)
        else:
            senderror(failed, o)
