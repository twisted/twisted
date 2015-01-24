from twisted.web.template import flattenString
from transparent_element import ExampleElement
def renderDone(output):
    print output
flattenString(None, ExampleElement()).addCallback(renderDone)
