from element_2 import ExampleElement

from twisted.web.template import flattenString


def renderDone(output):
    print(output)


flattenString(None, ExampleElement()).addCallback(renderDone)
