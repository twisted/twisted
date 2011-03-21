from twisted.web.template import flattenString
from element_1 import ExampleElement
def renderDone(output):
    print output
flattenString(None, ExampleElement()).addCallback(renderDone)
