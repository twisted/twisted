
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
"""

import calendar
import time
from twisted.web import html

class Calendar(html.Interface):
    isLeaf=1
    def __init__(self):
        html.Interface.__init__(self)
        self.events={}
        self.ids=[]
    def make_day(self,d,m,y):
        if not self.events.has_key(y):
            self.events[y]={m:{d:[]}}
        else:
            if not self.events[y].has_key(m):
                self.events[y][m]={d:[]}
            else:
                if not self.events[y][m].has_key(d):
                    self.events[y][m][d]=[]

    def get_day(self,d,m,y):
        if not self.events.has_key(y):
            return []
        if not self.events[y].has_key(m):
            return []
        if not self.events[y][m].has_key(d):
            return []
        return self.events[y][m][d]
    def set_args(self,request):
        curtime=time.localtime(time.time())
        self.curmonth=curtime[1]
        self.curyear=curtime[0]
        if request.args.has_key("month"):
            self.month=int(request.args["month"][0])
        else:
            self.month=self.curmonth
        if request.args.has_key("year"):
            self.year=int(request.args["year"][0])
        else:
            self.year=self.curyear
        self.day=curtime[2]

    def pagetitle(self,request):
        self.set_args(request)
        return html.Interface.pagetitle(self,request)
        #return "Calendar for %s %s" % (calendar.month_name[self.month],self.year)

    def content(self,request):
        if request.args.has_key("action"):
            if request.args["action"][0]=="post":
                return self.handlePost(request)
            elif request.args["action"][0]=="event":
                return self.handleEvent(request)
            elif request.args["action"][0]=="add":
                self.handleAdd(request)
            elif request.args["action"][0]=="del":
                self.handleDel(request)
        c="""<table border=0 cellpadding=2>
<tr>"""
        for d in calendar.day_name:
            c=c+"<td><center>&nbsp;%s&nbsp;</center></td>"%d
        c=c+"</tr>\n"
        days=calendar.monthcalendar(self.year,self.month)
        for week in days:
            c=c+"<tr>"
            for day in week:
                ev=self.get_day(day,self.month,self.year)
                if day==self.day and self.month==self.curmonth and self.year==self.curyear:
                    day="<b>%s</b>"%day
                if day:
                    c=c+"<td><center>%s"%day
                    for e in ev:
                        c=c+"""<br><a href="%s?action=event&id=%s">%s</a>"""%(request.path,e.id,e.short)
                    c=c+"</center></td>"
                else:
                    c=c+"<td></td>"
            c=c+"</tr>\n"
        c=c+"</table>"
        c=self.box(request,"%s %s"%(calendar.month_name[self.month],self.year),c)
        #date=(self.month,self.year)
        #if date[0]==12:
        #    next=(1,date[1]+1)
        #else:
        #    next=(date[0]+1,date[1])
        #if date[0]==1:
        #    prev=(12,date[1]-1)
        #else:
        #    prev=(date[0]-1,date[1])
        #url=request.path+"?month=%s&year=%s"
        #nexturl=url%next
        #prevurl=url%prev
        #c=c+"""<a href="%s">%s %s <</a>"""%(prevurl,calendar.month_name[prev[0]],prev[1])
        #c=c+"&nbsp"*20
        #c=c+"""<a href="%s">> %s %s</a>"""%(nexturl,calendar.month_name[next[0]],next[1])
        return c

    def handlePost(self,request):
        return self.form(request,[["hidden","","action","add"],
                            ["menu","Day","d",map(str,range(1,32))],
                            ["menu","Month","m",calendar.month_name[1:]],
                            ["string","Year","y",str(self.curyear)],
                            ["string","Title","title",""],
                            ["text","Data","data",""]])
    def handleAdd(self,request):
        items=["d","m","y","title","data"]
        if reduce(lambda x,y:x and y,map(request.args.has_key,items)):
            d=int(request.args["d"][0])
            m=int(calendar.month_name.index(request.args["m"][0]))
            y=int(request.args["y"][0])
            self.make_day(d,m,y)
            e=Event(len(self.ids),request.args["title"][0],request.args["data"][0],d,m,y)
            self.events[y][m][d].append(e)
            self.ids.append(e)
    def handleDel(self,request):
        id=int(request.args["id"][0])
        e=self.ids[id]
        for event in self.ids[id+1:]:
            event.id=event.id-1
        del self.ids[id]
        self.events[e.y][e.m][e.d].remove(e) 
    def handleEvent(self,request):
        e=self.ids[int(request.args["id"][0])]
        parts= [["Date","%s %s, %s"%(calendar.month_name[e.m],e.d,e.y)],
                ["Title",e.short],
                ["Data",e.long]]
        c="<b>Date:</b> %s %s, %s<br>"%(calendar.month_name[e.m],e.d,e.y)
        c=c+e.long+"<br>"
        c=c+"""<a href="%s?action=del&id=%s">Delete</a>"""%(request.path,e.id)
        return self.box(request,e.short,c)
class Event:
    def __init__(self,id,short,long,d,m,y):
        self.id=id
        self.short=short
        self.long=long
        self.d=d
        self.m=m
        self.y=y
