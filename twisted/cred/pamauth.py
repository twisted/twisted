# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for asynchronously authenticating using PAM.
"""


import PAM

import getpass, threading, os

from twisted.internet import threads, defer

def pamAuthenticateThread(service, user, conv):
    def _conv(items):
        from twisted.internet import reactor
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

    return callIntoPAM(service, user, _conv)

def callIntoPAM(service, user, conv):
    """A testing hook.
    """
    pam = PAM.pam()
    pam.start(service)
    pam.set_item(PAM.PAM_USER, user)
    pam.set_item(PAM.PAM_CONV, conv)
    gid = os.getegid()
    uid = os.geteuid()
    os.setegid(0)
    os.seteuid(0)
    try:
        pam.authenticate() # these will raise
        pam.acct_mgmt()
        return 1
    finally:
        os.setegid(gid)
        os.seteuid(uid)

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
