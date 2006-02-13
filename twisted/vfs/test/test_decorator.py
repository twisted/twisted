
from twisted.trial import unittest
from twisted.vfs.decorator import Decorator, CommonWrapperDecorator
from twisted.vfs.decorator import IndirectWrap, introspectMethods

class A(object):
    def __init__(self, num):
        self.num = num
    def new(self, num):
        return A(num)
    def getNum(self):
        return self.num
    def getNum2(self):
        return self.num
    def getNum3(self):
        return self.num

class ADecorator(Decorator):
    def __init__(self, target, factoryMethods=['new']):
        Decorator.__init__(self, target, factoryMethods)
    
class AddOne(ADecorator):
    def getNum(self):
        return self.target.getNum() + 1

class TimesTwo(ADecorator):
    def getNum(self):
        return self.target.getNum() * 2


addOneDirect = lambda x: x + 1
addOneIndirect = lambda f, *a, **kw: f(*a, **kw) + 1


class DecoratorTest(unittest.TestCase):
    def test_passthru(self):
        a = Decorator(A(3))
        self.assertEquals(a.getNum(), 3)

    def test_passthru_factory(self):
        a = Decorator(A(3))
        self.assert_(isinstance(a.new(5), A))
        self.assertNot(isinstance(a.new(5), Decorator))

    def test_redecorate(self):
        a = Decorator(A(3), ['new'])
        self.assertNot(isinstance(a.new(5), A))
        self.assert_(isinstance(a.new(5), Decorator))

    def test_redecorate_2deep(self):
        a = Decorator(A(3), ['new'])
        self.assertNot(isinstance(a.new(5).new(15), A))
        self.assert_(isinstance(a.new(5).new(15), Decorator))

    def test_stack(self):
        a = TimesTwo(AddOne(A(3)))
        self.assertEquals(a.getNum(), 8)

    def test_stack_alt(self):
        a = AddOne(TimesTwo(A(3)))
        self.assertEquals(a.getNum(), 7)

    def test_stack_redecorate(self):
        a = TimesTwo(AddOne(A(3)))
        self.assertEquals(a.new(5).getNum(), 12)

    def test_stack_alt_redecorate(self):
        a = AddOne(TimesTwo(A(3)))
        self.assertEquals(a.new(5).getNum(), 11)

    def test_commonwrap_direct(self):
        a = CommonWrapperDecorator(A(3), factoryMethods=['new'],
            wrapper=addOneDirect, wrappedMethods=['getNum', 'getNum3'])
        self.assertEquals(a.getNum(), 4)
        self.assertEquals(a.getNum2(), 3)
        self.assertEquals(a.getNum3(), 4)

    def test_commonwrap_indirect(self):
        a = CommonWrapperDecorator(A(3), factoryMethods=['new'],
            wrapper=addOneIndirect, wrappedMethods=['getNum', 'getNum3'], 
                wrapStyle=IndirectWrap)
        self.assertEquals(a.getNum(), 4)
        self.assertEquals(a.getNum2(), 3)
        self.assertEquals(a.getNum3(), 4)

    def test_commonwrap_indirect_redecorate(self):
        a = CommonWrapperDecorator(A(3), factoryMethods=['new'],
            wrapper=addOneIndirect, wrappedMethods=['getNum', 'getNum3'], 
                wrapStyle=IndirectWrap)
        self.assertEquals(a.new(5).getNum(), 6)
        self.assertEquals(a.new(5).getNum2(), 5)
        self.assertEquals(a.new(5).getNum3(), 6)
        
    def test_commonwrap_stack(self):
        a = TimesTwo(CommonWrapperDecorator(A(3), factoryMethods=['new'],
            wrapper=addOneDirect, wrappedMethods=['getNum', 'getNum3']))
        self.assertEquals(a.getNum(), 8)
        self.assertEquals(a.getNum2(), 3)
        self.assertEquals(a.getNum3(), 4)

    def test_commonwrap_stack_redecorate(self):
        a = TimesTwo(CommonWrapperDecorator(A(3), factoryMethods=['new'],
            wrapper=addOneDirect, wrappedMethods=['getNum', 'getNum3']))
        self.assertEquals(a.new(15).getNum(), 32)
        self.assertEquals(a.new(15).getNum2(), 15)
        self.assertEquals(a.new(15).getNum3(), 16)

    def test_commonwrap_stack_redecorate_2deep(self):
        a = TimesTwo(CommonWrapperDecorator(A(3), factoryMethods=['new'],
            wrapper=addOneDirect, wrappedMethods=['getNum', 'getNum3']))
        self.assertEquals(a.new(15).new(7).getNum(), 16)
        self.assertEquals(a.new(15).new(7).getNum2(), 7)
        self.assertEquals(a.new(15).new(7).getNum3(), 8)

    def test_introspectMethods(self):
        methods = introspectMethods(A)
        methods.sort()
        self.assertEquals(methods, [
            'getNum',
            'getNum2',
            'getNum3',
            'new',
        ])

    def test_introspectMethods(self):
        methods = introspectMethods(A, exceptMethods=['new', 'getNum2'])
        methods.sort()
        self.assertEquals(methods, [
            'getNum',
            'getNum3',
        ])
