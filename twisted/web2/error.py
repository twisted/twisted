
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I am the Twisted.Web error resources and exceptions."""

#t.w imports
#from twisted.web2 import resource
from twisted.web2 import responsecode

# 300 - Should include entity with choices
# 301 -
# 304 - Must include Date, ETag, Content-Location, Expires, Cache-Control, Vary.
# 
# 401 - Must include WWW-Authenticate.
# 405 - Must include Allow.
# 406 - Should include entity describing allowable characteristics
# 407 - Must include Proxy-Authenticate
# 413 - May  include Retry-After
# 416 - Should include Content-Range
# 503 - Should include Retry-After
