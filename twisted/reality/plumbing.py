
"""Plumbing classes (pump, pipeline) to put Twisted Reality on the net.
"""

import md5
import string
from cStringIO import StringIO

from twisted.reality import player
from twisted.protocols import telnet, protocol, http
from twisted.python import threadable, authenticator
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
        

    def authenticate(self, username, password):
        """Checks authentication against the reality; returns a boolean indicating success.
        """
        try:
            self.factory.reality.check(username, password)
        except authenticator.Unauthorized:
            self.transport.write("NEIN!\r\n")
            return 0
        else:
            self.player = self.factory.reality.getPerspectiveNamed(self.username)
            self.transport.write("Hello "+self.player.name+", welcome to Reality!\r\n"+telnet.IAC+telnet.WONT+telnet.ECHO)
            self.player.intelligence = self
            return 1

    def processCommand(self, cmd):
        """Execute a command as a player.
        """
        try:
            self.player.execute(cmd)
        except:
            pass
        return "Command"

    def connectionLost(self):
        """Disconnect player from this Intelligence, and clean up connection.
        """
        telnet.Telnet.connectionLost(self)
        if hasattr(self, 'player'):
            player = self.player
            if hasattr(player, 'intelligence'):
                del player.intelligence
            del self.player
            player.logout()
        
    def seeName(self, name):
        """Display a focused name bracketed, in bold.
        """
        self.transport.write(telnet.BOLD_MODE_ON+"[ "+name+" ]"+telnet.BOLD_MODE_OFF+
                   "\r\n")
    def seeItem(self, thing,name):
        """Display an item that's present.
        """
        self.transport.write(" "+name+"\r\n")
    def dontSeeItem(self, thing):
        """no-op; would be nonsensical over telnet.
        """
    def seeNoItems(self):
        """no-op; would be nonsensical over telnet.
        """
    def seeExit(self, direction, exit):
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
