
from twisted.application.service import ServiceMaker

finger = ServiceMaker(
    'finger', 'finger.tap', 'Run a finger service', 'finger')
