import sys
import os
import time
from StringIO import StringIO

from nevow import flat, tags as T

import hier

PROGNAME = sys.argv[0]
USAGE = "%s text_directory html_directory language_code" % PROGNAME

def error(msg,exitcode=0,usage=False):
    sys.stderr.write("%s: %s\n" % (PROGNAME,msg))

    if usage:
        sys.stderr.write("\nusage: %s\n" % USAGE)
    
    if exitcode:
        sys.exit(exitcode)

if len(sys.argv) != 4:
    error("Incorrect number of arguments",1,True)

LANGUAGE = sys.argv[3]

import qdlocale as locale
try:
    conf = locale.locale[LANGUAGE]
except:
    error("Could not load locale configuration for '%s'" % LANGUAGE,4)

try:
    _dc = hier.title[LANGUAGE]
except:
    error("No title specified for locale '%s'" % LANGUAGE,5)

try:
    from docutils.core import publish_string
    from docutils.parsers import rst
    from docutils import nodes, utils, io
except ImportError:
    error("Error during import: Docutils is required.",99)

try:
    from twisted.python import htmlizer
except ImportError:
    error("Error during import: twisted.python.htmlizer is required", 99)

def python(name, arguments, options, content, lineno,
           content_offset, block_text, state, state_machine):
    inp = StringIO('\n'.join(content))
    outp = StringIO()
    htmlizer.filter(inp, outp, writer=htmlizer.SmallerHTMLWriter)
    html = outp.getvalue()
    return [nodes.raw('', html, format='html')]
python.content = 1

def pythonfile(name, arguments, options, content, lineno,
               content_offset, block_text, state, state_machine):
    fname = arguments[0]
    source_dir = os.path.dirname(
        os.path.abspath(state.document.current_source))
    path = os.path.normpath(os.path.join(source_dir, arguments[0]))
    path = utils.relative_path(None, path)
    state.document.settings.record_dependencies.add(path)
    encoding = options.get('encoding', state.document.settings.input_encoding)
    raw_file = io.FileInput(
        source_path=path, encoding=encoding,
        error_handler=state.document.settings.input_encoding_error_handler,
        handle_io_errors=None)
    content = raw_file.read()
    return python(name, None, None, [content], None, None, None, None, None)

pythonfile.arguments = (1, 0, 1)
rst.directives.register_directive('python', python)
rst.directives.register_directive('pythonfile', pythonfile)

TEMPLATE = \
'''~~~~~~~~~~
$title
~~~~~~~~~~

$header

-----------

^^^^^^^^^
$title
^^^^^^^^^

%s

-----------

$footer
'''


def navBar(name,flathier):
    ind = [nm for nm,node in flathier].index(name)
    
    # Set previous/next.
    if ind:
        prev = flathier[ind - 1]
    else:
        prev = None

    if ind != len(flathier) - 1:
        next = flathier[ind + 1]
    else:
        next = None

    # Find parent
    parent = None
    while ind:
        ind -= 1
        if not flathier[ind][1][-1]:
            continue
        child_pages = [page.keys()[0] for page in flathier[ind][1][-1]]
        if name in child_pages:
            parent = flathier[ind][0],flathier[ind][1]

    return flat.flatten(
        [T.a(name="top",id="top"),
        T.div(_class="navbar")[
            T.span(_class="docTitle")[hier.title[LANGUAGE]],T.br,
            T.span(_class="right")[
                prev and [conf["prev"], ": ",
                T.a(href=[prev[0],".html"])["[", prev[1][0],"]",]] or "",
                parent and [conf["up"],": ",
                T.a(href=[parent[0],".html"])["[", parent[1][0],"]",]] or "",
                conf["home"],": ",
                T.a(href=[flathier[0][0],".html"])["[",flathier[0][1][0],"]"],
                next and [conf["next"], ": ",
                    T.a(href=[next[0],".html"])["[", next[1][0],"]",]] or ""
            ],
                    ]])

def genDirectory(prefix,tree):
    elements = []
    x = 0
    for page in tree:
        x += 1
        nodenum = prefix + str(x)
        name,node = page.items()[0]
        desc,subtree = node
        elements.append(
            T.li[T.a(href=name + ".html")[" ".join((nodenum,desc))]])
        if subtree:
            elements.append(genDirectory(nodenum + ".",subtree))
    return T.ul[ elements ]

def footer(node):
    name,tree = node
    if not tree:
        directory = ""
    else:
        directory = [T.div(_class="directoryHeader")[conf["sub"]],
            T.blockquote[
            genDirectory(name != conf["toc"] and (name.split(" ")[0] + ".") or "" ,tree),
            ],T.hr()]

    return flat.flatten([directory,
    T.a(href="#top")["[",conf["top"],"]"],T.span(_class="genNote")
        [conf["updatedOn"], ' ' ,time.strftime("%a, %d %b %Y",time.localtime(time.time()))]]) 

def generateHtml(outpath,text,name,node,flathier):
    title, tree = node
    print outpath
    # Apply our basic template before docstring work.
    text = TEMPLATE % text
    html = publish_string(text, writer_name = 'html', destination_path=outpath, settings_overrides={'stylesheet':None, 'stylesheet_path':"../html/default.css"})

    # Insert the title.
    html = html.replace("$title",title,3)

    # Navigation bar
    nb = navBar(name,flathier)
    html = html.replace("<p>$header</p>",nb)

    foot = footer(node)

    # We need to use rfind to make sure we replace the *last* 
    # $footer instance
    ind = html.rfind("<p>$footer</p>")

    html = html[:ind] + foot +  html[ind + 14:]

    return html

def startNode(name):
    sys.stdout.write("%-70s" % ("Processing '%s':" % name))
    sys.stdout.flush()

def endNode():
    sys.stdout.write("[OK]\n")

def failNode():
    sys.stdout.write("[ERROR]\n")

def flattenHier(hier,flat=None,prefix=""):
    if not flat:
        name,node = hier[0].items()[0]
        return flattenHier(node[-1],[(name,node)])

    x = 0
    for node in hier:
        x += 1
        nodenum = prefix + (str(x))

        name,node = node.items()[0]

        # Convert to list so we can change the title
        node = list(node)
        node[0] = " ".join((nodenum,node[0]))
        flat.append((name,node))
        tree = node[-1]
        if tree:
            flattenHier(tree,flat,prefix + ("%d." % x))

    return flat

def generateExample(outpath, path, name, node, flathier):
    return generateHtml(outpath, """
.. pythonfile:: %s
""" % path, name, node, flathier)

def go():

    txtdir, htmldir = sys.argv[1:3]
    
    flathier = flattenHier(({conf["defaultPage"]:(conf["toc"],hier.hier)},))

    for name,node in flathier[1:]:
        startNode(name)
        for ext in ("txt", "py"):
            path = os.path.join(txtdir, name + '.' + ext)
            if os.path.exists(path):
                break
        else:
            failNode()
            error("'%s' is in hier but '%s' cannot be opened in '%s'" % (name,name,txtdir))
            continue

        outpath = os.path.join(htmldir,name + ".html")
        if ext == 'py':
            html = generateExample(outpath,path,name,node,flathier)
        else:
            data = open(path).read()
            html = generateHtml(outpath,data,name,node,flathier)
        open(outpath,"w").write(html)
        endNode()

    outpath = os.path.join(htmldir,conf["defaultPage"] + ".html")
    html = generateHtml(os.path.dirname(outpath), "",conf["defaultPage"],flathier[0][1],flathier)
    open(outpath,"w").write(html)

if __name__ == "__main__":
    go()
