# With this, you can have an instant "community web site",
# letting your shell users publish data in secure ways.
#
# Just put this script anywhere, and /path/to/this/script/<user>/
# will publish a user's ~/public_html, and a .../<user>.twistd/
# will attempt to contact a user's personal web server.
#
# For example, if you put this at the root of the web server
# as "users.rpy", and configure --allow-ignore-ext, then
# http://example.com/users/<name>/ and http://example.com/users/<name>.twistd
# will work similarily to how they work on twistedmatrix.com
 
from twisted.web import distrib

resource = registry.getComponent(distrib.UserDirectory)
if not resource:
    resource = distrib.UserDirectory()
    registry.setComponent(distrib.UserDirectory, resource)
