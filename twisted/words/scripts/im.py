# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import os

def run():
    if os.name == 'java':
        from twisted.internet import javareactor
        javareactor.install()
        from twisted.words.im.jyaccount import AccountManagementGUI
        AccountManagementGUI()
    else:
        from twisted.internet import gtkreactor
        gtkreactor.install()
        from twisted.words.im.gtkaccount import AccountManager
        AccountManager()

    from twisted.internet import reactor
    reactor.run()

if __name__ == '__main__':
    run()
