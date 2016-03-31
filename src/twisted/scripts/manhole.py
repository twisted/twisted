# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Start a L{twisted.manhole} client.
"""

import sys

from twisted.python import usage

def run():
    config = MyOptions()
    try:
        config.parseOptions()
    except usage.UsageError, e:
        print str(e)
        print str(config)
        sys.exit(1)

    run_gtk2(config)

    from twisted.internet import reactor
    reactor.run()


def run_gtk2(config):
    # Put these off until after we parse options, so we know what reactor
    # to load.
    from twisted.internet import gtk2reactor
    gtk2reactor.install()

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


pbportno = 8787

class MyOptions(usage.Options):
    optParameters=[("user", "u", "guest", "username"),
                   ("password", "w", "guest"),
                   ("service", "s", "twisted.manhole", "PB Service"),
                   ("host", "h", "localhost"),
                   ("port", "p", str(pbportno)),
                   ("perspective", "P", "",
                    "PB Perspective to ask for "
                    "(if different than username)")]

    compData = usage.Completions(
        optActions={"host": usage.CompleteHostnames(),
                    "user": usage.CompleteUsernames()}
        )

if __name__ == '__main__':
    run()
