
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

"""I am an interactive calendar for twisted.web.
Use /<password> to access the protected features of calendar, posting and deleting events.
"""

import calendar
import time
import string
import cPickle
from twisted.web import widgets,error

class CalendarWidget(widgets.StreamWidget):
    def __init__(self,year,month,getday):
        self.month=month
        self.year=year
        self.getday=getday
    def stream(self,write,request):
        write('''<table border=0 cellpadding=2>
<tr>''')
        for day in calendar.day_name:
            write("<td><center><b>&nbsp;%s&nbsp;</b></center></td>"%day)
        write('''</tr>
''')
        cal=calendar.monthcalendar(self.year,self.month)
        for week in cal:
            write('''<tr>
''')
            for day in week:
                write("<td><center>")
                if day:
                    write(str(day))
                inf=self.getday(request,day,self.month,self.year)
                if inf:
                    write("<BR>"+inf)
                write("</center></td>")
            write('''</tr>
''')
        write("</table>")

class PostForm(widgets.Form):
    formGen=widgets.Form.formGen
    formGen['intmenu']=widgets.htmlFor_menu
    
    formFields = [
        ["intmenu","Day","day",map(str,range(1,32))],
        ["menu","Month","month",calendar.month_name[1:]],
        ["int","Year","year",str(time.localtime(time.time())[0])],
        ["string","Title","title",""],
        ["text","Data","data",""]
    ]

    formParse = {
        'int':int,
        'intmenu':int
    }

    def __init__(self,page):
        self.page=page

    def process(self,write,request,day,month,year,title,data):
#        day=kw['day']
#        month=kw['month']
#        year=kw['year']
#        title=kw['title']
#        data=kw['data']
        month=calendar.month_name.index(month)
        self.page.setDay(day,month,year,title,data)
        return [self.page.backToCalendar(request)]
        
class CalendarPage(widgets.Page):
    isLeaf = 1
    
    template = '''<HTML>
<HEAD>
<TITLE>%%%%title(request)%%%%</TITLE>
</HEAD>
<BODY>
%%%%displayPage(request)%%%%
%%%%displayAuth(request)%%%%
</BODY>
</HTML>'''

    def __init__(self,password=None,filename=None):
        widgets.Page.__init__(self)
        self.password=password
        self.events={}
        self.filename=filename
        self.loadPickle()

    def setDate(self,request):
        curtime=time.localtime(time.time())
        if request.args.has_key("m"):
            self.month=int(request.args['m'][0])
        else:
            self.month=curtime[1]
        if request.args.has_key("y"):
            self.year=int(request.args['y'][0])
        else:
            self.year=curtime[0]
        request.auth=0
        if request.postpath:
            if self.password:
                if request.postpath[0]==self.password:
                    request.auth=1
                    del request.postpath[0]
            else:
                request.auth=1
        if request.postpath:
            try:
                if int(request.postpath[0])<=12 and int(request.postpath[0])>=1:
                    self.month=int(request.postpath[0])
                    del request.postpath[0]
                    if request.postpath:
                        self.year=int(request.postpath[0])
                        if self.year==0:
                            self.year=2000
                        elif self.year<100:
                            self.year=1900+self.year
                        del request.postpath[0]
#                elif
            except ValueError: pass

    def title(self,request):
        self.setDate(request)
        return calendar.month_name[self.month]+" "+str(self.year)

    def displayPage(self,request):
        #self.setDate(request)
        if not request.postpath:
            return self.displayCalendar(request)
        else:
            if request.postpath[0]=="event":
                year,month,day,ind=map(int,request.postpath[1:])
                return self.events[year][month][day][ind]
            elif request.auth and self.displayAuth(request):
                return ""
            else:
                return error.NoResource(string.join(request.postpath,"/")).render(request)

    def displayCalendar(self,request):
        return CalendarWidget(self.year,self.month,self.getDay)

    def backToCalendar(self,request):
        url="/"+string.join(request.prepath,"/")
        if request.auth:
            return """<a href="%s">Back To the Calendar</a>"""%(url+"/"+self.password)
        else:
            return """<a href="%s">Back To the Calendar</a>"""%url

    def displayAuth(self,request):
        if request.auth:
            if request.postpath and request.postpath[0]=="post":
                return PostForm(self)
            elif request.postpath and request.postpath[0]=="event":
                return """<a href="%s/%s/%s/%s/%s">Delete</a>""" % (
                    request.sibLink("%s/delete"%self.password), request.postpath[1], request.postpath[2],
                    request.postpath[3], request.postpath[4])+"<br>"+self.backToCalendar(request)
            elif request.postpath and request.postpath[0]=="delete":
                year,month,day,ind=map(int,request.postpath[1:5])
                try:
                    del self.events[year][month][day][ind]
                    self.savePickle()
                except IndexError:
                    pass
                return self.backToCalendar(request)
            else:
                return """<a href="%s/post">Post an Event</a>"""%(self.password)
        else:
            if request.postpath and request.postpath[0]=="event":
                return self.backToCalendar(request)
            return ""

    def getDay(self,request,day,month,year):
        if not self.events.has_key(year):
            return
        if not self.events[year].has_key(month):
            return
        if not self.events[year][month].has_key(day):
            return
        c=""
        for event in self.events[year][month][day]:
            c=c+"""<a href="%s/event/%s/%s/%s/%s">%s</a><br>""" % (
                request.path,
                year, month, day, self.events[year][month][day].index(event),
                event.title)
        return c
        

    def setDay(self,day,month,year,title,data):
        self.makeDay(day,month,year)
        self.events[year][month][day].append(EventWidget(day,month,year,title,data))
        self.savePickle()

    def makeDay(self,day,month,year):
        if not self.events.has_key(year):
            self.events[year]={}
        if not self.events[year].has_key(month):
            self.events[year][month]={}
        if not self.events[year][month].has_key(day):
            self.events[year][month][day]=[]
#        if not type(self.events[year][month][day])==type([]):
#            self.events[year][month][day]=[]

    def loadPickle(self):
        if not self.filename:
            return
        try:
            self.events=cPickle.load(open(self.filename))
        except:
            pass

    def savePickle(self):
        if not self.filename:
            return
        cPickle.dump(self.events,open(self.filename,"w"))

class EventWidget(widgets.Widget):
    def __init__(self,day,month,year,title,data):
        self.day=day
        self.month=month
        self.year=year
        self.title=title
        self.data=data

    def display(self,request):
        c="<b>Date:</b> %s %s, %s<br>\n"%(calendar.month_name[self.month],
                                              self.day, self.year)
        c=c+"<b>Title:</b> %s<br>\n"%self.title
        c=c+"<b>Data:</b> %s<br>\n"%self.data
        return [c]
