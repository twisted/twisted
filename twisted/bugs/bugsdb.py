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
    """
    
    def createBug(self, name, email, version, os, security, bug_type, summary, description):
        """Add a new bug to the database."""
        sql = """INSERT INTO bugs_items
                (submittor_name, submittor_email, assigned, date_submitted, date_modified,
                 version, os, security, type, status, summary, description) VALUES
                (%s, %s, NULL, now(), now(), %s, %s, %s, %s, 'open', %s, %s)
              """
        if security:
            security = 't'
        else:
            security = 'f'
        return self.runOperation(sql, name, email, version, os, security, bug_type, summary, description)
    
    def createComment(self, bug_id, name, email, comment):
        sql = """INSERT into bugs_comments (bug_id, submittor_name, submittor_email, comment, date)
                 VALUES (%s, %s, %s, %s, now())"""
        return self.runOperation(sql, bug_id, name, email, comment)
    
    def getAllBugs(self):
        """Returns (bug_id, summary, type, status, assigned, date_modified) for all bugs."""
        sql = """SELECT bug_id, summary, type, status, assigned, date_modified FROM bugs_items"""
        return self.runQuery(sql)
    
    def getBug(self, bug_id):
        """Returns all columns for a bug."""
        sql = """SELECT ALL * FROM bugs_items WHERE bug_id = %d""" % bug_id
        return self.runQuery(sql)
    
    def getBugComments(self, bug_id):
        sql = """SELECT post_id, submittor_name, submittor_email, date, comment FROM bugs_comments
                 WHERE bug_id = %d ORDER BY post_id""" % bug_id
        return self.runQuery(sql)
    
    def updateBugStatus(self, bug_id, assigned, status):
        sql = """UPDATE bugs_items SET assigned = %s, status = %s, date_modified = now()
                 WHERE bug_id = %s"""
        return self.runOperation(sql, assigned, status, bug_id)
