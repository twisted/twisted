# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is a mock win32process module.

The purpose of this module is mock process creation for the PID test.

CreateProcess(...) will spawn a process, and always return a PID of 42.
"""

import pywincffi.kernel32

from pywincffi.core import dist

_, _library = dist.load()

GetExitCodeProcess = pywincffi.kernel32.GetExitCodeProcess

STARTUPINFO = _library.STARTUPINFO

STARTF_USESTDHANDLES = _library.STARTF_USESTDHANDLES


def CreateProcess(appName,
                  cmdline,
                  procSecurity,
                  threadSecurity,
                  inheritHandles,
                  newEnvironment,
                  env,
                  workingDir,
                  startupInfo):
    """
    This function mocks the generated pid aspect of the win32.CreateProcess
    function.
      - the true win32process.CreateProcess is called
      - return values are harvested in a tuple.
      - all return values from createProcess are passed back to the calling
        function except for the pid, the returned pid is hardcoded to 42
    """

    hProcess, hThread, dwPid, dwTid = pywincffi.kernel32.CreateProcess(
                      appName,
                      cmdline,
                      procSecurity,
                      threadSecurity,
                      inheritHandles,
                      newEnvironment,
                      env,
                      workingDir,
                      startupInfo)
    dwPid = 42
    return (hProcess, hThread, dwPid, dwTid)
