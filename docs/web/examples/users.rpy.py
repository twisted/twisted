# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example showing how to use a distributed web server's user directory support.

With this, you can have an instant "community web site",
letting your shell users publish data in secure ways.

Just put this script anywhere, and /path/to/this/script/<user>/ will publish a
user's ~/public_html, and a .../<user>.twistd/ will attempt to contact a user's
personal web server.

For example, if you put this at /var/www/users.rpy and run a server like:
    $ twistd -n web --allow-ignore-ext --path /var/www

Then http://example.com/users/<name>/ and http://example.com/users/<name>.twistd
will work similarly to how they work on twistedmatrix.com.
"""

from twisted.web import distrib

resource = distrib.UserDirectory()
registry.setComponent(distrib.UserDirectory, resource)
