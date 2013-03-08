# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
A modified gtk2 reactor with a Glade dialog in-process that allows you to stop,
suspend, resume and inspect transports interactively.
"""

__all__ = ['install']

# Twisted Imports
from twisted.python import log, threadable, runtime, failure, util, reflect
from twisted.internet.gtk2reactor import Gtk2Reactor as sup

import gtk
import gobject
import gtk.glade

COLUMN_DESCRIPTION = 0
COLUMN_TRANSPORT = 1
COLUMN_READING = 2
COLUMN_WRITING = 3


class GladeReactor(sup):
    """GTK+-2 event loop reactor with GUI.
    """

    def listenTCP(self, port, factory, backlog=50, interface=''):
        from _inspectro import LoggingFactory
        factory = LoggingFactory(factory)
        return sup.listenTCP(self, port, factory, backlog, interface)
    
    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        from _inspectro import LoggingFactory
        factory = LoggingFactory(factory)
        return sup.connectTCP(self, host, port, factory, timeout, bindAddress)

    def listenSSL(self, port, factory, contextFactory, backlog=50, interface=''):
        from _inspectro import LoggingFactory
        factory = LoggingFactory(factory)
        return sup.listenSSL(self, port, factory, contextFactory, backlog, interface)

    def connectSSL(self, host, port, factory, contextFactory, timeout=30, bindAddress=None):
        from _inspectro import LoggingFactory
        factory = LoggingFactory(factory)
        return sup.connectSSL(self, host, port, factory, contextFactory, timeout, bindAddress)

    def connectUNIX(self, address, factory, timeout=30):
        from _inspectro import LoggingFactory
        factory = LoggingFactory(factory)
        return sup.connectUNIX(self, address, factory, timeout)

    def listenUNIX(self, address, factory, backlog=50, mode=0666):
        from _inspectro import LoggingFactory
        factory = LoggingFactory(factory)
        return sup.listenUNIX(self, address, factory, backlog, mode)

    def on_disconnect_clicked(self, w):
        store, iter = self.servers.get_selection().get_selected()
        store[iter][COLUMN_TRANSPORT].loseConnection()

    def on_viewlog_clicked(self, w):
        store, iter = self.servers.get_selection().get_selected()
        data = store[iter][1]
        from _inspectro import LogViewer
        if hasattr(data, "protocol") and not data.protocol.logViewer:
            LogViewer(data.protocol)
    
    def on_inspect_clicked(self, w):
        store, iter = self.servers.get_selection().get_selected()
        data = store[iter]
        from _inspectro import Inspectro
        Inspectro(data[1])

    def on_suspend_clicked(self, w):
        store, iter = self.servers.get_selection().get_selected()
        data = store[iter]
        sup.removeReader(self, data[1])
        sup.removeWriter(self, data[1])
        if data[COLUMN_DESCRIPTION].endswith('(suspended)'):
            if data[COLUMN_READING]:
                sup.addReader(self, data[COLUMN_TRANSPORT])
            if data[COLUMN_WRITING]:
                sup.addWriter(self, data[COLUMN_TRANSPORT])
            data[COLUMN_DESCRIPTION] = str(data[COLUMN_TRANSPORT])
            self.toggle_suspend(1)
        else:
            data[0] += ' (suspended)'
            self.toggle_suspend(0)

    def toggle_suspend(self, suspending=0):
        stock, nonstock = [('gtk-redo', 'Resume'),
                           ('gtk-undo', 'Suspend')][suspending]
        b = self.xml.get_widget("suspend")
        b.set_use_stock(1)
        b.set_label(stock)
        b.get_child().get_child().get_children()[1].set_label(nonstock)

    def servers_selection_changed(self, w):
        store, iter = w.get_selected()
        if iter is None:
            self.xml.get_widget("suspend").set_sensitive(0)
            self.xml.get_widget('disconnect').set_sensitive(0)
        else:
            data = store[iter]
            self.toggle_suspend(not 
                data[COLUMN_DESCRIPTION].endswith('(suspended)'))
            self.xml.get_widget("suspend").set_sensitive(1)
            self.xml.get_widget('disconnect').set_sensitive(1)

    def on_quit_clicked(self, w):
        self.stop()

    def __init__(self):
        self.xml = gtk.glade.XML(util.sibpath(__file__,"gladereactor.glade"))
        d = {}
        for m in reflect.prefixedMethods(self, "on_"):
            d[m.im_func.__name__] = m
        self.xml.signal_autoconnect(d)
        self.xml.get_widget('window1').connect('destroy',
                                               lambda w: self.stop())
        self.servers = self.xml.get_widget("servertree")
        sel = self.servers.get_selection()
        sel.set_mode(gtk.SELECTION_SINGLE)
        sel.connect("changed",
                    self.servers_selection_changed)
        ## argh coredump: self.servers_selection_changed(sel)
        self.xml.get_widget('suspend').set_sensitive(0)
        self.xml.get_widget('disconnect').set_sensitive(0)
        # setup model, connect it to my treeview
        self.model = gtk.ListStore(str, object, gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_BOOLEAN)
        self.servers.set_model(self.model)
        self.servers.set_reorderable(1)
        self.servers.set_headers_clickable(1)
        # self.servers.set_headers_draggable(1)
        # add a column
        for col in [
            gtk.TreeViewColumn('Server',
                               gtk.CellRendererText(),
                               text=0),
            gtk.TreeViewColumn('Reading',
                               gtk.CellRendererToggle(),
                               active=2),
            gtk.TreeViewColumn('Writing',
                               gtk.CellRendererToggle(),
                               active=3)]:
            
            self.servers.append_column(col)
            col.set_resizable(1)
        sup.__init__(self)

    def addReader(self, reader):
        sup.addReader(self, reader)
##      gtk docs suggest this - but it's stupid
##         self.model.set(self.model.append(),
##                        0, str(reader),
##                        1, reader)
        self._maybeAddServer(reader, read=1)

    def _goAway(self,reader):
        for p in range(len(self.model)):
            if self.model[p][1] == reader:
                self.model.remove(self.model.get_iter_from_string(str(p)))
                return


    def _maybeAddServer(self, reader, read=0, write=0):
        p = 0
        for x in self.model:
            if x[1] == reader:
                if reader == 0:
                    reader += 1
                x[2] += read
                x[3] += write
                x[2] = max(x[2],0)
                x[3] = max(x[3],0)
                
                if not (x[2] or x[3]):
                    x[0] = x[0] + '(disconnected)'
                    self.callLater(5, self._goAway, reader)
                return
            p += 1
        else:
            read = max(read,0)
            write = max(write, 0)
            if read or write:
                self.model.append((reader,reader,read,write))

    def addWriter(self, writer):
        sup.addWriter(self, writer)
        self._maybeAddServer(writer, write=1)

    def removeReader(self, reader):
        sup.removeReader(self, reader)
        self._maybeAddServer(reader, read=-1)

    def removeWriter(self, writer):
        sup.removeWriter(self, writer)
        self._maybeAddServer(writer, write=-1)

    def crash(self):
        gtk.main_quit()

    def run(self, installSignalHandlers=1):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.simulate()
        gtk.main()


def install():
    """Configure the twisted mainloop to be run inside the gtk mainloop.
    """
    reactor = GladeReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor
