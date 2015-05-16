# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The example gets RSS feeds from LiveJournal users.  It demonstrates how to use
chained Deferred callbacks.

To test the script, rename the file to lj.rpy, and move it to any directory,
let's say /var/www/html/.

Now, start your Twisted web server:
    $ twistd -n web --path /var/www/html/

And visit a URL like http://127.0.0.1:8080/lj.rpy?user=foo with a web browser,
replacing "foo" with a valid LiveJournal username.
"""

from twisted.web import resource as resourcelib
from twisted.web import client, microdom, domhelpers, server

urlTemplate = 'http://%s.livejournal.com/data/rss'

class LJSyndicatingResource(resourcelib.Resource):

    def render_GET(self, request):
        """
        Get an xml feed from LiveJournal and construct a new HTML page using the
        'title' and 'link' parsed from the xml document.
        """
        url = urlTemplate % request.args['user'][0]
        client.getPage(url, timeout=30).addCallback(
        microdom.parseString).addCallback(
        lambda t: domhelpers.findNodesNamed(t, 'item')).addCallback(
        lambda itms: zip([domhelpers.findNodesNamed(x, 'title')[0]
                                                               for x in itms],
                         [domhelpers.findNodesNamed(x, 'link')[0]
                                                               for x in itms]
                        )).addCallback(
        lambda itms: '<html><head></head><body><ul>%s</ul></body></html>' %
                          '\n'.join(
               ['<li><a href="%s">%s</a></li>' % (
                  domhelpers.getNodeText(link), domhelpers.getNodeText(title))
                       for (title, link) in itms])
        ).addCallback(lambda s: (request.write(s),request.finish())).addErrback(
        lambda e: (request.write('Error: %s' % e),request.finish()))
        return server.NOT_DONE_YET

resource = LJSyndicatingResource()
