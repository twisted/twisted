# -*- test-case-name: twisted.web.test.test_util -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An assortment of web server-related utilities.
"""

__all__ = [
    "redirectTo", "Redirect", "ChildRedirector", "ParentRedirect",
    "DeferredResource", "htmlIndent", "FailureElement", "formatFailure"]

from cStringIO import StringIO
import linecache
import types

from twisted.python.reflect import fullyQualifiedName
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version
from twisted.python.modules import getModule

from twisted.web import html, resource
from twisted.web.template import (
    TagLoader, XMLFile, Element, renderer, flattenString)


def redirectTo(URL, request):
    """
    Generate a redirect to the given location.

    @param URL: A C{str} giving the location to which to redirect.
    @type URL: C{str}

    @param request: The request object to use to generate the redirect.
    @type request: L{IRequest<twisted.web.iweb.IRequest>} provider

    @raise TypeError: If the type of C{URL} a C{unicode} instead of C{str}.

    @return: A C{str} containing HTML which tries to convince the client agent
        to visit the new location even if it doesn't respect the I{FOUND}
        response code.  This is intended to be returned from a render method,
        eg::

            def render_GET(self, request):
                return redirectTo("http://example.com/", request)
    """
    if isinstance(URL, unicode) :
        raise TypeError("Unicode object not allowed as URL")
    request.setHeader("content-type", "text/html; charset=utf-8")
    request.redirect(URL)
    return """
<html>
    <head>
        <meta http-equiv=\"refresh\" content=\"0;URL=%(url)s\">
    </head>
    <body bgcolor=\"#FFFFFF\" text=\"#000000\">
    <a href=\"%(url)s\">click here</a>
    </body>
</html>
""" % {'url': URL}

class Redirect(resource.Resource):

    isLeaf = 1

    def __init__(self, url):
        resource.Resource.__init__(self)
        self.url = url

    def render(self, request):
        return redirectTo(self.url, request)

    def getChild(self, name, request):
        return self

class ChildRedirector(Redirect):
    isLeaf = 0
    def __init__(self, url):
        # XXX is this enough?
        if ((url.find('://') == -1)
            and (not url.startswith('..'))
            and (not url.startswith('/'))):
            raise ValueError("It seems you've given me a redirect (%s) that is a child of myself! That's not good, it'll cause an infinite redirect." % url)
        Redirect.__init__(self, url)

    def getChild(self, name, request):
        newUrl = self.url
        if not newUrl.endswith('/'):
            newUrl += '/'
        newUrl += name
        return ChildRedirector(newUrl)


from twisted.python import urlpath

class ParentRedirect(resource.Resource):
    """
    I redirect to URLPath.here().
    """
    isLeaf = 1
    def render(self, request):
        return redirectTo(urlpath.URLPath.fromRequest(request).here(), request)

    def getChild(self, request):
        return self


class DeferredResource(resource.Resource):
    """
    I wrap up a Deferred that will eventually result in a Resource
    object.
    """
    isLeaf = 1

    def __init__(self, d):
        resource.Resource.__init__(self)
        self.d = d

    def getChild(self, name, request):
        return self

    def render(self, request):
        self.d.addCallback(self._cbChild, request).addErrback(
            self._ebChild,request)
        from twisted.web.server import NOT_DONE_YET
        return NOT_DONE_YET

    def _cbChild(self, child, request):
        request.render(resource.getChildForRequest(child, request))

    def _ebChild(self, reason, request):
        request.processingFailed(reason)
        return reason


stylesheet = ""

def htmlrepr(x):
    return htmlReprTypes.get(type(x), htmlUnknown)(x)

def saferepr(x):
    try:
        rx = repr(x)
    except:
        rx = "<repr failed! %s instance at %s>" % (x.__class__, id(x))
    return rx

def htmlUnknown(x):
    return '<code>'+html.escape(saferepr(x))+'</code>'

def htmlDict(d):
    io = StringIO()
    w = io.write
    w('<div class="dict"><span class="heading">Dictionary instance @ %s</span>' % hex(id(d)))
    w('<table class="dict">')
    for k, v in d.items():

        if k == '__builtins__':
            v = 'builtin dictionary'
        w('<tr><td class="dictKey">%s</td><td class="dictValue">%s</td></tr>' % (htmlrepr(k), htmlrepr(v)))
    w('</table></div>')
    return io.getvalue()

def htmlList(l):
    io = StringIO()
    w = io.write
    w('<div class="list"><span class="heading">List instance @ %s</span>' % hex(id(l)))
    for i in l:
        w('<div class="listItem">%s</div>' % htmlrepr(i))
    w('</div>')
    return io.getvalue()

def htmlInst(i):
    if hasattr(i, "__html__"):
        s = i.__html__()
    else:
        s = html.escape(saferepr(i))
    return '''<div class="instance"><span class="instanceName">%s instance @ %s</span>
              <span class="instanceRepr">%s</span></div>
              ''' % (i.__class__, hex(id(i)), s)

def htmlString(s):
    return html.escape(saferepr(s))

def htmlFunc(f):
    return ('<div class="function">' +
            html.escape("function %s in file %s at line %s" %
                        (f.__name__, f.func_code.co_filename,
                         f.func_code.co_firstlineno))+
            '</div>')

htmlReprTypes = {types.DictType: htmlDict,
                 types.ListType: htmlList,
                 types.InstanceType: htmlInst,
                 types.StringType: htmlString,
                 types.FunctionType: htmlFunc}



def htmlIndent(snippetLine):
    """
    Strip trailing whitespace, escape HTML entities and expand indentation
    whitespace to HTML non-breaking space.

    @param snippetLine: The line of input to indent.
    @type snippetLine: L{bytes}

    @return: The escaped and indented line.
    """
    ret = (html.escape(snippetLine.rstrip())
            .replace('  ', '&nbsp;')
            .replace('\t', '&nbsp; &nbsp; &nbsp; &nbsp; '))
    return ret



class _SourceLineElement(Element):
    """
    L{_SourceLineElement} is an L{IRenderable} which can render a single line of
    source code.

    @ivar number: A C{int} giving the line number of the source code to be
        rendered.
    @ivar source: A C{str} giving the source code to be rendered.
    """
    def __init__(self, loader, number, source):
        Element.__init__(self, loader)
        self.number = number
        self.source = source


    @renderer
    def sourceLine(self, request, tag):
        """
        Render the line of source as a child of C{tag}.
        """
        return tag(self.source.replace('  ', u' \N{NO-BREAK SPACE}'))


    @renderer
    def lineNumber(self, request, tag):
        """
        Render the line number as a child of C{tag}.
        """
        return tag(str(self.number))



class _SourceFragmentElement(Element):
    """
    L{_SourceFragmentElement} is an L{IRenderable} which can render several lines
    of source code near the line number of a particular frame object.

    @ivar frame: A L{Failure<twisted.python.failure.Failure>}-style frame object
        for which to load a source line to render.  This is really a tuple
        holding some information from a frame object.  See
        L{Failure.frames<twisted.python.failure.Failure>} for specifics.
    """
    def __init__(self, loader, frame):
        Element.__init__(self, loader)
        self.frame = frame


    def _getSourceLines(self):
        """
        Find the source line references by C{self.frame} and yield, in source
        line order, it and the previous and following lines.

        @return: A generator which yields two-tuples.  Each tuple gives a source
            line number and the contents of that source line.
        """
        filename = self.frame[1]
        lineNumber = self.frame[2]
        for snipLineNumber in range(lineNumber - 1, lineNumber + 2):
            yield (snipLineNumber,
                   linecache.getline(filename, snipLineNumber).rstrip())


    @renderer
    def sourceLines(self, request, tag):
        """
        Render the source line indicated by C{self.frame} and several
        surrounding lines.  The active line will be given a I{class} of
        C{"snippetHighlightLine"}.  Other lines will be given a I{class} of
        C{"snippetLine"}.
        """
        for (lineNumber, sourceLine) in self._getSourceLines():
            newTag = tag.clone()
            if lineNumber == self.frame[2]:
                cssClass = "snippetHighlightLine"
            else:
                cssClass = "snippetLine"
            loader = TagLoader(newTag(**{"class": cssClass}))
            yield _SourceLineElement(loader, lineNumber, sourceLine)



class _FrameElement(Element):
    """
    L{_FrameElement} is an L{IRenderable} which can render details about one
    frame from a L{Failure<twisted.python.failure.Failure>}.

    @ivar frame: A L{Failure<twisted.python.failure.Failure>}-style frame object
        for which to load a source line to render.  This is really a tuple
        holding some information from a frame object.  See
        L{Failure.frames<twisted.python.failure.Failure>} for specifics.
    """
    def __init__(self, loader, frame):
        Element.__init__(self, loader)
        self.frame = frame


    @renderer
    def filename(self, request, tag):
        """
        Render the name of the file this frame references as a child of C{tag}.
        """
        return tag(self.frame[1])


    @renderer
    def lineNumber(self, request, tag):
        """
        Render the source line number this frame references as a child of
        C{tag}.
        """
        return tag(str(self.frame[2]))


    @renderer
    def function(self, request, tag):
        """
        Render the function name this frame references as a child of C{tag}.
        """
        return tag(self.frame[0])


    @renderer
    def source(self, request, tag):
        """
        Render the source code surrounding the line this frame references,
        replacing C{tag}.
        """
        return _SourceFragmentElement(TagLoader(tag), self.frame)



class _StackElement(Element):
    """
    L{_StackElement} renders an L{IRenderable} which can render a list of frames.
    """
    def __init__(self, loader, stackFrames):
        Element.__init__(self, loader)
        self.stackFrames = stackFrames


    @renderer
    def frames(self, request, tag):
        """
        Render the list of frames in this L{_StackElement}, replacing C{tag}.
        """
        return [
            _FrameElement(TagLoader(tag.clone()), frame)
            for frame
            in self.stackFrames]



class FailureElement(Element):
    """
    L{FailureElement} is an L{IRenderable} which can render detailed information
    about a L{Failure<twisted.python.failure.Failure>}.

    @ivar failure: The L{Failure<twisted.python.failure.Failure>} instance which
        will be rendered.

    @since: 12.1
    """
    loader = XMLFile(getModule(__name__).filePath.sibling("failure.xhtml"))

    def __init__(self, failure, loader=None):
        Element.__init__(self, loader)
        self.failure = failure


    @renderer
    def type(self, request, tag):
        """
        Render the exception type as a child of C{tag}.
        """
        return tag(fullyQualifiedName(self.failure.type))


    @renderer
    def value(self, request, tag):
        """
        Render the exception value as a child of C{tag}.
        """
        return tag(str(self.failure.value))


    @renderer
    def traceback(self, request, tag):
        """
        Render all the frames in the wrapped
        L{Failure<twisted.python.failure.Failure>}'s traceback stack, replacing
        C{tag}.
        """
        return _StackElement(TagLoader(tag), self.failure.frames)



def formatFailure(myFailure):
    """
    Construct an HTML representation of the given failure.

    Consider using L{FailureElement} instead.

    @type myFailure: L{Failure<twisted.python.failure.Failure>}

    @rtype: C{str}
    @return: A string containing the HTML representation of the given failure.
    """
    result = []
    flattenString(None, FailureElement(myFailure)).addBoth(result.append)
    if isinstance(result[0], str):
        # Ensure the result string is all ASCII, for compatibility with the
        # default encoding expected by browsers.
        return result[0].decode('utf-8').encode('ascii', 'xmlcharrefreplace')
    result[0].raiseException()


_twelveOne = Version("Twisted", 12, 1, 0)

for name in ["htmlrepr", "saferepr", "htmlUnknown", "htmlString", "htmlList",
             "htmlDict", "htmlInst", "htmlFunc", "htmlIndent", "htmlReprTypes",
             "stylesheet"]:
    deprecatedModuleAttribute(
        _twelveOne, "See twisted.web.template.", __name__, name)
del name
