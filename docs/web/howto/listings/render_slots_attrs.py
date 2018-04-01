from __future__ import print_function

from twisted.web.template import flattenString
from slots_attributes_1 import ExampleElement
def renderDone(output):
    print(output)
flattenString(None, ExampleElement()).addCallback(renderDone)
