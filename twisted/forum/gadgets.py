## WARNING - this is experimental code.
## DO NOT USE THIS!!!

import string

from twisted.web import widgets
from twisted.python import defer

from sim.server import engine, player

"""The forum application has these functional pages:
     intro   - (/)        - List of forums
     threads - (/threads) - List of threads in a forum
     posts   - (/posts)   - List of messages in a thread
     full    - (/full)    - List of messages with details for a thread
     details - (/details) - Details of a message
     reply   - (/reply)   - Reply form to reply to a message
     new     - (/new)     - Post a new message/thread

  The ForumGadget contains widgets to perform each of these functions.
  
"""
class ForumGadget(widgets.Gadget, widgets.StreamWidget):
    title = "Posting Board"
    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service
        self.putWidget('threads', ThreadsGadget(self.app, self.service))
        self.putWidget('posts',   PostsGadget(self.app, self.service))
        self.putWidget('full',    FullGadget(self.app, self.service))                
        self.putWidget('details', DetailsGadget(self.app, self.service))
        self.putWidget('reply',   ReplyForm(self.app, self.service))
        self.putWidget('new',     NewPostForm(self.app, self.service))

    def display(self, request):
        """Display the intro list of forums. This is only called if there is no URI.
        """
        d = self.service.manager.getForums('poster', self.gotForums, self.gotError)
        return [d]

    def gotForums(self, data):
        l = []
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000"><b> Forum Name </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Posts </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Description </b> </td>' )        
        l.append( '</tr>\n' )

        for (id, name, desc, posts) in data:
            l.append( "<tr> <td> <a href='/threads/?forum_id=%d'>%s</a></td><td> %d </td> <td> %s</d></tr>\n" % (id,name, posts, desc) )
        l.append("</table>")
        l.append( '<hr> <i> Twisted Forums </i>' )        
        return l
            

    def gotError(self, error):
        print error
        return "ERROR:" + repr(error)


class ThreadsGadget(widgets.Gadget, widgets.StreamWidget):
    """Displays a list of threads for a forum
    """
    
    title = " "

    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service

    def display(self, request):
        self.forum_id = int(request.args.get('forum_id',[0])[0])
        print "Getting threads for forum: %d" % self.forum_id
        d = self.service.manager.getTopMessages(self.forum_id, 'poster', self.onThreadData, self.onThreadError)
        return [d]

    def onThreadData(self, data):
        l = []
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000"><b> Thread Subject </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Thread Starter </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Replies </b> </td>' )
        l.append( '</tr>\n' )
        
        for (id, subject, postdate, username, replies) in data:
            l.append("<tr> <td> <a href='/full/?forum_id=%d&amp;post_id=%d'> %s </a> </td>" % (self.forum_id, int(id), subject))
            l.append("<td> <i> %s </i> </td>" % username)
            l.append("<td> %d replies </td>" % replies)
            l.append("</tr>\n")

        l.append( '</table><br>' )
        l.append( '[<a href="/new/?forum_id=%d">Start a new thread</a>]' % (self.forum_id) )
        l.append( '[<a href="/">Return to Forums</a>]' )                
        l.append( '<hr> <i> Twisted Forums </i>' )        
        return l

    def onThreadError(self, error):
        print error
        return "ERROR: " + repr(error)


class FullGadget(widgets.Gadget, widgets.StreamWidget):
    """Displays a full details of all posts for a thread in a forum
    """
    
    title = " "

    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service

    def display(self, request):
        self.request = request
        self.forum_id = int(request.args.get('forum_id',[0])[0])
        self.post_id = int(request.args.get('post_id',[0])[0])        
        print "Getting posts for thread %d for forum: %d" % (self.post_id, self.forum_id)
        d = self.service.manager.getFullMessages(self.forum_id, self.post_id, 'poster', self.onPostData, self.onPostError)
        return [d]

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
                l.append( '<td COLOR="#000000"><b> Author </b> </td>' )
                l.append( '<td COLOR="#000000"><b> Topic: %s </b> </td>'%subject )        
                l.append( '</tr>\n' )

            body = string.replace(body, "\n", "<p>")
            l.append( '<tr> <td valign=top > <b> %s </b> <br> </td>' % (username) )
            l.append( '<td> <i> %s </i> (%s) <hr> %s <br></td> </tr>\n' % ( subject, posted, body) )

        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000" width=30%> </td>' )
        l.append( '<td COLOR="#000000"> </td>' )        
        l.append( '</tr>\n' )

        l.append( '</table>' )

        l.append( '[<a href="/threads/?forum_id=%d">Back to forum</a> ]' % self.forum_id)
        l.append( '[<a href="/reply/?post_id=%d&amp;forum_id=%d&amp;thread_id=%d">Reply</a>]' % (post_id, self.forum_id, first) )
        l.append( '<hr> <i> Twisted Forums </i>' )        
        return l

    
    def onPostError(self, error):
        print error
        return "ERROR: " + repr(error)


class PostsGadget(widgets.Gadget, widgets.StreamWidget):
    """Displays a list of posts for a thread in a forum
    """
    
    title = " "

    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service

    def display(self, request):
        self.forum_id = int(request.args.get('forum_id',[0])[0])
        self.post_id = int(request.args.get('post_id',[0])[0])        
        print "Getting posts for thread %d for forum: %d" % (self.post_id, self.forum_id)
        d = self.service.manager.getThreadMessages(self.forum_id, self.post_id, self.onPostData, self.onPostError)
        return [d]

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
        l.append( '<hr> <i> Twisted Forums </i>' )        
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

class DetailsGadget(widgets.Gadget, widgets.StreamWidget):
    title = " "
    
    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service

    def display(self, request):
        self.request = request
        self.post_id = int(request.args.get('post_id',[0])[0])
        print "Getting details for post %d" % (self.post_id)
        d = self.service.manager.getMessage(self.post_id, self.onDetailData, self.onDetailError)
        return [d]

    def onDetailData(self, data):
        (post_id, parent_id, forum_id, thread_id, subject, posted, user, body) = data[0]
        l = []
        l.append( ActionsWidget(post_id, parent_id, forum_id, thread_id).display(self.request) + ("<H2> %s </H2>\n" % subject) )
        l.append( '(#%d)Posted on <i>%s</i> by <i>%s</i> <HR>' % (post_id,posted, user) )
        l.append( '<PRE>' + body  + '</PRE>')
        l.append( '<hr> <i> Twisted Forums </i>' )    
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

    def display(self, request):
        # setup the thread ID correctly for top level posts
        if self.thread_id == 0:
            self.thread_id = self.post_id
            
        outString = '<TABLE border=1 width=95%> <TR>'
        outString = outString + self.makeMenu("/posts/?post_id=%d" % self.post_id, "Back to Threads", 1)
        outString = outString + self.makeMenu("/details/?post_id=%d" % self.parent_id, "Prev Thread", self.parent_id != 0)
        outString = outString + self.makeMenu("/details/?post_id=%d" % self.parent_id, "Next Thread", 0)
        outString = outString + self.makeMenu("/details/?post_id=%d" % (self.post_id-1), "Prev Date", self.post_id > 1)
        outString = outString + self.makeMenu("/details/?post_id=%d" % (self.post_id+1), "Next Date", self.post_id > 0) #NOTE: TODO
        outString = outString + self.makeMenu("/reply/?post_id=%d&amp;forum_id=%d&amp;thread_id=%d" % (self.post_id, self.forum_id, self.thread_id), "Reply", 1)
        return outString
        
    def makeMenu(self, link, text, flag):
        if flag:
            return '[<a href="%s">%s</a>]\n' % (link, text)
        else:
            return "[ %s ]\n" % (text)            


class ReplyForm(widgets.Gadget, widgets.Form):
    title = "Reply to Posted message:"

    def __init__(self, app, service):
        self.app = app
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
        self.service.manager.postMessage(self.forum_id, 'poster', self.thread_id, int(post_id), subject, body)
        write("Posted reply to '%s'.<hr>\n" % subject)
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




class NewPostForm(widgets.Gadget, widgets.Form):
    title = "Post a new message:"

    def __init__(self, app, service):
        self.app = app
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
        self.service.manager.newMessage(self.forum_id, 'poster', subject, body)             
        write("Posted new message '%s'.<hr>\n" % subject)
        write("<a href='/threads/?forum_id=%s'>Return to Threads</a>" % self.forum_id)

    def insertDone(self, done):
        print 'INSERT SUCCESS'

    def insertError(self, error):
        print 'ERROR: Reply', error
        return "ERROR"
        
