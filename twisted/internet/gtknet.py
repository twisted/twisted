""" GTK mainloop networking.

This allows you to integrate twisted.net servers and clients with a running GTK
process.
"""

import select
import gtk
import sys
import traceback
import threadable

from twisted import net

_trans = {
    gtk.GDK.INPUT_READ: 'Read',
    gtk.GDK.INPUT_WRITE: 'Write',
    
    # This is here because SOMETIMES, GTK tells us about this
    # condition (wtf is 3!?! GDK.INPUT_EXCEPTION is 4!) even though we
    # don't ask.  I believe this is almost always indicative of a
    # closed connection.
    3: 'Read'
    }

class Selector:
    """I am a class conforming to net.Selector's interface.
    """
    def __init__(self):
        """Start up and insinuate myself into GTK's main loop.
        """
        self.readers = {}
        self.writers = {}
        gtk.idle_add(self.work)
        self.tdsp = threadable.dispatch
        threadable.dispatch = self.dispatch

    def addServer(self, server):
        """Since I'm not persistent, do nothing.
        """
    
    def dispatch(self, *args, **kw):
        """(internal) threadable dispatch function.
        """
        apply(self.tdsp, args, kw)
        gtk.idle_add(self.work)
        
    def work(self):
        """Do threadable work and re-add myself for next idle call.
        """
        if threadable.dispatcher.work():
            gtk.idle_add(self.work)

    def addReader(self, obj):
        """Add an object to be notified on read to me.
        """
        if not self.readers.has_key(obj):
            self.readers[obj] = gtk.input_add(obj, gtk.GDK.INPUT_READ,
                                              self.doCallback)
    def addWriter(self, obj):
        """Add an object to be notified on write to me.
        """
        if not self.writers.has_key(obj):
            self.writers[obj] = gtk.input_add(obj, gtk.GDK.INPUT_WRITE,
                                              self.doCallback)
            
    def removeReader(self, obj):
        """Remove an object to be notified on read from me.
        """
        if self.readers.has_key(obj):
            gtk.input_remove(self.readers[obj])
            del self.readers[obj]

    def removeWriter(self, obj):
        """Remove an object to be notified on write from me.
        """
        if self.writers.has_key(obj):
            gtk.input_remove(self.writers[obj])
            del self.writers[obj]
        
    def _applyMethod(self, instance, methodType):
        """(internal) apply doRead and doWrite methods.
        """
        methodName = "do"+methodType
        try:
            method = getattr(instance, methodName)
            why = method()
        except:
            why = net.CONNECTION_LOST
            print 'Error In',instance,'.',methodName
            traceback.print_exc(file=sys.stdout)
        if why:
            try:    instance.connectionLost()
            except: traceback.print_exc(file=sys.stdout)
            self.removeReader(instance)
            self.removeWriter(instance)
            
    
    def doCallback(self, source, condition):
        """(internal) do state lookup for condition, then do appropriate callbacks
        """
        self._applyMethod(source, _trans[condition])
        
    def doBlockingLoop(self):
        """(internal) this is outdated.
        """
        r, w, e = select.select(self.readers.keys(),
                                self.writers.keys(),
                                [])
        for reader in r:
            self._applyMethod(reader, 'Read')
        for writer in w:
            self._applyMethod(writer, 'Write')
