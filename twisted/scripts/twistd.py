# -*- test-case-name: twisted.test.test_twistd -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The Twisted Daemon: platform-independent interface.

@author: Christopher Armstrong
"""

import signal
import os
from twisted.application import app
from twisted.internet import reactor
from twisted.python import log

from twisted.python.runtime import platformType
if platformType == "win32":
    from twisted.scripts._twistw import ServerOptions, \
        WindowsApplicationRunner as _SomeApplicationRunner
else:
    from twisted.scripts._twistd_unix import ServerOptions, \
        UnixApplicationRunner as _SomeApplicationRunner

class TwistdApplicationRunner(_SomeApplicationRunner):
    """
    @ivar _exitStatus: preserves exit status of twistd.
    """
    def __init__(self, config):
        self._exitStatus = 0
        _SomeApplicationRunner.__init__(self, config)
        signal.signal(signal.SIGINT, self.sigInt)
        signal.signal(signal.SIGTERM, self.sigTerm)

        # Catch Ctrl-Break in windows
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self.sigBreak)

    def sigInt(self, *args):
        """Handle a SIGINT interrupt.
        """
        log.msg("Received SIGINT, shutting down.")
        reactor.callFromThread(reactor.stop)
        self._exitStatus = signal.SIGINT

    def sigBreak(self, *args):
        """Handle a SIGBREAK interrupt.
        """
        log.msg("Received SIGBREAK, shutting down.")
        reactor.callFromThread(reactor.stop)
        self._exitStatus = signal.SIGBREAK

    def sigTerm(self, *args):
        """Handle a SIGTERM interrupt.
        """
        log.msg("Received SIGTERM, shutting down.")
        reactor.callFromThread(reactor.stop)
        self._exitStatus = signal.SIGTERM

def runApp(config):
    app = TwistdApplicationRunner(config)
    app.run()
    if app._exitStatus:
        signal.signal(app._exitStatus, signal.SIG_DFL)
        if platformType == "win32":
            #The application terminated as a result of a CTRL+C.
            #for SIGINT and SIGBREAK (572)
            #The process terminated unexpectedly for SIGTERM (1067)
            replacements = {signal.SIGINT: 572, signal.SIGBREAK: 572,
                            signal.SIGTERM: 1067}
            app._exitStatus = replacements[app._exitStatus]
        os.kill(os.getpid(), app._exitStatus)

def run():
    app.run(runApp, ServerOptions)

__all__ = ['run', 'runApp']
