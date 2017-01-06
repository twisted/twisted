# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import absolute_import, division

from twisted.application.reactors import Reactor
from twisted.python.reflect import requireModule

default = Reactor(
    'default', 'twisted.internet.default',
    'A reasonable default: poll(2) if available, otherwise select(2).')

select = Reactor(
    'select', 'twisted.internet.selectreactor', 'select(2)-based reactor.')

poll = Reactor(
    'poll', 'twisted.internet.pollreactor', 'poll(2)-based reactor.')
epoll = Reactor(
    'epoll', 'twisted.internet.epollreactor', 'epoll(4)-based reactor.')

kqueue = Reactor(
    'kqueue', 'twisted.internet.kqreactor', 'kqueue(2)-based reactor.')

__all__ = [
    "default", "select", "poll", "epoll", "kqueue",
]

if requireModule("twisted.internet.cfreactor") is not None:
    cf = Reactor(
        'cf' , 'twisted.internet.cfreactor',
        'CoreFoundation integration reactor.')

    __all__.extend([
         "cf"
    ])


if requireModule("twisted.internet.asyncioreactor") is not None:
    asyncio = Reactor(
        'asyncio', 'twisted.internet.asyncioreactor',
        'asyncio integration reactor')

    __all__.extend([
        "asyncio"
    ])

if requireModule("twisted.internet.wxreactor") is not None:
    wx = Reactor(
        'wx', 'twisted.internet.wxreactor', 'wxPython integration reactor.')
    __all__.extend([
        "wx"
    ])

if requireModule("twisted.internet.gireactor") is not None:
    gi = Reactor(
        'gi', 'twisted.internet.gireactor',
        'GObject Introspection integration reactor.')
    __all__.extend([
         "gi"
    ])

if requireModule("twisted.internet.gtk3reactor") is not None:
    gtk3 = Reactor(
         'gtk3', 'twisted.internet.gtk3reactor', 'Gtk3 integration reactor.')
    __all__.extend([
        "gtk3"
    ])

if requireModule("twisted.internet.gtk2reactor") is not None:
    gtk2 = Reactor(
        'gtk2', 'twisted.internet.gtk2reactor', 'Gtk2 integration reactor.')
    __all__.extend([
        "gtk2"
])

if requireModule("twisted.internet.glib2reactor") is not None:
    glib2 = Reactor(
        'glib2', 'twisted.internet.glib2reactor',
        'GLib2 event-loop integration reactor.')
    __all__.extend([
    "glib2"
])

if requireModule("twisted.internet.win32eventreactor") is not None:
    win32er = Reactor(
        'win32', 'twisted.internet.win32eventreactor',
        'Win32 WaitForMultipleObjects-based reactor.')
    __all__.extend([
        "win32er"
    ])

if requireModule("twisted.internet.iocpreactor") is not None:
    iocp = Reactor(
        'iocp', 'twisted.internet.iocpreactor',
        'Win32 IO Completion Ports-based reactor.')
    __all__.extend([
        "iocp"
    ])
