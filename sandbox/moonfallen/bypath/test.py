expected = '''*** global ***
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
div
div
div
<DOM Element: html at 0xa43ee0>
!div <DOM Element: html at 0xa43ee0>
!div <DOM Element: head at 0xa4c058>
!div <DOM Element: meta at 0xa4c0a8>
!div <DOM Element: title at 0xa4c1e8>
!div <DOM Element: style at 0xa4c260>
!div <DOM Element: script at 0xa4c350>
!div <DOM Element: body at 0xa4c4e0>
!div <DOM Element: n:invisible at 0xa4c620>
<DOM Element: title at 0xa4c1e8>
<DOM Element: style at 0xa4c260>
<DOM Element: script at 0xa4c350>
<DOM Element: n:invisible at 0xa4c620>
'''


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import sys, os

out = os.popen("python bypath.py tests/foo.byp donot.html").read()
assert out == expected
print 'tests passed'
