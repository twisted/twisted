#! /usr/bin/python

# This is a Gnome-2 panel applet that uses Twisted. All normal the usual
# Twisted stuff (pb, reactor.listenTCP, etc) should be available. See the
# notes at the end for installation hints and support files (you cannot
# simply run this script from the shell).

# These applets are run in an environment that throws away stdout and
# stderr. Any logging must be done with syslog or explicitly to a file.
# Exceptions are particularly annoying in such an environment.

if 1:
    import sys
    dpipe = open("/tmp/applet.log", "a", 1)
    sys.stdout = dpipe
    sys.stderr = dpipe
    print "starting"

from twisted.internet import gtk2reactor
gtk2reactor.install()

import pygtk
pygtk.require("2.0")
import gtk
import gnome.applet, gnome.ui

class MyApplet:
    def __init__(self, container):
        b = gtk.Button("twist!")
        b.connect('clicked', self.push)
        size = container.get_size()
        container.set_size_request(size, size)
        container.add(b)
        container.show_all()
        
    def push(self, widget):
        print "push!"
        
              
def factory(applet, iid):
    MyApplet(applet)
    applet.show_all()
    return gtk.TRUE


from twisted.internet import reactor

# instead of reactor.run(), we do the following:
reactor.startRunning()
reactor.simulate()
gnome.applet.bonobo_factory("OAFIID:GNOME_twistlet_Factory", 
                            gnome.applet.Applet.__gtype__, 
                            "twistlet", "0", factory)

# code ends here: bonobo_factory runs gtk.mainloop() internally and
# doesn't return until the program ends


# SUPPORTING FILES:

# save this as ~/lib/bonobo/servers/twistlet.server, and update all the
# pathnames to match your system
twistlet_server = """
<oaf_info>

<oaf_server iid="OAFIID:GNOME_twistlet_Factory"
	    type="exe"
	    location="/usr/home/warner/stuff/python/misc/twistlet.py">

	<oaf_attribute name="repo_ids" type="stringv">
		<item value="IDL:Bonobo/GenericFactory:1.0"/>
		<item value="IDL:Bonobo/Unknown:1.0"/>
	</oaf_attribute>
	<oaf_attribute name="name" type="string" value="twistlet Factory"/>
	<oaf_attribute name="description" type="string" value="Test"/>
</oaf_server>

<oaf_server iid="OAFIID:GNOME_twistlet"
	    type="factory" 
	    location="OAFIID:GNOME_twistlet_Factory">

	<oaf_attribute name="repo_ids" type="stringv">
		<item value="IDL:GNOME/Vertigo/PanelAppletShell:1.0"/>
		<item value="IDL:Bonobo/Control:1.0"/>
		<item value="IDL:Bonobo/Unknown:1.0"/>
	</oaf_attribute>
	<oaf_attribute name="name" type="string" value="Twistlet"/>
	<oaf_attribute name="description" type="string" value="Twisted Applet"
        />
	<oaf_attribute name="panel:category" type="string" value="Utility"/>
	<oaf_attribute name="panel:icon" type="string"
 value="/usr/home/warner/.galeon/favicons/twistedmatrix.com_images_favicon.png"
 />

</oaf_server>

</oaf_info>
"""

# a quick rundown on the Gnome2 applet scheme (probably wrong: there are
# better docs out there that you should be following instead)
#  http://www.pycage.de/howto_bonobo.html describes a lot of
#   the base Bonobo stuff.
#  http://www.daa.com.au/pipermail/pygtk/2002-September/003393.html

# twistlet.server must be in your $BONOBO_ACTIVATION_PATH . I use
# ~/lib/bonobo/servers . This environment variable is read by
# bonobo-activation-server, so it must be set before you start any Gnome
# stuff. I set it in ~/.bash_profile . You can also put it in
# /usr/lib/bonobo/servers/

# It is safest to put this in place before bonobo-activation-server is
# started, which may mean before any Gnome program is running. It may or may
# not detect twistlet.server if it is installed afterwards.. there seem to
# be hooks, some of which involve FAM, but I never managed to make them
# work. The file must have a name that ends in .server or it will be
# ignored.

# The .server file registers two OAF ids and tells the activation-server how
# to create those objects. The first is the twistlet_Factory, and is created
# by running the twistlet.py script. The second is the twistlet applet
# itself, and is created by asking the twistlet_Factory to make it.

# gnome-panel's "Add To Panel" menu will gather all the OAF ids that claim
# to implement the "IDL:GNOME/Vertigo/PanelAppletShell:1.0" in its
# "repo_ids" attribute. The sub-menu is determined by the "panel:category"
# attribute. The icon comes from "panel:icon", the text displayed in the
# menu comes from "name", the text in the tool-tip comes from "description".

# The factory() function is called when a new applet is created. It receives
# a container that should be populated with the actual applet contents (in
# this case a Button).

# Menus are left as an exercise for the reader (they involve writing an XML
# description of the menu).

# Because of an annoying "feature" of applet menus in gnome-2, you will
# probably need to kill the applet with 'kill -9 PID' to make it go away
# (there is no room for the per-applet menu that would normally let you
# remove it). ('kill PID' won't work because the program is sitting in C
# code, and SIGINT isn't delivered until after it surfaces to python, which
# will be never). When the panel asks you if you want to reload the applet,
# say no.

# Running twistlet.py by itself will result in a factory instance being
# created and then sitting around forever waiting for the activation-server
# to ask it to make an applet. This isn't very useful.

# The "location" filename in twistlet.server must point to twistlet.py, and
# twistlet.py must be executable.

# Enjoy!
#  -Brian Warner
