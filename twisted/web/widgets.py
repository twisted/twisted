
# System Imports
import string, time, types, traceback, copy, pprint
from cStringIO import StringIO

# Twisted Imports
from twisted.python import defer

# Sibling Imports
import html, resource
from server import NOT_DONE_YET

"""A twisted web component framework.
"""

class Widget:
    def display(self, request):
        raise NotImplementedError("twisted.web.widgets.Widget.display")

class StreamWidget(Widget):
    def stream(self, write, request):
        raise NotImplementedError("twisted.web.widgets.StringWidget.stream")

    def display(self, request):
        io = StringIO()
        try:
            self.stream(io.write, request)
            return [io.getvalue()]
        except:
            io = StringIO()
            traceback.print_exc(file=io)
            return [html.PRE(io.getvalue())]

def htmlFor_hidden(write, name, value):
    write('<INPUT TYPE="hidden" NAME="%s" VALUE="%s">' % (name, value))
def htmlFor_file(write, name, value):
    write('<INPUT SIZE=60 TYPE="file" NAME="%s">' % name)
def htmlFor_string(write, name, value):
    write('<INPUT SIZE=60 TYPE="text" NAME="%s" VALUE="%s">' % (name, value))
def htmlFor_password(write, name, value):
    write('<INPUT SIZE=60 TYPE="password" NAME=%s>' % name)
def htmlFor_text(write, name, value):
    write('<TEXTAREA COLS="60" ROWS="10" NAME="%s" WRAP="virtual">%s</textarea>' % (name, value))
def htmlFor_menu(write, name, value):
    "Value of the format (NAME, [OPTION, OPTION, OPTION])"
    write('<SELECT NAME="%s">\n' % name)
    for item in value:
        write("<OPTION>\n%s\n" % item)
    write("</select>")


class FormInputError(Exception):
    pass

class Form(StreamWidget):
    formGen = {
        'hidden': htmlFor_hidden,
        'file': htmlFor_file,
        'string': htmlFor_string,
        'int': htmlFor_string,
        'text': htmlFor_text,
        'menu': htmlFor_menu,
        'password': htmlFor_password
    }
    formParse = {
        'int': int
    }
    # Subclasses should override this!
    form = [
    ]
    def format(self, write):
        write('<FORM ENCTYPE="multipart/form-data" METHOD="post">\n'
              '<TABLE BORDER="2">\n')
        for inputType, displayName, inputName, inputValue in self.form:
            write('<TR>\n<TD ALIGN="right" VALIGN="top"><B>%s</b></td>\n'
                  '<TD VALIGN="%s">\n' %
                  (displayName, ((inputType == 'text') and 'top') or 'middle'))
            self.formGen[inputType](write, inputName, inputValue)
            write('</td>\n</tr>\n')
        write('<TR><TD></TD><TD ALIGN="center">\n'
              '<INPUT TYPE="submit" NAME=submit VALUE="%s">\n'
              '</td></tr>\n</table></form>' % str(self.__class__))


    def process(self, write, request, **kw):
        write(pprint.PrettyPrinter().pformat(kw))

    # Form generation HTML constants:
    def stream(self, write, request):
        args = request.args
        print args
        print request.received
        if args and args.has_key('submit') and args['submit'][0] == str(self.__class__):
            del args['submit']
            kw = {}
            for inputType, displayName, inputName, inputValue in self.form:
                if not args.has_key(inputName):
                    raise FormInputError("suck ït down!")
                formData = args[inputName]
                del args[inputName]
                if not len(formData) == 1:
                    raise FormInputError("Suck it Down!!")
                formData = formData[0]
                method = self.formParse.get(inputType)
                if method:
                    formData = method(formData)
                kw[inputName] = formData
            if args:
                raise FormInputError("SUCK IT DOWN!!! %s" % repr(args))
            apply(self.process, (write, request), kw)
        else:
            return self.format(write)


class TextWidget(Widget):
    def __init__(self, text):
        self.text = text

    def display(self, request):
        return [self.text]

class TextDeferred(Widget):
    def __init__(self, text):
        self.text = text

    def display(self, request):
        d = defer.Deferred()
        d.callback(self.text)
        return [d]

class Time(Widget):
    """A demonstration synchronous widget.
    """
    def display(self, request):
        """Display the time.
        """
        return [time.ctime(time.time())]

class Wrapper(Widget):
    """I wrap another widget inside a box with a border and a title.
    """
    templateBegin = ('<table cellpadding=1 cellspacing=0 border=0><tr>'
                     '<td bgcolor="#000000"><center><font color="#FFFFFF">')
    # Title
    templateMiddle = ('</font></center><table cellpadding=3 cellspacing=0 border=0>'
                      '<tr><td bgcolor="#FFFFFF">')
    # Content
    templateEnd = '</td></tr></table></td></tr></table>'
    def __init__(self, title, widget):
        """Wrap a widget with a given title.
        """
        self.widget = widget
        self.title = title

    def display(self, request):
        """Return a list of HTML components.
        """
        d = [self.templateBegin, self.title, self.templateMiddle]
        try:
            disp = self.widget.display()
        except:
            io = StringIO()
            traceback.print_exc(file = io)
            disp = [html.PRE(io.getvalue())]
        d.extend(self.widget.display())
        d.append(self.templateEnd)
        return d

class Container(Widget):
    """A container of HTML.
    """
    def __init__(self, *widgets):
        self.widgets = widgets

    def display(self, request):
        value = []
        for widget in self.widgets:
            d = widget.display(request)
            value.extend(d)
        return value

class RenderSession:
    def __init__(self, lst, request):
        self.lst = lst
        self.request = request
        self.position = 0
        pos = 0
        toArm = []
        for item in lst:
            if isinstance(item, defer.Deferred):
                args = (pos,)
                item.addCallbacks(self.callback, self.errback,
                                  callbackArgs=args, errbackArgs=args)
                toArm.append(item)
            pos = pos + 1
        self.keepRendering()
        # print "RENDER: DONE WITH INITIAL PASS"
        for item in toArm:
            item.arm()

    def callback(self, result, position):
        self.lst[position] = result
        self.keepRendering()

    def errback(self, error, position):
        self.lst[position] = error
        self.keepRendering()

    def keepRendering(self):
        assert self.lst is not None, "This shouldn't happen."
        while 1:
            item = self.lst[self.position]
            if isinstance(item, types.StringType):
                self.request.write(item)
            elif isinstance(item, defer.Deferred):
                return
            else:
                self.request.write("RENDERING UNKNOWN: %s" % str(item))
            self.position = self.position + 1
            if self.position == len(self.lst):
                self.lst = None
                self.request.finish()
                return



class Page(resource.Resource, Container):
    def __init__(*args):
        resource.Resource.__init__(args[0])
        apply(Container.__init__, args)

    def render(self, request):
        RenderSession(self.display(request), request)
        return NOT_DONE_YET

class Gadget(resource.Resource):
    def __init__(self, **pages):
        pages[''] = pages.get("index")
        self.children = pages

class Presentation(Widget):
    template = 'hello %%%%world%%%%'

    def __init__(self, filename=None):
        if filename:
            self.template = open('filename').read()
        self.tmpl = string.split(self.template, "%%%%")

    def addClassVars(self, namespace, Class):
        for base in Class.__bases__:
            # Traverse only superclasses that know about Presentation.
            if issubclass(base, Presentation) and base is not Presentation:
                self.addClassVars(namespace, base)
        # 'lower' classes in the class heirarchy take precedence.
        for k in Class.__dict__.keys():
            namespace[k] = getattr(self, k)

    def addVariables(self, namespace, request):
        self.addClassVars(namespace, self.__class__)

    def display(self, request):
        "display me..."
        tm = []
        flip = 0
        namespace = {}
        self.addVariables(namespace, request)
        # This variable may not be obscured...
        namespace['request'] = request
        for elem in self.tmpl:
            flip = not flip
            if flip:
                tm.append(elem)
            else:
                try:
                    x = eval(elem, namespace, namespace)
                except:
                    io = StringIO()
                    traceback.print_exc(file = io)
                    tm.append(html.PRE(io.getvalue()))
                else:
                    if isinstance(x, types.ListType):
                        tm.extend(x)
                    elif isinstance(x, Widget):
                        tm.extend(x.display(request))
                    else:
                        tm.append(x)
        return tm

class AuthGadget(Gadget):
    """Uhh... TODO.
    """


class Toolbar(StreamWidget):
    bar = ['Twisted',
            ['mirror', 'http://coopweb.org/ssd/twisted/'],
            ['mailing list', 'cgi-bin/mailman/listinfo/twisted-python']]

    start = "<TABLE width=120 cellspacing=1 cellpadding=1 border=0>"
    rowstart = '<TR><TD colspan=2 bgcolor="#000000"><font color=white><b>%s</b></font></td></td></tr>'
    row = ('<TR><td align=right bgcolor="#e0e0e0" width=6>·</td>'
           '<TD bgcolor="#eeeeee"><A HREF="%s">%s</a></td></tr>')
    rowend = ''
    highlightedRowstart = '<TR><TD colspan=2 bgcolor="#000000"><font color=white><b>%s</b></font></td></td></tr>'
    highlightedRow = ('<TR><td align=right bgcolor="#8080e0" width=6>·</td>'
                      '<TD bgcolor="#8888ee"><A HREF="%s">%s</a></td></tr>')
    highlightedRowend = ''
    end = '</table>'

    def __init__(self, highlightHeader, highlight):
        self.highlightPage = highlihg

    def stream(self, write):
        highlighted = 0
        write(self.start)
        for each in self.bar:
            write(((highlighted and self.highlightedRowstart) or self.rowstart) % each[0])
            for name, link in each[1:]:
                write(((highlighted and self.highlightedRow) or self.row) % (link, name))
        write(self.end)

