# -*- test-case-name: twisted.trial.test.test_trial -*-

from cStringIO import StringIO

from twisted import trial
from twisted.trial import reporter, util, runner
from twisted.internet import defer
from twisted.trial.assertions import assertIdentical, assertEqual, assert_

import zope.interface as zi

class BaseTest(object):
    setUpCalled = tearDownCalled = setUpClassCalled = tearDownClassCalled = False
    methodCalled = False
    def setUpClass(self):
        self.setUpClassCalled = True

    def setUp(self):
        self.setUpCalled = True

    def tearDown(self):
        self.tearDownCalled = True

    def tearDownClass(self):
        self.tearDownClassCalled = True

    def testMethod(self):
        self.methodCalled = True


bogus = lambda *a, **kw: None

class BogusReporter(reporter.TreeReporter):
    tbformat = 'plain'
    names = ('module', 'class', 'test')

    cleanerrs = importError = None
    setUpReporterCalled = tearDownReporterCalled = False
    

    def __init__(self):
        super(BogusReporter, self).__init__(StringIO(), 'plain', None, False)
        self.startCtr = dict([(n, 0) for n in self.names])
        self.endCtr = self.startCtr.copy()

    out = property(lambda self:self.stream.getvalue())

    def setUpReporter(self):
        self.setUpReporterCalled = True
        return defer.succeed(None)

    def tearDownReporter(self):
        self.tearDownReporterCalled = True
        return defer.succeed(None)

    def startModule(self, mod):
        super(BogusReporter, self).startModule(mod)
        self.startCtr['module'] += 1
        self.module = mod

    def endModule(self, mod):
        super(BogusReporter, self).endModule(mod)
        self.endCtr['module'] += 1
        assertIdentical(self.module, mod)

    def startClass(self, klass):
        super(BogusReporter, self).startClass(klass)
        self.startCtr['class'] += 1
        self.klass = klass

    def endClass(self, klass):
        super(BogusReporter, self).endClass(klass)
        self.endCtr['class'] += 1
        assertIdentical(self.klass, klass)

    def startTest(self, tm):
        super(BogusReporter, self).startTest(tm)
        self.startCtr['test'] += 1
        self.tm = tm
        
    def endTest(self, tm):
        super(BogusReporter, self).endTest(tm)
        self.endCtr['test'] += 1
        assertIdentical(self.tm, tm)

    def upDownError(self, method, warn=True, printStatus=True):
        super(BogusReporter, self).upDownError(method, False, printStatus)
        self.udeMethod = method

    def reportImportError(self, name, exc):
        self.importError = (name, exc)

    def cleanupErrors(self, errs):
        self.cleanerrs = errs

    def verify(self, failIfImportErrors=True):
        for v in self.setUpReporterCalled, self.tearDownReporterCalled:
            assert_(v)
        for n in self.names:
            assertEqual(self.startCtr[n], self.endCtr[n])
        if failIfImportErrors:
            assert_(not self.importError)


class RegistryBaseMixin(object):
    trialGlobalNames = ('_trialRegistry', '_setUpAdapters', 'registerAdapter', 'adaptWithDefault')
    _suite = None

    # the following is a flag to the reporter.verify() method that gets reset to 
    # True after each testMethod. Most testMethods should not raise importErrors,
    # however, if a test needs to, and it is not an erroneous condition, the testMethod
    # should set this to False before the method returns
    failIfImportErrors = True

    def setUpClass(self):
        # here we replace the trial.__init__ adapter registry 
        # with our own to make sure tests don't alter global state
        self.hookslen = len(zi.interface.adapter_hooks)
        self.registry = trial.TrialAdapterRegistry()
        self.registry.setUpRegistry(hooksListIndex=0)
        self.janitor = util._Janitor()
        self.origReg = {}
        for name in self.trialGlobalNames[1:]:
            self.origReg[name] = getattr(trial, name)
            setattr(trial, name, getattr(self.registry, name))
        trial._trialRegistry = self.registry

    def setUp(self):
        self.registry._setUpAdapters()
        self.reporter = BogusReporter()

    def _getSuite(self, newSuite=False, benchmark=0):
        if self._suite is None or newSuite:
            self._suite = runner.TestSuite(self.reporter, self.janitor, benchmark)
            self._suite._initLogging = bogus
            self._suite._setUpSigchldHandler = bogus
            self._suite._bail = bogus
        return self._suite
    def _setSuite(self, val):
        self._suite = val
    suite = property(_getSuite)

    def tearDown(self):
        self.registry._clearAdapterRegistry()
        self.reporter.verify(self.failIfImportErrors)
        self.failIfImportErrors = True
        self._suite = None

    def tearDownClass(self):
        assertEqual(len(zi.interface.adapter_hooks), self.hookslen)
        for k, v in self.origReg.iteritems():
            setattr(trial, k, v)

    def getReporter(self):
        return self.reporter

