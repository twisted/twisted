# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Start a L{twisted.manhole} client.

@var toolkitPreference: A list of all toolkits we have front-ends for, with
   the ones we most prefer to use listed first.
@type toolkitPreference: list of strings
"""

import sys

from twisted.python import usage

# Prefer gtk2 because it is the way of the future!
toolkitPreference = ('gtk2', 'gtk1')

class NoToolkitError(usage.UsageError):
    wantToolkits = toolkitPreference
    def __str__(self):
        return (
            "I couldn't find any of these toolkits installed, and I need "
            "one of them to run: %s" % (', '.join(self.wantToolkits),))

def bestToolkit():
    """The most-preferred available toolkit.

    @returntype: string
    """
    avail = getAvailableToolkits()
    for v in toolkitPreference:
        if v in avail:
            return v
    else:
        raise NoToolkitError

_availableToolkits = None
def getAvailableToolkits():
    """Autodetect available toolkits.

    @returns: A list of usable toolkits.
    @returntype: list of strings
    """
    global _availableToolkits
    # use cached result
    if _availableToolkits is not None:
        return _availableToolkits

    avail = []

    # Recent GTK.
    try:
        import pygtk
    except:
        pass
    else:
        gtkvers = pygtk._get_available_versions().keys()
        for v in gtkvers:
            frontend = {'1.2': 'gtk1',
                        '2.0': 'gtk2'}.get(v)
            if frontend is not None:
                avail.append(frontend)

    if not avail:
        # Older GTK
        try:
            # WARNING: It's entirely possible that this does something crappy,
            # such as running gtk_init, which may have undesirable side
            # effects if that's not the toolkit we end up using.
            import gtk
        except:
            pass
        else:
            avail.append('gtk1')

    # There may be some "middle gtk" that got left out -- that is, a
    # version of pygtk 1.99.x that happened before the pygtk module
    # with its _get_available_versions was introduced.  Chances are
    # that the gtk2 front-end wouldn't work with it anyway, but it may
    # get mis-identified it as gtk1. :(

    _availableToolkits = avail
    return avail


def run():
    config = MyOptions()
    try:
        config.parseOptions()
    except usage.UsageError, e:
        print str(e)
        print str(config)
        sys.exit(1)

    try:
        run = getattr(sys.modules[__name__], 'run_' + config.opts['toolkit'])
    except AttributeError:
        print "Sorry, no support for toolkit %r." % (config.opts['toolkit'],)
        sys.exit(1)

    run(config)

    from twisted.internet import reactor
    reactor.run()

def run_gtk1(config):
    # Put these off until after we parse options, so we know what reactor
    # to install.
    from twisted.internet import gtkreactor
    gtkreactor.install()
    from twisted.spread.ui import gtkutil

    # Put this off until after we parse options, or else gnome eats them.
    # (http://www.daa.com.au/pipermail/pygtk/2002-December/004051.html)
    sys.argv[:] = ['manhole']
    from twisted.manhole.ui import gtkmanhole

    i = gtkmanhole.Interaction()
    lw = gtkutil.Login(i.connected,
                       i.client,
                       initialUser=config.opts['user'],
                       initialPassword=config.opts['password'],
                       initialService=config.opts['service'],
                       initialHostname=config.opts['host'],
                       initialPortno=config.opts['port'],
                       initialPerspective=config.opts['perspective'])

    i.loginWindow = lw

    lw.show_all()


def run_gtk2(config):
    # Put these off until after we parse options, so we know what reactor
    # to load.
    from twisted.internet import gtk2reactor
    gtk2reactor.install()
    from twisted.spread.ui import gtk2util

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


# from twisted.spread import pb
# can't do that, it installs a reactor.  grr.
pbportno = 8787

class MyOptions(usage.Options):
    optParameters=[("user", "u", "guest", "username"),
                   ("password", "w", "guest"),
                   ("service", "s", "twisted.manhole", "PB Service"),
                   ("host", "h", "localhost"),
                   ("port", "p", str(pbportno)),
                   ("perspective", "P", "",
                    "PB Perspective to ask for "
                    "(if different than username)"),
                   ("toolkit", "t", bestToolkit(),
                    "Front-end to use; one of %s"
                    % (' '.join(getAvailableToolkits()),)),
                   ]

    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    #zsh_mutuallyExclusive = [("foo", "bar"), ("bar", "baz")]
    zsh_actions = {"host":"_hosts",
                   "toolkit":"(gtk1 gtk2)"}
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}

if __name__ == '__main__':
    run()
