from bundlebuilder import buildapp
    
buildapp(
    name = 'Twistzilla',
    mainprogram = "Twistzilla.py",
    resources = ["English.lproj"],
    nibname = "MainMenu",
)
