
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

"""I am an implementation of a weblog that uses shelve.
"""

#t.w imports
import html

import shelve
import time

class WebLog(html.Interface):
    
    # This variable defines how the log is displayed
    logsrc = """
        <B>%(title)s</B> on %(date)s @ %(ltime)s<BR><BR>
        %(body)s<BR><BR>
    """
    # This is the filename for the log
    logfile = "weblog"
    
    # these are the username and password
    loguser = "web"
    logpass = "log"
    
    def __init__(self):
        html.Interface.__init__(self)
        
        self.title = "Weblog"
        
    def render(self, request):

        return self.webpage(request, self.title, self.box(request, self.title, self.main(request)))

    def getLogs(self, request, limit):
        # Open the shelved log file
        
        log = shelve.open(self.logfile, "r")
        
        x = 0
        content = ""
        
        # get the list of logs (shelve uses a dict interface) and perform some sorting of it
        
        logs = log.keys()
        logs.sort()
        logs.reverse()
       
        if len(logs) == 0:
            content = content + "No entries yet"
        else:
            for i in logs:
                i = str(i)
                if x < limit:
                    date = log[i]['DATE'] 
                    ltime = log[i]['TIME']
                    title = log[i]['TITLE']
                    body = log[i]['BODY']

                    content = content + self.logsrc % {'date': date, 'ltime': ltime, 'title': title, 'body': body} 
       
                x = x + 1
        
        content = content + '<P ALIGN="center"><SMALL><A HREF="'+request.path+'?action=login">Post</A></SMALL></P>'
       
        log.close()
        del log
       
        return content

    def writeLog(self, title, body):
        log = shelve.open(self.logfile, "w")
        
        utime = time.time()
        
        date = time.strftime("%m-%d-%Y", time.localtime(utime))
        ltime = time.strftime("%I:%M:%S", time.localtime(utime))
    
        
        log[str(int(utime))] = {"DATE": date, "TIME": ltime, "TITLE": title, "BODY": body}
   
        log.close()
        del log
   
    def checkPass(self, user, passwd):
        if self.loguser == user and self.logpass == passwd:
            return 1 

    def logLogin(self, request):
        return self.form(request,
            [["hidden", "", "action", "post"],
             ["string", "Username", "username", ""],
             ["password", "Password", "password", ""]],
             
             submit="Login",
             action=request.path)

    def logForm(self, request, username, password):
        return self.form(request,
            [["hidden", "", "action", "add"],
             ["hidden", "", "username", username],
             ["hidden", "", "password", password],
             ["string", "Title", "title", ""],
             ["text", "Body", "body", ""]],

             submit="Post",
             action=request.path)
    
    def handleArgs(self, request):
        content = "" 
        if request.args.has_key("action"):
            if request.args['action'][0] == "post":
                if self.checkPass(request.args['username'][0], request.args['password'][0]):
                    content = content + self.logForm(request, request.args['username'][0], request.args['password'][0])
                    
                else:
                    content = content + "Login Failed"
            elif request.args['action'][0] == "login":
            
                content = content + self.logLogin(request)
        
            elif request.args['action'][0] == "add":
                if self.checkPass(request.args['username'][0], request.args['password'][0]):

                    self.writeLog(request.args['title'][0], request.args['body'][0])
                    content = content + self.getLogs(request, 10)
                    

                else:
                    content = content + "Login Failed"
        else:    
            content = content + self.getLogs(request, 10) 
    
        return content

    def main(self, request):
        content = ""
        content = content + self.handleArgs(request)

        return content
