import sys

# import pyobjc
import objc
import Foundation
import AppKit

# import classes required to start application
import WSTApplicationDelegateClass
import WSTConnectionWindowControllerClass

# pass control to the AppKit
sys.exit( AppKit.NSApplicationMain(sys.argv) )
