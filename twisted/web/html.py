
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
import resource

import traceback, string

from cStringIO import StringIO

def escape(text):
    "Escape a few HTML special chars with HTML entities."
    for s, h in [('&', '&amp;'), #order is important
                 ('<', '&lt;'),
                 ('>', '&gt;'),
                 ('"', '&quot;')]:
        text = string.replace(text, s,h)
    return text

def PRE(text):
    "Wrap <PRE> tags around some text and escape it with web.escape."
    return "<PRE>"+escape(text)+"</PRE>"

def UL(lst):
    io = StringIO()
    io.write("<UL>\n")
    for el in lst:
        io.write("<LI> %s\n" % el)
    io.write("</ul>")
    return io.getvalue()

def linkList(lst):
    io = StringIO()
    io.write("<UL>\n")
    for hr, el in lst:
        io.write('<LI> <A HREF="%s">%s</a>\n' % (hr, el))
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
        io.write("Calling:\n\t")
        io.write(repr(func))
        io.write("\nWith:\n\t")
        io.write(repr(args))
        io.write("\n\t")
        io.write(repr(kw))
        io.write("\n\n")

        traceback.print_exc(file=io)

        return PRE(io.getvalue())


class Interface(resource.Resource):
    """I am an interface to something through the web.
    
    I am a utility class designed to aid in development of web resources which
    are actually user interfaces to programs. See web.Test for an example.  If
    you want to use a stylesheet with your resources, override the string
    attribute 'stylesheet' in your subclass.
    """

    # First, some static data
    stylesheet = '''
A
{
    font-family: Lucida, Verdana, Helvetica, Arial;
    color: #336699;
    text-decoration: none;
}

TH
{
    font-family: Lucida, Verdana, Helvetica, Arial;
    font-weight: bold;
    text-decoration: none;
}

PRE, CODE
{
    font-family: Courier New, Courier;
}

P, BODY, TD, OL, UL, MENU, BLOCKQUOTE, DIV
{
    font-family: Lucida, Verdana, Helvetica, Arial;
    color: #000000;
}

'''
    # <link rel="STYLESHEET" type="text/css" href="%(path)s/style">
     
    boxsrc = '''
    <table cellpadding=1 cellspacing=0 border=0><tr><td bgcolor="#000000">
    <center><font color="#FFFFFF">%(title)s</font></center>
    <table cellpadding=3 cellspacing=0 border=0><tr><td bgcolor="#FFFFFF">
    %(content)s
    </td></tr></table></td></tr></table>
    '''

    pagesrc = '''
    <HTML>
    <STYLE>
    %(stylesheet)s
    </STYLE>
    <HEAD>
       <TITLE>%(title)s</TITLE>

    </HEAD>
    <BODY>

      %(content)s
    </body>
    </html>
    '''
    # '


    def webpage(self, request, title, content):
        """I create an HTML-formatted string for a complete page.

        This uses the 'self.pagesrc' attribute to format a title, stylesheet,
        and a page's content.  It returns this formatted as a string.
        """
        return self.pagesrc % {"path": self._getpath(request),
                               "stylesheet": self.stylesheet,
                               "title": title,
                               "content": content}

    def pagetitle(self,request):
        """Return the title of the page.

        Default vaule 
        """
        return str(self.__class__)

    def render(self, request):
        """
        TODO: Documentation
        """
        return self.webpage(request, self.pagetitle(request),
                            output(self.content, request))

    def img(self, request, name):
        """
        img(request, name) -> string
        Generates an <img> tag from 'name', which is the name of your
        image file.
        """
        path = self._getpath(request)
        return '<IMG SRC="%s/%s">'% (path, name)

    def centered(self, content):
        """
        centered(content) -> string
        Puts <CENTER> </CENTER> tags around your content.
        """
        return "<CENTER>"+content+"</CENTER>"

    def _input_hidden(self, request, name, data):
        return '<INPUT TYPE="hidden" NAME="%s" VALUE="%s">' % (name, data)

    def _input_file(self, request, name, data):
        return '<INPUT SIZE=60 TYPE="file" NAME="%s">' % (name)

    def _input_string(self, request, name, data):
        return '<INPUT SIZE=60 TYPE="text" NAME="%s" VALUE="%s">' % (name, data)

    def _input_text(self, request, name, data):
        return '<TEXTAREA COLS="60" ROWS="10" NAME="%s" WRAP="virtual">%s</textarea>' % (name, data)

    def _input_menu(self, request, name, data):
        "Data of the format (NAME, [OPTION, OPTION, OPTION])"
        io = StringIO()
        io.write('<SELECT NAME="')
        io.write(name)
        io.write('">\n')
        for item in data:
            io.write("<OPTION>")
            io.write(item)
            io.write("\n")
        io.write("</select>")
        return io.getvalue()

    def _input_password(self, request, name, data):
        return '<INPUT SIZE=60 TYPE="password" NAME="%s">' % (name)

    def form(self, request, dataList, submit="OK", action=None):
        """Return an HTML form from some formatted parameters.

        'dataList' is of the format::

         [(inputType, displayName, inputName, customData), ...]

        'submit' is the string that you would like your submit button to show.
        'action' is the URL to load after the user presses the submit button.
        This method is extremely fragile.  Running it under web.output is
        highly advisable.
        """
        io = StringIO()
        io.write('<FORM')
        if action is not None:
            io.write(' ACTION="%s"' % action)
        io.write(' ENCTYPE="multipart/form-data" METHOD="post">')

        io.write('<TABLE WIDTH="80%">')

        for inputType, displayName, inputName, customData in dataList:
            inputFunc = getattr(self, "_input_%s" % inputType)
            io.write('<TR><TD WIDTH="60%" ALIGN="right" VALIGN="top"><B>')
            io.write(displayName)
            if inputType == 'text':
                valign='top'
            else:
                valign='middle'

            io.write('</b></td><TD VALIGN="%s">' % valign)
            io.write(inputFunc(request, inputName, customData))
            io.write("</td></tr>")

        io.write('<TR><TD></TD><TD ALIGN="right"><INPUT TYPE="submit" NAME=submit VALUE="%s"></td</tr>' % submit)
        io.write("</TABLE>")
        io.write("</FORM>")
        return io.getvalue()

    def _getpath(self, request):
        path = request.uri
        if path[-1]=='/':
            path = path[:-1]
        path = string.split(path, '?')[0]
        return path

    def box(self, request, title, content):
        """
        box(request, title, content) -> string
        Puts your content into a nice-looking nested table with a
        black border.
        """
        path = self._getpath(request)
        return self.boxsrc % {"title": title, "content": content}

    def runBox(self, request, title, contentfunc, *cargs, **ckw):
        """
        runBox(request, title, contentfunc, *cargs, **ckw) -> string

        Calls 'contentfunc' with args *cargs and keywoard args **ckw and puts
        the output in a box()
        """
        return self.box(request, title, apply(output, (contentfunc,)+cargs, ckw))
