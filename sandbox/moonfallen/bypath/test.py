expected = '''2
<?xml version="1.0" ?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:n="http://nevow.com/ns/nevow/0.1">
  <head>
    <meta content="text/html; charset=UTF-8" http-equiv="Content-Type"/>
    <title>Do Not Hand Edit</title>
    <style type="text/css">
      /* styles here */
    </style>
    <script language="javascript" type="text/javascript">
      // scripts here
    </script>
  hi</head>
  <body n:render="hideEditWarning">
    <div>Do Not Hand-Edit Me.  Edit toc.yml instead.</div>
    <n:invisible n:pattern="lala" style="display:none">lalala table of
    contents</n:invisible>
    <div>foo</div>
    <div>bar</div>
  </body>
</html>
hi
testtesttesttest
None
div
div
div
html
!div html
!div head
!div meta
!div title
!div style
!div script
!div body
!div n:invisible
title
style
script
n:invisible
'''


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import sys, os

out = os.popen("python bypath.py tests/foo.byp donot.html").read()
for l1, l2 in zip(out.splitlines(), expected.splitlines()):
    assert l1 == l2, '%s != %s' % (l1, l2)
print 'tests passed'
