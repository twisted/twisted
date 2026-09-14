import io

from twisted.logger import eventsFromJSONLogFile

for event in eventsFromJSONLogFile(open("log.json")):
    print(sum(event["values"]))
