"""
WSTApplicationDelegateClass

An instance of this class is instantiated in the MainMenu.nib default NIB file.
All outlets and the base class are automatically derived at runtime by the
AutoBaseClass mechanism provided by the NibClassBuilder.
"""

from PyObjCTools import NibClassBuilder

# Make NibClassBuilder aware of the classes in the main NIB file.
NibClassBuilder.extractClasses( "MainMenu" )

# WSTApplicationDelegate will automatically inherit from the
# appropriate ObjC class [NSObject, in this case] and will have the
# appropriate IBOutlets already defined based on the data found in the
# NIB file(s) that define the class. 
class WSTApplicationDelegate(NibClassBuilder.AutoBaseClass):

    def newConnectionAction_(self, sender):
        """Action method fired when the user selects the 'new connection'
        menu item.  Note that the WSTConnectionWindowControllerClass is
        defined the first time this method is invoked.

        This kind of lazy evaluation is generally recommended;  it speeds
        app launch time and it ensures that cycles aren't wasted loading
        functionality that will never be used.

        (In this case, it is largely moot due to the implementation of
        applicationDidFinishLaunching_().
        """
        from WSTConnectionWindowControllerClass import WSTConnectionWindowController
        WSTConnectionWindowController.connectionWindowController().showWindow_(sender)

    def applicationDidFinishLaunching_(self, aNotification):
        """Create and display a new connection window
        """
        self.newConnectionAction_(None)
