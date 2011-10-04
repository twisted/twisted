from twisted.web.template import Element, renderer, XMLFile, flattenString

class WidgetsElement(Element):
    loader = XMLFile('iteration-1.xml')

    widgetData = ['gadget', 'contraption', 'gizmo', 'doohickey']

    @renderer
    def widgets(self, request, tag):
        for widget in self.widgetData:
            yield tag.clone().fillSlots(widgetName=widget)

def printResult(result):
    print result

flattenString(None, WidgetsElement()).addCallback(printResult)
