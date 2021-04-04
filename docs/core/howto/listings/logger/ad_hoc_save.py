import io
from twisted.logger import jsonFileLogObserver, globalLogPublisher
from ad_hoc import AdHoc

globalLogPublisher.addObserver(jsonFileLogObserver(open("log.json", "a")))

AdHoc(3, 4).logMessage()
