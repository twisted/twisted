
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

"""This module is deprecated.

The functionality it used to provide is now provided by reactor.callFromThread,
and reactor.callLater(0, ...).
"""

def schedule(callable, *args, **kw):
    from twisted.internet import reactor
    from twisted.python import log
    log.msg("using deprecated task.schedule.  "
            "use twisted.internet.reactor.callFromThread/callLater instead.")
    apply(reactor.callFromThread, (callable,)+ args, kw)

