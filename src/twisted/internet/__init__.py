# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Internet: Asynchronous I/O and Events.

Twisted Internet is a collection of compatible event-loops for Python. It contains
the code to dispatch events to interested observers and a portable API so that
observers need not care about which event loop is running. Thus, it is possible
to use the same code for different loops, from Twisted's basic, yet portable,
select-based loop to the loops of various GUI toolkits like GTK+ or Tk.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .interfaces import (
        IReactorCore,
        IReactorFDSet,
        IReactorProcess,
        IReactorTCP,
        IReactorTime,
    )

    class _IReactorCommon(
        IReactorCore,
        IReactorTime,
        IReactorFDSet,
        IReactorTCP,
        IReactorProcess,
    ):
        """
        A make-believe interface supporting all the commonly-implemented parts
        of the reactor.  For other interfaces which may or may not be supplied
        by the environment, i.e. IReactorSSL, adapt the reactor like
        C{IReactorSSL(reactor)}.
        """

    reactor: _IReactorCommon
