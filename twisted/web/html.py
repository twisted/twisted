
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I hold HTML generation helpers.
"""

#t.w imports
from twisted.web import resource

import traceback, string

from cStringIO import StringIO
from microdom import escape

def PRE(text):
    "Wrap <pre> tags around some text and HTML-escape it."
    return "<pre>"+escape(text)+"</pre>"

def UL(lst):
    io = StringIO()
    io.write("<ul>\n")
    for el in lst:
        io.write("<li> %s</li>\n" % el)
    io.write("</ul>")
    return io.getvalue()

def linkList(lst):
    io = StringIO()
    io.write("<ul>\n")
    for hr, el in lst:
        io.write('<li> <a href="%s">%s</a></li>\n' % (hr, el))
    io.write("</ul>")
    return io.getvalue()

def output(func, *args, **kw):
    """output(func, *args, **kw) -> html string
    Either return the result of a function (which presumably returns an
    HTML-legal string) or an HTMLized traceback describing why that function
    didn't run.
    """
    try:
        return apply(func, args, kw)
    except:
        io = StringIO()
        return PRE(io.getvalue())
