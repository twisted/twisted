from bundlebuilder import buildapp 
import glob
    
buildapp(
    name = 'Twistzilla',
    mainprogram = "Twistzilla.py",
    resources = ["English.lproj"],
    nibname = "MainMenu",
)   
