
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

"""I am the support module for creating process monitors with 'mktap'
"""

from twisted.python import usage
from twisted.runner import procmon

class Options(usage.Options):
    synopsis = "Usage: mktap procmon [options] processname command [args]"
    optParameters = [
        ["service-name", None, "procmon", "Service name to use."],
        ["uid", None, None, "Uid to run the process as."],
        ["gid", None, None, "Gid to run the process as."],
        ]

    longdesc = """\
This creates a procmon.tap file that can be used by twistd. If the
named service exists, the process is added to that ProcessMonitor.
"""

    def parseArgs(self, processName, command, *args):
        self.opts['processname'] = processName
        self.opts['command'] = (command,)+args

import twisted.internet.app

def updateApplication(app, config):
    svc = None
    svc = app.services.get(config.opts['service-name'])
    if svc is None:
        svc = procmon.ProcessMonitor(config.opts['service-name'], app)
    if not isinstance(svc, procmon.ProcessMonitor):
        raise usage.UsageError("Service %r is not a ProcessMonitor service." % svc)
    svc.addProcess(config.opts['processname'], config.opts['command'])
