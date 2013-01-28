# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the flattening portion of L{twisted.web.template}, implemented in
L{twisted.web._flatten}.
"""

import sys
import traceback

from xml.etree.cElementTree import XML

from zope.interface import implements

from twisted.trial.unittest import TestCase
from twisted.internet.defer import succeed, gatherResults
from twisted.web._stan import Tag
from twisted.web._flatten import flattenString
from twisted.web.error import UnfilledSlot, UnsupportedType, FlattenerError
from twisted.web.template import tags, Comment, CDATA, CharRef, slot
from twisted.web.iweb import IRenderable
from twisted.test.testutils import XMLAssertionMixin
from twisted.web.test._util import FlattenTestCase



class OrderedAttributes(object):
    """
    An L{OrderedAttributes} is a stand-in for the L{Tag.attributes} dictionary
    that orders things in a deterministic order.  It doesn't do any sorting, so
    whatever order the attributes are passed in, they will be returned.

    @ivar attributes: The result of a L{dict.items} call.
    @type attributes: C{list} of 2-C{tuples}
    """

    def __init__(self, attributes):
        self.attributes = attributes


    def iteritems(self):
        """
        Like L{dict.iteritems}.

        @return: an iterator
        @rtype: list iterator
        """
        return iter(self.attributes)



class TestSerialization(FlattenTestCase, XMLAssertionMixin):
    """
    Tests for flattening various things.
    """
    def test_nestedTags(self):
        """
        Test that nested tags flatten correctly.
        """
        return self.assertFlattensTo(
            tags.html(tags.body('42'), hi='there'),
            '<html hi="there"><body>42</body></html>')


    def test_serializeString(self):
        """
        Test that strings will be flattened and escaped correctly.
        """
        return gatherResults([
            self.assertFlattensTo('one', 'one'),
            self.assertFlattensTo('<abc&&>123', '&lt;abc&amp;&amp;&gt;123'),
        ])


    def test_serializeSelfClosingTags(self):
        """
        The serialized form of a self-closing tag is C{'<tagName />'}.
        """
        return self.assertFlattensTo(tags.img(), '<img />')


    def test_serializeAttribute(self):
        """
        The serialized form of attribute I{a} with value I{b} is C{'a="b"'}.
        """
        self.assertFlattensImmediately(tags.img(src='foo'),
                                       '<img src="foo" />')


    def test_serializedMultipleAttributes(self):
        """
        Multiple attributes are separated by a single space in their serialized form.
        """
        tag = tags.img()
        tag.attributes = OrderedAttributes([("src", "foo"), ("name", "bar")])
        self.assertFlattensImmediately(tag, '<img src="foo" name="bar" />')


    def test_serializedAttributeWithSanitization(self):
        """
        Attribute values containing C{"<"}, C{">"}, C{"&"}, or C{'"'} have
        C{"&lt;"}, C{"&gt;"}, C{"&amp;"}, or C{"&quot;"} substituted for those
        bytes in the serialized output.
        """
        self.assertFlattensImmediately(
            tags.img(src="<>&\""), '<img src="&lt;&gt;&amp;&quot;" />')


    def test_serializedAttributeWithTransparentTag(self):
        """
        Attribute values which are supplied via the value of an I{transparent}
        tag have the same subsitution rules to them as values supplied
        directly.
        """
        self.assertFlattensImmediately(tags.img(src=tags.transparent('<>&"')),
                                       '<img src="&lt;&gt;&amp;&quot;" />')


    def test_serializedAttributeWithTag(self, wrapTag=lambda t: t):
        """
        L{Tag} objects which are serialized within the context of an attribute
        are serialized such that the text content of the attribute may be
        parsed to retrieve the tag.
        """
        innerTag = tags.a('<>&"')
        outerTag = tags.img(src=wrapTag(innerTag))
        outer = self.successResultOf(flattenString(None, outerTag))
        inner = self.successResultOf(flattenString(None, innerTag))
        self.assertEquals(
            outer,
            '<img src="&lt;a&gt;&amp;lt;&amp;gt;&amp;amp;&quot;&lt;/a&gt;" />')

        # Since the above quoting is somewhat tricky, validate it by making sure
        # that the main use-case for tag-within-attribute is supported here: if
        # we serialize a tag, it is quoted *such that it can be parsed out again
        # as a tag*.
        self.assertXMLEqual(XML(outer).attrib['src'], inner)


    def test_serializedAttributeWithDeferredTag(self):
        """
        Like L{test_serializedAttributeWithTag}, but when the L{Tag} is in a
        L{Deferred}.
        """
        self.test_serializedAttributeWithTag(succeed)


    def test_serializedAttributeWithTagWithAttribute(self):
        """
        Similar to L{test_serializedAttributeWithTag}, but for the additional
        complexity where the tag which is the attribute value itself has an
        attribute value which contains bytes which require substitution.
        """
        # Is this really the best behavior for this case?
        value = '<>&"'
        escapedValue = '&lt;&gt;&amp;&quot;'
        a = '<a href="' + escapedValue + '"></a>'
        escapedA = (a.replace('&', '&amp;').replace('<', '&lt;')
                     .replace('>', '&gt;').replace('"', '&quot;'))
        self.assertFlattensImmediately(tags.img(src=tags.a(href=value)),
                                       '<img src="' + escapedA + '" />')


    def test_serializeComment(self):
        """
        Test that comments are correctly flattened and escaped.
        """
        return self.assertFlattensTo(Comment('foo bar'), '<!--foo bar-->'),


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
                c.startswith('<!--'),
                "%r does not start with the comment prefix" % (c,))
            self.assertTrue(
                c.endswith('-->'),
                "%r does not end with the comment suffix" % (c,))
            # If it is shorter than 7, then the prefix and suffix overlap
            # illegally.
            self.assertTrue(
                len(c) >= 7,
                "%r is too short to be a legal comment" % (c,))
            content = c[4:-3]
            self.assertNotIn('--', content)
            self.assertNotIn('>', content)
            if content:
                self.assertNotEqual(content[-1], '-')

        results = []
        for c in [
            '',
            'foo---bar',
            'foo---bar-',
            'foo>bar',
            'foo-->bar',
            '----------------',
        ]:
            d = flattenString(None, Comment(c))
            d.addCallback(verifyComment)
            results.append(d)
        return gatherResults(results)


    def test_serializeCDATA(self):
        """
        Test that CDATA is correctly flattened and escaped.
        """
        return gatherResults([
            self.assertFlattensTo(CDATA('foo bar'), '<![CDATA[foo bar]]>'),
            self.assertFlattensTo(
                CDATA('foo ]]> bar'),
                '<![CDATA[foo ]]]]><![CDATA[> bar]]>'),
        ])


    def test_serializeUnicode(self):
        """
        Test that unicode is encoded correctly in the appropriate places, and
        raises an error when it occurs in inappropriate place.
        """
        snowman = u'\N{SNOWMAN}'
        return gatherResults([
            self.assertFlattensTo(snowman, '\xe2\x98\x83'),
            self.assertFlattensTo(tags.p(snowman), '<p>\xe2\x98\x83</p>'),
            self.assertFlattensTo(Comment(snowman), '<!--\xe2\x98\x83-->'),
            self.assertFlattensTo(CDATA(snowman), '<![CDATA[\xe2\x98\x83]]>'),
            self.assertFlatteningRaises(
                Tag(snowman), UnicodeEncodeError),
            self.assertFlatteningRaises(
                Tag('p', attributes={snowman: ''}), UnicodeEncodeError),
        ])


    def test_serializeCharRef(self):
        """
        A character reference is flattened to a string using the I{&#NNNN;}
        syntax.
        """
        ref = CharRef(ord(u"\N{SNOWMAN}"))
        return self.assertFlattensTo(ref, "&#9731;")


    def test_serializeDeferred(self):
        """
        Test that a deferred is substituted with the current value in the
        callback chain when flattened.
        """
        return self.assertFlattensTo(succeed('two'), 'two')


    def test_serializeSameDeferredTwice(self):
        """
        Test that the same deferred can be flattened twice.
        """
        d = succeed('three')
        return gatherResults([
            self.assertFlattensTo(d, 'three'),
            self.assertFlattensTo(d, 'three'),
        ])


    def test_serializeIRenderable(self):
        """
        Test that flattening respects all of the IRenderable interface.
        """
        class FakeElement(object):
            implements(IRenderable)
            def render(ign,ored):
                return tags.p(
                    'hello, ',
                    tags.transparent(render='test'), ' - ',
                    tags.transparent(render='test'))
            def lookupRenderMethod(ign, name):
                self.assertEqual(name, 'test')
                return lambda ign, node: node('world')

        return gatherResults([
            self.assertFlattensTo(FakeElement(), '<p>hello, world - world</p>'),
        ])


    def test_serializeSlots(self):
        """
        Test that flattening a slot will use the slot value from the tag.
        """
        t1 = tags.p(slot('test'))
        t2 = t1.clone()
        t2.fillSlots(test='hello, world')
        return gatherResults([
            self.assertFlatteningRaises(t1, UnfilledSlot),
            self.assertFlattensTo(t2, '<p>hello, world</p>'),
        ])


    def test_serializeDeferredSlots(self):
        """
        Test that a slot with a deferred as its value will be flattened using
        the value from the deferred.
        """
        t = tags.p(slot('test'))
        t.fillSlots(test=succeed(tags.em('four>')))
        return self.assertFlattensTo(t, '<p><em>four&gt;</em></p>')


    def test_unknownTypeRaises(self):
        """
        Test that flattening an unknown type of thing raises an exception.
        """
        return self.assertFlatteningRaises(None, UnsupportedType)


# Use the co_filename mechanism (instead of the __file__ mechanism) because
# it is the mechanism traceback formatting uses.  The two do not necessarily
# agree with each other.  This requires a code object compiled in this file.
# The easiest way to get a code object is with a new function.  I'll use a
# lambda to avoid adding anything else to this namespace.  The result will
# be a string which agrees with the one the traceback module will put into a
# traceback for frames associated with functions defined in this file.

HERE = (lambda: None).func_code.co_filename


class FlattenerErrorTests(TestCase):
    """
    Tests for L{FlattenerError}.
    """

    def test_string(self):
        """
        If a L{FlattenerError} is created with a string root, up to around 40
        bytes from that string are included in the string representation of the
        exception.
        """
        self.assertEqual(
            str(FlattenerError(RuntimeError("reason"), ['abc123xyz'], [])),
            "Exception while flattening:\n"
            "  'abc123xyz'\n"
            "RuntimeError: reason\n")
        self.assertEqual(
            str(FlattenerError(
                    RuntimeError("reason"), ['0123456789' * 10], [])),
            "Exception while flattening:\n"
            "  '01234567890123456789<...>01234567890123456789'\n"
            "RuntimeError: reason\n")


    def test_unicode(self):
        """
        If a L{FlattenerError} is created with a unicode root, up to around 40
        characters from that string are included in the string representation
        of the exception.
        """
        self.assertEqual(
            str(FlattenerError(
                    RuntimeError("reason"), [u'abc\N{SNOWMAN}xyz'], [])),
            "Exception while flattening:\n"
            "  u'abc\\u2603xyz'\n" # Codepoint for SNOWMAN
            "RuntimeError: reason\n")
        self.assertEqual(
            str(FlattenerError(
                    RuntimeError("reason"), [u'01234567\N{SNOWMAN}9' * 10],
                    [])),
            "Exception while flattening:\n"
            "  u'01234567\\u2603901234567\\u26039<...>01234567\\u2603901234567"
            "\\u26039'\n"
            "RuntimeError: reason\n")


    def test_renderable(self):
        """
        If a L{FlattenerError} is created with an L{IRenderable} provider root,
        the repr of that object is included in the string representation of the
        exception.
        """
        class Renderable(object):
            implements(IRenderable)

            def __repr__(self):
                return "renderable repr"

        self.assertEqual(
            str(FlattenerError(
                    RuntimeError("reason"), [Renderable()], [])),
            "Exception while flattening:\n"
            "  renderable repr\n"
            "RuntimeError: reason\n")


    def test_tag(self):
        """
        If a L{FlattenerError} is created with a L{Tag} instance with source
        location information, the source location is included in the string
        representation of the exception.
        """
        tag = Tag(
            'div', filename='/foo/filename.xhtml', lineNumber=17, columnNumber=12)

        self.assertEqual(
            str(FlattenerError(RuntimeError("reason"), [tag], [])),
            "Exception while flattening:\n"
            "  File \"/foo/filename.xhtml\", line 17, column 12, in \"div\"\n"
            "RuntimeError: reason\n")


    def test_tagWithoutLocation(self):
        """
        If a L{FlattenerError} is created with a L{Tag} instance without source
        location information, only the tagName is included in the string
        representation of the exception.
        """
        self.assertEqual(
            str(FlattenerError(RuntimeError("reason"), [Tag('span')], [])),
            "Exception while flattening:\n"
            "  Tag <span>\n"
            "RuntimeError: reason\n")


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
        except RuntimeError, exc:
            # Get the traceback, minus the info for *this* frame
            tbinfo = traceback.extract_tb(sys.exc_info()[2])[1:]
        else:
            self.fail("f() must raise RuntimeError")

        self.assertEqual(
            str(FlattenerError(exc, [], tbinfo)),
            "Exception while flattening:\n"
            "  File \"%s\", line %d, in f\n"
            "    g()\n"
            "  File \"%s\", line %d, in g\n"
            "    raise RuntimeError(\"reason\")\n"
            "RuntimeError: reason\n" % (
                HERE, f.func_code.co_firstlineno + 1,
                HERE, g.func_code.co_firstlineno + 1))

