# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The reactor is the Twisted event loop within Twisted, the loop which drives
applications using Twisted.  The reactor provides APIs for networking,
threading, dispatching events, and more.

This module is the way to access the current global reactor, by doing::

    from twisted.internet import reactor

The specific capabilities of the default reactor depends on your platform, and
will be installed if this module is imported without another reactor being
explicitly installed beforehand.  Regardless of which reactor is installed,
importing this module is the way to get a reference to it.

In order to minimize dependencies on mutable global state, new application code
should prefer to pass and accept the reactor as a parameter where it is needed,
rather than relying on being able to import this module to get a reference.

To get the reactor at the beginning of your program without using this global
import, use L{twisted.internet.task.react}, like so::

    # If you need a custom reactor, you can install it at the beginning:
    from twisted.internet.custom_reactor import install
    install()

    from twisted.internet.task import react
    from twisted.internet.defer import Deferred

    async def main(reactor: IReactorTCP) -> None:
        reactor.listenTCP(...)
        await Deferred()        # wait forever

    if __name__ == '__main__':
        react(main, ())

This simplifies testing and may make it easier to one day support multiple
reactors.

@note: Another reason to prefer getting the reactor as a parameter is that type
    information about the object you get from C{from twisted.internet import
    reactor} is always slightly inaccurate.  At runtime, interfaces are only
    contextually provided depending upon the installed reactor, the installed
    libraries, and the capabilities of your platform, so there is no "correct"
    type for this object to statically be.  Thus, it provides a conglomeration
    of many of the most common reactor interfaces which are usually available.

    To be fully correct in new code, it's best to always adapt the reactor to
    your desired interface in order to interrogate its capabilities; for
    example, if you need to call a method on
    L{IReactorSSL<twisted.internet.interfaces.IReactorSSL>} but provide useful
    error messages if it's not available, you can do something like this::

        from twisted.internet import reactor

        if (sslReactor := IReactorSSL(reactor, None)) is not None:
            sslReactor.listenSSL(...)
        else:
            print("TLS support not available.")

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

@see: L{IReactorSocket<twisted.internet.interfaces.IReactorSocket>}

@see: L{IReactorWin32Events<twisted.internet.interfaces.IReactorWin32Events>}

@see: L{IReactorThreads<twisted.internet.interfaces.IReactorThreads>}

@see:
    L{IReactorPluggableResolver<twisted.internet.interfaces.IReactorPluggableResolver>}

@see: L{IReactorDaemonize<twisted.internet.interfaces.IReactorDaemonize>}
"""


import sys

del sys.modules["twisted.internet.reactor"]
from twisted.internet import default

default.install()
