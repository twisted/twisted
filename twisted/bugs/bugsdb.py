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

"""The bugs database."""

from twisted.enterprise import adbapi


class BugsDatabase(adbapi.Augmentation):
    """A bugs database."""
    
    statuses = ("open", "closed", "rejected")
    types = ("wishlist", "minor", "normal", "critical")
    
    schema = """
    DROP TABLE bugs_items;
    DROP TABLE bugs_admins;
    DROP TABLE bugs_comments;
    DROP TABLE bugs_status;
    DROP TABLE bugs_types;
    
    CREATE TABLE bugs_status (
        name  varchar(16)     UNIQUE
    );
    INSERT INTO bugs_status VALUES ('open');
    INSERT INTO bugs_status VALUES ('closed');
    INSERT INTO bugs_status VALUES ('rejected');
    
    CREATE TABLE bugs_types (
        name  varchar(16)     UNIQUE
    );
    
    INSERT INTO bugs_types VALUES ('wishlist');
    INSERT INTO bugs_types VALUES ('minor');
    INSERT INTO bugs_types VALUES ('normal');
    INSERT INTO bugs_types VALUES ('critical');
    
    CREATE TABLE bugs_admins (
        identity_name     varchar(64)  PRIMARY KEY,
        user_name         varchar(64)  UNIQUE,
        email             varchar(128)
    );
    
    CREATE TABLE bugs_items (
        bug_id          serial          PRIMARY KEY,
        submittor_name  varchar(64),
        submittor_email varchar(128),
        assigned        varchar(64)     CONSTRAINT assigned_users
                                        REFERENCES bugs_admins (user_name),
        date_submitted  timestamp,
        date_modified   timestamp,
        version         varchar(16),
        os              varchar(32),
        security        boolean,
        type            varchar(16)     CONSTRAINT bug_item_type
                                        REFERENCES bugs_types (name),
        status          varchar(16)     CONSTRAINT bug_item_status
                                        REFERENCES bugs_status (name),
        summary         varchar(100),
        description     text
    );
    
    CREATE TABLE bugs_comments (
        post_id      serial  PRIMARY KEY,
        bug_id       int     CONSTRAINT comment_bug_ids
                             REFERENCES bugs_items (bug_id),
        submittor_name  varchar(64),
        submittor_email varchar(128),
        comment      text
    );
    
    """
    
    def createBug(self, name, email, version, os, security, bug_type, status, summary, description):
        """Add a new bug to the database."""
        sql = """INSERT INTO bugs_items
                (submittor_name, submittor_email, assigned, date_submitted, date_modified,
                 version, os, security, type, status, summary, description) VALUES
                (%s, %s, NULL, now(), now(), %s, %s, %s, %s, %s, %s, %s)
              """
        if security:
            security = 't'
        else:
            security = 'f'
        return self.runOperation(sql, name, email, version, os, security, bug_type, status, summary, description)
    
    def createComment(self, bug_id, name, email, comment):
        sql = """INSERT into bugs_comments (bug_id, submittor_name, submittor_email, comment)
                 VALUES (%s, %s, %s, %s)"""
        return self.runOperation(sql, bug_id, name, email, comment)
    
    def getAllBugs(self, callbackIn, errbackIn):
        """Returns a set of columns for all bugs."""
        sql = """SELECT ALL * FROM bugs_items"""
        return self.runQuery(sql, callbackIn, errbackIn)
    
    def getBugComments(self, bug_id, callbackIn, errbackIn):
        sql = """SELECT post_id, submittor_name, submittor_email, comment FROM bugs_comments
                 WHERE bug_id = %d ORDER BY post_id""" % bug_id
        return self.runQuery(sql, callbackIn, errbackIn)
    
    def updateBugStatus(self, bug_id, assigned, status):
        sql = """UPDATE bugs_items SET assigned = %s, status = %s, date_modified = now()
                 WHERE bug_id = %s"""
        return self.runOperation(sql, (assigned, status, bug_id))
