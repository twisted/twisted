import io

from analyze import analyze

from twisted.logger import eventsFromJSONLogFile

for event in eventsFromJSONLogFile(open("log.json")):
    analyze(event)
