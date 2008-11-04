# Copyright (c) 2006-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.internet import defer, error
import os
import compiler
import twisted
import sys

class TestCase(unittest.TestCase):
    def setUp(self):
        if not (hasattr(twisted, '__path__') and twisted.__path__):
            raise unittest.SkipTest

        path = os.path.join(twisted.__path__[0], '..', 'doc')
        if not os.path.exists(path):
            raise unittest.SkipTest

        self.fingerpath = os.path.join(path,
                'core/howto/tutorial/listings/finger')
        sys.path.append(self.fingerpath)

    def tearDown(self):
        sys.path.remove(self.fingerpath)

class AbstractFingerTestCase(TestCase):
    """
    Abstract parent that will create a fake 'module' based on the 'module'
    attribute of an instance in the L{setUp}.
    """
    module = None

    def setUp(self):
        super(AbstractFingerTestCase, self).setUp()
        self.finger = __import__(self.module)

class Finger2TestCase(AbstractFingerTestCase):

    module = 'finger02'

    def testFactory(self):
        """
        Create a factory, and make sure that it builds the correct protocol.
        """
        p = self.getProtocol()
        self.assert_(isinstance(p, self.finger.FingerProtocol))

    def getFactory(self):
        return self.finger.FingerFactory()

    def getProtocol(self):
        return self.getFactory().buildProtocol(self)

class Finger3TestCase(Finger2TestCase):

    module = 'finger03'

    # because we mock a transport, we need this attribute
    disconnecting = False

    def setUp(self):
        self.loseConnectionCalled = False
        super(Finger3TestCase, self).setUp()

    def loseConnection(self):
        self.loseConnectionCalled = True

    def testProtocol(self):
        """
        Create a protocol directly, and make sure that it correctly drops the
        connection when it is created.
        """
        p = self.getProtocol()
        p.transport = self
        p.connectionMade()
        self.assert_(self.loseConnectionCalled)

class Finger4TestCase(Finger3TestCase):
    """
    loseConnection functionality is inherited from Finger3TestCase
    """

    module = 'finger04'

    def testProtocol(self):
        """
        Create a protocol directly, and make sure that it correctly drops the
        connection when a line is received.
        """
        p = self.getProtocol()
        p.transport = self
        p.dataReceived('test\r\n')
        self.assert_(self.loseConnectionCalled)

class Finger5TestCase(Finger3TestCase):
    """
    loseConnection functionality is inherited from Finger3TestCase
    """

    module = 'finger05'

    def setUp(self):
        super(Finger5TestCase, self).setUp()
        self.data = None

    def write(self, data):
        self.data = data

    def testProtocol(self):
        """
        Create a protocol directly, and make sure that it correctly 
        writes some data and drops the connection when data is received.
        """
        p = self.getProtocol()
        p.transport = self
        p.dataReceived('test\r\n')
        self.assertEquals(self.data, "No such user\r\n")
        self.assert_(self.loseConnectionCalled)

class Finger6TestCase(Finger5TestCase):

    module = 'finger06'

    def testGetUser(self):
        f = self.getFactory()
        self.assertEquals('No such user', f.getUser(''))

class Finger7TestCase(Finger6TestCase):

    module = 'finger07'

    def getFactory(self):
        return self.finger.FingerFactory(moshez='Happy and well')

    def testGetUser(self):
        f = self.getFactory()
        self.assertEquals('No such user', f.getUser(''))
        self.assertEquals('Happy and well', f.getUser('moshez'))

    def testFingerTestUser(self):
        p = self.getProtocol()
        p.transport = self
        p.dataReceived('moshez' + p.delimiter)
        self.assertEquals(self.data, "Happy and well" + p.delimiter)
        self.assert_(self.loseConnectionCalled)

class Finger8TestCase(Finger7TestCase):

    module = 'finger08'

    def getUser(self, name):
        return defer.fail(Exception())

    def testErrorOnCallback(self):
        p = self.getProtocol()
        p.factory = self
        p.transport = self
        p.dataReceived('moshez' + p.delimiter)
        self.assert_(self.loseConnectionCalled)
        self.assertEquals(self.data, "Internal error in server" + p.delimiter)

    def testGetUser(self):
        f = self.getFactory()
        return f.getUser('').addCallback(
            self.assertEquals, 'No such user')

class Finger11TestCase(Finger8TestCase):

    module = 'finger11'

    def getFactory(self):
        return self.finger.factory

class Finger12TestCase(Finger11TestCase):

    module = 'finger12'

    def getFingerSetterFactory(self):
        return self.finger.fsfactory

    def testFingerSetter(self):
        self.getFingerSetterFactory().setUser('testuser', 'teststatus')
        return self.getFactory().getUser('testuser'
                ).addCallback(self.assertEquals, 'teststatus')

class Finger13TestCase(Finger12TestCase):

    module = 'finger13'

    def getFingerSetterFactory(self):
        return self.finger.svc.getFingerSetterFactory()

    def getFactory(self):
        return self.finger.svc.getFingerFactory()

class Finger14TestCase(Finger11TestCase):

    module = 'finger14'

    def setUp(self):
        """
        Use C{startService} to cause etc.users to be read correctly.
        C{FingerService.filename} needs to be mutated to point to the correct
        path.
        """
        super(Finger14TestCase, self).setUp()
        self.finger.svc.filename = os.path.join(self.fingerpath, 'etc.users')
        self.finger.svc.startService()

    def tearDown(self):
        """
        Stopping the service causes a C{callLater} to be cancelled.
        """
        self.finger.svc.stopService()
        super(Finger14TestCase, self).tearDown()

    def getFactory(self):
        return self.finger.svc.getFingerFactory()

class Finger15TestCase(Finger14TestCase):

    module = 'finger15'

    def getFingerResource(self):
        return self.finger.svc.getResource()

    def testFingerResource(self):
        self.d = defer.Deferred()
        self.getFingerResource().getChild('moshez', self)
        return self.d.addCallback(self.assertEquals, 
                "<h1>moshez</h1><p>Happy and well</p>")

    # To satisfy requirements of being a 'Request' in testFingerResource
    method = 'POST'
    def setHeader(self, name, value):
        pass
    def finish(self):
        self.d.callback(self.data)

class Finger16TestCase(Finger15TestCase):

    module = 'finger16'

class Finger17TestCase(Finger16TestCase):

    module = 'finger17'

class Finger19TestCase(AbstractFingerTestCase):

    module = 'finger19'

    def testApplicationExists(self):
        self.assert_(self.finger.application)

    def testFingerFactory(self):
        ff = self.finger.IFingerFactory(self.finger.svc)
        return ff.getUser('root')

    def tearDown(self):
        self.finger.svc.stopService()

    def setUp(self):
        super(Finger19TestCase, self).setUp()
        self.finger.svc.filename = os.path.join(self.fingerpath, 'etc.users')

class Finger20TestCase(Finger19TestCase):
    
    module = 'finger20'

class Finger21TestCase(Finger20TestCase):
    
    module = 'finger21'

class Finger22TestCase(Finger20TestCase):
    
    module = 'finger22'

class CompileTestCase(TestCase):
    def testCompile(self):
        for filename in ['finger01.py', 'finger02.py', 'finger03.py',
    'finger04.py', 'finger05.py', 'finger06.py', 'finger07.py', 'finger08.py',
    'finger09.py', 'finger10.py', 'finger11.py', 'finger12.py', 'finger13.py',
    'finger14.py', 'finger15.py', 'finger16.py', 'finger17.py', 'finger18.py',
    'finger19.py', 'finger19a.py', 'finger19a_changes.py', 'finger19b.py',
    'finger19b_changes.py', 'finger19c.py', 'finger19c_changes.py', 'finger20.py',
    'finger21.py', 'finger22.py', 'fingerPBclient.py', 'fingerXRclient.py',
    'finger_config.py', 'fingerproxy.py', 'organized-finger.tac',
    'simple-finger.tac']:
            compiler.parseFile(os.path.join(self.fingerpath, filename))

