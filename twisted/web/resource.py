"""I hold the lowest-level Resource class."""


# System Imports
import string

class Resource:
    """
    web.Resource

    This defines a resource or directory!
    """

    server = None

    def Link(self, x, y, **kw):
        "Link text X to URI Y"
        uri = y

        argpart = string.join(map(lambda (x,y): x+y, kw.items()),'&')
        if argpart:
            uri = uri + "?" + argpart

        return '<A HREF="%s">%s</a> &nbsp;&nbsp;&nbsp;'%(uri, x)


    def __init__(self):
        self.children = {}

    isLeaf = 0

    classChildren = {}

    def getChild(self, path, request):
        return error.NoResource()

    def getChildWithDefault(self,path, request):
        for dict in (self.children, self.classChildren):
            if dict.has_key(path):
                return dict[path]

        return self.getChild(path, request)


    def putChild(self, path, child):
        self.children[path] = child
        child.server = self.server


    def render(self, request):
        """Render a given resource.
        
        The return value of this method will be the rendered page, unless the
        return value is twisted.web.server.NOT_DONE_YET, in which case it is
        this class's responsability to write the results to
        request.write(data), then call request.finish().
        """
        raise "%s called" % str(self.__class__.__name__)

#t.w imports
#This is ugly, I know, but since error.py directly access resource.Resource
#during import-time (it subclasses it), the Resource class must be defined
#by the time error is imported.
import error
