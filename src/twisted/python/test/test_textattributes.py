# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.textattributes}.
"""

import functools
import operator

from twisted.trial import unittest
from twisted.python._textattributes import (
    _Attribute,
    _BackgroundColorAttr,
    CharacterAttributesMixin,
    _ColorAttr,
    _ColorAttribute,
    DefaultFormattingState,
    flatten,
    _ForegroundColorAttr,
    _FormattingStateMixin,
    _OtherAttr,
    _NormalAttr,
)


class RecordsFakeAttribute:
    """
    Records calls to a L{FakeAttributes} instance.

    @ivar serializeCalls: The arguments passed to each call to the
        containing object's C{serialize} method
    @type serializeCalls: a L{list} of L{tuple}s, each of which are
        the arguments for one call to C{serialize}
    """

    def __init__(self):
        self.serializeCalls = []


class FakeAttribute(_Attribute):
    """
    A fake L{_Attribute} that records calls to its methods via its
    C{recorder} instance.

    @param recorder: The object that holds all calls to this fake.
    @type recorder: L{RecordsFakeAttribute}
    """

    def __init__(self, recorder):
        self._recorder = recorder

    def serialize(self, write, attrs, attributeRenderer):
        self._recorder.serializeCalls.append((write, attrs, attributeRenderer))


class RecordsFakeFormattingState:
    """
    Records calls to a L{FakeFormattingState} instance.

    @ivar renderMethodName: The name of the render method.  The
        containing object aliases this to its interal render method.
    @type renderMethodName: L{str}

    @ivar renderMethodCallCount: The number of times the containing
        object's render method has been called.

    @type renderMethodCalls: L{int}

    @ivar renderMethodReturns: What to return from the containing
        object's render method.
    """

    def __init__(self, renderMethodName):
        self.renderMethodName = renderMethodName
        self.renderMethodCallCount = 0
        self.renderMethodReturns = "<rendered>"

        self.copyCallCount = 0
        self.copyReturns = "<attrs>"

        self.withAttributeCalls = []
        self.withAttributeReturns = "<_withAttribute>"


class FakeFormattingState:
    """
    A L{DefaultFormattingState} subclass that records all calls to its
    C{recorder}
    """

    _initCallCount = 0

    @classmethod
    def newInstance(cls, recorder):
        """
        Use me to create a new instance, because C{__init__} is an API
        under test.

        @param recorder: The object that holds all calls to this fake.
        @type recorder: L{RecordsFakeFormattingState}
        """
        instance = cls()
        instance._recorder = recorder
        return instance

    def __init__(self):
        self._initCallCount += 1

    def __getattr__(self, name):
        if name == self._recorder.renderMethodName:
            return self.renderer
        raise AttributeError(name)

    def copy(self):
        self._recorder.copyCallCount += 1
        return self._recorder.copyReturns

    def renderer(self):
        self._recorder.renderMethodCallCount += 1
        return self._recorder.renderMethodReturns

    def _withAttribute(self, name, value):
        self._recorder.withAttributeCalls.append((name, value))
        return self._recorder.withAttributeReturns


class _AttributeTestsMixin(unittest.TestCase):
    """
    Common set up for attribute test cases

    @cvar attributeFactory: A callable that returns attribute
        instances.  Can be an instance method.
    @type attributeFactory: L{callable}

    @cvar renderMethodName: the method name to pass to the
        L{RecordsFakeFormattingState} initializer
    @type renderMethodName: L{str}
    """

    attributeFactory = None
    renderMethodName = "toVT102"

    def setUp(self):
        self.attribute = self.attributeFactory()

        self.attributeRecorder = RecordsFakeAttribute()
        self.fakeAttribute = FakeAttribute(self.attributeRecorder)

        self.fakeWriteCalls = []

        self.formattingStateRecorder = RecordsFakeFormattingState(
            renderMethodName="toVT102"
        )
        self.fakeFormattingState = FakeFormattingState.newInstance(
            self.formattingStateRecorder
        )

    def fakeWrite(self, argument):
        """
        An implementation of the C{write} callable required by
        L{_Attribute.serialize} that records its argument.

        @param argument: the bytes the caller intends to write
        @type argument: L{bytes}
        """
        self.fakeWriteCalls.append(argument)

    def assertIsAttribute(self, value):
        """
        Assert that C{value} is C{self.attribute}.

        @param value: (hopefully) an attribute object.
        @type value: L{_Attribute}
        """
        self.assertIs(self.attribute, value)


class AttributeTests(_AttributeTestsMixin):
    """
    Tests for L{twisted.python._textattributes._Attribute}
    """

    attributeFactory = _Attribute

    def test_reprSanity(self):
        """
        The L{_Attribute.__repr__} method should return a L{str}
        without raising an exception
        """
        self.assertIsInstance(repr(self.attribute), str)

    def test_getitemAssertsTypes(self):
        """
        L{_Attribute.__getitem__} asserts that its argument is one of
        a small set of types.
        """
        self.assertRaises(AssertionError, operator.itemgetter(object), self.attribute)

    def test_getitemBytestring(self):
        """
        L{_Attribute.__getitem__} appends a single L{bytes} instance
        to its C{children}.
        """
        self.assertIsAttribute(self.attribute[b"some bytes"])
        self.assertEqual(self.attribute.children, [b"some bytes"])

    def test_getitemAttribute(self):
        """
        L{_Attribute.__getitem__} appends a single L{_Attribute}
        instance to its C{children}.
        """
        childAttribute = _Attribute()
        self.assertIsAttribute(self.attribute[childAttribute])
        self.assertEqual(self.attribute.children, [childAttribute])

    def test_getitemList(self):
        """
        L{_Attribute.__getitem__} adds all elements of a L{list} to
        its C{children}.
        """
        listOfBytes = [b"a", b"b", b"c"]
        self.assertIsAttribute(self.attribute[listOfBytes])
        self.assertEqual(self.attribute.children, listOfBytes)

    def test_getitemTuple(self):
        """
        L{_Attribute.__getitem__} adds all elements of a L{tuple} to
        its C{children}.
        """
        tupleOfBytes = (b"a", b"b", b"c")
        self.assertIsAttribute(self.attribute[tupleOfBytes])
        self.assertEqual(self.attribute.children, list(tupleOfBytes))

    def test_serializeRecurs(self):
        """
        L{_Attribute.serialize} recursively serializes children that
        are L{_Attribute}s
        """
        fakeWriter = self.fakeWrite
        self.assertIsAttribute(self.attribute[self.fakeAttribute])
        self.attribute.serialize(fakeWriter)

        self.assertEqual(len(self.attributeRecorder.serializeCalls), 1)
        [(write, _, _)] = self.attributeRecorder.serializeCalls
        self.assertIs(write, fakeWriter)

    def test_serializeDefaultFormattingState(self):
        """
        L{_Attribute.serialize} creates an instance of
        L{DefaultFormattingState} when no formatting state is provided.
        """
        self.assertIsAttribute(self.attribute[self.fakeAttribute])
        self.attribute.serialize(self.fakeWrite)

        self.assertEqual(len(self.attributeRecorder.serializeCalls), 1)
        [(_, attrs, _)] = self.attributeRecorder.serializeCalls
        self.assertIsInstance(attrs, DefaultFormattingState)

    def test_serializeSpecifiedFormattingState(self):
        """
        L{_Attribute.serialize} uses the formatting state instance
        provided as its C{attrs} argument.
        """
        self.assertIsAttribute(self.attribute[self.fakeAttribute])
        self.attribute.serialize(self.fakeWrite, self.fakeFormattingState)

        self.assertEqual(len(self.attributeRecorder.serializeCalls), 1)
        [(_, attrs, _)] = self.attributeRecorder.serializeCalls
        self.assertIs(attrs, self.formattingStateRecorder.copyReturns)

    def test_serializePassesDefaultRenderMethod(self):
        """
        L{_Attribute.serialize} passes on to any L{_Attribute}
        children a default render method when none is specified.
        """
        self.assertIsAttribute(self.attribute[self.fakeAttribute])
        self.attribute.serialize(self.fakeWrite, self.fakeFormattingState)

        self.assertEqual(len(self.attributeRecorder.serializeCalls), 1)
        [(_, _, renderMethodName)] = self.attributeRecorder.serializeCalls
        self.assertIs(renderMethodName, self.formattingStateRecorder.renderMethodName)

    def test_serializePassesSpecifiedRenderMethod(self):
        """
        L{_Attribute.serialize} passes on to any L{_Attribute}
        children the specified render method.
        """
        self.assertIsAttribute(self.attribute[self.fakeAttribute])
        self.attribute.serialize(
            self.fakeWrite, self.fakeFormattingState, attributeRenderer="foo"
        )

        self.assertEqual(len(self.attributeRecorder.serializeCalls), 1)
        [(_, _, renderMethodName)] = self.attributeRecorder.serializeCalls
        self.assertEqual(renderMethodName, "foo")

    def test_renderMethodCalled(self):
        """
        L{_Attribute.serialize} calls the specified render method
        before serializing children that are L{bytes}.
        """
        self.formattingStateRecorder.renderMethodName = "foo"

        self.assertIsAttribute(self.attribute[b"bytes"])
        self.attribute.serialize(
            self.fakeWrite, self.fakeFormattingState, attributeRenderer="foo"
        )

        self.assertNot(len(self.attributeRecorder.serializeCalls))

        self.assertEqual(
            self.fakeWriteCalls,
            [self.formattingStateRecorder.renderMethodReturns, b"bytes"],
        )

    def test_unicodeDeprecation(self):
        """
        L{_Attribute.__geitem__} emits a deprecation warning when
        given a L{unicode}/L{str} object instead of a L{bytes} object.
        """
        self.attribute["unicode"]
        message = (
            "Calling _Attribute.__getitem__ with a unicode/str"
            " object instead of a bytes object is deprecated"
            " since Twisted NEXT"
        )
        warnings = self.flushWarnings([self.test_unicodeDeprecation])
        self.assertEqual(1, len(warnings))
        self.assertEqual(DeprecationWarning, warnings[0]["category"])
        self.assertEqual(message, warnings[0]["message"])


class NormalAttrTests(_AttributeTestsMixin):
    """
    Tests for L{_NormalAttr}
    """

    attributeFactory = _NormalAttr
    renderMethodName = "ignored renderer"

    def test_serializeReInitsFormattingState(self):
        """
        L{_NormalAttr.serialize} calls the provided formatting state's
        C{__init__} method to reset the formatting state prior to
        serialization.
        """
        self.attribute.serialize(
            "ignored write", self.fakeFormattingState, "ignored renderer"
        )
        self.assertEqual(self.fakeFormattingState._initCallCount, 2)


class _ModifyingAttrTestsMixin(_AttributeTestsMixin):
    """
    A mixin to ease testing L{_Attribute} subclasses that modify a
    formatting state.
    """

    def assertWithAttributeCalled(self, name, value):
        """
        Assert that our L{FakeFormattingState}'s C{_withAttribute}
        method was called with C{name} and C{value}, and that it was
        passed to the base class' C{serialize} method.

        @param name: the name argument passed to
            C{self.fakeFormattingState._withAttribute}
        @type name: L{bytes}

        @param value: the value argument passed to
            C{self.fakeFormattingState._withAttribute}
        @type value: L{bytes}
        """
        self.assertIsAttribute(self.attribute[self.fakeAttribute])

        fsr = self.formattingStateRecorder
        fsr.withAttributeReturns = self.fakeFormattingState

        self.attribute.serialize(
            self.fakeWrite, self.fakeFormattingState, self.renderMethodName
        )

        self.assertEqual(len(self.formattingStateRecorder.withAttributeCalls), 1)
        [(_name, _value)] = self.formattingStateRecorder.withAttributeCalls
        self.assertEqual(name, _name)
        self.assertEqual(value, _value)

        # _Attribute.serialize calls attrs.copy
        self.assertEqual(self.formattingStateRecorder.copyCallCount, 1)


class OtherAttrTests(_ModifyingAttrTestsMixin):
    """
    Tests for L{_OtherAttr}.
    """

    renderMethodName = "renderIt"

    attrname = "attrname"
    attrvalue = True

    def attributeFactory(self):
        """
        Make an L{_OtherAttr} instance.

        @return: an L{_OtherAttr} that was passed C{self.attrname} and
            C{self.attrvalue}
        @rtype: L{_OtherAttr}
        """
        return _OtherAttr(self.attrname, self.attrvalue)

    def test_neg(self):
        """
        Apply a unary minus operator to an L{_OtherAttr} instance
        returns a new L{_OtherAttr} instance with an inverted
        C{attrvalue}.
        """
        negated = -self.attribute
        self.assertEqual(negated.attrvalue, not self.attrvalue)

    def test_negWithChildren(self):
        """
        Apply a unary minus operator to an L{_OtherAttr} instance
        returns a new L{_OtherAttr} instance with an inverted
        C{attrvalue} and all of the first attr's children.
        """
        children = [b"a", b"b", b"c"]
        self.assertIsAttribute(self.attribute[children])

        negated = -self.attribute
        self.assertEqual(negated.attrvalue, not self.attrvalue)
        self.assertEqual(negated.children, children)

        for originalChild, negatedChild in zip(children, negated.children):
            self.assertIs(originalChild, negatedChild)

    def test_serialize(self):
        """
        L{_OtherAttr.serialize} applies its C{attrname} and
        C{attrvalue} to the formatting state instance before
        serializing.
        """
        self.assertWithAttributeCalled(self.attrname, self.attrvalue)


class ColorAttrTests(_ModifyingAttrTestsMixin):
    """
    Tests for L{_ColorAttr}.
    """

    color = "purple"
    ground = "middleground"

    def attributeFactory(self):
        """
        Make a L{_ColorAttr} instance.

        @return: an L{_ColorAttr} instance that was passed
            C{self.color} and C{self.ground}
        @rtype: L{_ColorAttr}
        """
        return _ColorAttr(self.color, self.ground)

    def test_serialize(self):
        """
        L{_ColorAttr.serialize} applies its C{ground} and C{color} to
        the formatting state instance before serializing.
        """
        self.assertWithAttributeCalled(self.ground, self.color)


class ForegroundColorAttrTests(ColorAttrTests):
    """
    Tests for L{_ForegroundColorAttr}
    """

    ground = "foreground"

    def attributeFactory(self):
        """
        Make a L{_ForegroundColorAttr} instance.
        """
        return _ForegroundColorAttr(self.color)


class BackgroundColorAttrTests(ColorAttrTests):
    """
    Tests for L{_BackgroundColorAttr}
    """

    ground = "background"

    def attributeFactory(self):
        """
        Make a L{_BackgroundColorAttr} instance.
        """
        return _BackgroundColorAttr(self.color)


class ColorAttributeTests(unittest.TestCase):
    """
    Tests for L{_ColorAttribute}
    """

    def setUp(self):
        self.attrs = {"blue": 0}
        self.groundName = "middleground"
        self.ground = functools.partial(_ColorAttr, ground=self.groundName)
        self.colorAttribute = _ColorAttribute(self.ground, self.attrs)

    def test_getattr(self):
        """
        Accessing a known color as an attribute returns an instance of
        the C{ground} class that represents the color's value.
        """
        colorAttr = self.colorAttribute.blue
        self.assertIsInstance(colorAttr, _ColorAttr)
        self.assertEqual(colorAttr.ground, self.groundName)
        self.assertEqual(colorAttr.color, self.attrs["blue"])

    def test_getattrUnknownColor(self):
        """
        Accessing an unknown color -- i.e., one not in
        L{_ColorAttribute.attrs} -- as an attribute raises an
        L{AttributeError}.
        """
        self.assertRaises(
            AttributeError, operator.attrgetter("black"), self.colorAttribute
        )


class CharacterAttributesMixinTest(unittest.TestCase):
    """
    Tests for L{CharacterAttributesMixin}
    """

    def setUp(self):
        self.attrs = {"something": b"ignored"}

        class TestableCharacterAttributes(CharacterAttributesMixin):
            """
            A testable implementer of L{CharacterAttributesMixin}
            """

            attrs = self.attrs

        self.characterAttrs = TestableCharacterAttributes()

    def test_getattrNormal(self):
        """
        Accessing "normal" as an attribute of a
        L{CharacterAttributesMixin} instance returns a L{_NormalAttr}
        instance.
        """
        self.assertIsInstance(self.characterAttrs.normal, _NormalAttr)

    def test_getattrKnownAttr(self):
        """
        Accessing a value that's in the class' C{attrs} dict as an
        attribute of a L{CharacterAttributesMixin} instance returns an
        L{_OtherAttrs} instance.
        """
        attr = self.characterAttrs.something
        self.assertEqual(attr.attrname, "something")
        self.assertTrue(attr.attrvalue)

    def test_getattrUnknownAttr(self):
        """
        Accessing a value that's not in the class' C{attrs} dict as an
        attribute of a L{CharacterAttributesMixin} instance raises an
        L{AttributeError}
        """
        self.assertRaises(
            AttributeError, operator.attrgetter("foo"), self.characterAttrs
        )


class DefaultFormattingStateTests(unittest.TestCase):
    """
    Tests for L{twisted.python._textattributes.DefaultFormattingState}.
    """

    def setUp(self):
        self.formattingState = DefaultFormattingState()

    def test_equality(self):
        """
        L{DefaultFormattingState}s are always equal to other
        L{DefaultFormattingState}s.
        """
        self.assertEqual(self.formattingState, DefaultFormattingState())
        self.assertNotEqual(DefaultFormattingState(), b"hello")

    def test_copy(self):
        """
        L{DefaultFormattingState.copy} returns an instance of
        L{DefaultFormattingState}
        """
        self.assertIsInstance(self.formattingState.copy(), DefaultFormattingState)

    def test_withAttribute(self):
        """
        L{DefaultFormattingState.withAttribute} returns a new instance
        of L{DefaultFormattingState}
        """
        self.assertIsInstance(
            self.formattingState._withAttribute("ignored", "also ignored"),
            DefaultFormattingState,
        )

    def test_toVT102(self):
        """
        L{DefaultFormattingState.toVT102} emits no control sequences.
        """
        empty = self.formattingState.toVT102()
        self.assertFalse(empty)
        self.assertIsInstance(empty, bytes)


class FormattingStateMixinTests(unittest.TestCase):
    """
    Tests for L{_FormattingStateMixin}
    """

    def setUp(self):
        class TestableFormattingState(_FormattingStateMixin):
            """
            A testable implementer of L{_FormattingStateMixin}
            """

        self.formattingState = TestableFormattingState()

    def test_copy(self):
        """
        L{_FormattingStateMixin.copy} returns a new instance that
        includes all dynamically set instance variables.
        """
        self.formattingState.foo = 1
        self.formattingState.bar = "string"

        copied = self.formattingState.copy()

        self.assertIsInstance(copied, _FormattingStateMixin)
        self.assertEqual(copied.foo, 1)
        self.assertEqual(copied.bar, "string")

    def test_withAttributeNewAttribute(self):
        """
        Given a new attribute-value pair,
        L{_FormattingStateMixin._withAttribute} returns a new instance
        with that attribute set to that value.
        """
        self.formattingState.foo = 1

        copied = self.formattingState._withAttribute("foo", 2)
        self.assertIsInstance(copied, _FormattingStateMixin)
        self.assertIsNot(copied, self.formattingState)
        self.assertEqual(copied.foo, 2)

    def test_withAttributeNoChange(self):
        """
        L{_FormattingStateMixin._withAttribute} returns a copy of the
        instance when given a value that does not differ from the
        current attribute's value.
        """
        self.formattingState.foo = 1

        copied = self.formattingState._withAttribute("foo", 1)
        self.assertIsInstance(copied, _FormattingStateMixin)
        self.assertIsNot(copied, self.formattingState)
        self.assertEqual(copied.foo, 1)

    def test_withAttributeUnknownAttribute(self):
        """
        L{_FormattingStateMixin._withAttribute} raises an
        L{AttributeError} when given an attribute that does not exist
        on the instance.
        """
        self.assertRaises(
            AttributeError, operator.attrgetter("missing"), self.formattingState
        )


class _FlattenableAttributes(CharacterAttributesMixin):
    """
    An implementation of L{CharacterAttributesMixin} for use in
    L{FlattenTests}
    """

    _FOREGROUND = {"red": b"<red>"}
    _BACKGROUND = {"blue": b"<blue>"}

    fg = _ColorAttribute(_ForegroundColorAttr, _FOREGROUND)
    bg = _ColorAttribute(_BackgroundColorAttr, _BACKGROUND)

    attrs = {
        "bold": b"<bold control sequence>",
        "reverseVideo": b"<reversed video control sequence>",
    }


class _FlattenableFormattingState(_FormattingStateMixin):
    """
    An implementation of L{_FormattingStateMixin} for use in
    L{FlattenTests}
    """

    bold = False
    reverseVideo = False

    foreground = b"<default foreground>"
    background = b"<default background>"

    _subtracting = False

    def toVT102(self):
        """
        Emit fake control sequences for testing.
        """
        attrs = []
        for name in ("bold", "reverseVideo"):
            if getattr(self, name):
                attrs.append(_FlattenableAttributes.attrs[name])
        for name in ("foreground", "background"):
            attrs.append(getattr(self, name))
        if self._subtracting:
            attrs.append[b"<subtracting>"]

        return b"".join(attrs)


class FlattenTests(unittest.TestCase):
    """
    Integration tests for L{flatten}
    """

    def setUp(self):
        self.A = _FlattenableAttributes()

    def test_flatten(self):
        """
        A constructed sequence of L{_Attribute}s L{flatten}s to a
        L{bytes} object that contains the intended control
        sequences.
        """
        serialized = flatten(
            self.A.normal[
                # bold...
                self.A.bold[
                    # ...red foreground, default background
                    self.A.fg.red[b"red bytes"],
                    # ...default foreground, blue background
                    self.A.bg.blue[b"blue bytes"],
                ],
                # reversed video...
                self.A.reverseVideo[
                    # default foreground, default background
                    self.A.normal[b"reversed"]
                ],
            ],
            _FlattenableFormattingState(),
        )

        redBytes = (
            b"<bold control sequence>" b"<red>" b"<default background>" b"red bytes"
        )
        blueBytes = (
            b"<bold control sequence>" b"<default foreground>" b"<blue>" b"blue bytes"
        )
        reversedBytes = (
            b"<reversed video control sequence>"
            b"<default foreground>"
            b"<default background>"
            b"reversed"
        )

        self.assertEqual(serialized, b"".join([redBytes, blueBytes, reversedBytes]))
