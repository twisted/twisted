
# System Imports
import gtk
import sys
import traceback
import time

# Twisted Imports

# Sibling Imports
import main

_conditions = {
    gtk.GDK.INPUT_READ: 'Read',
    gtk.GDK.INPUT_WRITE: 'Write',
    
    # This is here because SOMETIMES, GTK tells us about this
    # condition (wtf is 3!?! GDK.INPUT_EXCEPTION is 4!) even though we
    # don't ask.  I believe this is almost always indicative of a
    # closed connection.
    3: 'Read'
    }

reads = main.reads
writes = main.writes
delayeds = main.delayeds
hasReader = reads.has_key
hasWriter = writes.has_key

def addReader(reader):
    if not hasReader(reader):
        reads[reader] = gtk.input_add(reader, gtk.GDK.INPUT_READ, callback)
    simulate()

def addWriter(writer):
    if not hasWriter(writer):
        writes[writer] = gtk.input_add(writer, gtk.GDK.INPUT_WRITE, callback)

def removeReader(reader):
    if hasReader(reader):
        gtk.input_remove(reads[reader])
        del reads[reader]

def removeWriter(writer):
    if hasWriter(writer):
        gtk.input_remove(writes[writer])
        del writes[writer]

def callback(source, condition):
    cbName = 'do'+_conditions[condition]
    try:
        method = getattr(source, cbName)
        why = method()
    except:
        why = main.CONNECTION_LOST
        print 'Error In',source,'.',cbName
        traceback.print_exc(file=sys.stdout)
    if why:
        try:
            source.connectionLost()
        except:
            traceback.print_exc(file=sys.stdout)
        removeReader(source)
        removeWriter(source)
    simulate()

# the next callback
_simtag = None

def simulate():
    """Run simulation loops and reschedule callbacks.
    """
    global _simtag
    if _simtag is not None:
        gtk.timeout_remove(_simtag)
    timeout = None
    for delayed in delayeds:
        delayed.runUntilCurrent()
        newTimeout = delayed.timeout()
        if ((newTimeout is not None) and
            ((timeout is None) or
             (newTimeout < timeout))):
            timeout = newTimeout
    if timeout is not None:
        _simtag = gtk.timeout_add(timeout * 1010, simulate) # grumble

def install():
    # Replace 'main' methods with my own
    main.addWriter = addWriter
    main.removeWriter = removeWriter
    main.addReader = addReader
    main.removeReader = removeReader
    # Indicate that the main loop is running, so application.run() won't try to
    # run it...
    main.running = 2
    # Indicate that rebuild should NOT touch this module now, since it's been
    # mucked with.
    main.ALLOW_TWISTED_REBUILD = 0
    # Begin simulation gtk tick
    simulate()

