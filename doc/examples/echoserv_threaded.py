
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

#  Threading in twisted
# ======================
#
# Many operations in twisted are not thread safe. Therefore, when using threads
# you need to do a number of things.
#
# First, in order to enable threads, you can not just import 'thread'; you must
# import twisted.python.threadable and call threadable.init().  This prepares
# Twisted to be used with threads.
#
# When you want to call a non thread-safe operation, you don't call it, but
# instead you add the operation to the twisted.internet.task scheduler. The
# main thread running the event loop will then read these tasks from the
# scheduler and execute them.
#
# The following example server has a thread for each connections that does the
# actual processing of the protocol, in this case echoing back all received
# data.
#
# For a more scalable solution you might want to use a thread pool, where
# commands received by each protocol are dispatched to threads. Check out
# twisted.internet.threadtask for details.

import threading, Queue
from twisted.python import threadable
threadable.init()

from twisted.protocols.protocol import Protocol, Factory
from twisted.internet import task

### Protocol Implementation

# This is just about the simplest possible protocol

class Echo(Protocol):

    def connectionMade(self):
        self.messagequeue = Queue.Queue()
        self.handler = Handler(self)
        self.handler.start()

    def dataReceived(self, data):
        "As soon as any data is received, add it to queue."
        self.messagequeue.put(data)

    def send(self, data):
        """Schedule data to be written in a thread-safe manner"""
        # instead of doing self.transport.write(data), which is not
        # thread safe, we do:
        task.schedule(self.transport.write, data)

    def connectionLost(self):
        # tell thread to shutdown
        self.messagequeue.put(None)
        del self.handler


class Handler(threading.Thread):
    """Thread that does processing on data received from Echo protocol"""

    def __init__(self, protocol):
        threading.Thread.__init__(self)
        self.protocol = protocol

    def run(self):
        while 1:
            # read data from queue
            data = self.protocol.messagequeue.get()
            if data != None:
                # write back data unchanged
                self.protocol.send(data)
            else:
                # connection was closed
                return


### Persistent Application Builder

# This builds a .tap file

if __name__ == '__main__':
    from twisted.internet.main import Application
    factory = Factory()
    factory.protocol = Echo
    app = Application("echo")
    app.listenOn(8000,factory)
    app.run(save=0)

