# this must happen first because reactors are magikal
from twisted.internet import gtk2reactor
gtk2reactor.install()

import sys
import os.path

from path import path

# win32all
from win32ui import CreateFileDialog
import win32con

# gtk2
import gtk, gobject
from gtk import glade

# twisted
from twisted.internet import reactor, defer
from twisted.python import usage, util, log, failure

# local
import tap2ntsvc


class WizardThing:
    def _logdlg(self, msg):
        dlg = gtk.MessageDialog(self.gw_ntsvcwizard,
                                gtk.DIALOG_MODAL|
                                gtk.DIALOG_DESTROY_WITH_PARENT,
                                gtk.MESSAGE_INFO, gtk.BUTTONS_OK, msg)
        dlg.run()
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
        self.gw_backbtn.set_sensitive(0)

        self.gw_cftypes.set_popdown_strings(tap2ntsvc.cftypes)
        self.gw_cftypes.entry.set_text("")

        self.gw_reactor.set_popdown_strings(tap2ntsvc.reactorTypes.keys())
        self.gw_reactor.entry.set_text("default")

        ico = tap2ntsvc.default_icon
        self.gw_pathtoicon.set_text(ico)
        self.gw_pathtoicon.set_position(len(ico))
        self.gw_icondisplay.set_from_file(ico)

        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.gw_datalist.set_model(store)
        TVC=gtk.TreeViewColumn
        CRT=gtk.CellRendererText
        self.gw_datalist.append_column(TVC("Source File", CRT(), text=1))
        self.gw_datalist.append_column(TVC("Install Destination",
                                       CRT(), text=1))

    def on_ntsvcwizard_destroy(self, widget):
        log.msg("Goodbye.")
        self.deferredResult.callback(None)

    def on_nextbtn_clicked(self, widget):
        cur = self.gw_notebook1.get_current_page()
        self.gw_notebook1.set_current_page(cur+1)

    def on_backbtn_clicked(self, widget):
        cur = self.gw_notebook1.get_current_page()
        self.gw_notebook1.set_current_page(cur-1)

    def on_notebook1_switch_page(self, widget, data, pagenum):
        PAGES = 5
        self.gw_backbtn.set_sensitive((pagenum in range(1, PAGES)))
        self.gw_nextbtn.set_sensitive((pagenum in range(0, PAGES-1)))

    def on_browsefortap_clicked(self, widget):
        dlg = CreateFileDialog(1, None,
                               os.path.join(os.getcwd(), '*'), 0,
                               'All files (*)|*||', None)
        if dlg.DoModal() == win32con.IDOK:
            pn = dlg.GetPathName()
            if os.path.isfile(pn):
                self.gw_pathtotap.set_text(pn)
                self.gw_pathtotap.set_position(len(pn))
                self.setNewValues()

    def on_browseforicon_clicked(self, widget):
        dlg = CreateFileDialog(1, None,
                               os.path.join(os.getcwd(), '*.ico'),
                               0, 'Icon Files(*.ico)|*.ico||', None)
        if dlg.DoModal() == win32con.IDOK:
            pn = dlg.GetPathName()
            if os.path.isfile(pn):
                self.gw_pathtoicon.set_text(pn)
                self.gw_pathtoicon.set_position(len(pn))
                self.gw_icondisplay.set_from_file(pn)

    def on_browsefordata_clicked(self, widget):
        dlg = CreateFileDialog(1, None,
                               os.path.join(os.getcwd(), '*'),
                               win32con.OFN_ALLOWMULTISELECT,
                               None, None)
        if dlg.DoModal() == win32con.IDOK:
            pns = dlg.GetPathNames()
            datafiles = self.gw_datalist.get_model()
            for p in pns:
                pth = path(p)
                tup = (pth, path('/') / pth.basename())
                datafiles.append(tup)  # FIXME - both columns display same

    def setNewValues(self):
        cf = self.gw_pathtotap.get_text()
        cfbase = os.path.basename(cf)
        try:
            guess = tap2ntsvc.guessType(cf)
            if guess:
                self.gw_cftypes.entry.set_text(guess)
        except KeyError:
            pass
        name = os.path.splitext(cfbase)[0]
        if not tap2ntsvc.isPythonName(name):
            name = "genericname"
        self.gw_name.set_text(name)
        self.gw_display_name.set_text("%s run by Twisted" % (name,))
        self.gw_package_version.set_text("1.0")
        

class WizOptions(usage.Options):
    optParameters = [['logfile', 'l', None, 'File to use for logging'],
                     ]


def quitWithMessage(fail=failure.Failure()):
    log.err(fail)
    gtk.mainquit()


# for py2exe, make sure __file__ is real
if not os.path.isfile(__file__):
    __file__ = sys.executable
    
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

