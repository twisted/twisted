# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
syslog = __import__('syslog')

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
