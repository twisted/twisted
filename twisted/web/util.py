# -*- test-case-name: twisted.web.test.test_util -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from cStringIO import StringIO
import linecache
import string, re
import types

from twisted.python import failure

from twisted.web import html, resource


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


stylesheet = """
<style type="text/css">
    p.error {
      color: red;
      font-family: Verdana, Arial, helvetica, sans-serif;
      font-weight: bold;
    }

    div {
      font-family: Verdana, Arial, helvetica, sans-serif;
    }

    div.stackTrace {
    }

    div.frame {
      padding: 1em;
      background: white;
      border-bottom: thin black dashed;
    }

    div.firstFrame {
      padding: 1em;
      background: white;
      border-top: thin black dashed;
      border-bottom: thin black dashed;
    }

    div.location {
    }

    div.snippet {
      margin-bottom: 0.5em;
      margin-left: 1em;
      background: #FFFFDD;
    }

    div.snippetHighlightLine {
      color: red;
    }

    span.code {
      font-family: "Courier New", courier, monotype;
    }

    span.function {
      font-weight: bold;
      font-family: "Courier New", courier, monotype;
    }

    table.variables {
      border-collapse: collapse;
      margin-left: 1em;
    }

    td.varName {
      vertical-align: top;
      font-weight: bold;
      padding-left: 0.5em;
      padding-right: 0.5em;
    }

    td.varValue {
      padding-left: 0.5em;
      padding-right: 0.5em;
    }

    div.variables {
      margin-bottom: 0.5em;
    }

    span.heading {
      font-weight: bold;
    }

    div.dict {
      background: #cccc99;
      padding: 2px;
      float: left;
    }

    td.dictKey {
      background: #ffff99;
      font-weight: bold;
    }

    td.dictValue {
      background: #ffff99;
    }

    div.list {
      background: #7777cc;
      padding: 2px;
      float: left;
    }

    div.listItem {
      background: #9999ff;
    }

    div.instance {
      background: #cc7777;
      padding: 2px;
      float: left;
    }

    span.instanceName {
      font-weight: bold;
      display: block;
    }

    span.instanceRepr {
      background: #ff9999;
      font-family: "Courier New", courier, monotype;
    }

    div.function {
      background: orange;
      font-weight: bold;
      float: left;
    }
</style>
"""


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
    ret = string.replace(string.replace(html.escape(string.rstrip(snippetLine)),
                                  '  ', '&nbsp;'),
                   '\t', '&nbsp; &nbsp; &nbsp; &nbsp; ')
    return ret

def formatFailure(myFailure):

    exceptionHTML = """
<p class="error">%s: %s</p>
"""

    frameHTML = """
<div class="location">%s, line %s in <span class="function">%s</span></div>
"""

    snippetLineHTML = """
<div class="snippetLine"><span class="lineno">%s</span><span class="code">%s</span></div>
"""

    snippetHighlightLineHTML = """
<div class="snippetHighlightLine"><span class="lineno">%s</span><span class="code">%s</span></div>
"""

    variableHTML = """
<tr class="varRow"><td class="varName">%s</td><td class="varValue">%s</td></tr>
"""

    if not isinstance(myFailure, failure.Failure):
        return html.PRE(str(myFailure))
    io = StringIO()
    w = io.write
    w(stylesheet)
    w('<a href="#tbend">')
    w(exceptionHTML % (html.escape(str(myFailure.type)),
                       html.escape(str(myFailure.value))))
    w('</a>')
    w('<div class="stackTrace">')
    first = 1
    for method, filename, lineno, localVars, globalVars in myFailure.frames:
        if filename == '<string>':
            continue
        if first:
            w('<div class="firstFrame">')
            first = 0
        else:
            w('<div class="frame">')
        w(frameHTML % (filename, lineno, method))

        w('<div class="snippet">')
        textSnippet = ''
        for snipLineNo in range(lineno-2, lineno+2):
            snipLine = linecache.getline(filename, snipLineNo)
            textSnippet += snipLine
            snipLine = htmlIndent(snipLine)
            if snipLineNo == lineno:
                w(snippetHighlightLineHTML % (snipLineNo, snipLine))
            else:
                w(snippetLineHTML % (snipLineNo, snipLine))
        w('</div>')

        # Instance variables
        for name, var in localVars:
            if name == 'self' and hasattr(var, '__dict__'):
                usedVars = [ (key, value) for (key, value) in var.__dict__.items()
                             if _hasSubstring('self.' + key, textSnippet) ]
                if usedVars:
                    w('<div class="variables"><b>Self</b>')
                    w('<table class="variables">')
                    for key, value in usedVars:
                        w(variableHTML % (key, htmlrepr(value)))
                    w('</table></div>')
                break

        # Local and global vars
        for nm, varList in ('Locals', localVars), ('Globals', globalVars):
            usedVars = [ (name, var) for (name, var) in varList
                         if _hasSubstring(name, textSnippet) ]
            if usedVars:
                w('<div class="variables"><b>%s</b><table class="variables">' % nm)
                for name, var in usedVars:
                    w(variableHTML % (name, htmlrepr(var)))
                w('</table></div>')

        w('</div>') # frame
    w('</div>') # stacktrace
    w('<a name="tbend"> </a>')
    w(exceptionHTML % (html.escape(str(myFailure.type)),
                       html.escape(str(myFailure.value))))

    return io.getvalue()



def _hasSubstring(key, text):
    """I return True if key is part of text."""
    escapedKey = re.escape(key)
    return bool(re.search(r'\W' + escapedKey + r'\W', text))
