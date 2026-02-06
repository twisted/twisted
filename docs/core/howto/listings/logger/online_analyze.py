from ad_hoc import AdHoc
from analyze import analyze

from twisted.logger import globalLogPublisher

globalLogPublisher.addObserver(analyze)

AdHoc(3, 4).logMessage()
