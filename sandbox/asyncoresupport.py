"""Use asyncore dispatchers with Twisted.

If you have an asyncore dispatcher, you can still use it with twisted.
Just import this module, and don't run asyncore.loop() -- instead start
the twisted event loop, either by calling twisted.internet.main.run(),
or the usual way by calling an Application instance's run() method.
"""

import asyncore

from twisted.internet import main


class AsyncoreLooper:
    """Run the asyncore event loop for asyncore dispatchers."""
    
    def timeout(self):
        if asyncore.socket_map:
            return 0.0
        else:
            return None
    
    def runUntilCurrent(self):
        # I'd have made this 0.0, except that sucks up all your CPU time
        # in the test code, because it runs this and only this repeatedly.
        asyncore.poll(0.001)

asyncoreLooper = AsyncoreLooper()
main.addDelayed(asyncoreLooper)

if __name__ == '__main__':
    # example, run debugging SMTP proxy (requires Python 2.1)
    # telnet to port 8025 to try it out.
    import smtpd
    d = smtpd.DebuggingServer(("localhost", 8025), ("mx1.mail.yahoo.com", 25))
    main.run()
