from twisted.python.filepath import FilePath
from twisted.web.template import Element, XMLFile, flattenString, renderer


class WidgetsElement(Element):
    loader = XMLFile(FilePath("iteration-1.xml"))

    widgetData = ["gadget", "contraption", "gizmo", "doohickey"]

    @renderer
    def widgets(self, request, tag):
        for widget in self.widgetData:
            yield tag.clone().fillSlots(widgetName=widget)


def printResult(result):
    print(result)


flattenString(None, WidgetsElement()).addCallback(printResult)
