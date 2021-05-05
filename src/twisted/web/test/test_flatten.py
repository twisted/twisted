# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the flattening portion of L{twisted.web.template}, implemented in
L{twisted.web._flatten}.
"""

import sys
import re
import traceback
from collections import OrderedDict
from textwrap import dedent

from twisted.test.testutils import XMLAssertionMixin
from xml.etree.ElementTree import XML

from twisted.internet.defer import (
    CancelledError,
    Deferred,
    gatherResults,
    passthru,
    succeed,
)
from twisted.python.failure import Failure
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.error import (
    FlattenerError,
    UnfilledSlot,
    UnsupportedType,
)
from twisted.web.iweb import IRenderable
from twisted.web.template import (
    CDATA,
    CharRef,
    Comment,
    Element,
    Tag,
    TagLoader,
    flattenString,
    renderer,
    slot,
    tags,
)
from twisted.web.test._util import FlattenTestCase
from zope.interface import implementer


class SerializationTests(FlattenTestCase, XMLAssertionMixin):
    """
    Tests for flattening various things.
    """

    def test_nestedTags(self):
        """
        Test that nested tags flatten correctly.
        """
        self.assertFlattensImmediately(
            tags.html(tags.body("42"), hi="there"),
            b'<html hi="there"><body>42</body></html>',
        )

    def test_serializeString(self):
        """
        Test that strings will be flattened and escaped correctly.
        """
        self.assertFlattensImmediately("one", b"one"),
        self.assertFlattensImmediately("<abc&&>123", b"&lt;abc&amp;&amp;&gt;123"),

    def test_serializeSelfClosingTags(self):
        """
        The serialized form of a self-closing tag is C{'<tagName />'}.
        """
        self.assertFlattensImmediately(tags.img(), b"<img />")

    def test_serializeAttribute(self):
        """
        The serialized form of attribute I{a} with value I{b} is C{'a="b"'}.
        """
        self.assertFlattensImmediately(tags.img(src="foo"), b'<img src="foo" />')

    def test_serializedMultipleAttributes(self):
        """
        Multiple attributes are separated by a single space in their serialized
        form.
        """
        tag = tags.img()
        tag.attributes = OrderedDict([("src", "foo"), ("name", "bar")])
        self.assertFlattensImmediately(tag, b'<img src="foo" name="bar" />')

    def checkAttributeSanitization(self, wrapData, wrapTag):
        """
        Common implementation of L{test_serializedAttributeWithSanitization}
        and L{test_serializedDeferredAttributeWithSanitization},
        L{test_serializedAttributeWithTransparentTag}.

        @param wrapData: A 1-argument callable that wraps around the
            attribute's value so other tests can customize it.
        @param wrapData: callable taking L{bytes} and returning something
            flattenable

        @param wrapTag: A 1-argument callable that wraps around the outer tag
            so other tests can customize it.
        @type wrapTag: callable taking L{Tag} and returning L{Tag}.
        """
        self.assertFlattensImmediately(
            wrapTag(tags.img(src=wrapData('<>&"'))),
            b'<img src="&lt;&gt;&amp;&quot;" />',
        )

    def test_serializedAttributeWithSanitization(self):
        """
        Attribute values containing C{"<"}, C{">"}, C{"&"}, or C{'"'} have
        C{"&lt;"}, C{"&gt;"}, C{"&amp;"}, or C{"&quot;"} substituted for those
        bytes in the serialized output.
        """
        self.checkAttributeSanitization(passthru, passthru)

    def test_serializedDeferredAttributeWithSanitization(self):
        """
        Like L{test_serializedAttributeWithSanitization}, but when the contents
        of the attribute are in a L{Deferred
        <twisted.internet.defer.Deferred>}.
        """
        self.checkAttributeSanitization(succeed, passthru)

    def test_serializedAttributeWithSlotWithSanitization(self):
        """
        Like L{test_serializedAttributeWithSanitization} but with a slot.
        """
        toss = []
        self.checkAttributeSanitization(
            lambda value: toss.append(value) or slot("stuff"),
            lambda tag: tag.fillSlots(stuff=toss.pop()),
        )

    def test_serializedAttributeWithTransparentTag(self):
        """
        Attribute values which are supplied via the value of a C{t:transparent}
        tag have the same substitution rules to them as values supplied
        directly.
        """
        self.checkAttributeSanitization(tags.transparent, passthru)

    def test_serializedAttributeWithTransparentTagWithRenderer(self):
        """
        Like L{test_serializedAttributeWithTransparentTag}, but when the
        attribute is rendered by a renderer on an element.
        """

        class WithRenderer(Element):
            def __init__(self, value, loader):
                self.value = value
                super().__init__(loader)

            @renderer
            def stuff(self, request, tag):
                return self.value

        toss = []
        self.checkAttributeSanitization(
            lambda value: toss.append(value) or tags.transparent(render="stuff"),
            lambda tag: WithRenderer(toss.pop(), TagLoader(tag)),
        )

    def test_serializedAttributeWithRenderable(self):
        """
        Like L{test_serializedAttributeWithTransparentTag}, but when the
        attribute is a provider of L{IRenderable} rather than a transparent
        tag.
        """

        @implementer(IRenderable)
        class Arbitrary:
            def __init__(self, value):
                self.value = value

            def render(self, request):
                return self.value

        self.checkAttributeSanitization(Arbitrary, passthru)

    def checkTagAttributeSerialization(self, wrapTag):
        """
        Common implementation of L{test_serializedAttributeWithTag} and
        L{test_serializedAttributeWithDeferredTag}.

        @param wrapTag: A 1-argument callable that wraps around the attribute's
            value so other tests can customize it.
        @param wrapTag: callable taking L{Tag} and returning something
            flattenable
        """
        innerTag = tags.a('<>&"')
        outerTag = tags.img(src=wrapTag(innerTag))
        outer = self.assertFlattensImmediately(
            outerTag,
            b'<img src="&lt;a&gt;&amp;lt;&amp;gt;&amp;amp;&quot;&lt;/a&gt;" />',
        )
        inner = self.assertFlattensImmediately(innerTag, b'<a>&lt;&gt;&amp;"</a>')

        # Since the above quoting is somewhat tricky, validate it by making sure
        # that the main use-case for tag-within-attribute is supported here: if
        # we serialize a tag, it is quoted *such that it can be parsed out again
        # as a tag*.
        self.assertXMLEqual(XML(outer).attrib["src"], inner)

    def test_serializedAttributeWithTag(self):
        """
        L{Tag} objects which are serialized within the context of an attribute
        are serialized such that the text content of the attribute may be
        parsed to retrieve the tag.
        """
        self.checkTagAttributeSerialization(passthru)

    def test_serializedAttributeWithDeferredTag(self):
        """
        Like L{test_serializedAttributeWithTag}, but when the L{Tag} is in a
        L{Deferred <twisted.internet.defer.Deferred>}.
        """
        self.checkTagAttributeSerialization(succeed)

    def test_serializedAttributeWithTagWithAttribute(self):
        """
        Similar to L{test_serializedAttributeWithTag}, but for the additional
        complexity where the tag which is the attribute value itself has an
        attribute value which contains bytes which require substitution.
        """
        flattened = self.assertFlattensImmediately(
            tags.img(src=tags.a(href='<>&"')),
            b'<img src="&lt;a href='
            b"&quot;&amp;lt;&amp;gt;&amp;amp;&amp;quot;&quot;&gt;"
            b'&lt;/a&gt;" />',
        )

        # As in checkTagAttributeSerialization, belt-and-suspenders:
        self.assertXMLEqual(
            XML(flattened).attrib["src"], b'<a href="&lt;&gt;&amp;&quot;"></a>'
        )

    def test_serializeComment(self):
        """
        Test that comments are correctly flattened and escaped.
        """
        self.assertFlattensImmediately(Comment("foo bar"), b"<!--foo bar-->")

    def test_commentEscaping(self):
        """
        The data in a L{Comment} is escaped and mangled in the flattened output
        so that the result is a legal SGML and XML comment.

        SGML comment syntax is complicated and hard to use. This rule is more
        restrictive, and more compatible:

        Comments start with <!-- and end with --> and never contain -- or >.

        Also by XML syntax, a comment may not end with '-'.

        @see: U{http://www.w3.org/TR/REC-xml/#sec-comments}
        """

        def verifyComment(c):
            self.assertTrue(
                c.startswith(b"<!--"),
                f"{c!r} does not start with the comment prefix",
            )
            self.assertTrue(
                c.endswith(b"-->"),
                f"{c!r} does not end with the comment suffix",
            )
            # If it is shorter than 7, then the prefix and suffix overlap
            # illegally.
            self.assertTrue(len(c) >= 7, f"{c!r} is too short to be a legal comment")
            content = c[4:-3]
            self.assertNotIn(b"--", content)
            self.assertNotIn(b">", content)
            if content:
                self.assertNotEqual(content[-1], b"-")

        results = []
        for c in [
            "",
            "foo---bar",
            "foo---bar-",
            "foo>bar",
            "foo-->bar",
            "----------------",
        ]:
            d = flattenString(None, Comment(c))
            d.addCallback(verifyComment)
            results.append(d)
        return gatherResults(results)

    def test_serializeCDATA(self):
        """
        Test that CDATA is correctly flattened and escaped.
        """
        self.assertFlattensImmediately(CDATA("foo bar"), b"<![CDATA[foo bar]]>"),
        self.assertFlattensImmediately(
            CDATA("foo ]]> bar"), b"<![CDATA[foo ]]]]><![CDATA[> bar]]>"
        )

    def test_serializeUnicode(self):
        """
        Test that unicode is encoded correctly in the appropriate places, and
        raises an error when it occurs in inappropriate place.
        """
        snowman = "\N{SNOWMAN}"
        self.assertFlattensImmediately(snowman, b"\xe2\x98\x83")
        self.assertFlattensImmediately(tags.p(snowman), b"<p>\xe2\x98\x83</p>")
        self.assertFlattensImmediately(Comment(snowman), b"<!--\xe2\x98\x83-->")
        self.assertFlattensImmediately(CDATA(snowman), b"<![CDATA[\xe2\x98\x83]]>")
        self.assertFlatteningRaises(Tag(snowman), UnicodeEncodeError)
        self.assertFlatteningRaises(
            Tag("p", attributes={snowman: ""}), UnicodeEncodeError
        )

    def test_serializeCharRef(self):
        """
        A character reference is flattened to a string using the I{&#NNNN;}
        syntax.
        """
        ref = CharRef(ord("\N{SNOWMAN}"))
        self.assertFlattensImmediately(ref, b"&#9731;")

    def test_serializeDeferred(self):
        """
        Test that a deferred is substituted with the current value in the
        callback chain when flattened.
        """
        self.assertFlattensImmediately(succeed("two"), b"two")

    def test_serializeSameDeferredTwice(self):
        """
        Test that the same deferred can be flattened twice.
        """
        d = succeed("three")
        self.assertFlattensImmediately(d, b"three")
        self.assertFlattensImmediately(d, b"three")

    def test_serializeCoroutine(self):
        """
        Test that a coroutine returning a value is substituted with the that
        value when flattened.
        """
        from textwrap import dedent

        namespace = {}
        exec(
            dedent(
                """
            async def coro(x):
                return x
            """
            ),
            namespace,
        )
        coro = namespace["coro"]

        self.assertFlattensImmediately(coro("four"), b"four")

    def test_serializeCoroutineWithAwait(self):
        """
        Test that a coroutine returning an awaited deferred value is
        substituted with that value when flattened.
        """
        from textwrap import dedent

        namespace = dict(succeed=succeed)
        exec(
            dedent(
                """
            async def coro(x):
                return await succeed(x)
            """
            ),
            namespace,
        )
        coro = namespace["coro"]

        self.assertFlattensImmediately(coro("four"), b"four")

    def test_serializeIRenderable(self):
        """
        Test that flattening respects all of the IRenderable interface.
        """

        @implementer(IRenderable)
        class FakeElement:
            def render(ign, ored):
                return tags.p(
                    "hello, ",
                    tags.transparent(render="test"),
                    " - ",
                    tags.transparent(render="test"),
                )

            def lookupRenderMethod(ign, name):
                self.assertEqual(name, "test")
                return lambda ign, node: node("world")

        self.assertFlattensImmediately(FakeElement(), b"<p>hello, world - world</p>")

    def test_serializeSlots(self):
        """
        Test that flattening a slot will use the slot value from the tag.
        """
        t1 = tags.p(slot("test"))
        t2 = t1.clone()
        t2.fillSlots(test="hello, world")
        self.assertFlatteningRaises(t1, UnfilledSlot)
        self.assertFlattensImmediately(t2, b"<p>hello, world</p>")

    def test_serializeDeferredSlots(self):
        """
        Test that a slot with a deferred as its value will be flattened using
        the value from the deferred.
        """
        t = tags.p(slot("test"))
        t.fillSlots(test=succeed(tags.em("four>")))
        self.assertFlattensImmediately(t, b"<p><em>four&gt;</em></p>")

    def test_slotDataPropagation(self):
        """
        slot data propagation is only made to child nodes.
        Before #9383 fix, slot datas were not correctly clean during tree
        traversal and some elements that are not directly child nodes can
        reach forbidden slot data.
        """
        span1 = tags.span(slot('test'))
        span2 = tags.span(slot('test', default='17'))
        tree = tags.div(
            tags.p(span1).fillSlots(test='42'),
            tags.p(span2)
        )
        result = (
            b'<div>'
            b'<p><span>42</span></p>'
            b'<p><span>17</span></p>'  # '42' was written before #9383
            b'</div>'
        )
        return self.assertFlattensTo(tree, result)


    def test_unknownTypeRaises(self):
        """
        Test that flattening an unknown type of thing raises an exception.
        """
        self.assertFlatteningRaises(None, UnsupportedType)


# Use the co_filename mechanism (instead of the __file__ mechanism) because
# it is the mechanism traceback formatting uses.  The two do not necessarily
# agree with each other.  This requires a code object compiled in this file.
# The easiest way to get a code object is with a new function.  I'll use a
# lambda to avoid adding anything else to this namespace.  The result will
# be a string which agrees with the one the traceback module will put into a
# traceback for frames associated with functions defined in this file.

HERE = (lambda: None).__code__.co_filename


class FlattenerErrorTests(SynchronousTestCase):
    """
    Tests for L{FlattenerError}.
    """

    def test_renderable(self):
        """
        If a L{FlattenerError} is created with an L{IRenderable} provider root,
        the repr of that object is included in the string representation of the
        exception.
        """

        @implementer(IRenderable)
        class Renderable:
            def __repr__(self) -> str:
                return "renderable repr"

        self.assertEqual(
            str(FlattenerError(RuntimeError("reason"), [Renderable()], [])),
            "Exception while flattening:\n"
            "  renderable repr\n"
            "RuntimeError: reason\n",
        )

    def test_tag(self):
        """
        If a L{FlattenerError} is created with a L{Tag} instance with source
        location information, the source location is included in the string
        representation of the exception.
        """
        tag = Tag("div", filename="/foo/filename.xhtml", lineNumber=17, columnNumber=12)

        self.assertEqual(
            str(FlattenerError(RuntimeError("reason"), [tag], [])),
            "Exception while flattening:\n"
            '  File "/foo/filename.xhtml", line 17, column 12, in "div"\n'
            "RuntimeError: reason\n",
        )

    def test_tagWithoutLocation(self):
        """
        If a L{FlattenerError} is created with a L{Tag} instance without source
        location information, only the tagName is included in the string
        representation of the exception.
        """
        self.assertEqual(
            str(FlattenerError(RuntimeError("reason"), [Tag("span")], [])),
            "Exception while flattening:\n" "  Tag <span>\n" "RuntimeError: reason\n",
        )

    def test_traceback(self):
        """
        If a L{FlattenerError} is created with traceback frames, they are
        included in the string representation of the exception.
        """
        # Try to be realistic in creating the data passed in for the traceback
        # frames.
        def f():
            g()

        def g():
            raise RuntimeError("reason")

        try:
            f()
        except RuntimeError as e:
            # Get the traceback, minus the info for *this* frame
            tbinfo = traceback.extract_tb(sys.exc_info()[2])[1:]
            exc = e
        else:
            self.fail("f() must raise RuntimeError")

        self.assertEqual(
            str(FlattenerError(exc, [], tbinfo)),
            "Exception while flattening:\n"
            '  File "%s", line %d, in f\n'
            "    g()\n"
            '  File "%s", line %d, in g\n'
            '    raise RuntimeError("reason")\n'
            "RuntimeError: reason\n"
            % (
                HERE,
                f.__code__.co_firstlineno + 1,
                HERE,
                g.__code__.co_firstlineno + 1,
            ),
        )

    def test_asynchronousFlattenError(self):
        """
        When flattening a renderer which raises an exception asynchronously,
        the error is reported when it occurs.
        """
        failing = Deferred()

        @implementer(IRenderable)
        class NotActuallyRenderable:
            "No methods provided; this will fail"

            def __repr__(self):
                return "<unrenderable>"

            def lookupRenderMethod(self, name):
                ...

            def render(self, request):
                return failing

        flattening = flattenString(None, [NotActuallyRenderable()])
        self.assertNoResult(flattening)
        exc = RuntimeError("example")
        failing.errback(exc)
        failure = self.failureResultOf(flattening, FlattenerError)
        self.assertRegex(
            str(failure.value),
            re.compile(
                dedent(
                    """\
                    Exception while flattening:
                      \\[<unrenderable>\\]
                      <unrenderable>
                      .*
                      File ".*", line \\d*, in _flattenTree
                        element = await element
                    RuntimeError: example
                    """
                ),
                flags=re.MULTILINE,
            ),
        )
        # The original exception is unmodified and will be logged separately if
        # unhandled.
        self.failureResultOf(failing, RuntimeError)

    def test_cancel(self):
        """
        The flattening of a Deferred can be cancelled.
        """
        cancelCount = 0
        cancelArg = None

        def checkCancel(cancelled):
            nonlocal cancelArg, cancelCount
            cancelArg = cancelled
            cancelCount += 1

        err = None

        def saveErr(failure):
            nonlocal err
            err = failure

        d = Deferred(checkCancel)
        flattening = flattenString(None, d)
        self.assertNoResult(flattening)
        d.addErrback(saveErr)

        flattening.cancel()

        # Check whether we got an orderly cancellation.
        # Do this first to get more meaningful reporting if something crashed.
        failure = self.failureResultOf(flattening, FlattenerError)

        self.assertEqual(cancelCount, 1)
        self.assertIs(cancelArg, d)

        self.assertIsInstance(err, Failure)
        self.assertIsInstance(err.value, CancelledError)

        exc = failure.value.args[0]
        self.assertIsInstance(exc, CancelledError)
