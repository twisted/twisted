
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

"""Threading in twisted.

Many operations in twisted are not thread safe. Therefore, when using threads
you need to do a number of things.

First, in order to enable threads, you can not just import 'thread'; you must
import twisted.python.threadable and call threadable.init().  This prepares
Twisted to be used with threads.

When you want to call a non thread-safe operation, you don't call it
directly, but schedule it with twisted.internet.reactor.callFromThread. The
main thread running the event loop will then read these callble objects from
the scheduler and execute them.

The following example server has a thread for each connections that does the
actual processing of the protocol, in this case echoing back all received
data. The threads are taken from the twisted thread pool, so only a limited
number of connections can be open at once.

In general, you should only be using threads for blocking operations anyway -
you should *not* write your servers to be like this example.
"""

import threading, Queue
from twisted.python import threadable
threadable.init()

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor

### Threaded Protocol Implementation

class Echo(Protocol):
    """This will run each echo protocol handler in a separate thread.

    This is in most cases a pretty silly thing to do.
    """
    
    def connectionMade(self):
        # create queue for exchanging messages with thread
        self.messagequeue = Queue.Queue()

        # run protocol runner in thread
        reactor.callInThread(self._runProtocol)

    def dataReceived(self, data):
        "As soon as any data is received, add it to queue."
        self.messagequeue.put(data)

    def connectionLost(self):
        # tell thread to shutdown
        self.messagequeue.put(None)

    def _runProtocol(self):
        """This will handle the protocol - it should be run in a separate thread."""
        while 1:
            # read data from queue
            data = self.messagequeue.get()
            if data != None:
                # instead of doing self.transport.write(data), which is not
                # thread safe, we do the following, which is thread-safe:
                reactor.callFromThread(self.transport.write, data)
            else:
                # connection was closed
                return


if __name__ == '__main__':
    from twisted.internet.app import Application
    factory = Factory()
    factory.protocol = Echo
    app = Application("echo")
    app.listenTCP(8000, factory)
    app.run(save=0)

