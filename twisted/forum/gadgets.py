## WARNING - this is experimental code.
## DO NOT USE THIS!!!

import string

from twisted.web import widgets
from twisted.python import defer

from sim.server import engine, player


class ForumGadget(widgets.Gadget, widgets.Presentation):
    title = "Posting Board"
    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        widgets.Presentation.__init__(self)
        self.app = app
        self.service = service
        self.putWidget('detail', DetailsGadget(self.app, self.service))
        self.putWidget('expand', SubjectsGadget(self.app, self.service))
        self.putWidget('reply', ReplyForm(self.app, self.service))                        
    template = '''
    <ul>
    <li><a href="expand">Top-level Subjects.</a>
    </ul>
    '''


class SubjectsGadget(widgets.Gadget, widgets.StreamWidget):
    """Displays a list of posts in the posts database.  """
    
    title = " "

    # get all the posts
    sql0 = "SELECT a.post_id,  \
                   a.parent_id,\
                   a.subject,  \
                   a.posted,   \
                   users.name \
           FROM posts a, users \
           WHERE a.poster_id = users.user_id\
           ORDER BY a.post_id ASC"
    
    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service

    def display(self, request):
        out1 = "<H2>All Posts:</H2>\n<HR>\n"
        d = defer.Deferred()
        d.addCallbacks(self.gotData, self.gotError)
        self.service.pool.query(self.sql0, d.callback, d.errback)
        return [out1, d]
        
    def gotData(self, data):
        self.threads = {}

        # group posts by thread
        for (post_id, parent_id, subject, posted, username) in data:
            thread = self.threads.get(parent_id, [])
            thread.append( (post_id, subject, posted, username) )
            self.threads[parent_id] = thread

        # output all the threads
        outString = "<UL>"
        topNodes = self.threads[0]
        for i in xrange(0, len(topNodes)-1):
            (post_id, subject, posted, username) = topNodes[-i]
            outString = outString + self.formatThread(post_id, subject, posted, username)
        outString = outString + "</UL> <HR>\n <i> Twisted Forums </i>"                            
                
        return outString

    def formatThread(self, post_id, subject, posted, username):
        outString = self.formatPost(post_id, subject, posted, username)
        thread = self.threads.get(post_id, [])        
        if len(thread) > 0:
            outString = outString + "<UL>"
            for (post_id, subject, posted, username) in thread:
                outString = outString + self.formatThread(post_id, subject, posted, username)
            outString = outString + "</UL>"
        return outString
        
    def formatPost(self, post_id, subject, posted, username):
        return '<LI> [<a href="/detail/?id=%d">%s</a>], <I>%s</I> <BR>\n' %\
                            (post_id, subject, username)

    def gotError(self, err):
        print "ERROR: Subjects ", err
        return "ERROR"
        
class DetailsGadget(widgets.Gadget, widgets.StreamWidget):
    title = " "
    
    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service

    def display(self, request):
        self.id = request.args.get('id',[0])[0]
        print "ID = ", self.id
        self.request = request
        d = defer.Deferred()
        d.addCallbacks(self.gotData, self.gotError)
        self.service.pool.query("SELECT post_id, parent_id, subject, posted, body, users.name \
                                 FROM posts,users\
                                 WHERE posts.poster_id = users.user_id\
                                 AND post_id = %d" % int(self.id), d.callback, d.errback)
        return [d]
        
    def gotData(self, data):
        (post_id, parent_id, subject, posted, body, user) = data[0]
        outString = ActionsWidget(post_id, parent_id).display(self.request) + ("<H2> %s </H2>\n" % subject)
        outString = outString + "(#%d)Posted on <i>%s</i> by <i>%s</i> <HR>" % (post_id,posted, user)
        outString = outString + "<PRE>" + body  + "</PRE><HR>\n <i> Twisted Forums </i>"
        return outString

    def gotError(self, error):
        print "ERROR: Details", error
        return "ERROR"

class ActionsWidget(widgets.StreamWidget):

    def __init__(self, id, parent_id):
        self.id = id
        self.parent_id = parent_id

    def display(self, request):
        outString = ''#'<TABLE border=1 width=95%> <TR>'
        outString = outString + self.makeMenu("/expand/", "Back to Threads", 1)
        outString = outString + self.makeMenu("/detail/?id=%d" % self.parent_id, "Prev Thread", self.parent_id != 0)
        outString = outString + self.makeMenu("/detail/?id=%d" % self.parent_id, "Next Thread", 0)
        outString = outString + self.makeMenu("/detail/?id=%d" % (self.id-1), "Prev Date", self.id > 1)
        outString = outString + self.makeMenu("/detail/?id=%d" % (self.id+1), "Next Date", self.id > 0) #NOTE: TODO
        outString = outString + self.makeMenu("/reply/?id=%d" % (self.id), "Reply", 1)
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
        self.id = request.args.get('id',[0])[0]
        print "ID = ", self.id
        self.request = request
        d = defer.Deferred()
        d.addCallbacks(self.gotData, self.gotError)
        self.service.pool.query("SELECT post_id, subject, posted, body, users.name \
                                 FROM posts,users\
                                 WHERE posts.poster_id = users.user_id\
                                 AND post_id = %d" % int(self.id), d.callback, d.errback)
        return [d]
    
    def process(self, write, request, submit, subject, body, id):
        self.service.pool.operation("INSERT INTO posts\
                                    (parent_id, subject, poster_id, posted, body) \
                                    VALUES \
                                    (%d, '%s', 1, now(), '%s')" % (int(id), subject, body),
                                self.insertDone,
                                self.insertError
                                )
                                
        write("Posed reply to '%s'.<hr>\n" % subject)
        write("<a href='/expand/'>Return to Threads</a>")

    def insertDone(self, done):
        print 'INSERT SUCCESS'

    def insertError(self, error):
        print 'ERROR: Reply', error
        return "ERROR"
        
    def gotData(self, data):
        (post_id, subject, posted, body, user) = data[0]
        outString = "\nOn %s, %s wrote:\n" % ( posted, user)
        lines = string.split(body,'\n')
        for line in lines:
            outString = outString + "> %s" % line
            
        self.formFields = [
            ['string', 'Subject: ', 'subject', "Re: %s" % subject],
            ['text',   'Message:',  'body',    outString],
            ['hidden', '',          'id',      self.id]
            ]
        
        return widgets.Form.display(self, self.request)
    
    def gotError(self, error):
        print "ERROR: populating Reply", error
        return "ERROR"
