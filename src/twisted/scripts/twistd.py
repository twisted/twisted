# -*- test-case-name: twisted.test.test_twistd -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The Twisted Daemon: platform-independent interface.

@author: Christopher Armstrong
"""

import os
import sys
from twisted.application import app

from twisted.python.runtime import platformType

if platformType == "win32":
    from twisted.scripts._twistw import (
        ServerOptions,
        WindowsApplicationRunner as _SomeApplicationRunner,
    )
else:
    from twisted.scripts._twistd_unix import (  # type: ignore[misc]
        ServerOptions,
        UnixApplicationRunner as _SomeApplicationRunner,
    )


def runApp(config):
    runner = _SomeApplicationRunner(config)
    runner.run()
    if runner._exitSignal is not None:
        app._exitWithSignal(runner._exitSignal)


def run():
    app.run(runApp, ServerOptions)


def set_path_then_run():
    if sys.version_info < (3, 7):
        sys.path.insert(0, os.path.abspath(os.getcwd()))
    return run()


__all__ = ["run", "runApp"]


if __name__ == "__main__":
    sys.exit(set_path_then_run())
