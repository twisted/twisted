from __future__ import print_function

from twisted.web.template import flattenString
from quoting_element import ExampleElement
def renderDone(output):
    print(output)
flattenString(None, ExampleElement()).addCallback(renderDone)
