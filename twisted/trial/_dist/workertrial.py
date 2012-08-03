# -*- test-case-name: twisted.trial._dist.test.test_workertrial -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of L{AMP} worker commands, and main executable entry point for
the workers.

@since: 12.2
"""

import _preamble

import sys
import os
import errno

from twisted.internet.protocol import FileWrapper
from twisted.python.log import startLoggingWithObserver, textFromEventDict
from twisted.protocols.amp import AMP
from twisted.trial.runner import TrialSuite, TestLoader
from twisted.trial._dist.workerreporter import WorkerReporter
from twisted.trial._dist import workercommands, managercommands
from twisted.trial._dist.options import WorkerOptions
from twisted.trial._dist import _WORKER_AMP_STDIN, _WORKER_AMP_STDOUT



class WorkerProtocol(AMP):
    """
    The worker-side trial distributed protocol.
    """

    def __init__(self, forceGarbageCollection=False):
        self._loader = TestLoader()
        self._result = WorkerReporter(self)
        self._forceGarbageCollection = forceGarbageCollection


    def run(self, testCase):
        """
        Run a test case by name.
        """
        case = self._loader.loadByName(testCase)
        suite = TrialSuite([case], self._forceGarbageCollection)
        suite.run(self._result)
        return {'success': True}

    workercommands.Run.responder(run)


    def start(self, directory):
        """
        Set up the worker, moving into given directory for tests to run in
        them.
        """
        os.chdir(directory)
        return {'success': True}

    workercommands.Start.responder(start)



class WorkerLogObserver(object):
    """
    A log observer that forward its output to a L{AMP} protocol.
    """

    def __init__(self, protocol):
        """
        @param protocol: a connected L{AMP} protocol instance.
        @type protocol: L{AMP}
        """
        self.protocol = protocol


    def emit(self, eventDict):
        """
        Produce a log output.
        """
        text = textFromEventDict(eventDict)
        if text is None:
            return
        self.protocol.callRemote(managercommands.TestWrite, out=text)



def main():
    """
    Main function to be run if __name__ == "__main__".
    """
    config = WorkerOptions()
    config.parseOptions()

    workerProtocol = WorkerProtocol(config['force-gc'])

    protocolIn = os.fdopen(_WORKER_AMP_STDIN)
    protocolOut = os.fdopen(_WORKER_AMP_STDOUT, 'w')
    workerProtocol.makeConnection(FileWrapper(protocolOut))

    observer = WorkerLogObserver(workerProtocol)
    startLoggingWithObserver(observer.emit, False)

    while True:
        try:
            r = protocolIn.read(1)
        except IOError, e:
            if e.args[0] == errno.EINTR:
                sys.exc_clear()
                continue
            else:
                raise
        if r == '':
            break
        else:
            workerProtocol.dataReceived(r)
            protocolOut.flush()
            sys.stdout.flush()
            sys.stderr.flush()

    if config.tracer:
        sys.settrace(None)
        results = config.tracer.results()
        results.write_results(show_missing=True, summary=False,
                              coverdir=config.coverdir().path)



if __name__ == '__main__':
    main()
