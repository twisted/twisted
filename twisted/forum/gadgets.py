## WARNING - this is experimental code.
## DO NOT USE THIS!!!

import string
import time

from twisted.web import widgets, guard, webpassport
from twisted.python import defer
from twisted.internet import passport

from sim.server import engine, player

class ForumPage(widgets.WidgetPage):
    """This class and stylesheet give forum pages a look different from the
    default web widgets pages.
    """
    
    stylesheet = '''
    A
    {
        font-family: Lucida, Verdana, Helvetica, Arial;
        color: #996633;
        text-decoration: none;
    }

    TH
    {
        font-family: Lucida, Verdana, Helvetica, Arial;
        font-weight: bold;
        text-decoration: none;
    }

    PRE, CODE
    {
        font-family: Courier New, Courier;
        font-size: 10pt;
    }

    P, BODY, TD, OL, UL, MENU, BLOCKQUOTE, DIV
    {
        font-family: Lucida, Verdana, Helvetica, Arial;
        font-size: 10pt;
        color: #000000;
    }
    '''

    template = '''
    <HTML>
    <STYLE>
    %%%%self.stylesheet%%%%
    </style>
    <HEAD>
    <TITLE>%%%%self.title%%%%</title>
    <BASE href="%%%%request.prePathURL()%%%%">
    </head>
    <BODY>
    %%%%self.header(request)%%%%
    %%%%self.widget%%%%
    %%%%self.footer(request)%%%%
    </body>
    </html>
    '''

    def header(self, request):
        p = self.widget.getPerspective(request)
        if p:
            msg = "logged in as %s" % p.perspectiveName
        else:
            msg = "<a href=/login/>not logged in</a>"
        title = "<table border=0 width=100%%> <tr> <td> %s:</td> <td> <a href='/'>%s</a></td> <td align=right> %s </td></tr></table><hr>" % (
            time.ctime(),
            self.widget.service.desc,
            msg)
        return title

    def footer(self, request):
        return "<hr> <i> Twisted Forums - %s </i>  (%d users online)" % (self.widget.service.desc, self.widget.service.usersOnline)
    
class ForumBaseGadget(webpassport.SessionPerspectiveMixin, widgets.Gadget, widgets.StreamWidget):
    """
    base gadget class for all forum gadgets. This sets the page template.
    """
    page = ForumPage

    def __init__(self, service):
        self.service = service
        widgets.Gadget.__init__(self)
    
"""The forum application has these functional pages:
     intro   - (/)        - List of forums
     threads - (/threads) - List of threads in a forum
     posts   - (/posts)   - List of messages in a thread
     full    - (/full)    - List of messages with details for a thread
     details - (/details) - Details of a message
     reply   - (/reply)   - Reply form to reply to a message
     new     - (/new)     - Post a new message/thread
     register- (/register) - Register a new user
     login   - (/login)   - enter username and password to log in

  The ForumGadget contains widgets to perform each of these functions.
  
"""

class ForumsGadget(ForumBaseGadget):
    title = "List of Forums"

    def __init__(self, service):
        ForumBaseGadget.__init__(self, service)
        self.putWidget('threads', ThreadsGadget(self.service))
        self.putWidget('posts',   PostsGadget(self.service))
        self.putWidget('full',    FullGadget(self.service))
        self.putWidget('details', DetailsGadget(self.service))
        self.putWidget('reply',   ReplyForm(self.service))
        self.putWidget('new',     NewPostForm(self.service))
        self.putWidget('register',RegisterUser(self.service))
        self.putWidget('login',   LoginForm(self.service))

    def stream(self, write, request):
        """Display the intro list of forums. This is only called if there is no URI.
        """
        write( self.service.manager.getForums('poster', self.gotForums, widgets.formatFailure) )

    def gotForums(self, data):
        l = []
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">'
                  '<tr bgcolor="#ff9900">'
                  '<td COLOR="#000000"><b> Forum Name </b> </td>'
                  '<td COLOR="#000000"><b> Posts </b> </td>'
                  '<td COLOR="#000000"><b> Description </b> </td>'
                  '</tr>\n' )

        for (id, name, desc, posts) in data:
            l.append( "<tr> <td> <a href='/threads/?forum_id=%d'>%s</a></td><td> %d </td> <td> %s</d></tr>\n" % (id,name, posts, desc) )
        l.append('</table>' )
        return l


class ThreadsGadget(ForumBaseGadget):
    """Displays a list of threads for a forum
    """
    
    title = "List of Threads for a forum"
    
    def stream(self, write, request):
        self.forum_id = int(request.args.get('forum_id',[0])[0])
        print "Getting threads for forum: %d" % self.forum_id
        write( self.service.manager.getTopMessages(self.forum_id, 'poster',
                                                  self.onThreadData,
                                                  self.onThreadError) )

    def onThreadData(self, data):
        l = []
        l.append( '<h3> %s:</h3>' % self.service.manager.getForumByID(self.forum_id) )
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000"><b> Thread Subject </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Thread Starter </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Replies </b> </td>' )
        l.append( '</tr>\n' )

        # change the background color of every second row 
        i=0
        for (id, subject, postdate, username, replies) in data:
            if i % 2 == 1:
                c = " bgcolor=#cccccc"
            else:
                c = ""
            i = i + 1
            l.append("<tr %s> <td> <a href='/full/?forum_id=%d&amp;post_id=%d'> %s </a> </td>" % (c, self.forum_id, int(id), subject))
            l.append("<td> <i> %s </i> </td>" % username)
            l.append("<td> %d replies </td>" % replies)
            l.append("</tr>\n")

        l.append( '</table><br>' )
        l.append( '[<a href="/new/?forum_id=%d">Start a new thread</a>]' % (self.forum_id) )
        l.append( '[<a href="/">Return to Forums</a>]' )                
        return l

    def onThreadError(self, error):
        print error
        return "ERROR: " + repr(error)


class FullGadget(ForumBaseGadget):
    """Displays a full details of all posts for a thread in a forum
    """
    
    title = "Contents of a thread"
    
    def stream(self, write, request):
        self.request = request
        self.forum_id = int(request.args.get('forum_id',[0])[0])
        self.post_id = int(request.args.get('post_id',[0])[0])        
        print "Getting posts for thread %d for forum: %d" % (self.post_id, self.forum_id)
        write( self.service.manager.getFullMessages(self.forum_id, self.post_id, 'poster',
                                                   self.onPostData, self.onPostError) )

    def onPostData(self, data):
        if len(data) == 0:
            return ["No Posts for this thread."]

        first = -1
        l = []
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')

        for (post_id, parent_id, subject, posted, username, body) in data:
            if first == -1:
                first = post_id
                l.append( '<tr bgcolor="#ff9900">' )
                l.append( '<td COLOR="#000000"><b> Topic </b> </td>')                
                l.append( '<td COLOR="#000000"><b> Author </b> </td>' )
                l.append( '<td COLOR="#000000"><b> Body </b> </td>')                
                l.append( '</tr>\n' )

            body = string.replace(body, "\n", "<br>")
            l.append( '<tr> <td valign=top> %s  </td>' % (subject) )
            l.append( '<td valign=top> %s  </td> ' % ( username) )
            l.append( '<td valign=top> <i>%s</i><hr> %s <br> </td> </tr>\n' % (posted, body) )

        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000" width=30%> </td>' )
        l.append( '<td COLOR="#000000"> </td>' )
        l.append( '<td COLOR="#000000"> </td>' )                
        l.append( '</tr>\n' )

        l.append( '</table>' )

        l.append( '[<a href="/threads/?forum_id=%d">Back to forum</a> ]' % self.forum_id)
        l.append( '[<a href="/reply/?post_id=%d&amp;forum_id=%d&amp;thread_id=%d">Reply</a>]' % (post_id, self.forum_id, first) )
        return l

    
    def onPostError(self, error):
        print error
        return "ERROR: " + repr(error)


class PostsGadget(ForumBaseGadget):
    """Displays a list of posts for a thread in a forum
    """
    
    title = "lists of posts for a thread"
    
    def stream(self, write, request):
        self.forum_id = int(request.args.get('forum_id',[0])[0])
        self.post_id = int(request.args.get('post_id',[0])[0])        
        print "Getting posts for thread %d for forum: %d" % (self.post_id, self.forum_id)
        write( self.service.manager.getThreadMessages(self.forum_id, self.post_id, self.onPostData, self.onPostError) )

    def onPostData(self, data):
        if len(data) == 0:
            return ["No Posts for this thread."]

        print "DATA:", data
        # put the messages into a dictionary of lists by parent
        self.byParent = {}
        for (post_id, parent_id, subject, posted, username) in data:
            forParent = self.byParent.get(parent_id, [])
            forParent.append( (post_id, subject, posted, username) )
            self.byParent[parent_id] = forParent

        tmp = self.byParent[0]
        subject = tmp[0][1]
        posted = tmp[0][2]
        
        l = []
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000"><b> Posts for Thread "%s" posted at %s </b> </td>' % (subject, posted) )
        l.append( '</tr></table>\n<BR>' )

        l.append( self.formatList(0) )
        return l

    def formatList(self, idIn):
        l = ["<UL>"]
        postList = self.byParent.get(idIn,[])
        for (post_id, subject, posted, username) in postList:
            l.append( self.formatPost(post_id, subject, posted, username) )
            l.append( self.formatList(post_id) )
        l.append( "</UL>" )
        return l
    
        
    def formatPost(self, post_id, subject, posted, username):
        return '<LI> [<a href="/details/?post_id=%d">%s</a>], <I>%s</I> <BR>\n' %\
                            (post_id, subject, username)
    
    def onPostError(self, error):
        print error
        return "ERROR: " + repr(error)

class DetailsGadget(ForumBaseGadget):
    title = "details for a post"
    
    def stream(self, write, request):
        self.request = request
        self.post_id = int(request.args.get('post_id',[0])[0])
        print "Getting details for post %d" % (self.post_id)
        write( self.service.manager.getMessage(self.post_id, self.onDetailData, self.onDetailError) )
        
    def onDetailData(self, data):
        (post_id, parent_id, forum_id, thread_id, subject, posted, user, body) = data[0]
        l = []
        l.append( ActionsWidget(post_id, parent_id, forum_id, thread_id).display(self.request) + ("<H2> %s </H2>\n" % subject) )
        l.append( '(#%d)Posted on <i>%s</i> by <i>%s</i> <HR>' % (post_id,posted, user) )
        #l.append( '<PRE>' + body  + '</PRE>')
        l.append(body)
        return l

    def onDetailError(self, error):
        print error
        return "ERROR:" + error

class ActionsWidget(widgets.StreamWidget):
    def __init__(self, post_id, parent_id, forum_id, thread_id):
        self.post_id = post_id
        self.parent_id = parent_id
        self.forum_id = forum_id
        self.thread_id = thread_id

    def stream(self, write, request):
        # setup the thread ID correctly for top level posts
        if self.thread_id == 0:
            self.thread_id = self.post_id

        l = []
        self.makeMenu(write, "/posts/?post_id=%d" % self.post_id, "Back to Threads", 1)
        self.makeMenu(write, "/details/?post_id=%d" % self.parent_id, "Prev Thread", self.parent_id != 0)
        self.makeMenu(write, "/details/?post_id=%d" % self.parent_id, "Next Thread", 0)
        self.makeMenu(write, "/details/?post_id=%d" % (self.post_id-1), "Prev Date", self.post_id > 1)
        self.makeMenu(write, "/details/?post_id=%d" % (self.post_id+1), "Next Date", self.post_id > 0) #NOTE: TODO
        self.makeMenu(write, "/reply/?post_id=%d&amp;forum_id=%d&amp;thread_id=%d" % (self.post_id, self.forum_id, self.thread_id), "Reply", 1)
        return l
    
    def makeMenu(self, write, link, text, flag):
        if flag:
            write( '[<a href="%s">%s</a>]\n' % (link, text) )
        else:
            write( "[ %s ]\n" % (text) )


class ReplyForm(webpassport.SessionPerspectiveMixin, widgets.Form, widgets.Gadget):
    
    title = "Reply to Posted message:"
    page = ForumPage
    
    def __init__(self, service):
        self.service = service
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.request = request
        self.post_id = int(request.args.get('post_id',[0])[0])
        self.forum_id = int(request.args.get('forum_id',[0])[0])
        self.thread_id = int(request.args.get('thread_id',[0])[0])                
        d = self.service.manager.getMessage(self.post_id, self.onDetailData, self.onDetailError)        
        return [d]
    
    def process(self, write, request, submit, subject, body, post_id, forum_id, thread_id):
        body = string.replace(body,"'","''")
        p = self.getPerspective(self.request)
        name = (p and p.perspectiveName) or 'anonymous'
        write(self.service.manager.postMessage(self.forum_id, name, self.thread_id, int(post_id), 0, subject, body))
        write("<a href='/threads/?forum_id=%s'>Return to Threads</a>" % self.forum_id)

    def insertDone(self, done):
        print 'INSERT SUCCESS'

    def insertError(self, error):
        print 'ERROR: Reply', error
        return "ERROR"
        
    def onDetailData(self, data):
        (post_id, parent_id, forum_id, thread_id, subject, posted, user, body) = data[0]        
        outString = "\nOn %s, %s wrote:\n" % ( posted, user)
        lines = string.split(body,'\n')
        for line in lines:
            outString = outString + "> %s" % line
            
        self.formFields = [
            ['string', 'Subject: ', 'subject', "RE: %s" % subject],
            ['text',   'Message:',  'body',    outString],
            ['hidden', '',          'post_id',  self.post_id],
            ['hidden', '',          'forum_id', self.forum_id],
            ['hidden', '',          'thread_id', self.thread_id]
            ]
        
        return widgets.Form.display(self, self.request)
    
    def onDetailError(self, error):
        print "ERROR: populating Reply", error
        return "ERROR"

class NewPostForm(webpassport.SessionPerspectiveMixin, widgets.Form, widgets.Gadget):
    
    title = "Post a new message:"
    page = ForumPage
    
    def __init__(self, service):
        self.service = service
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.request = request
        self.forum_id = int(request.args.get('forum_id',[0])[0])

        self.formFields = [
            ['string', 'Subject: ', 'subject', ''],
            ['text',   'Message:',  'body',    ''],
            ['hidden', '',          'forum_id', self.forum_id],
            ]
        
        return widgets.Form.display(self, self.request)
    
    def process(self, write, request, submit, subject, body, forum_id):
        body = string.replace(body,"'","''")
        p = self.getPerspective(request)
        name = (p and p.perspectiveName) or 'anonymous'
        self.service.manager.newMessage(self.forum_id, name, subject, body)             
        write("Posted new message '%s'.<hr>\n" % subject)
        write("<a href='/threads/?forum_id=%s'>Return to Threads</a>" % self.forum_id)


class RegisterUser(webpassport.SessionPerspectiveMixin, widgets.Form, widgets.Gadget):
    """This creates a new identity and perspective for the user.
    """
    
    title = "Register new user"
    page = ForumPage    

    def __init__(self, service):
        self.service = service
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.request = request

        self.formFields = [
            ['string',   'User Name:',         'name',  ''],
            ['password', 'Password:',          'password1', ''],
            ['password', 'Confirm Password:',  'password2', ''],
            ['string',   'Signature:',         'signature', ''],
            ['checkbox', 'Log In Immediately', 'login_now', 1]
            ]

        return widgets.Form.display(self, self.request)

    def process(self, write, request, submit, name, password1, password2, signature, login_now):
        if password1 != password2:
            write("ERROR: Passwords not valid!")
            return

        newIdentity = passport.Identity(name, self.service.application)
        newIdentity.setPassword(password1)
        newPerspective = self.service.createPerspective(name)
        newIdentity.addKeyForPerspective(newPerspective)
        self.name = name
        self.signature = signature
        # create the identity in the database
        self.login_now = login_now
        self.request = request
        self.identity = newIdentity
        print 'in process',request.getSession()
        return ["Creating identity...",self.service.application.authorizer.addIdentity(newIdentity).addCallbacks(self.doneIdentity, self.errIdentity)]

    def doneIdentity(self, result):
        print "Created Identity Successfully for %s" % self.name
        print "Creating forum user."
        
        # create the forum user in the database
        defr = self.service.manager.createUser(self.name, self.signature)
        defr.addCallbacks(self.donePerspective, self.errPerspective)
        if self.login_now:
            sess = self.request.getSession()
            print 'in doneIdentity',sess, self.identity
            sess.identity = self.identity
            sess.perspectives = {}
            print 'Logged in in doneIdentity'
        return ["Created identity...<br>Creating perspective...", defr]

    def donePerspective(self, result):
        return ["Created perspective.  <hr><a href='/threads/'>Return to Forums</a>"]

    def errPerspective(self, error):
        return ["Couldn't create perspective."]

    def errIdentity(self, error):
        print "ERROR: couldn't create identity."
        return ["Drat and blast!  No identity created: %s." % error]

class NewForumForm(webpassport.SessionPerspectiveMixin, widgets.Form, widgets.Gadget):
    
    title = "Create a new forum:"
    page = ForumPage
    
    def __init__(self, service):
        self.service = service
        widgets.Gadget.__init__(self)

    def display(self, request):
        self.request = request

        self.formFields = [
            ['string', 'Forum Name:',   'name', ''],
            ['text',   'Description:',  'description',    ''],
            ['checkbox',    'Allow Default Access:', 'default_access', 1],
            ]
        
        return widgets.Form.display(self, self.request)
    
    def process(self, write, request, submit, name, description, default_access):
        self.service.manager.createForum(name, description, default_access)
        write("Created new forum '%s'.<hr>\n" % name)
        write("<a href='/'>Return</a>")

    
class LoginForm(webpassport.LogInForm, widgets.Gadget):

    title = "Enter the forum"
    page = ForumPage
    
    def __init__(self, service):
        self.service = service
        widgets.Gadget.__init__(self)

    def getPerspective(self, request):
        """dummy method - this page does not require login.
        """
        return None
    
    def display(self, request):
        self.request = request
        
        self.formFields = [
            ['string','User Name','identityName',''],
            ['password','Password','password','']
            ]
        
        l = widgets.Form.display(self, self.request)
        l.insert(0, "<p align=center><a href=/register>[Create a new account]</a></p><hr>")
        return l
