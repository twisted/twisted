from cStringIO import StringIO

from twisted.python import failure

import html
import resource


import linecache
import string, re
import types


def redirectTo(URL, request):
    request.redirect(URL)
    return """
<html>
    <head>
        <meta http-equiv=\"refresh\" content=\"0;URL=%(url)s\">
    </head>
    <body bgcolor=\"#FFFFFF\" text=\"#000000\">
    <!- The user\'s browser must be incredibly feeble if they have to click...-->
        Click <a href=\"%(url)s\">here</a>.
    </body>
</html>
""" % {'url': URL}

class Redirect(resource.Resource):
    def __init__(self, url):
        resource.Resource.__init__(self)
        self.url = url

    def render(self, request):
        return redirectTo(self.url, request)


def htmlrepr(x):
    return htmlReprTypes.get(type(x), htmlUnknown)(x)

def saferepr(x):
    try:
        rx = repr(x)
    except:
        rx = "<repr failed! %s instance at %s>" % (x.__class__, id(x))
    return rx

def htmlUnknown(x):
    return '<CODE>'+html.escape(saferepr(x))+'</code>'

def htmlDict(d):
    io = StringIO()
    w = io.write
    w('<table bgcolor="#cccc99"><tr><th colspan="2" align="left">Dictionary %d</th></tr>' % id(d))
    for k, v in d.items():
        if k == '__builtins__':
            v = 'builtin dictionary'
        w('\n<tr bgcolor="#ffff99"><td valign="top"><b>%s</b></td>\n<td>%s</td></tr>\n' % (htmlrepr(k), htmlrepr(v)))
    w('</table>')
    return io.getvalue()

def htmlList(l):
    io = StringIO()
    w = io.write
    w('<table bgcolor="#7777cc"><tr><th colspan="2" align="left">List %d</th></tr>' % id(l))
    for i in l:
        w('<tr bgcolor="#9999ff"><td>%s</td></tr>\n' % htmlrepr(i))
    w('</table>\n')
    return io.getvalue()

def htmlInst(i):
    if hasattr(i, "__html__"):
        s = i.__html__()
    else:
        s = '<code>'+html.escape(saferepr(i))+'</code>'
    return '''<table bgcolor="#cc7777"><tr><td><b>%s</b> instance @ 0x%x</td></tr>
              <tr bgcolor="#ff9999"><td>%s</td></tr>
              </table>
              ''' % (i.__class__, id(i), s)

def htmlString(s):
    return html.escape(saferepr(s))

htmlReprTypes = {types.DictType: htmlDict,
                 types.ListType: htmlList,
                 types.InstanceType: htmlInst,
                 types.StringType: htmlString}


def formatFailure(myFailure):
    if not isinstance(myFailure, failure.Failure):
        return html.PRE(str(myFailure))
    io = StringIO()
    w = io.write
    w("<table>")
    w('<th align="left" colspan="3"><font color="red">%s: %s</font></th>' % (html.escape(str(myFailure.type)), html.escape(str(myFailure.value))))
    line = 0
    for method, filename, lineno, localVars, globalVars in myFailure.frames:
        # Cheat to make tracebacks shorter.
        if filename == '<string>':
            continue
        # file, line number
        w('<tr bgcolor="#%s"><td colspan="2" valign="top">%s, line %s in <b>%s</b><br /><table width="100%%">' % (["bbbbbb", "cccccc"][line % 2], filename, lineno, method))
        snippet = ''
        for snipLineNo in range(lineno-2, lineno+2):
            snipLine = linecache.getline(filename, snipLineNo)
            snippet = snippet + snipLine
            snipLine = string.replace(
                string.replace(html.escape(string.rstrip(snipLine)),
                               '  ','&nbsp;'),
                '\t', '&nbsp; &nbsp; &nbsp; &nbsp; ')


            if snipLineNo == lineno:
                color = 'bgcolor="#ffffff"'
            else:
                color = ''
            w('<tr %s><td>%s</td><td><code>%s</code></td></tr>' % (color, snipLineNo,snipLine))
        w('</table></td></tr>')
        # Self vars
        w('<tr bgcolor="#%s">' % (["bbbbbb", "cccccc"][line % 2]))
        w('<td valign="top" colspan="2"><table><tr><th align="left" colspan="2">'
              'Self'
              '</th></tr>')
        for name, var in localVars:
            if name == 'self' and hasattr(var, '__dict__'):
                for key, value in var.__dict__.items():
                    if re.search(r'\W'+'self.'+key+r'\W', snippet):
                        w('<tr><td valign="top"><b>%s</b></td>'
                            '<td>%s</td></tr>' % (key, htmlrepr(value)))
        w('</table></td></tr>')
        w('<tr bgcolor="#%s">' % (["bbbbbb", "cccccc"][line % 2]))
        # Local and global vars
        for nm, varList in ('Locals', localVars), ('Globals', globalVars):
            w('<td valign="top"><table><tr><th align="left" colspan="2">'
              '%s'
              '</th></tr>' % nm)
            for name, var in varList:
                if re.search(r'\W'+name+r'\W', snippet):
                    w('<tr><td valign="top"><b>%s</b></td>'
                      '<td>%s</td></tr>' % (name, htmlrepr(var)))
            w('</table></td>')
        w('</tr>')
        line = line + 1
    w('</table>')
    return io.getvalue()
