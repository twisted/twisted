# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
syslog = __import__('syslog')
import sys
import log

class SyslogObserver:
    def __init__(self, prefix):
        syslog.openlog(prefix)

    def emit(self, eventDict):
        edm = eventDict['message']
        if not edm:
            if eventDict['isError'] and eventDict.has_key('failure'):
                text = eventDict['failure'].getTraceback()
            elif eventDict.has_key('format'):
                text = eventDict['format'] % eventDict
            else:
                # we don't know how to log this
                return
        else:
            text = ' '.join(map(str, edm))

        lines = text.split('\n')
        while lines[-1:] == ['']:
            lines.pop()

        firstLine = 1
        for line in lines:
            if firstLine:
                firstLine=0
            else:
                line = '\t%s' % line
            syslog.syslog('[%s] %s' % (eventDict['system'], line))

def startLogging(prefix='Twisted', setStdout=1):
    obs = SyslogObserver(prefix)
    log.startLoggingWithObserver(obs.emit, setStdout=setStdout)
