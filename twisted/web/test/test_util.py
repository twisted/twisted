# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.util}.
"""

from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase
from twisted.internet import defer
from twisted.web import util
from twisted.web.error import FlattenerError
from twisted.web.util import (
    redirectTo, _SourceLineElement,
    _SourceFragmentElement, _FrameElement, _StackElement,
    FailureElement, formatFailure, DeferredResource, htmlIndent)

from twisted.web.http import FOUND
from twisted.web.server import Request
from twisted.web.template import TagLoader, flattenString, tags
from twisted.web import resource
from twisted.web.test.requesthelper import DummyChannel, DummyRequest


class RedirectToTestCase(TestCase):
    """
    Tests for L{redirectTo}.
    """

    def test_headersAndCode(self):
        """
        L{redirectTo} will set the C{Location} and C{Content-Type} headers on
        its request, and set the response code to C{FOUND}, so the browser will
        be redirected.
        """
        request = Request(DummyChannel(), True)
        request.method = 'GET'
        targetURL = "http://target.example.com/4321"
        redirectTo(targetURL, request)
        self.assertEqual(request.code, FOUND)
        self.assertEqual(
            request.responseHeaders.getRawHeaders('location'), [targetURL])
        self.assertEqual(
            request.responseHeaders.getRawHeaders('content-type'),
            ['text/html; charset=utf-8'])


    def test_redirectToUnicodeURL(self) :
        """
        L{redirectTo} will raise TypeError if unicode object is passed in URL
        """
        request = Request(DummyChannel(), True)
        request.method = 'GET'
        targetURL = u'http://target.example.com/4321'
        self.assertRaises(TypeError, redirectTo, targetURL, request)



class FailureElementTests(TestCase):
    """
    Tests for L{FailureElement} and related helpers which can render a
    L{Failure} as an HTML string.
    """
    def setUp(self):
        """
        Create a L{Failure} which can be used by the rendering tests.
        """
        def lineNumberProbeAlsoBroken():
            message = "This is a problem"
            raise Exception(message)
        # Figure out the line number from which the exception will be raised.
        self.base = lineNumberProbeAlsoBroken.func_code.co_firstlineno + 1

        try:
            lineNumberProbeAlsoBroken()
        except:
            self.failure = Failure(captureVars=True)
            self.frame = self.failure.frames[-1]


    def test_sourceLineElement(self):
        """
        L{_SourceLineElement} renders a source line and line number.
        """
        element = _SourceLineElement(
            TagLoader(tags.div(
                    tags.span(render="lineNumber"),
                    tags.span(render="sourceLine"))),
            50, "    print 'hello'")
        d = flattenString(None, element)
        expected = (
            u"<div><span>50</span><span>"
            u" \N{NO-BREAK SPACE} \N{NO-BREAK SPACE}print 'hello'</span></div>")
        d.addCallback(
            self.assertEqual, expected.encode('utf-8'))
        return d


    def test_sourceFragmentElement(self):
        """
        L{_SourceFragmentElement} renders source lines at and around the line
        number indicated by a frame object.
        """
        element = _SourceFragmentElement(
            TagLoader(tags.div(
                    tags.span(render="lineNumber"),
                    tags.span(render="sourceLine"),
                    render="sourceLines")),
            self.frame)

        source = [
            u' \N{NO-BREAK SPACE} \N{NO-BREAK SPACE}message = '
            u'"This is a problem"',

            u' \N{NO-BREAK SPACE} \N{NO-BREAK SPACE}raise Exception(message)',
            u'# Figure out the line number from which the exception will be '
            u'raised.',
        ]
        d = flattenString(None, element)
        d.addCallback(
            self.assertEqual,
            ''.join([
                    '<div class="snippet%sLine"><span>%d</span><span>%s</span>'
                    '</div>' % (
                        ["", "Highlight"][lineNumber == 1],
                        self.base + lineNumber,
                        (u" \N{NO-BREAK SPACE}" * 4 + sourceLine).encode(
                            'utf-8'))
                    for (lineNumber, sourceLine)
                    in enumerate(source)]))
        return d


    def test_frameElementFilename(self):
        """
        The I{filename} renderer of L{_FrameElement} renders the filename
        associated with the frame object used to initialize the
        L{_FrameElement}.
        """
        element = _FrameElement(
            TagLoader(tags.span(render="filename")),
            self.frame)
        d = flattenString(None, element)
        d.addCallback(
            # __file__ differs depending on whether an up-to-date .pyc file
            # already existed.
            self.assertEqual, "<span>" + __file__.rstrip('c') + "</span>")
        return d


    def test_frameElementLineNumber(self):
        """
        The I{lineNumber} renderer of L{_FrameElement} renders the line number
        associated with the frame object used to initialize the
        L{_FrameElement}.
        """
        element = _FrameElement(
            TagLoader(tags.span(render="lineNumber")),
            self.frame)
        d = flattenString(None, element)
        d.addCallback(
            self.assertEqual, "<span>" + str(self.base + 1) + "</span>")
        return d


    def test_frameElementFunction(self):
        """
        The I{function} renderer of L{_FrameElement} renders the line number
        associated with the frame object used to initialize the
        L{_FrameElement}.
        """
        element = _FrameElement(
            TagLoader(tags.span(render="function")),
            self.frame)
        d = flattenString(None, element)
        d.addCallback(
            self.assertEqual, "<span>lineNumberProbeAlsoBroken</span>")
        return d


    def test_frameElementSource(self):
        """
        The I{source} renderer of L{_FrameElement} renders the source code near
        the source filename/line number associated with the frame object used to
        initialize the L{_FrameElement}.
        """
        element = _FrameElement(None, self.frame)
        renderer = element.lookupRenderMethod("source")
        tag = tags.div()
        result = renderer(None, tag)
        self.assertIsInstance(result, _SourceFragmentElement)
        self.assertIdentical(result.frame, self.frame)
        self.assertEqual([tag], result.loader.load())


    def test_stackElement(self):
        """
        The I{frames} renderer of L{_StackElement} renders each stack frame in
        the list of frames used to initialize the L{_StackElement}.
        """
        element = _StackElement(None, self.failure.frames[:2])
        renderer = element.lookupRenderMethod("frames")
        tag = tags.div()
        result = renderer(None, tag)
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], _FrameElement)
        self.assertIdentical(result[0].frame, self.failure.frames[0])
        self.assertIsInstance(result[1], _FrameElement)
        self.assertIdentical(result[1].frame, self.failure.frames[1])
        # They must not share the same tag object.
        self.assertNotEqual(result[0].loader.load(), result[1].loader.load())
        self.assertEqual(2, len(result))


    def test_failureElementTraceback(self):
        """
        The I{traceback} renderer of L{FailureElement} renders the failure's
        stack frames using L{_StackElement}.
        """
        element = FailureElement(self.failure)
        renderer = element.lookupRenderMethod("traceback")
        tag = tags.div()
        result = renderer(None, tag)
        self.assertIsInstance(result, _StackElement)
        self.assertIdentical(result.stackFrames, self.failure.frames)
        self.assertEqual([tag], result.loader.load())


    def test_failureElementType(self):
        """
        The I{type} renderer of L{FailureElement} renders the failure's
        exception type.
        """
        element = FailureElement(
            self.failure, TagLoader(tags.span(render="type")))
        d = flattenString(None, element)
        d.addCallback(
            self.assertEqual, "<span>exceptions.Exception</span>")
        return d


    def test_failureElementValue(self):
        """
        The I{value} renderer of L{FailureElement} renders the value's exception
        value.
        """
        element = FailureElement(
            self.failure, TagLoader(tags.span(render="value")))
        d = flattenString(None, element)
        d.addCallback(
            self.assertEqual, '<span>This is a problem</span>')
        return d



class FormatFailureTests(TestCase):
    """
    Tests for L{twisted.web.util.formatFailure} which returns an HTML string
    representing the L{Failure} instance passed to it.
    """
    def test_flattenerError(self):
        """
        If there is an error flattening the L{Failure} instance,
        L{formatFailure} raises L{FlattenerError}.
        """
        self.assertRaises(FlattenerError, formatFailure, object())


    def test_returnsBytes(self):
        """
        The return value of L{formatFailure} is a C{str} instance (not a
        C{unicode} instance) with numeric character references for any non-ASCII
        characters meant to appear in the output.
        """
        try:
            raise Exception("Fake bug")
        except:
            result = formatFailure(Failure())

        self.assertIsInstance(result, str)
        self.assertTrue(all(ord(ch) < 128 for ch in result))
        # Indentation happens to rely on NO-BREAK SPACE
        self.assertIn("&#160;", result)



class DeprecatedHTMLHelpers(TestCase):
    """
    The various HTML generation helper APIs in L{twisted.web.util} are
    deprecated.
    """
    def _htmlHelperDeprecationTest(self, functionName):
        """
        Helper method which asserts that using the name indicated by
        C{functionName} from the L{twisted.web.util} module emits a deprecation
        warning.
        """
        getattr(util, functionName)
        warnings = self.flushWarnings([self._htmlHelperDeprecationTest])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            "twisted.web.util.%s was deprecated in Twisted 12.1.0: "
            "See twisted.web.template." % (functionName,))


    def test_htmlrepr(self):
        """
        L{twisted.web.util.htmlrepr} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlrepr")


    def test_saferepr(self):
        """
        L{twisted.web.util.saferepr} is deprecated.
        """
        self._htmlHelperDeprecationTest("saferepr")


    def test_htmlUnknown(self):
        """
        L{twisted.web.util.htmlUnknown} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlUnknown")


    def test_htmlDict(self):
        """
        L{twisted.web.util.htmlDict} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlDict")


    def test_htmlList(self):
        """
        L{twisted.web.util.htmlList} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlList")


    def test_htmlInst(self):
        """
        L{twisted.web.util.htmlInst} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlInst")


    def test_htmlString(self):
        """
        L{twisted.web.util.htmlString} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlString")


    def test_htmlIndent(self):
        """
        L{twisted.web.util.htmlIndent} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlIndent")


    def test_htmlFunc(self):
        """
        L{twisted.web.util.htmlFunc} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlFunc")


    def test_htmlReprTypes(self):
        """
        L{twisted.web.util.htmlReprTypes} is deprecated.
        """
        self._htmlHelperDeprecationTest("htmlReprTypes")


    def test_stylesheet(self):
        """
        L{twisted.web.util.stylesheet} is deprecated.
        """
        self._htmlHelperDeprecationTest("stylesheet")



class SDResource(resource.Resource):
    def __init__(self,default):
        self.default = default


    def getChildWithDefault(self, name, request):
        d = defer.succeed(self.default)
        resource = util.DeferredResource(d)
        return resource.getChildWithDefault(name, request)



class DeferredResourceTests(TestCase):
    """
    Tests for L{DeferredResource}.
    """

    def testDeferredResource(self):
        r = resource.Resource()
        r.isLeaf = 1
        s = SDResource(r)
        d = DummyRequest(['foo', 'bar', 'baz'])
        resource.getChildForRequest(s, d)
        self.assertEqual(d.postpath, ['bar', 'baz'])


    def test_render(self):
        """
        L{DeferredResource} uses the request object's C{render} method to
        render the resource which is the result of the L{Deferred} being
        handled.
        """
        rendered = []
        request = DummyRequest([])
        request.render = rendered.append

        result = resource.Resource()
        deferredResource = DeferredResource(defer.succeed(result))
        deferredResource.render(request)
        self.assertEqual(rendered, [result])



class HtmlIndentTests(TestCase):
    """
    Tests for L{htmlIndent}
    """

    def test_simpleInput(self):
        """
        L{htmlIndent} transparently processes input with no special cases
        inside.
        """
        line = "foo bar"
        self.assertEqual(line, htmlIndent(line))


    def test_escapeHtml(self):
        """
        L{htmlIndent} escapes HTML from its input.
        """
        line = "<br />"
        self.assertEqual("&lt;br /&gt;", htmlIndent(line))


    def test_stripTrailingWhitespace(self):
        """
        L{htmlIndent} removes trailing whitespaces from its input.
        """
        line = " foo bar  "
        self.assertEqual(" foo bar", htmlIndent(line))


    def test_forceSpacingFromSpaceCharacters(self):
        """
        If L{htmlIndent} detects consecutive space characters, it forces the
        rendering by substituting unbreakable space.
        """
        line = "  foo  bar"
        self.assertEqual("&nbsp;foo&nbsp;bar", htmlIndent(line))


    def test_indentFromTabCharacters(self):
        """
        L{htmlIndent} replaces tab characters with unbreakable spaces.
        """
        line = "\tfoo"
        self.assertEqual("&nbsp; &nbsp; &nbsp; &nbsp; foo", htmlIndent(line))
