
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""Plumbing classes (pump, pipeline) to put Twisted Reality on the net.
"""

import md5
import string
from cStringIO import StringIO

from twisted.reality import player
from twisted.protocols import telnet, protocol, http
from twisted.python import threadable, authenticator, log
from twisted.internet import tcp
from twisted.web import resource, html
from twisted import copyright

portno  = 8889
tportno = 8888

class Hose(telnet.Telnet):
    """A telnet protocol implementation for TR.
    """
    mode = "User"

    def welcomeMessage(self):
        """A message welcoming you to TR.
        """
        return "\r\nTwisted Reality %s\r\n" % copyright.version


    def loginPrompt(self):
        """A login prompt that asks for your character name.
        """
        return "character: "


    def processPassword(self, password):
        """Checks authentication against the reality; returns a boolean indicating success.
        """
        self.transport.write(telnet.IAC+ telnet.WONT+ telnet.ECHO+".....\r\n")
        req = self.factory.reality.application.authorizer.getIdentityRequest(self.username)
        self.pw = password
        req.addCallbacks(self.loggedIn, self.notLoggedIn)
        req.arm()
        # kludge; this really ought to be called later, but since the arm()
        # call actually calls self.loggedIn, then the return value of this
        # function will be used to assign to self.mode... ugh.
        if self.mode == 'Command':
            return 'Command'
        return "Pending"

    def loggedIn(self, identity):
        """The player's identity has been retrieved.  Now, check their password.
        """
        if identity.verifyPlainPassword(self.pw):
            # The identity checks out.
            characters = []
            # XXX REFACTOR: Hmm.  Is this next bit common behavior?
            for k in identity.getAllKeys():
                svc = k.getService()
                if svc is self.factory.reality:
                    characters.append(k.getPerspective())
            lc = len(characters)
            if lc == 1:
                p = characters[0]
            elif lc > 1:
                p = characters[0]
                self.transport.write("TODO: character selection menu\r\n")
            else:
                raise passport.Unauthorized("that identity has no TR characters")

            p.attached(self, identity)
            self.player = p
            self.transport.write("Hello "+self.player.name+", welcome to Reality!\r\n"+
                                 telnet.IAC+telnet.WONT+telnet.ECHO)
            self.mode = "Command"
        else:
            log.msg("incorrect password") 
            self.transport.loseConnection()

    def notLoggedIn(self, err):
        log.msg('requested bad username')
        self.transport.loseConnection()

    def processPending(self, pend):
        self.transport.write("Please hold...\r\n")
        return "Pending"
    
    def processCommand(self, cmd):
        """Execute a command as a player.
        """
        self.player.execute(cmd)
        return "Command"

    def connectionLost(self):
        """Disconnect player from this Intelligence, and clean up connection.
        """
        telnet.Telnet.connectionLost(self)
        if hasattr(self, 'player'):
            if hasattr(self.player, 'intelligence'):
                self.player.detached(self)


    def seeName(self, name):
        """Display a focused name bracketed, in bold.
        """
        self.transport.write(telnet.BOLD_MODE_ON+"[ "+name+" ]"+telnet.BOLD_MODE_OFF+
                             "\r\n")


    def seeItem(self, key, parent, value):
        """Display an item that's present.
        """
        self.transport.write(" "+value+"\r\n")

    def dontSeeItem(self, key, parent):
        """no-op; would be nonsensical over telnet.
        """

    def seeNoItems(self):
        """no-op; would be nonsensical over telnet.
        """

    def seeExit(self, direction):
        """Display a single exit.
        """
        self.transport.write("You can go "+direction+"\r\n")

    def dontSeeExit(self, direction):
        """no-op; would be nonsensical over telnet.
        """

    def seeNoExits(self):
        """no-op; would be nonsensical over telnet.
        """

    def seeDescription(self, key, description):
        """Displays a description.
        """
        self.transport.write(description+"\r\n")

    def dontSeeDescription(self, key):
        """no-op; would be nonsensical over telnet.
        """

    def seeNoDescriptions(self):
        """no-op; would be nonsensical over telnet.
        """

    def seeEvent(self, string):
        """Displays an event to the player.
        """
        self.transport.write(string+'\r\n')

    def request(self, question,default,ok,cancel):
        """Requests are not supported by this interface; calls cancel() immediately.
        """
        self.transport.write('edit operations not supported in telnet!\r\n')
        cancel()



class Spigot(protocol.Factory):
    """
    A telnet factory for twisted.reality.
    """

    def buildProtocol(self, addr):
        p = Hose()
        p.factory = self
        return p
    
    def __init__(self, world):
        """Initialize with a twisted.reality.Reality instance.
        """
        self.reality = world

class Placer(resource.Resource):
    """A callback to place() an object through the web.
    """
    def __init__(self, thing):
        """Initialize, with the thing to be moved.
        """
        resource.Resource.__init__(self)
        self.thing = thing
        
    def render(self, request):
        """Render a redirect to place the item.
        """
        request.setHeader("Location","http://%s/%s" % (request.getHeader("host"), string.join(request.prepath[:-2],'/')))
        request.code = http.MOVED_PERMANENTLY
        return "NO CONTENT"


class WebThing(html.Interface):
    """A web-based interface to a twisted.reality.thing.Thing.
    """
    def __init__(self, thing):
        """Initialize with a particular thing.
        """
        html.Interface.__init__(self)
        self.thing = thing

    def pagetitle(self,request):
        """Return a page title formatting the request.
        """
        session = request.getSession()
        return "Twisted Reality: %s" % self.thing.shortName(
            session.truser)
    
    def descBox(self, request):
        """Display the description in a box.
        """
        player = request.getSession().truser
        x = StringIO()
        x.write(self.thing.descriptionTo(player))
        x.write('<br><A HREF="%s?action=moveMe">Move Me Here</a>' %
                (self._getpath(request)))
        return x.getvalue()

    def itemsBox(self, request):
        """Display the items in a box.
        """
        player = request.getSession().truser
        x = StringIO()
        w = x.write
        w("<UL>")
        for thing in self.thing.getThings(player):
            w('<LI><A HREF="%s">%s</A>' % (
                thing.thing_id,
                thing.presentPhrase(player)))
        w("</UL>")
        return x.getvalue()

    def exitsBox(self, request):
        """Display the exits in a box.
        """
        player = request.getSession().truser
        x = StringIO()
        w = x.write
        w("<UL>")
        for direc in self.thing.exits:
            dest = self.thing.findExit(direc)
            w("<LI>")
            w(direc)
            w(": ")
            w('<A HREF="%s">' % dest.thing_id)
            w(dest.shortName(player))
            w('</A>')
        w("</UL>")
        return x.getvalue()
        

    def thingInfo(self, request):
        """Display boxes continaing description, items, and exits.
        """
        a = self.runBox(request, "Description",
                        self.descBox, request)
        b = self.runBox(request, "Items",
                        self.itemsBox, request)
        c = self.runBox(request, "Exits",
                        self.exitsBox, request)
        return ("<table><tr><td colspan=2>%(a)s</td></tr>"
                "<tr><td>%(b)s</td><td>%(c)s</td></tr></table>" % locals())

    def content(self, request):
        """Display representation of a Thing (or move a Thing and redirect, depending on URI).
        """
        player = request.getSession().truser
        if request.args.has_key("action"):
            # cheating...
            request.setHeader("Location","http://%s%s" % (
                request.getHeader("host"), self._getpath(request)))
            request.code = http.MOVED_PERMANENTLY
            player.location = self.thing
            return "NO CONTENT"
            
        return self.runBox(request,
                           self.thing.shortName(player),
                           self.thingInfo, request)
        
    
class Web(html.Interface):
    """A web interface to a twisted.reality.reality.Reality.
    """
    def __init__(self, in_reality):
        """Initialize with a reality.
        """
        html.Interface.__init__(self)
        self.reality = in_reality
        
    def getChild(self, name, request):
        """Get a Thing from this reality.
        """
        if name == '':
            return self
        return WebThing(self.reality.getThingById(int(name)))
        
    def listStuff(self, request):
        """List all availble Things and there IDs
        """
        player = request.getSession().truser
        x = StringIO()
        x.write('<UL>\n')
        for thing in self.reality.objects():
            np = thing.nounPhrase(player)
            x.write('<LI><A HREF="%s">%s</a>\n'% (str(thing.thing_id),np))
        x.write('</UL>\n')
        return x.getvalue()
    
    def loginForm(self, request):
        """Display a login form for a character.
        """
        return self.form(request,
                         [['string', "Character Name", "UserName", ""],
                          ['password', "Password", "Password", ""]])

    def content(self, request):
        """Display content depending on URI.
        """
        session = request.getSession()
        if hasattr(session, 'truser'):
            return self.runBox(request, "Twisted Reality",
                               self.listStuff, request)
        else:
            if not request.args:
                return self.runBox(request, "Log In Please", self.loginForm, request)
            else:
                u = request.args["UserName"][0]
                p = request.args["Password"][0]
                r = self.reality
                player = r.get(u,None)
                if ((player is not None) and
                    (md5.new(p).digest() == player.password)):
                    session.truser = player
                    return self.runBox(request, "Twisted Reality",
                                       self.listStuff, request)
                else:
                    return self.runBox(request, "Login Incorrect.",
                                       self.loginForm, request)
