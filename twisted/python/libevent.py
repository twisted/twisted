# -*- test-case-name: twisted.test.test_libevent -*-
# Copyright (c) 2007  Twisted Matrix Laboratories
# Copyright (c) 2006  Andy Gross <andy@andygross.org>
# Copyright (c) 2006  Nick Mathewson
# See libevent_LICENSE for licensing information.

"""
Libevent wrapper: define shortcut for default EventBase object.
"""

from twisted.python._libevent import *


createEvent = DefaultEventBase.createEvent

createTimer = DefaultEventBase.createTimer

createSignalHandler = DefaultEventBase.createSignalHandler

loop = DefaultEventBase.loop

loopExit = DefaultEventBase.loopExit

dispatch = DefaultEventBase.dispatch

