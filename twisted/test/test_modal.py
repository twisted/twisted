
from twisted.trial import unittest

from twisted.python.modal import mode, Modal, getMethods

class ModalTestClass(Modal):

    modeAttribute = 'mode'
    initialMode = 'alpha'

    class alpha(mode):
        def one(self):
            return 'alpha-one'
        def two(self):
            return 'alpha-two'

    class beta(mode):
        def two(self):
            return 'beta-two'
        def three(self):
            return 'beta-three'

    def four(self):
        return 'unmode-four'

    class gamma(mode):
        def change(self):
            self.mode = 'delta'
            return self.change()

    class delta(mode):
        def change(self):
            return 'delta-change'

class ModalTestSubclass(ModalTestClass):
    pass

class ModalityTestCase(unittest.TestCase):
    modalFactory = ModalTestClass
    def testModalMethods(self):
        x = self.modalFactory()
        self.assertEquals(x.one(), 'alpha-one')
        self.assertEquals(x.two(), 'alpha-two')
        self.assertRaises(AttributeError, getattr, x, 'three')
        self.assertEquals(x.four(), 'unmode-four')

        x.mode = 'beta'
        self.assertRaises(AttributeError, getattr, x, 'one')
        self.assertEquals(x.two(), 'beta-two')
        self.assertEquals(x.three(), 'beta-three')
        self.assertEquals(x.four(), 'unmode-four')

    def testInternalModeChange(self):
        x = self.modalFactory()
        x.mode = 'gamma'
        self.assertEquals(x.change(), 'delta-change')


class MostBasicInheritanceTestCase(ModalityTestCase):
    modalFactory = ModalTestSubclass


class GetMethodsTest(unittest.TestCase):
    """
    Tests for L{getMethods}.
    """

    def test_noInheritance(self):
        methods = getMethods(mode)
        self.assertIn('__enter__', methods)
        self.assertIdentical(mode.__dict__['__enter__'], methods['__enter__'])
        self.assertIn('__exit__', methods)
        self.assertIdentical(mode.__dict__['__exit__'], methods['__exit__'])


    def test_primaryInheritance(self):
        alpha = ModalTestClass.alpha
        methods = getMethods(alpha)
        self.assertIn('__enter__', methods)
        self.assertIdentical(mode.__dict__['__enter__'], methods['__enter__'])
        self.assertIn('__exit__', methods)
        self.assertIdentical(mode.__dict__['__exit__'], methods['__exit__'])
        self.assertIn('one', methods)
        self.assertIdentical(alpha.__dict__['one'], methods['one'])
        self.assertIn('two', methods)
        self.assertIdentical(alpha.__dict__['two'], methods['two'])

    def test_secondaryInheritance(self):
        alpha = ModalTestSubclass.alpha
        methods = getMethods(alpha)
        self.assertIn('__enter__', methods)
        self.assertIdentical(mode.__dict__['__enter__'], methods['__enter__'])
        self.assertIn('__exit__', methods)
        self.assertIdentical(mode.__dict__['__exit__'], methods['__exit__'])
        self.assertIn('one', methods)
        self.assertIdentical(alpha.__dict__['one'], methods['one'])
        self.assertIn('two', methods)
        self.assertIdentical(alpha.__dict__['two'], methods['two'])

    def test_overriding(self):
        alpha = ModalTestClass.alpha
        class alpha2(alpha):
            def one(self):
                return "alpha-overridden-one"

        methods = getMethods(alpha2)
        self.assertIn('__enter__', methods)
        self.assertIdentical(mode.__dict__['__enter__'], methods['__enter__'])
        self.assertIn('__exit__', methods)
        self.assertIdentical(mode.__dict__['__exit__'], methods['__exit__'])
        self.assertIn('one', methods)
        self.assertIdentical(alpha2.__dict__['one'], methods['one'])
        self.assertIn('two', methods)
        self.assertIdentical(alpha.__dict__['two'], methods['two'])


class ModalTest(unittest.TestCase):
    """
    Tests for L{Modal}.
    """

    def test_transitionTo(self):
        """
        Making a transition to another mode changes the mode.
        """
        modal = ModalTestClass()
        modal.transitionTo("beta")
        self.assertEqual('beta', modal.mode)


    def test_overridden(self):
        """
        Overriding a mode in a subclass, replaces the methods for that mode.
        """
        class OverridingModal(ModalTestClass):
            class beta(mode):
                def two(self):
                    return 'beta-two-overridden'

        modal = OverridingModal()
        modal.transitionTo("beta")
        self.assertEqual('beta-two-overridden', modal.two())
        self.assertEqual('beta-three', modal.three())


    def test_overriddenWithGap(self):
        """
        Overriding a mode of a subsubclass still replaces the methods.
        """
        class OverridingModal(ModalTestSubclass):
            class beta(mode):
                def two(self):
                    return 'beta-two-overridden'

        modal = OverridingModal()
        modal.transitionTo("beta")
        self.assertEqual('beta-two-overridden', modal.two())
        self.assertEqual('beta-three', modal.three())
