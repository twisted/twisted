import warnings, re, os, traceback, os.path, mimetypes

from twisted.vfs import ivfs

from twisted.python import components

from nevow import stan, loaders, rend, tags as T, entities as E
from nevow import static, inevow, url

from twisted.vfs import webhack
import twisted.vfs.adapters.stream

def loadMimeTypes(mimetype_locations=['/etc/mime.types']):
    """
    Multiple file locations containing mime-types can be passed as a list.
    The files will be sourced in that order, overriding mime-types from the
    files sourced beforehand, but only if a new entry explicitly overrides
    the current entry.
    """
    # Grab Python's built-in mimetypes dictionary.
    contentTypes = mimetypes.types_map
    # Update Python's semi-erroneous dictionary with a few of the
    # usual suspects.
    contentTypes.update(
        {
            '.conf':  'text/plain',
            '.diff':  'text/plain',
            '.exe':   'application/x-executable',
            '.flac':  'audio/x-flac',
            '.java':  'text/plain',
            '.ogg':   'application/ogg',
            '.oz':    'text/x-oz',
            '.swf':   'application/x-shockwave-flash',
            '.tgz':   'application/x-gtar',
            '.wml':   'text/vnd.wap.wml',
            '.xul':   'application/vnd.mozilla.xul+xml',
            '.py':    'text/plain',
            '.patch': 'text/plain',
        }
    )
    # Users can override these mime-types by loading them out configuration
    # files (this defaults to ['/etc/mime.types']).
    for location in mimetype_locations:
        if os.path.exists(location):
            contentTypes.update(mimetypes.read_mime_types(location))

    return contentTypes

def WebViewVFSLeaf(node):
    p, ext = os.path.splitext(node.name)
    return webhack.Stream(node, loadMimeTypes().get(ext, "text/html"))

class WebViewVFSContainer(rend.Page):
    def __init__(self, node) :
        rend.Page.__init__( self )
        self.node = node

    def renderHTTP(self, context):
        request = inevow.IRequest(context)

        if request.args.has_key('dirToMake'):
            self.node.createDirectory(request.args['dirToMake'][0])

        if request.args.has_key('filedata'):
            filename = request.args['filename'][0]
            filename = os.path.basename(re.sub("\\\\","/", filename))
            child = self.node.createFile(filename)
            child.open(os.O_WRONLY)
            child.writeChunk( 0, request.args['filedata'][0] )
            child.close()

        return rend.Page.renderHTTP(self, context)

    def childFactory(self, context, name):
        try:
            return self.node.child(name)
        except KeyError:
            return None


    def render_navbar(self, context, data):
        currnode = self.node
        currurl  = url.here
        ret      = []
        while currnode.parent != currnode:
            ret.append( T.a(href=currurl)[currnode.name] )
            ret += [ E.nbsp, '/', E.nbsp ]
            currnode = currnode.parent
            currurl  = currurl.parent()
        ret.append( T.a(href=currurl)["top"] )
        ret.reverse()
        return ret

    def render_children(self, context, data):
        return T.ul[
            [ T.li[T.a(href=name)[name]]
                for (name, child) in self.node.children() ]
        ]

    addSlash = True
    docFactory = loaders.stan(
        T.html[
            T.head[
                T.title['VFS - web front'],
                ],
            T.body[

                T.form(method="post", enctype='multipart/form-data')[
                    'upload:',
                    T.input(
                        name="filedata",
                        type="file",
                        onChange="document.getElementById('filename').value=this.value;"
                    ),
                    T.input(id="filename", name="filename", type="hidden"),
                    T.input(name="submit", type="submit", value="go")
                ],

                T.form(method="post", enctype='multipart/form-data')[
                    'mkdir:', T.input(name="dirToMake", type="text"),
                    T.input(name="submit", type="submit", value="go")
                ],
                render_navbar,
                render_children
            ],]
        )

components.registerAdapter(WebViewVFSContainer, ivfs.IFileSystemContainer,
    inevow.IResource)
components.registerAdapter(WebViewVFSLeaf, ivfs.IFileSystemLeaf,
    inevow.IResource)
