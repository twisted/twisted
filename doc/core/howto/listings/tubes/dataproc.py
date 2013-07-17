
from twisted.tubes.tube import cascade
from twisted.tubes.framing import bytesToLines, linesToBytes

from intparse import LinesToIntegersOrCommands
from worker import CommandsAndIntegersToResultIntegers
from output import IntegersToLines

def dataProcessor():
    return cascade(
        bytesToLines(), LinesToIntegersOrCommands(),
        CommandsAndIntegersToResultIntegers(), IntegersToLines(),
        linesToBytes()
    )
