"""I am an interactive calendar for twisted.web.
I use MethodDirectory, which doesn't exist any more, so I need to be
rewritten.
"""

import calendar

##class Calendar(web.MethodDirectory):
##    def __init__(self):
##        web.MethodDirectory.__init__(self)
##        self.calendar = {}
##        self.registeredMethods = ["post"]
##        self.curdate = list(time.localtime(time.time()))
    
##    def getChild(self, path, request):
##        if path in calendar.month_abbr:
##            return web.Method(self, self.displayCalendar, [self.curdate[0], calendar.month_abbr.index(path), 0])
##        elif 1902 < int(path) < 3000:
##            return Year(int(path))
##        else:
##            return web.NoResource()

##    def getDay(self, date):
##        #date is a tuple of [year, month, day]
##        try:
##            return str(self.calendar[date[0]][date[1]][date[2]])
##        except: return "&nbsp;"
    
##    def setDay(self, date, data):
##        #kludge.
##        year, month, day = date
##        if self.calendar.has_key(year):
##            if self.calendar[year].has_key(month):
##                self.calendar[year][month][day] = data
##            else:
##                self.calendar[year][month] = {}
##                self.calendar[year][month][day] = data
##        else:
##            self.calendar[year] = {}
##            self.calendar[year][month] = {}
##            self.calendar[year][month][day] = data
            
##    def handleForm(self, request):
##        foo = request.args
###        return str([foo["Year"], foo["Month"], foo["Day"]])
##        if foo.has_key("Year") and foo.has_key("Month") and foo.has_key("Day") and foo.has_key("Data"):
##            self.setDay([int(foo["Year"][0]),
##                          calendar.month_abbr.index(foo["Month"][0]),
##                          int(foo["Day"][0])],
##                         foo["Data"][0])

##    def displayCalendar(self, request, date):
##        calendar.setfirstweekday(6)
##        content = ""
##        content = content + "<table border=1 cellpadding=1 cellspacing=1>\n"
##        content = content + "<b>" + calendar.month_name[date[1]] + " " + str(date[0]) + "</b>\n"
##        content = content + "<tr><td>Sunday</td><td>Monday</td><td>Tuesday</td><td>Wednesday</td><td>Thursday</td><td>Friday</td><td>Saturday</td>"
##        for week in calendar.monthcalendar(date[0], date[1]):
##            content = content + "<tr>\n"
##            for day in week:
##                content = content + "<td>"
##                if not day == 0:
##                    if day == date[2]:
##                        content = content + "<font color='red'>" + str(day) + "</font>"
##                    else:
##                        content = content + str(day)
##                    content = content + self.getDay([date[0], date[1], day]) + "</td>\n"
##            content = content + "</tr>\n"
##        content = content + "</table>\n"
##        return content
    
##    def post(self, request):
##        content = ""
##        content = content + "<p>Wanna add an event to the calendar? go for it!</p>"
##        content = content + self.form(request, [["string", "Year", "Year", str(time.localtime(time.time())[0])],
##                                           ["menu", "Month", "Month", ["Jan", "Feb", "Mar",
##                                                                       "Apr", "May", "Jun",
##                                                                       "Jul", "Aug", "Sep",
##                                                                       "Oct", "Nov", "Dec"]],
##                                           ["menu", "Day", "Day", map(str, range(1,32))],
##                                           ["text", "Data", "Data", ""]],
##                                 action="?__page=index")
##        return content

##    def index(self, request):
##        timetuple = list(time.localtime(time.time()))
##        self.handleForm(request)
##        content = ""
##        content = content + self.displayCalendar(request, timetuple[:3])
###        content.append("<br><br>" + str(self.calendar))
##        return self.webpage(request, "Calendar!", content)


##class Year(Calendar):
##    def __init__(self, year):
##        web.Resource.__init__(self)
##        self.year = year

##    def getChild(self, path, request):
##        if path in calendar.month_abbr:
##            return web.Method(self, self.displayCalendar, [self.year, calendar.month_abbr.index(path), 0])

##    def render(self, request):
##        content = ""
##        for i in range(1,13):
##            content = content + self.displayCalendar(request, [self.year, i, 0])
##        return content
