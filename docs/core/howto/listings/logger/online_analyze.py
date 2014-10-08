from twisted.logger import globalLogPublisher
from analyze import analyze
from ad_hoc import AdHoc

globalLogPublisher.addObserver(analyze)

AdHoc(3, 4).logMessage()
