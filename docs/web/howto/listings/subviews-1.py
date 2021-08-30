from twisted.python.filepath import FilePath
from twisted.web.template import Element, TagLoader, XMLFile, flattenString, renderer


class WidgetsElement(Element):
    loader = XMLFile(FilePath("subviews-1.xml"))

    widgetData = ["gadget", "contraption", "gizmo", "doohickey"]

    @renderer
    def widgets(self, request, tag):
        for widget in self.widgetData:
            yield WidgetElement(TagLoader(tag), widget)


class WidgetElement(Element):
    def __init__(self, loader, name):
        Element.__init__(self, loader)
        self._name = name

    @renderer
    def name(self, request, tag):
        return tag(self._name)


def printResult(result):
    print(result)


flattenString(None, WidgetsElement()).addCallback(printResult)
