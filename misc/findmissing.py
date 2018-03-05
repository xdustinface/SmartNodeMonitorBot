import json
import re
import logging
import os
import time

logger = logging.getLogger("smartnodes")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)
# Index assignment of the "smartnodelist full"
STATUS_INDEX = 0
PROTOCOL_INDEX = 1
PAYEE_INDEX = 2
SEEN_INDEX = 3
ACTIVE_INDEX = 4
PAIDTIME_INDEX = 5
PAIDBLOCK_INDEX = 6
IPINDEX_INDEX = 7

transactionRawCheck = re.compile("COutPoint\([\d\a-f]{64},.[\d]{1,}\)")
transactionStringCheck = re.compile("[\d\a-f]{64}-[\d]{1,}")

class Transaction(object):

    def __init__(self, txhash, txindex):
        self.hash = txhash
        self.index = txindex

    def __str__(self):
        return '{0.hash}-{0.index}'.format(self)

    def __eq__(self, other):
        return self.hash == other.hash and\
                self.index == other.index

    def __hash__(self):
        return hash((self.hash,self.index))

    @classmethod
    def fromRaw(cls, s):

        if transactionRawCheck.match(s):
            parts = s[10:-1].split(', ')
            return cls(parts[0], int(parts[1]))

    @classmethod
    def fromString(cls, s):

        if transactionStringCheck.match(s):
            parts = s.split('-')
            return cls(parts[0], int(parts[1]))

class SmartNode(object):

    def __init__(self, **kwargs):

        self.tx = kwargs['tx']
        self.payee = str(kwargs['payee'])
        self.status = str(kwargs['status'])
        self.activeSeconds = int(kwargs['active_seconds'])
        self.lastPaidBlock = int(kwargs['last_paid_block'])
        self.lastPaidTime = int(kwargs['last_paid_time'])
        self.lastSeen = int(kwargs['last_seen'])
        self.protocol = int(kwargs['protocol'])
        self.rank = int(kwargs['rank'])
        self.ip = str(kwargs['ip'])
        self.timeout = int(kwargs['timeout'])
        self.position = -1


    @classmethod
    def fromRaw(cls,tx, raw):

        data = raw.split()

        return cls(tx = tx,
                   payee = data[PAYEE_INDEX],
                   status = data[STATUS_INDEX].replace('_','-'), # Avoid markdown problems
                   active_seconds = data[ACTIVE_INDEX],
                   last_paid_block = data[PAIDBLOCK_INDEX],
                   last_paid_time = data[PAIDTIME_INDEX],
                   last_seen = data[SEEN_INDEX],
                   protocol = data[PROTOCOL_INDEX],
                   ip = data[IPINDEX_INDEX],
                   rank = -1,
                   timeout = -1)

    @classmethod
    def fromDb(cls, row):

        tx = Transaction.fromString(row['collateral'])

        return cls(tx = tx,
                   payee = row['payee'],
                   status = row['status'],
                   active_seconds = row['activeseconds'],
                   last_paid_block = row['last_paid_block'],
                   last_paid_time = row['last_paid_time'],
                   last_seen = row['last_seen'],
                   protocol = row['protocol'],
                   ip = row['ip'],
                   rank = -1,
                   timeout = row['timeout'] )

def secondsToText(secs):
    days = secs//86400
    hours = (secs - days*86400)//3600
    minutes = (secs - days*86400 - hours*3600)//60
    seconds = secs - days*86400 - hours*3600 - minutes*60
    result = ("{0} day{1}, ".format(days, "s" if days!=1 else "") if days else "") + \
    ("{0} hour{1}, ".format(hours, "s" if hours!=1 else "") if hours else "") + \
    ("{0} minute{1}, ".format(minutes, "s" if minutes!=1 else "") if minutes else "") + \
    ("{0} second{1} ".format(seconds, "s" if seconds!=1 else "") if seconds else "")
    return result

def compare():

    directory = os.path.dirname(os.path.realpath(__file__))

    oldNodes = directory + "/oldnodes.log"
    newNodes = directory + "/newnodes.log"

    oldList = {}
    newList = {}
    missingList = {}

    newProtocolInOld = 0
    newProtocolInNew = 0

    with open(oldNodes) as oldJson:
        old = json.load(oldJson)

        for key, data in old.items():

            tx = Transaction.fromRaw(key)

            oldList[tx] = SmartNode.fromRaw(tx, data)

            if int(oldList[tx].protocol) == 90025:
                newProtocolInOld += 1

    with open(newNodes) as newJson:
        new = json.load(newJson)

        for key, data in new.items():

            tx = Transaction.fromRaw(key)

            newList[tx] = SmartNode.fromRaw(tx, data)

            if int(newList[tx].protocol) == 90025 :
                newProtocolInNew += 1

    for tx, node in oldList.items():
        if tx not in newList:
            missingList[tx] = node

    missingJson = {}

    for tx, node in missingList.items():
        missingJson[str(tx)] = {'status': node.status, 'payee':node.payee, 'lastSeen' : secondsToText(time.time() - node.lastSeen) , 'uptime': secondsToText(node.activeSeconds) }

    with open(directory + "/missing.json", 'w') as outfile:
        json.dump(missingJson, outfile,indent=2)

    logger.info("Old count: {}".format(len(oldList)))
    logger.info("New count: {}".format(len(newList)))
    logger.info("Missing count: {}".format(len(missingList)))
    logger.info("90025 in old: {}".format(newProtocolInOld))
    logger.info("90025 in new: {}".format(newProtocolInNew))

if __name__ == '__main__':
    compare()
