# This is a resource file, which generates some useful
# information
# To use it, rename it to "hello.rpy" and put it in the path of
# any normally-configured Twisted web server.

from twisted.web import static
import time

now = time.ctime()

d = '''\
<HTML><HEAD><TITLE>Hello Rpy</TITLE>

<H1>Hello World, It is Now %(now)s</H1>

<UL>
''' % vars()

for i in range(10):
    d += "<LI>%(i)s" % vars()

d += '''\
</UL>

</BODY></HTML>
'''

resource = static.Data(d, 'text/html')
