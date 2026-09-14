from twisted.python.filepath import FilePath
from twisted.web.template import Element, XMLFile, renderer, tags


class ExampleElement(Element):
    loader = XMLFile(FilePath("template-1.xml"))

    @renderer
    def header(self, request, tag):
        return tag(tags.b("Header."))

    @renderer
    def footer(self, request, tag):
        return tag(tags.b("Footer."))
