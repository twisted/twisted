import sys
from twisted.web.template import XMLString, Element, renderer, flatten
from twisted.internet.defer import Deferred

sample = XMLString(
    """
    <div xmlns:t="http://twistedmatrix.com/ns/twisted.web.template/0.1">
    Before waiting ...
    <span t:render="wait"></span>
    ... after waiting.
    </div>
    """)

class WaitForIt(Element):
    def __init__(self):
        Element.__init__(self, loader=sample)
        self.deferred = Deferred()

    @renderer
    def wait(self, request, tag):
        return self.deferred.addCallback(
            lambda aValue: tag("A value: " + repr(aValue)))

def done(ignore):
    print("[[[Deferred fired.]]]")

print('[[[Rendering the template.]]]')
it = WaitForIt()
flatten(None, it, sys.stdout.write).addCallback(done)
print('[[[In progress... now firing the Deferred.]]]')
it.deferred.callback("<value>")
print('[[[All done.]]]')
