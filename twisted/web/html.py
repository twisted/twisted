
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
