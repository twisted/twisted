#!/usr/bin/env python
"""A rate-limited web server.
"""
from twisted.internet import htb, tcp

serverFilter = htb.HierarchicalBucketFilter()
serverBucket = htb.Bucket()

# Cap total server traffic at 20 kB/s
serverBucket.maxburst = 20000
serverBucket.rate = 20000

serverFilter.buckets[None] = serverBucket

# Web service is also limited per-host:
class WebClientBucket(htb.Bucket):
    # Your first 10k is free
    maxburst = 10000
    # One kB/s thereafter.
    rate = 1000

webFilter = htb.FilterByHost(serverFilter)
webFilter.bucketFactory = WebClientBucket

# My, this is somewhat clumsy to use, isn't it.
class WebPort(tcp.Port):
    transport = htb.ThrottledServerFactory(webFilter)

from twisted.internet import app
from twisted.web import server, static
site = server.Site(static.File("/var/www"))

myApp = app.Application("htbwebsite")
myApp.listenWith(WebPort, 8000, site)
myApp.run(save=0)
