To run this you need
 
- py2exe installed, 0.5+
- win32all
- unzip modulegraph.zip into sys.path

IMPORTANT: for py2exe 0.5.4, a patch is needed.  After the next official
release of py2exe this will no longer be required.  Here is the patch:
_______________________________________________________________________
--- boot_service.py     2004-11-03 11:02:31.147398500 -0800
+++ boot_service.py.new 2004-11-03 11:02:19.522844900 -0800
@@ -9,7 +9,11 @@
 service_klasses = []
 try:
     for name in service_module_names:
-        mod = __import__(name)
+        # Use the documented fact that when a fromlist is present,
+        # __import__ returns the innermost module in "name".
+        # This makes it possible to have a dotted name work the
+        # way you"d expect.
+        mod = __import__(name, globals(), locals(), ["DUMMY"])
         for ob in mod.__dict__.values():
             if hasattr(ob, "_svc_name_"):
                 service_klasses.append(ob)
_______________________________________________________________________



Use: Create a setup.py file that does basically this:

-=-=-=-=-=-=-=-=-=-=-
from distutils.core import setup
import ntsvc

setup(appconfig='my.tac')  # currently only works on tac files.
# Make sure you don't use an absolute or relative path for appconfig.  It
# must be a file in the current directory.
-=-=-=-=-=-=-=-=-=-=-

You can also use all the setup options that py2exe allows, such as includes and
data_files.  The .tac file itself is automatically appended to data_files,
and everything the .tac imports will be in library.zip.



Then run:

$ python setup.py twistedservice


This process generates a file named ntsvc.cfg which is copied into the dist
directory.  If an ntsvc.cfg already exists, I will use the existing one
instead.  ntsvc.cfg is an ini file (parseable by ConfigParser) with one
section, "[service]", and the following useful keys:

* cftype = type of config file.  Currently only 'python' is supported, for .tac
files.  Other types correspond to .tap, .tas etc. but again, are not yet
supported.

* basecf = filename of a .tac file.  This value will *override* the value
specified for 'appconfig', if any.

* svcname = a short name for the service.  This name becomes the registry key,
and also the thing you type when you want to do 'net start ...'.

* display = a human-readable name for the service, which will be displayed in
the services applet.

* reactortype = one of 'default', 'win', 'iocp', 'gtk2', etc.  CAUTION:
reactors other than 'default' will have to be added to an includes option
inside your setup.py.  For example:
    setup(appconfig='my.tac', options=
                {'twistedservice': 
                    {'includes': 'twisted.internet.win32eventreactor'}})


