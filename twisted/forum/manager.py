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
# Metrics System database interface
#
# WARNING: experimental database code!

from twisted.python import defer
from twisted.enterprise import adbapi


class ForumDB(adbapi.Augmentation):
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

    schema = """
    CREATE TABLE forums
    (
      forum_id       serial        PRIMARY KEY,
      name           varchar(64)   NOT NULL,
      description    varchar(256)  NOT NULL,
      moderator      varchar(64)
    );

    CREATE TABLE posts
    (
      post_id        serial        PRIMARY KEY,
      forum_id       int           NOT NULL,
      parent_id      int           NOT NULL,
      thread_id      int           NOT NULL,
      subject        varchar(64)   NOT NULL,
      poster_name    varchar(64)   NOT NULL,
      posted         timestamp     NOT NULL,
      body           varchar(1024) NOT NULL
    );

    CREATE TABLE forum_perspectives
    (
      identity_name     varchar(64)  PRIMARY KEY,
      user_name         varchar(64)  NOT NULL,
      signature         varchar(64)  NOT NULL
    );
    """

    def createForum(self, name, description):
        """Create a new forum with this name.
        """
        sql = """INSERT INTO forums
               (name, description)
               VALUES
               ('%s', '%s')""" % (name, description)
        self.runOperation(sql)

    def deleteForum(self, forum_id):
        """Delete the forum with this name and all posted messages in it.
        """
        # NOTE: This should be in a transaction!!!
        sql = """DELETE FROM forums WHERE forum_id = %d;
                 DELETE FROM posts WHERE forum_id = %d""" % (forum_id, forum_id)
        self.runOperation(sql)
        
    def postMessage(self, forum_id, user_name, thread_id, parent_id, subject, body):
        """Post a message to a forum. Could be in reply to a message or a new thread.
        """
        sql = """INSERT INTO posts
                 (forum_id, parent_id, thread_id, subject, user_name, posted, body)
                 VALUES
                 (%d, %d, %d, '%s', %s, now(), '%s')""" % (forum_id, parent_id, thread_id, subject, user_name, body)
        self.runOperation(sql)

    def newMessage(self, forum_id, user_name, subject, body):
        """Post a new message - start a new thread."""
        sql = """INSERT INTO posts
                 (forum_id, parent_id, thread_id, subject, poster_id, posted, body)
                 VALUES
                 (%d, 0, 0, '%s', %s, now(), '%s')""" % (forum_id, subject, user_name, body)
        self.runOperation(sql)        
        
    def getForums(self, callbackIn, errbackIn):
        """Gets the list of forums and the number of msgs in each one.
        """
        sql = """SELECT forum_id, name, description,
                    (SELECT count(*) FROM posts WHERE posts.forum_id = forums.forum_id)
                 FROM forums"""
        return self.runQuery(sql, callbackIn, errbackIn)        
    
    def getTopMessages(self, forum_id, callbackIn, errbackIn):
        """Get the top-level messages in the forum - those that begin threads. This returns
        a set of the columns (id, subject, post date, username, # replies) for the forum
        """
        sql = """SELECT p.post_id, p.subject, p.posted, p.user_name,
                   (SELECT count(*) FROM posts p_inner WHERE p_inner.thread_id = p.post_id)
               FROM posts p
               WHERE p.forum_id  = %d
               AND   p.thread_id = 0""" % (forum_id)
        
        return self.runQuery(sql, callbackIn, errbackIn)        
                   
    def getThreadMessages(self, forum_id, thread_id, callbackIn, errbackIn):
        """Get the messages in a thread in a forum. This returns a set of columns
        (id, parent_id, subject, post_date, username)
        """
        sql = """SELECT p.post_id, p.parent_id, p.subject, p.posted, p.user_name
               FROM posts p
               WHERE  p.forum_id  = %d
               AND   (p.thread_id = %d OR p.post_id = %d)""" % (forum_id, thread_id, thread_id)

        return self.runQuery(sql, callbackIn, errbackIn)        

    def getFullMessages(self, forum_id, thread_id, callbackIn, errbackIn):
        """Get the messages in a thread in a forum. This returns a set of columns
        (id, parent_id, subject, post_date, username, body)
        """
        sql = """SELECT p.post_id, p.parent_id, p.subject, p.posted, p.user_name, p.body
               FROM posts p
               WHERE p.forum_id  = %d\
               AND   (p.thread_id = %d OR p.post_id = %d)""" % (forum_id, thread_id, thread_id)

        return self.runQuery(sql, callbackIn, errbackIn)        
        
    def getMessage(self, post_id, callbackIn, errbackIn):
        """Get the details of a single message.
        """
        sql = """SELECT post_id, parent_id, forum_id, thread_id, subject, posted, user_name, body
               FROM posts
               WHERE posts.post_id = %d""" % (post_id)

        return self.runQuery(sql, callbackIn, errbackIn)
        
