# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

"""Support for asynchronously authenticating using PAM.
"""

from __future__ import nested_scopes

import PAM
from twisted.internet import reactor
from twisted.internet import threads, defer

import sys, time, getpass, threading, os

def pamAuthenticateThread(service, user, conv):
    def _conv(p, items):
        try:
            d = conv(items)
        except:
            import traceback
            traceback.print_exc()
            return
        ev = threading.Event()
        def cb(r):
            ev.r = (1, r)
            ev.set()
        def eb(e):
            ev.r = (0, e)
            ev.set()
        reactor.callFromThread(d.addCallbacks, cb, eb)
        ev.wait()
        done = ev.r
        if done[0]:
            return done[1]
        else:
            raise done[1].type, done[1].value

    pam = PAM.pam()
    pam.start(service, user, _conv)
    gid = os.getegid()
    uid = os.geteuid()
    os.setegid(0)
    os.seteuid(0)
    try:
        pam.authenticate() # these will raise
        pam.acct_mgmt()
    except:
        os.setegid(gid)
        os.seteuid(uid)
        raise
    else:
        os.setegid(gid)
        os.seteuid(uid)
        return 1

def defConv(items):
    resp = []
    for i in range(len(items)):
        message, kind = items[i]
        if kind == 1: # password
            p = getpass.getpass(message)
            resp.append((p, 0))
        elif kind == 2: # text
            p = raw_input(message)
            resp.append((p, 0))
        elif kind in (3,4):
            print message
            resp.append(("", 0))
        else:
            return defer.fail('foo')
    d = defer.succeed(resp)
    return d

def pamAuthenticate(service, user, conv):
    return threads.deferToThread(pamAuthenticateThread, service, user, conv)
