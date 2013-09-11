
from twisted.tubes.tube import series
from twisted.tubes.framing import bytesToLines, linesToBytes

from intparse import LinesToIntegersOrCommands
from worker import CommandsAndIntegersToResultIntegers
from output import IntegersToLines

def dataProcessor():
    return series(
        bytesToLines(),
        LinesToIntegersOrCommands(),
        CommandsAndIntegersToResultIntegers(),
        IntegersToLines(),
        linesToBytes()
    )
