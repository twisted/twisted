from __future__ import print_function

from twisted.web.template import Element, renderer, XMLFile, flattenString
from twisted.python.filepath import FilePath

class WidgetsElement(Element):
    loader = XMLFile(FilePath('iteration-1.xml'))

    widgetData = ['gadget', 'contraption', 'gizmo', 'doohickey']

    @renderer
    def widgets(self, request, tag):
        for widget in self.widgetData:
            yield tag.clone().fillSlots(widgetName=widget)

def printResult(result):
    print(result)

flattenString(None, WidgetsElement()).addCallback(printResult)
