from twisted.trial import unittest
from zope.interface import Interface, Attribute, implements
from twisted.trial.assertions import *

import iproxy

class ITest(Interface):
    def r0():
        pass

    def r1(arg1):
        pass

    def r1o1(arg1, arg2=1):
        pass

    def r1o1kw(arg1, arg2=1, **kw):
        pass

    def r1o1args(arg1, arg2=1, *args):
        pass
    
class Test(object):
    implements(ITest)

    def f(self,*arg, **kw):
        return 0
    
    def __getattr__(self, name):
        return self.f

class Test_real(object):
    def r0():
        return 0
    r0=staticmethod(r0)
    
    def r1(arg1):
        return 0
    r1=staticmethod(r1)
    
    def r1o1(arg1, arg2=1):
        return 0
    r1o1=staticmethod(r1o1)
    
    def r1o1kw(arg1, arg2=1, **kw):
        return 0
    r1o1kw=staticmethod(r1o1kw)
    
    def r1o1args(arg1, arg2=1, *args):
        return 0
    r1o1args=staticmethod(r1o1args)

class ITest2(Interface):
    foo=Attribute("foo")
    
class Test2(object):
    implements(ITest2)
    foo=1

class ITest3(ITest2):
    bar=Attribute("bar")

class ITest3a(ITest2):
    frob=Attribute("frob")

class Test3(object):
    implements(ITest3)
    foo=1
    bar=1
    frob=1
    
def assertRaisesMsg(exception, msg, f, *args, **kwargs):
    assertEquals(msg, str(assertRaises(exception, f, *args, **kwargs)))
    
class IProxyTestCase(unittest.TestCase):
    # Verifies the output of the Proxy against the builtin python
    # method calling checks.
    
    def t(self, f, *args, **kw):
        res=res2=err=err2=None
        
        try:
            res=getattr(self.obj, f)(*args, **kw)
        except TypeError, e:
            err=str(e)

        try:
            res2=getattr(self.proxy, f)(*args, **kw)
        except TypeError, e:
            err2=str(e)

        #print "Testing %s on %r, %r:" %(f, args, kw)
        self.assertEquals(err, err2)
        self.assertEquals(res, res2)
        #if err is None:
        #    print "  Res: %r" % (res)
        #else:
        #    print "  Err: %r" % (err)
        
    def doit(self, f):
        self.t(f)
        self.t(f, 1)
        self.t(f, 1,2)
        self.t(f, 1,2,3)
        self.t(f, 1,frobnotz=1)
        self.t(f, 1,2,frobnotz=1)
        self.t(f, 1,2,3,frobnotz=1)
        self.t(f, arg1=1)
        self.t(f, 1, arg1=1)
        self.t(f, 1, arg2=2)
        

    def test_sigchecking(self):
        self.proxy = iproxy.InterfaceProxy(Test())
        self.obj = Test_real()
        
        self.doit('r0')
        self.doit('r1')
        self.doit('r1o1')
        self.doit('r1o1kw')
        self.doit('r1o1args')

    def test_attributes(self):
        obj=Test2()
        proxy = iproxy.InterfaceProxy(obj)

        assertEquals(obj.foo, 1)
        assertEquals(proxy.foo, 1)
        
        proxy.foo=2
        assertEquals(obj.foo, 2)
        assertEquals(proxy.foo, 2)
        
        obj.foo=3
        assertEquals(obj.foo, 3)
        assertEquals(proxy.foo, 3)

        def g():
            proxy.frob
        def s():
            proxy.frob=1
        assertRaisesMsg(AttributeError,
                        "'Test2' object has no attribute 'frob'",
                        g)
        assertRaisesMsg(AttributeError,
                        "'Test2' object has no attribute 'frob'",
                        s)
        
    def test_specified(self):
        obj = Test3()
        proxy = iproxy.InterfaceProxy(obj, (ITest3,))
        assertEquals(proxy.foo, 1)
        assertEquals(proxy.bar, 1)
        def g():
            proxy.frob
        assertRaisesMsg(AttributeError,
                        "'Test3' object has no attribute 'frob'",
                        g)
        
        proxy = iproxy.InterfaceProxy(obj, (ITest3,ITest3a))
        assertEquals(proxy.foo, 1)
        assertEquals(proxy.bar, 1)
        assertEquals(proxy.frob, 1)
        
