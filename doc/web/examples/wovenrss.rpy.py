from twisted.web import microdom, client, domhelpers
from twisted.web.woven import page

def getTitleLink(url):
    d = client.getPage("http://moshez.org/discuss/rss")
    d.addCallback(microdom.parseString)
    d.addCallback(lambda d: domhelpers.findNodesNamed(d, 'item')[0])
    d.addCallback(lambda d: (
               domhelpers.getNodeText(domhelpers.findNodesNamed(d, 'link')[0]),
               domhelpers.getNodeText(domhelpers.findNodesNamed(d, 'title')[0]),
              ))
    return d

class RssViewer(page.Page):

    template = '''<html><head><title>RSS Viewer</title></head>

    <body><h1>RSS Viewer</h1><a model="rss" view="Link" /></body></html>'''

    def initialize(self, *args, **kwargs):
        self.url = kwargs['url']

    def wmfactory_rss(self, request):
        d = getTitleLink(self.url)
        d.addCallback(lambda t: {'href': t[0], 'text': t[1]})
        return d

resource = RssViewer(url='http://moshez.org/discuss/rss')
