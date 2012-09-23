# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The reactor is the Twisted event loop within Twisted, the loop which drives
applications using Twisted. The reactor provides APIs for networking,
threading, dispatching events, and more.

The default reactor depends on the platform and will be installed if this
module is imported without another reactor being explicitly installed
beforehand. Importing this module will get a reference to whichever reactor
is installed.

The recommended way to get references to the reactor is to pass and accept the
reactor as a parameter where it is needed, and to import the reactor only at
the root of the application.  This simplifies unit testing and may make it
easier to one day support multiple reactors (as a performance enhancement),
though this is not currently possible.

For example, if the library code is::

    def do_something_later(*args, reactor=None, **kwargs):
        reactor.callLater(5, do_something, *args, **kwargs)

And the application or plugin code has something like::

    def makeService(options):
        import reactor
        ...
        do_something_later("something", reactor=reactor)

Then the `do_something_later` function can then be tested by passing a
L{IReactorTime<twisted.internet.interfaces.IReactorTime>} provider, instead of
a reactor (see L{twisted.internet.task.Clock}).  If the library code imported
the reactor instead of accepting it as an argument, then the reactor may need
to be monkey-patched with a mocked version when tested.

Also, the fewer places the reactor is imported in one location, the easier it
is to debug "reactor already installed" errors, which can happen if `twistd`
is run with a specified reactor, and the application code imports the reactor
too early.

@see: L{IReactorCore<twisted.internet.interfaces.IReactorCore>}
@see: L{IReactorTime<twisted.internet.interfaces.IReactorTime>}
@see: L{IReactorProcess<twisted.internet.interfaces.IReactorProcess>}
@see: L{IReactorTCP<twisted.internet.interfaces.IReactorTCP>}
@see: L{IReactorSSL<twisted.internet.interfaces.IReactorSSL>}
@see: L{IReactorUDP<twisted.internet.interfaces.IReactorUDP>}
@see: L{IReactorMulticast<twisted.internet.interfaces.IReactorMulticast>}
@see: L{IReactorUNIX<twisted.internet.interfaces.IReactorUNIX>}
@see: L{IReactorUNIXDatagram<twisted.internet.interfaces.IReactorUNIXDatagram>}
@see: L{IReactorFDSet<twisted.internet.interfaces.IReactorFDSet>}
@see: L{IReactorThreads<twisted.internet.interfaces.IReactorThreads>}
@see: L{IReactorPluggableResolver<twisted.internet.interfaces.IReactorPluggableResolver>}
"""

from __future__ import division, absolute_import

import sys
del sys.modules['twisted.internet.reactor']
from twisted.internet import default
default.install()
