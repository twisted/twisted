from twisted.web.template import Element, renderer, XMLFile

class ExampleElement(Element):
    loader = XMLFile('template-1.xml')

    @renderer
    def header(self, request, tag):
        return tag('Header.')

    @renderer
    def footer(self, request, tag):
        return tag('Footer.')
