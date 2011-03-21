from twisted.web.template import Element, renderer, XMLFile, tags

class ExampleElement(Element):
    loader = XMLFile('template-1.xml')

    @renderer
    def header(self, request, tag):
        return tag(tags.p('Header.'), id='header')

    @renderer
    def footer(self, request, tag):
        return tag(tags.p('Footer.'), id='footer')
