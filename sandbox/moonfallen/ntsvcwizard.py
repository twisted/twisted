# this must happen first because reactors are magikal
from twisted.internet import gtk2reactor
gtk2reactor.install()

import sys
import os.path

# gtk2
import gtk
from gtk import glade

# twisted
from twisted.internet import reactor, defer
from twisted.python import usage, util, log, failure

# for py2exe, make sure __file__ is real
if not os.path.isfile(__file__):
    __file__ = sys.executable

class WizardThing:
    def __getattr__(self, name):
        if name.startswith("gw_"):
            return self.glade.get_widget(name[3:])
        raise AttributeError, "%s instance has no attribute %s" % (
            self.__class__, name)

    def __init__(self, deferred, gladefile):
        self.deferredResult = deferred

        self.glade = glade.XML(gladefile)
        self.glade.signal_autoconnect(self)
        self.gw_ntsvcwizard.show()

    def on_ntsvcwizard_destroy(self, widget):
        log.msg("Goodbye.")
        self.deferredResult.callback(None)

    def on_notebook1_switch_page(self, widget, pagenum, data):
        if pagenum == 1:
            pass # self.gw_backbtn.disable()
        if pagenum == 5:
            pass # self.gw_nextbtn.disable()

class WizOptions(usage.Options):
    optParameters = [['logfile', 'l', None, 'File to use for logging'],
                     ]


def quitWithMessage(fail=failure.Failure()):
    log.err(fail)
    gtk.mainquit()


def run(argv = sys.argv):
    o = WizOptions()
    o.parseOptions(argv[1:])
    try:
        logfile = file(o['logfile'], 'w+')
        log.startLogging(logfile)
    except (TypeError, EnvironmentError):
        log.startLogging(sys.stderr)

    gladefile = util.sibpath(__file__, "ntsvcwizard.glade")

    d = defer.Deferred()
    wt = WizardThing(d, gladefile)

    d.addCallback(gtk.mainquit).addErrback(quitWithMessage)
    reactor.run()

