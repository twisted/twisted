
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


"""
This module integrates Tkinter with twisted.internet's mainloop.
"""
# System Imports
import select

# Twisted Imports
from twisted.python import threadable

# Sibling Imports
import main

_root = None
_condition = None
_sim = None

class Simulator:
    # Workaround for not having threads...
    cancelled = 0

    def simulate(self):
        if self.cancelled:
            return
        global _sim
        if _sim is not None:
            _sim.cancel()
        timeout = main.runUntilCurrent()
        if timeout is not None:
            _sim = Simulator()
            _root.after(int(timeout * 1010), _sim.simulate)

    def cancel(self):
        self.cancelled = 1

def worker():
    # should be happening in the tk main loop.
    _condition.acquire()
    main.doSelect(0)
    Simulator().simulate()
    threadable.dispatcher.work()
    _condition.notify()
    _condition.release()

stopped = 0
waiterthread = 0

def waiter():
    # we don't require threadability...
    import thread
    global waiterthread
    waiterthread = thread.get_ident()
    while 1:
        # Do the select, see if there's any input waiting...
        print 'tkinternet: waiting on select'
        select.select(main.reads.keys(), main.writes.keys(), [])
        if stopped:
            return
        print 'tkinternet: waiting for condition'
        # Wait for the main thread to be done before select()ing again
        _condition.acquire()
        print 'tkinternet: scheduling event'
        # Tell the main thread to go boogie when there is...
        _root.after(0, worker)
        _condition.wait()
        _condition.release()

def install(widget):
    global _root
    global _condition
    import threading # Oh no, Mr. Bill.
    main.installWaker()
    threadable.isInIOThread = isInIOThread
    _condition = threading.Condition()
    _root = widget
    t = threading.Thread(target=waiter)
    t.start()

def isInIOThread():
    import thread
    return (thread.get_ident() == _condition)

def stop():
    global stopped
    stopped = 1
    main.waker.wakeUp()
