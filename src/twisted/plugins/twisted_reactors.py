# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import absolute_import, division

from twisted.application.reactors import Reactor
from twisted.python.reflect import requireModule

def _addReactorToAll(shortName, moduleName, description):
    """

    @param shortName: Short name of reactor
    @param moduleName: The fully-qualified module name of the reactor
    @param description: Description of reactor
    @return: newly created reactor
    @rtype: L{Reactor} or L{None}
    """
    newReactor = None
    if requireModule(moduleName) is not None:
        newReactor = Reactor(shortName, moduleName, description)
        __all__.append(shortName)
    return newReactor


__all__ = []

default = _addReactorToAll(
    'default', 'twisted.internet.default',
    'A reasonable default: poll(2) if available, otherwise select(2).')

select = _addReactorToAll(
    'select', 'twisted.internet.selectreactor', 'select(2)-based reactor.')

poll = _addReactorToAll(
    'poll', 'twisted.internet.pollreactor', 'poll(2)-based reactor.')
epoll = _addReactorToAll(
    'epoll', 'twisted.internet.epollreactor', 'epoll(4)-based reactor.')

kqueue = _addReactorToAll(
    'kqueue', 'twisted.internet.kqreactor', 'kqueue(2)-based reactor.')

cf = _addReactorToAll(
    'cf' , 'twisted.internet.cfreactor',
    'CoreFoundation integration reactor.')

asyncio = _addReactorToAll(
    'asyncio', 'twisted.internet.asyncioreactor',
    'asyncio integration reactor')

wx = _addReactorToAll(
    'wx', 'twisted.internet.wxreactor', 'wxPython integration reactor.')

gi = _addReactorToAll(
    'gi', 'twisted.internet.gireactor',
    'GObject Introspection integration reactor.')

gtk3 = _addReactorToAll(
     'gtk3', 'twisted.internet.gtk3reactor', 'Gtk3 integration reactor.')

gtk2 = _addReactorToAll(
    'gtk2', 'twisted.internet.gtk2reactor', 'Gtk2 integration reactor.')

glib2 = _addReactorToAll(
    'glib2', 'twisted.internet.glib2reactor',
    'GLib2 event-loop integration reactor.')

win32er = _addReactorToAll(
    'win32', 'twisted.internet.win32eventreactor',
    'Win32 WaitForMultipleObjects-based reactor.')

iocp = _addReactorToAll(
    'iocp', 'twisted.internet.iocpreactor',
    'Win32 IO Completion Ports-based reactor.')
