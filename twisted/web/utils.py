import error
import html


class NamespaceInterface(html.Interface):
    """I am a web-based interface to Python namespaces.

    I can interface to any object with attributes, but I do it poorly :).
    """
    def __init__(self, name, namespace):
        """Initialize, given some name and namespace.
        """
        html.Interface.__init__(self)
        self.name = name
        self.namespace = namespace
        
    def getChild(self, path, request):
        """Implementation of 'web.Resource.getChild'.

        If my namespace has a name 'path', I will return a NamespaceInterface
        for that object.  Otherwise, web.NoResource().
        """
        try:
            return NamespaceInterface(path, getattr(self.namespace, path))
        except AttributeError:
            return error.NoResource()

    def render(self, request):
        """Implementation of 'web.Resource.render'.

        Display a dictionary
        """
        content = ""
        foo = 0
        if request.args.has_key("action"):
            if "repr" in request.args["action"]:
                return self.webpage(request, "namespace browser", web.PRE(str(self.namespace)))
            else:
                foo = 1
        else:
            foo = 1

        if foo == 1:
            for x in dir(self.namespace):
                #TODO: use childLink
                content = content + '[ <a href="%s/%s?action=repr">repr()</a> <a href="%s/%s">%s</a> - %s]<br>\n' % (self.name, x, self.name, x, x, web.PRE(str(type(getattr(self.namespace, x)))))

        return self.webpage(request, "namespace browser", content)
