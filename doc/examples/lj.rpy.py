# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Syndicate LiveJournal users
# Demonstrates how to use chained callbacks
from __future__ import nested_scopes

from twisted.web import resource as resourcelib
from twisted.web import client, microdom, domhelpers, server

urlTemplate = 'http://www.livejournal.com/users/%s/rss'

class LJSyndicatingResource(resourcelib.Resource):

    def render_GET(self, request):
        url = urlTemplate % request.args['user'][0]
        client.getPage(url).addCallback(
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
