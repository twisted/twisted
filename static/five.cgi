#!/usr/bin/env python

###
### This is a particularly brutal CGI; it takes 10 seconds to execute.
### It's to test race conditions, concurrency, etc.
###

import time
import sys

print 'content-type: text/html'
print
print 
print '<HTML>'
print '<BODY>'
print 'ONE<BR>'*10000
sys.stdout.flush()
time.sleep(1)
print 'TWO<BR>'*10000
sys.stdout.flush()
time.sleep(1)
print 'THREE<BR>'*10000
sys.stdout.flush()
time.sleep(1)
print 'FOUR<BR>'*10000
sys.stdout.flush()
time.sleep(1)
print 'FIVE<BR>'*10000
sys.stdout.flush()
time.sleep(1)
print 'DONE'*10000
print "</body>"
print "</html>"
