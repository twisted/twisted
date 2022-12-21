from twisted.python.filepath import FilePath
from twisted.web.template import Element, XMLFile, renderer


class ExampleElement(Element):
    loader = XMLFile(FilePath("template-1.xml"))

    @renderer
    def header(self, request, tag):
        return tag("<<<Header>>>!")

    @renderer
    def footer(self, request, tag):
        return tag('>>>"Footer!"<<<', id='<"fun">')
