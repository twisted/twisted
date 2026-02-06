from twisted.python.filepath import FilePath
from twisted.web.template import Element, XMLFile, renderer


class ExampleElement(Element):
    loader = XMLFile(FilePath("transparent-1.xml"))

    @renderer
    def renderer1(self, request, tag):
        return tag("hello")

    @renderer
    def renderer2(self, request, tag):
        return tag("world")
