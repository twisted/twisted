from twisted.python import defer

class ForumManager:
    """This class handles interactions with the forums database. It holds all the SQL
    code used.

    Database operations include:
       - create a forum
       - delete a forum
       - get the list of forums
       - post a new message (start a thread)
       - post a reply to a message
       - get all the threads in a forum
       - get all the posts in a thread
       - get details of a message
       

    This class operates asynchronously (like everything in twisted). The query methods
    (getTopMessages and getThreadMessages) take callback and errback methods which will
    be called when the query has finished.
       
    """

    def __init__(self, dbpool):
        self.dbpool = dbpool
        self.dbpool.connect()

    def operationDone(self, done):
        print "Operation done."

    def operationError(self, error):
        print "Operation error:", error

    def createForum(self, name):
        """Create a new forum with this name.
        """
        sql = "INSERT INTO forums\
               (name)\
               VALUES\
               ('%s')" % name
        self.dbpool.operation(sql, self.operationDone, self.operationError)

    def deleteForum(self, forum_id):
        """Delete the forum with this name and all posted messages in it.
        """
        # NOTE: This should be in a transaction!!!
        sql1 = "DELETE FROM forums WHERE forum_id = %d" % forum_id
        sql2 = "DELETE FROM posts WHERE forum_id = %d" % forum_id
        self.dbpool.operation(sql1, self.operationDone, self.operationError)
        self.dbpool.operation(sql2, self.operationDone, self.operationError)        

    def postMessage(self, forum_id, user_id, thread_id, parent_id, subject, body):
        """Post a message to a forum. Could be in reply to a message or a new thread.
        """
        sql = "INSERT INTO posts\
               (forum_id, parent_id, thread_id, subject, poster_id, posted, body)\
               VALUES\
               (%d, %d, %d, '%s', %d, now(), '%s')" % (forum_id, parent_id, thread_id, subject, user_id, body)
        self.dbpool.operation(sql, self.operationDone, self.operationError)        

    def newMessage(self, forum_id, user_id, subject, body):
        """Post a new message - start a new thread."""
        sql = "INSERT INTO posts\
               (forum_id, parent_id, thread_id, subject, poster_id, posted, body)\
               VALUES\
               (%d, 0, 0, '%s', %d, now(), '%s')" % (forum_id, subject, user_id, body)
        self.dbpool.operation(sql, self.operationDone, self.operationError)
        
    def getForums(self, callbackIn, errbackIn):
        """Gets the list of forums and the number of msgs in each one.
        """
        sql = "SELECT forum_id, name, (SELECT count(*) FROM posts WHERE posts.forum_id = forums.forum_id) FROM forums"
        # use a defered 
        d = defer.Deferred()
        d.addCallbacks(callbackIn, errbackIn)
        self.dbpool.query(sql, d.callback, d.errback)
        return d
    
    def getTopMessages(self, forum_id, callbackIn, errbackIn):
        """Get the top-level messages in the forum - those that begin threads. This returns
        a set of the columns (id, subject, post date, username, # replies) for the forum
        """
        sql = "SELECT p.post_id, p.subject, p.posted, users.name,\
                   (SELECT count(*) FROM posts p_inner WHERE p_inner.thread_id = p.post_id)\
               FROM posts p, users\
               WHERE p.poster_id = users.user_id\
               AND   p.forum_id  = %d\
               AND   p.thread_id = 0" % (forum_id)

        # use a defered 
        d = defer.Deferred()
        d.addCallbacks(callbackIn, errbackIn)
        self.dbpool.query(sql, d.callback, d.errback)
        return d
                   
    def getThreadMessages(self, forum_id, thread_id, callbackIn, errbackIn):
        """Get the messages in a thread in a forum. This returns a set of columns
        (id, parent_id, subject, post_date, username)
        """
        sql = "SELECT p.post_id, p.parent_id, p.subject, p.posted, users.name\
               FROM posts p, users\
               WHERE p.poster_id = users.user_id\
               AND   p.forum_id  = %d\
               AND   (p.thread_id = %d OR p.post_id = %d)" % (forum_id, thread_id, thread_id)

        # use a defered
        d = defer.Deferred()
        d.addCallbacks(callbackIn, errbackIn)
        self.dbpool.query(sql, d.callback, d.errback)
        return d

    def getFullMessages(self, forum_id, thread_id, callbackIn, errbackIn):
        """Get the messages in a thread in a forum. This returns a set of columns
        (id, parent_id, subject, post_date, username, body)
        """
        sql = "SELECT p.post_id, p.parent_id, p.subject, p.posted, users.name, p.body\
               FROM posts p, users\
               WHERE p.poster_id = users.user_id\
               AND   p.forum_id  = %d\
               AND   (p.thread_id = %d OR p.post_id = %d)" % (forum_id, thread_id, thread_id)

        # use a defered
        d = defer.Deferred()
        d.addCallbacks(callbackIn, errbackIn)
        self.dbpool.query(sql, d.callback, d.errback)
        return d

        
    def getMessage(self, post_id, callbackIn, errbackIn):
        """Get the details of a single message.
        """

        sql = "SELECT post_id, parent_id, forum_id, thread_id, subject, posted, users.name, body\
               FROM posts, users\
               WHERE posts.poster_id = users.user_id\
               AND posts.post_id = %d" % (post_id)
        
        # use a defered
        d = defer.Deferred()
        d.addCallbacks(callbackIn, errbackIn)
        self.dbpool.query(sql, d.callback, d.errback)
        return d
        
