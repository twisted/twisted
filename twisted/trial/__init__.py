# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

"""Unit testing framework."""

try:
    from zope.interface import interface, declarations
    from zope.interface.adapter import AdapterRegistry
except ImportError:
    raise ImportError, "you need zope.interface installed (http://zope.org/Products/ZopeInterface/)"


class TrialAdapterRegistry(object):
    # we define a private adapter registry here to avoid conflicts and
    # have a bit more control

    def setUpRegistry(self, hooksListIndex=-1):
        self._registry = AdapterRegistry()
        interface.adapter_hooks.insert(hooksListIndex, self._hook)

    def registerAdapter(self, adapterFactory, origInterface, *interfaceClasses):
        if not hasattr(self, '_registry'):
            self.setUpRegistry()

        assert interfaceClasses, "You need to pass an Interface"

        if not isinstance(origInterface, interface.InterfaceClass):
            origInterface = declarations.implementedBy(origInterface)

        for interfaceClass in interfaceClasses:
            factory = self._registry.get(origInterface).selfImplied.get(interfaceClass, {}).get('')
            if factory and adapterFactory is not None:
                raise ValueError("an adapter (%r, %r, %r) was already registered." % (
                                 factory, origInterface, interfaceClasses))

        for interfaceClass in interfaceClasses:
            self._registry.register([origInterface], interfaceClass, '', adapterFactory)


    def adaptWithDefault(self, iface, orig, default=None):
        # GUH! zi sucks
        face = default
        try:
            face = iface(orig)
        except TypeError, e:
            if e.args[0] == 'Could not adapt':
                pass
            else:
                raise
        return face

    def _clearAdapterRegistry(self):
        """FOR INTERNAL USE ONLY"""
        del self._registry
        assert self._hook in interface.adapter_hooks
        interface.adapter_hooks.remove(self._hook)

    # add global adapter lookup hook for our newly created registry
    def _hook(self, iface, ob):
        factory = self._registry.lookup1(declarations.providedBy(ob), iface)
        if factory is None:
            return None
        else:
            return factory(ob)

    def _setUpAdapters(self):
        import types
        from twisted.trial import reporter, runner, itrial, adapters, remote
        from twisted.trial import tdoctest, doctest
        from twisted.spread import jelly
        from twisted.python import failure
        for a, o, i in [

# ---- ITestRunner and ITestMethod adapters -----------
(runner.TestCaseRunner, itrial.ITestCaseFactory, itrial.ITestRunner),
(runner.TestModuleRunner, types.ModuleType, itrial.ITestRunner),
(runner.PyUnitTestCaseRunner, itrial.IPyUnitTCFactory, itrial.ITestRunner),
(runner.TestCaseMethodRunner, types.MethodType, itrial.ITestRunner),
(runner.TestMethod, types.MethodType, itrial.ITestMethod),

# ---- Doctest support --------------------------------
(tdoctest.DocTestRunnerToITestMethod, tdoctest.DocTestRunner, itrial.ITestMethod),
(tdoctest.DocTestRunner, doctest.DocTest, itrial.ITestRunner),

# XXX: i'm not happy about this association
(tdoctest.ModuleDocTestsRunner, types.ListType, itrial.ITestRunner),


# ---- Error Reporting and Failure formatting ----------
(adapters.formatFailureTraceback, failure.Failure, itrial.IFormattedFailure),
(adapters.formatMultipleFailureTracebacks, types.ListType, itrial.IFormattedFailure),
(adapters.formatMultipleFailureTracebacks, types.TupleType, itrial.IFormattedFailure),
(adapters.formatTestMethodFailures, itrial.ITestMethod, itrial.IFormattedFailure),
(adapters.formatError, itrial.ITestMethod, itrial.IErrorReport),
(adapters.formatImportError, types.TupleType, itrial.IImportErrorReport),
(adapters.formatDoctestError, itrial.IDocTestMethod, itrial.IErrorReport),

# ---- ITestStats  ------------------------------------
(reporter.TestStats, itrial.ITestSuite, itrial.ITestStats),
(reporter.TestStats, runner.TestModuleRunner, itrial.ITestStats),
(reporter.TestStats, tdoctest.ModuleDocTestsRunner, itrial.ITestStats),
(reporter.DocTestRunnerStats, tdoctest.DocTestRunner, itrial.ITestStats),
(reporter.TestCaseStats, runner.TestCaseRunner, itrial.ITestStats),
(reporter.TestCaseStats, runner.TestCaseMethodRunner, itrial.ITestStats),
(reporter.TestCaseStats, runner.PyUnitTestCaseRunner, itrial.ITestStats),

# ---- Miscellaneous 'utility' adapters ---------------
(adapters.getModuleNameFromModuleType, types.ModuleType, itrial.IModuleName),
(adapters.getModuleNameFromClassType, types.ClassType, itrial.IModuleName),
(adapters.getModuleNameFromClassType, types.TypeType, itrial.IModuleName),
(adapters.getModuleNameFromMethodType, types.MethodType, itrial.IModuleName),
(adapters.getModuleNameFromFunctionType, types.FunctionType, itrial.IModuleName),
(adapters.getClassNameFromClass, types.ClassType, itrial.IClassName),
(adapters.getClassNameFromMethodType, types.MethodType, itrial.IClassName),
(adapters.getClassNameFromClass, types.TypeType, itrial.IClassName),
(adapters.getFQClassName, types.ClassType, itrial.IFQClassName),
(adapters.getFQClassName, types.TypeType, itrial.IFQClassName),
(adapters.getFQClassName, types.MethodType, itrial.IFQClassName),
(lambda x: x, types.StringType, itrial.IFQClassName),
(adapters.getFQMethodName, types.MethodType, itrial.IFQMethodName),
(adapters.getClassFromMethodType, types.MethodType, itrial.IClass),
(adapters.getClassFromFQString, types.StringType, itrial.IClass),
(adapters.getModuleFromMethodType, types.MethodType, itrial.IModule),
(lambda x: x, types.StringType, itrial.IClassName),
(lambda x: x, types.StringType, itrial.IModuleName),

# ---- Magic Attribute Adapters -----------------------
(adapters.TupleTodo, types.TupleType, itrial.ITodo),
(adapters.StringTodo, types.StringType, itrial.ITodo),
(adapters.TodoBase, types.NoneType, itrial.ITodo),
(adapters.TupleTimeout, types.TupleType, itrial.ITimeout),
(adapters.NumericTimeout, types.FloatType, itrial.ITimeout),
(adapters.NumericTimeout, types.IntType, itrial.ITimeout),
(adapters.TimeoutBase, types.NoneType, itrial.ITimeout),
(adapters.TimeoutBase, types.MethodType, itrial.ITimeout),
#(runner.UserMethodWrapper, types.MethodType, itrial.IUserMethod),
(remote.JellyableTestMethod, itrial.ITestMethod, jelly.IJellyable)]:

            self.registerAdapter(a, o, i)


#XXX: refactor this so that things which need to adjust the global registry
#     don't use these module-level names

_trialRegistry = TrialAdapterRegistry()

_setUpAdapters = _trialRegistry._setUpAdapters

registerAdapter = _trialRegistry.registerAdapter
adaptWithDefault = _trialRegistry.adaptWithDefault


__all__ = ['registerAdapter', 'adaptWithDefault']
