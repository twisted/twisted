from twisted.web.template import Element, renderer, XMLFile

class ExampleElement(Element):
    loader = XMLFile('transparent-1.xml')

    @renderer
    def renderer1(self, request, tag):
        return tag("hello")

    @renderer
    def renderer2(self, request, tag):
        return tag("world")
