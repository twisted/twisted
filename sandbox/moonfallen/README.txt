To run this you need
 
- py2exe installed, 0.5+
- win32all
- unzip modulegraph.zip into sys.path

Use: Create a setup.py file that does basically this:

-=-=-=-=-=-=-=-=-=-=-
from distutils.core import setup
import ntsvc

setup(appconfig='my.tac')  # currently only works on tac files.
-=-=-=-=-=-=-=-=-=-=-

You can use all the setup options that py2exe allows, such as includes and
data_files.  The .tac file itself is automatically appended to data_files,
and everything the .tac imports will be in library.zip.
