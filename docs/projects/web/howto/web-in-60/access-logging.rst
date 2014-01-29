
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Access Logging
==============

As long as we're on the topic of :doc:`logging <error-logging>` , this is probably a good time to mention Twisted Web's access log support.
In this example, we'll see what Twisted Web logs for each request it processes and how this can be customized.

If you've run any of the previous examples and watched the output of ``twistd`` or read ``twistd.log`` then you've already seen some log lines like this:

  2014-01-29 17:50:50-0500 [HTTPChannel,0,127.0.0.1] "127.0.0.1" - - [29/Jan/2014:22:50:50 +0000] "GET / HTTP/1.1" 200 2753 "-" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36"

If you focus on the right-hand side of this log message you'll see something that looks like a standard "combined log format" message.
However, it's prefixed with the normal Twisted logging prefix giving a timestamp and some protocol and peer addressing information.
Much of this information is redundant since it is part of the combined log format.
:api:`twisted.web.server.Site <Site>` lets you produce a more compact log which omits the normal Twisted logging prefix.
To take advantage of this feature all that is necessary is to tell :api:`twisted.web.server.Site <Site>` where to write this compact log.
Do this by passing ``logPath`` to the initializer:

.. code-block:: python

    ...

    factory = Site(root, logPath=b"/tmp/access-logging-demo.log")

