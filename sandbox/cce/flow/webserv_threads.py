from __future__ import generators
from twisted.flow import flow
from twisted.flow.threads import Threaded

def cooperative():
    """ simulate a cooperative resource, that doesn't block """
    from random import random
    while 1:
        val = random()
        yield flow.Cooperate(val/5)
        yield str(val)[-5:]

def blocking():
    """ simulate a blocking database resource """
    from time import sleep
    sleep(1)
    yield (3,'AL','Alabama')
    yield (4,'AK','Alaska')
    yield (6,'AZ','Arizona')
    yield (7,'AR','Arkansas')
    yield (8,'CA','California')
    yield (9,'CO','Colorado')
    yield (1,'CT','Connecticut')
    sleep(1)
    yield (1,'DE','Delaware')
    yield (2,'DC','District of Columbia')
    yield (4,'FL','Florida')
    yield (5,'GA','Georgia')
    yield (7,'HI','Hawaii')
    yield (8,'ID','Idaho')
    yield (9,'IL','Illinois')
    yield (3,'IN','Indiana')
    yield (1,'IA','Iowa')
    yield (2,'KS','Kansas')
    yield (3,'KY','Kentucky')
    sleep(1)
    yield (4,'LA','Louisiana')
    yield (5,'ME','Maine')
    yield (7,'MD','Maryland')
    yield (8,'MA','Massachusetts')
    yield (9,'MI','Michigan')
    yield (0,'MN','Minnesota')
    yield (1,'MS','Mississippi')
    yield (2,'MO','Missouri')
    yield (3,'MT','Montana')
    yield (4,'NE','Nebraska')
    yield (5,'NV','Nevada')
    yield (6,'NH','New Hampshire')
    sleep(1)
    yield (7,'NJ','New Jersey')
    yield (8,'NM','New Mexico')
    yield (9,'NY','New York')
    yield (0,'NC','North Carolina')
    yield (1,'ND','North Dakota')
    yield (3,'OH','Ohio')
    yield (4,'OK','Oklahoma')
    yield (5,'OR','Oregon')
    sleep(1)
    yield (7,'PA','Pennsylvania')
    yield (9,'RI','Rhode Island')
    yield (0,'SC','South Carolina')
    yield (1,'SD','South Dakota')
    yield (2,'TN','Tennessee')
    yield (3,'TX','Texas')
    yield (4,'UT','Utah')
    yield (5,'VT','Vermont')
    yield (7,'VA','Virginia')
    yield (8,'WA','Washington')
    yield (9,'WV','West Virginia')
    yield (3,'WI','Wisconsin')
    yield (8,'WY','Wyoming')

def render(req):
    req.write("""
       <html>
         <head>
           <title>Icremental Webpage</title></head>
         <body>
           <h1>Incremental Webpage</h1>
           <table>
             <tr>
                <td>State</td>
                <td>Zipcodes</td>
             <tr>
    """)
    zips   = flow.wrap(cooperative())
    states = flow.wrap(Threaded(blocking()))
    yield states
    for cnt, abbr, state in states:
        req.write("""
            <tr><td>%s</td><td>%s</td>
                <td>
        """ % (abbr, state))
        for x in range(cnt):
            yield zips; 
            if x: req.write(", ")
            for result in zips.results:
               req.write(result)
               zips.results = []
        req.write("""
            </td></tr>
        """)
        yield states

if __name__=='__main__':
    from twisted.internet import reactor
    from twisted.web.server import Site
    from twisted.flow.web import Resource
    print "visit http://localhost:8081/ to view"
    reactor.listenTCP(8081,Site(Resource(render)))
    reactor.run()
