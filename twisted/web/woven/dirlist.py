
from os.path import join as joinpath

import page, model, widgets, view

from twisted.web.microdom import lmx
from twisted.web.domhelpers import RawText

from twisted.python.filepath import FilePath

class DirectoryLister(page.Page):
    template = '''
    <html>
    <head>
    <title model="header"> </title>
    <style>
    .even-dir { background-color: #efe0ef }
    .even { background-color: #eee }
    .odd-dir {background-color: #f0d0ef }
    .odd { background-color: #dedede }
    .icon { text-align: center }
    .listing {
        margin-left: auto;
        margin-right: auto;
        width: 50%;
        padding: 0.1em;
        }

    body { border: 0; padding: 0; margin: 0; background-color: #efefef; }
    h1 {padding: 0.1em; background-color: grey; color: white; border-bottom: thin white dashed;}

    </style>
    </head>
    
    <body>
    <h1 model="header"> </h1>

    <table class="listing" view="listing">
    </table>
    
    </body>
    </html>
    '''

    def __init__(self, fp):
        self.fp = fp
        page.Page.__init__(self)

    def wvupdate_listing(self, request, node, model):
        l = lmx('div')
        ev = True
        for p in self.fp.listdir():
            r = l.tr(_class=ev and "even" or "odd")
            x = self.fp.preauthChild(p)
            if x.isdir():
                c = 'D'
            elif x.islink():
                c = 'L'
            else:
                c = 'F'
            r.td(_class="icon").text(c)
            r.td().a(href=p).text(p)
            ev = not ev
        node.appendChild(RawText(l.node.toxml()))

    def wmfactory_header(self, request):
        return "Directory listing for %s" % request.uri

from twisted.web.static import File
File._directoryLister = DirectoryLister

