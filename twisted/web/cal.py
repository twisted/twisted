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
import StringIO
import operator
from twisted.web import widgets,error

class CalendarWidget(widgets.StreamWidget):
    def __init__(self,year,month,getday):
        self.month=month
        self.year=year
        self.getday=getday

    def stream(self,write,request):
        write('''<table border=0 cellpadding=2 width=100%>
''')
        write('''<tr><td colspan=7 bgcolor=black><font color=white><center><b>%s %s</b></center></font></td></tr>
    <tr>'''%(calendar.month_name[self.month],self.year))
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
                write("</center></td>\n")
            write('''</tr>
''')
        write("</table>")

class PostForm(widgets.Form):
    formGen=widgets.Form.formGen
    formGen['intmenu']=widgets.htmlFor_menu

    formFields = [
        ["intmenu","Day","day",map(str,range(1,32))],
        ["menu","Month","month",map(operator.getitem, [calendar.month_name]*12,
                                                      range(1,13))],
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

    def process(self,write,request,submit,day,month,year,title,data):
        month=calendar.month_name.index(month)
        self.page.setDay(day,month,year,title,data)
        return [self.page.backToCalendar(request)]

class EditForm(widgets.Form):
    def __init__(self,page,event):
        self.page=page
        self.event=event

    def getFormFields(self,request):
        text=string.replace(self.event.data,"<br>\n","\n")
        return [
            ["string","Title","title",self.event.title],
            ["text","Data","data",text]]

    def process(self,write,request,submit,title,data):
        self.event.title=title
        self.event.data=string.replace(data,"\n","<br>\n")
        return [self.page.backToCalendar(request)]

class CalendarPage(widgets.Page):
    isLeaf = 1

    template = '''<HTML>
<HEAD>
<TITLE>%%%%self.title(request)%%%%</TITLE>
</HEAD>
<BODY>
%%%%self.displayPage(request)%%%%
%%%%self.displayFooter(request)%%%%
</BODY>
</HTML>'''

    def __init__(self,password="twisted",filename=None):
        widgets.Page.__init__(self)
        self.password=password
        self.events={}
        self.filename=filename
        self.loadPickle()

    def setValues(self,request):
        self.auth=0
        if request.postpath:
            if request.postpath[0]==self.password:
                self.auth=1
                del request.postpath[0]
        if request.postpath:
            try:
                test=int(request.postpath[0])
                self.command="calendar"
                self.options=request.postpath
            except:
                self.command=request.postpath[0]
                self.options=request.postpath[1:]
        else:
            self.command="calendar"
            self.options=[]
        request.postpath=[]

    def setDate(self):
        curtime=time.localtime(time.time())
        self.month=curtime[1]
        self.year=curtime[0]
        if not self.options:
            self.givendate=0
            return
        if int(self.options[0])<=12 and int(self.options[0])>=1:
            self.month=int(self.options[0])
            self.givendate=1
            if len(self.options)>1:
                self.year=int(self.options[1])
                if self.year==0:
                    self.year=2000
                elif self.year<100:
                    self.year=1900+self.year

    def title(self,request):
        self.setValues(request)
        func=getattr(self,"title_%s"%self.command,None)
        if func:
            return func(request)
        else:
            return "No Title"

    def displayPage(self,request):
        func=getattr(self,"page_%s"%self.command,None)
        if func:
            return func(request)
        else:
            return "No page for command %s"%self.command

    def displayFooter(self,request):
        func=getattr(self,"footer_%s"%self.command,None)
        if func:
            return func(request)
        else:
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
            c=c+"""* <a href="%s/event/%s/%s/%s/%s">%s</a><br>
""" % (
        self.currentPath(request),
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

    def title_event(self,request):
        return self.getCurrentEvent().title

    def title_calendar(self,request):
        self.setDate()
        return calendar.month_name[self.month]+" "+str(self.year)

    def title_post(self,request):
        return "Post an Event"

    def title_delete(self,request):
        return "Deleting Event: %s"%self.getCurrentEvent().title

    def title_edit(self,request):
        return "Editing Event: %s"%self.getCurrentEvent().title

    def page_calendar(self,request):
        if self.givendate:
            return CalendarWidget(self.year,self.month,self.getDay)
        m=self.month+1
        y=self.year
        if m==13:
            m=1
            y=y+1
        s=StringIO.StringIO()
        CalendarWidget(self.year,self.month,self.getDay).stream(s.write,request)
        CalendarWidget(y,m,self.getDay).stream(s.write,request)
        return s.getvalue()

    def page_event(self,request):
        return self.getCurrentEvent()

    def page_post(self,request):
        if not self.auth: return ""
        return PostForm(self)

    def page_edit(self,request):
        if not self.auth: return ""
        return EditForm(self,self.getCurrentEvent())

    def page_delete(self,request):
        if not self.auth: return ""
        options=map(int,self.options)
        year,month,day,ind=options
        try:
            del self.events[year][month][day][ind]
            self.savePickle()
        except:
            pass
        return self.backToCalendar(request)

    def footer_event(self,request):
        if not self.auth: return self.backToCalendar(request)
        return '''<a href="%s">Delete</a><br>
<a href="%s">Edit</a><br>
%s'''%(
        self.currentPath(request)+"/delete/"+string.join(self.options,"/"),
        self.currentPath(request)+"/edit/"+string.join(self.options,"/"),
        self.backToCalendar(request))

    def footer_calendar(self,request):
        if not self.auth: return ""
        return '''<a href="%s">Post Event</a>'''%(self.currentPath(request)+"/post")

    def currentPath(self,request):
        url="/"+string.join(request.prepath,"/")
        if self.auth: return url+"/"+self.password
        return url

    def backToCalendar(self,request):
        return """<a href="%s">Back To the Calendar</a>"""%self.currentPath(request)

    def getCurrentEvent(self):
        options=map(int,self.options)
        year,month,day,ind=options
        return self.events[year][month][day][ind]

class EventWidget(widgets.Widget):
    def __init__(self,day,month,year,title,data):
        self.day=day
        self.month=month
        self.year=year
        self.title=title
        self.data=string.replace(data,"\n","<br>\n")

    def display(self,request):
        c="<b>Date:</b> %s %s, %s<br>\n"%(calendar.month_name[self.month],
            self.day, self.year)
        c=c+"<b>Title:</b> %s<br>\n"%self.title
        c=c+"<b>Data:</b> %s<br>\n"%self.data
        return [c]
