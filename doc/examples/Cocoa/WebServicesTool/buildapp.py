from bundlebuilder import buildapp

OTHERSRC=[
    'WSTApplicationDelegateClass.py', 
    'WSTConnectionWindowControllerClass.py']

buildapp(
	name = "Web Services Tool",
	mainprogram = "Main.py",
	resources = ["English.lproj", "Preferences.png", "Reload.png", "WST.png"] + OTHERSRC,
	nibname = "MainMenu",
	iconfile = "WST.icns",
)
