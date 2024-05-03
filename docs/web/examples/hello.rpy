# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is a resource file that renders a static web page.

To test the script, rename the file to hello.rpy, and move it to any directory,
let's say /var/www/html/.

Now, start your Twisted web server:
    $ twistd -n web --path /var/www/html/

And visit http://127.0.0.1:8080/hello.rpy with a web browser.
"""

from twisted.web import static
import time

now = time.ctime()

d = """\
<HTML><HEAD><TITLE>Hello Rpy</TITLE>

<H1>Hello World, It is Now {now}</H1>

<UL>
""".format(
    now=now
)

for i in range(10):
    d += "<LI>{i}".format(i=i)

d += """\
</UL>

</BODY></HTML>
"""

data = d.encode("utf8")

resource = static.Data(data, "text/html")
