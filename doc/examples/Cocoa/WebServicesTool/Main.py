import sys
from PyObjCTools import AppHelper

# import classes required to start application
import WSTApplicationDelegateClass
import WSTConnectionWindowControllerClass

# pass control to the AppKit
AppHelper.runEventLoop()
