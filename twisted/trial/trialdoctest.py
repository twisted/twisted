from doctest import _normalize_module, _find_tests, _utest, Tester

from twisted.trial import itrial, runner
from twisted.trial.reporter import  FAILURE, ERROR, SUCCESS

import zope.interface as zi

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

def bogus(n=None):
    pass

# XXX: This is a horrid hack to avoid rewriting most of runner.py

class Proxy(object):
    def __init__(self, method):
        self.method = method

    def __call__(self, *a):
        self.method(*a)


class DocTestMethod(runner.TestMethod):
    zi.implements(itrial.ITestMethod)
    def __init__(self, module, name, doc, filename, lineno):
        self._module, self._name, self._doc, self._filename, self._lineno = module, name, doc, filename, lineno

        def _orig(ignore=None):
            tester = Tester(self._module)
            _utest(tester, self._name, self._doc, self._filename, self._lineno)

        proxy = Proxy(_orig)

        proxy.__name__ = self._name
        proxy.im_class = DocTestMethod
        proxy.__module__ = self._module
        proxy.__doc__ = self._doc

        super(DocTestMethod, self).__init__(proxy)

        self.fullname = "doctest %s of file %s at lineno %s" % (name, filename, lineno)

    def bogus(*a):
        pass
    setUp = classmethod(bogus)
    tearDown = classmethod(bogus)

    todo = skip = None
    status = property(runner.TestMethod._getStatus)
    results = property(runner.TestMethod._getResults)
    hasTbs = property(runner.TestMethod._getHasTbs)


class DocTestCase(object):
    zi.classProvides(itrial.ITestCaseFactory)
    def __init__(self, module):
        self.setUp = self.tearDown = self.setUpClass = self.tearDownClass = bogus
        module = _normalize_module(module)
        tests = _find_tests(module)

        if not tests:
            raise ValueError(module, 'has no tests')

        for name, doc, filename, lineno in tests:
            if not filename:
                filename = module.__file__
                if filename.endswith(".pyc"):
                    filename = filename[:-1]
                elif filename.endswith(".pyo"):
                    filename = filename[:-1]

            tmname = 'test_%s' % (name.replace('.', '_'),)
            dtm = DocTestMethod(module, name, doc, filename, lineno)

            # XXX: YES I AM A TERRIBLE PERSON!
            self.__dict__[tmname] = dtm

    def __call__(self):
        return None
               
        
