# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
I{Private} test utilities for use throughout Twisted's test suite.  Unlike
C{proto_helpers}, this is no exception to the
don't-use-it-outside-Twisted-we-won't-maintain-compatibility rule!

@note: Maintainers be aware: things in this module should be gradually promoted
    to more full-featured test helpers and exposed as public API as your
    maintenance time permits.  In order to be public API though, they need
    their own test cases.
"""

import os
import sys

from io import BytesIO
from xml.dom import minidom as dom

from twisted.internet import utils
from twisted.internet.protocol import FileWrapper
from twisted.python import usage
from twisted.python.filepath import FilePath
from twisted.trial.unittest import SkipTest



class IOPump:
    """Utility to pump data between clients and servers for protocol testing.

    Perhaps this is a utility worthy of being in protocol.py?
    """
    def __init__(self, client, server, clientIO, serverIO):
        self.client = client
        self.server = server
        self.clientIO = clientIO
        self.serverIO = serverIO

    def flush(self):
        "Pump until there is no more input or output."
        while self.pump():
            pass

    def pump(self):
        """Move data back and forth.

        Returns whether any data was moved.
        """
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        cData = self.clientIO.read()
        sData = self.serverIO.read()
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        self.clientIO.truncate()
        self.serverIO.truncate()
        for byte in cData:
            self.server.dataReceived(byte)
        for byte in sData:
            self.client.dataReceived(byte)
        if cData or sData:
            return 1
        else:
            return 0


def returnConnected(server, client):
    """Take two Protocol instances and connect them.
    """
    cio = BytesIO()
    sio = BytesIO()
    client.makeConnection(FileWrapper(cio))
    server.makeConnection(FileWrapper(sio))
    pump = IOPump(client, server, cio, sio)
    # Challenge-response authentication:
    pump.flush()
    # Uh...
    pump.flush()
    return pump



class XMLAssertionMixin(object):
    """
    Test mixin defining a method for comparing serialized XML documents.

    Must be mixed in to a L{test case<unittest.TestCase>}.
    """

    def assertXMLEqual(self, first, second):
        """
        Verify that two strings represent the same XML document.

        @param first: An XML string.
        @type first: L{bytes}

        @param second: An XML string that should match C{first}.
        @type second: L{bytes}
        """
        self.assertEqual(
            dom.parseString(first).toxml(),
            dom.parseString(second).toxml())



class _Equal(object):
    """
    A class the instances of which are equal to anything and everything.
    """
    def __eq__(self, other):
        return True


    def __ne__(self, other):
        return False



class _NotEqual(object):
    """
    A class the instances of which are equal to nothing.
    """
    def __eq__(self, other):
        return False


    def __ne__(self, other):
        return True



class ComparisonTestsMixin(object):
    """
    A mixin which defines a method for making assertions about the correctness
    of an implementation of C{==} and C{!=}.

    Use this to unit test objects which follow the common convention for C{==}
    and C{!=}:

        - The object compares equal to itself
        - The object cooperates with unrecognized types to allow them to
          implement the comparison
        - The object implements not-equal as the opposite of equal
    """
    def assertNormalEqualityImplementation(self, firstValueOne, secondValueOne,
                                           valueTwo):
        """
        Assert that C{firstValueOne} is equal to C{secondValueOne} but not
        equal to C{valueOne} and that it defines equality cooperatively with
        other types it doesn't know about.

        @param firstValueOne: An object which is expected to compare as equal to
            C{secondValueOne} and not equal to C{valueTwo}.

        @param secondValueOne: A different object than C{firstValueOne} but
            which is expected to compare equal to that object.

        @param valueTwo: An object which is expected to compare as not equal to
            C{firstValueOne}.
        """
        # This doesn't use assertEqual and assertNotEqual because the exact
        # operator those functions use is not very well defined.  The point
        # of these assertions is to check the results of the use of specific
        # operators (precisely to ensure that using different permutations
        # (eg "x == y" or "not (x != y)") which should yield the same results
        # actually does yield the same result). -exarkun
        self.assertTrue(firstValueOne == firstValueOne)
        self.assertTrue(firstValueOne == secondValueOne)
        self.assertFalse(firstValueOne == valueTwo)
        self.assertFalse(firstValueOne != firstValueOne)
        self.assertFalse(firstValueOne != secondValueOne)
        self.assertTrue(firstValueOne != valueTwo)
        self.assertTrue(firstValueOne == _Equal())
        self.assertFalse(firstValueOne != _Equal())
        self.assertFalse(firstValueOne == _NotEqual())
        self.assertTrue(firstValueOne != _NotEqual())



class ExampleTestBaseMixin(object):
    """
    This is a mixin which adds an example to the path, tests it, and then
    removes it from the path and unimports the modules which the test loaded.
    Test cases which test example code and documentation listings should use
    this.

    This is done this way so that examples can live in isolated path entries,
    next to the documentation, replete with their own plugin packages and
    whatever other metadata they need.  Also, example code is a rare instance
    of it being valid to have multiple versions of the same code in the
    repository at once, rather than relying on version control, because
    documentation will often show the progression of a single piece of code as
    features are added to it, and we want to test each one.
    """

    def setUp(self):
        """
        Add our example directory to the path and record which modules are
        currently loaded.
        """
        self.originalPath = sys.path[:]
        self.originalModules = sys.modules.copy()

        # Get branch root
        here = FilePath(__file__).parent().parent().parent()

        # Find the example script within this branch
        for childName in self.exampleRelativePath.split('/'):
            here = here.child(childName)
            if not here.exists():
                raise SkipTest(
                    "Examples (%s) not found - cannot test" % (here.path,))
        self.examplePath = here

        # Add the example parent folder to the Python path
        sys.path.append(self.examplePath.parent().path)

        # Import the example as a module
        moduleName = self.examplePath.basename().split('.')[0]
        self.example = __import__(moduleName)


    def tearDown(self):
        """
        Remove the example directory from the path and remove all
        modules loaded by the test from L{sys.modules}.
        """
        sys.modules.clear()
        sys.modules.update(self.originalModules)
        sys.path[:] = self.originalPath



class ExecutableExampleTestMixin(ExampleTestBaseMixin):
    """
    Tests for consistency and executability in executable example
    scripts.
    """

    def test_executableModule(self):
        """
        The example scripts should have an if __name__ ==
        '__main__' so that they do something when called.
        """
        args = [self.examplePath.path, '--help']

        # Give the subprocess access to the same Python paths as the
        # parent process
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)

        d = utils.getProcessOutputAndValue(sys.executable, args, env=env)
        def whenComplete(res):
            out, err, code = res
            self.assertEqual(
                out.splitlines()[0],
                self.example.Options().synopsis)
        d.addCallback(whenComplete)
        return d


    def test_shebang(self):
        """
        The example scripts start with the standard shebang line.
        """
        self.assertEquals(
            self.examplePath.open().readline().rstrip(),
            '#!/usr/bin/env python')


    def test_definedOptions(self):
        """
        Example scripts contain an Options class which is a subclass
        of L{twisted.python.usage.Options}
        """
        self.assertIsInstance(self.example.Options(), usage.Options)


    def test_usageMessageConsistency(self):
        """
        The example script usage message should begin with a "Usage:"
        summary line.
        """
        out = self.example.Options.synopsis
        self.assertTrue(
            out.startswith('Usage:'),
            'Usage message first line should start with "Usage:". '
            'Actual: %r' % (out,))


    def test_usageErrorsBeginWithUsage(self):
        """
        The example script first prints a full usage message to stderr
        if it is passed incorrect command line arguments.
        """

        fakeErr = BytesIO()
        self.patch(sys, 'stderr', fakeErr)

        self.assertRaises(
            SystemExit,
            self.example.main,
            None, '--unexpected_option')
        err = fakeErr.getvalue()
        usageMessage = str(self.example.Options())
        self.assertEqual(
            err[:len(usageMessage)],
            usageMessage)


    def test_usageErrorsEndWithError(self):
        """
        The example script prints an "Error:" summary on the last line
        of stderr when incorrect arguments are supplied.
        """
        fakeErr = BytesIO()
        self.patch(sys, 'stderr', fakeErr)

        self.assertRaises(
            SystemExit,
            self.example.main,
            None, '--unexpected_option')
        err = fakeErr.getvalue().splitlines()
        self.assertTrue(
            err[-1].startswith('ERROR:'),
            'Usage message last line should start with "ERROR:" '
            'Actual: %r' % (err[-1],))
