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

class SyslogLogger:

    def __init__(self, prefix):
        self.prefix = prefix

    def write(self, data):
        if not data or data=='\n':
            return
        logger = log.logOwner.owner()
        if logger:
            data = logger.log(data)
        data = data.split('\n')
        if not data[-1]:
            data.pop()
        for line in data:
            syslog.syslog("[%s] %s" % (self.prefix, line))

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def close(self):
        pass

    def flush(self):
        pass


def startLogging(prefix='Twisted'):
    sys.stdout = sys.stderr = log.logfile = SyslogLogger(prefix)
