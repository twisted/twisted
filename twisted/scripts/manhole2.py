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

import sys

from twisted.internet import gtk2reactor
gtk2reactor.install()
from twisted.internet import reactor
from twisted.python import usage
from twisted.spread.ui import gtk2util
from twisted.spread import pb

class MyOptions(usage.Options):
    optParameters=[("user", "u", "guest", "username"),
                   ("password", "w", "guest"),
                   ("service", "s", "twisted.manhole", "PB Service"),
                   ("host", "h", "localhost"),
                   ("port", "p", str(pb.portno)),
                   ("perspective", "P", "",
                    "PB Perspective to ask for "
                    "(if different than username)")]

def run():
    config = MyOptions()
    try:
        config.parseOptions()
    except usage.UsageError, e:
        print str(e)
        print str(config)
        sys.exit(1)

    # Put this off until after we parse options, or else gnome eats them.
    sys.argv[:] = ['manhole']
    from twisted.manhole.ui import gtk2manhole

    o = config.opts
    defaults = {
        'host': o['host'],
        'port': o['port'],
        'identityName': o['user'],
        'password': o['password'],
        'serviceName': o['service'],
        'perspectiveName': o['perspective']
        }
    w = gtk2manhole.ManholeWindow()
    w.setDefaults(defaults)
    w.login()

    reactor.run()
