import os, stat
import re
import subprocess
import json
import time
import csv
from src import util
import logging
import threading
import re

# Index assignment of the "smartnodelist full"
STATUS_INDEX = 0
PROTOCOL_INDEX = 1
PAYEE_INDEX = 2
SEEN_INDEX = 3
ACTIVE_INDEX = 4
PAIDTIME_INDEX = 5
PAIDBLOCK_INDEX = 6
IPINDEX_INDEX = 7

# Smartnode position states
POS_CALCULATING = -1
POS_UPDATE_REQUIRED = -2
POS_TOO_NEW = -3
POS_NOT_QUALIFIED = -4

logger = logging.getLogger("smartnodes")

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

        self.collateral = kwargs['collateral']
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
        self.position = POS_CALCULATING


    @classmethod
    def fromRaw(cls,collateral, raw):

        data = raw.split()

        return cls(collateral = collateral,
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

        collateral = Transaction.fromString(row['collateral'])

        return cls(collateral = collateral,
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

    def update(self, raw):

        update = {'status' : False,
                  'payee':False,
                  'timeout' : False,
                  'lastPaid' : False,
                  'protocol' : False,
                  'ip' : False
                 }

        data = raw.split()

        status = data[STATUS_INDEX].replace('_','-') # replace _ with - to avoid md problems

        if self.status != status:
            update['status'] = True
            self.status = status

        if int(self.protocol) != int(data[PROTOCOL_INDEX]):
            update['protocol'] = True
            self.protocol = int(data[PROTOCOL_INDEX])

        if self.payee != data[PAYEE_INDEX]:
            update['payee'] = True
            self.payee = data[PAYEE_INDEX]

        self.lastSeen = int(data[SEEN_INDEX])
        lastSeenDiff = ( int(time.time()) - self.lastSeen )
        if lastSeenDiff > 1800 and\
            lastSeenDiff < 3900: # > 30min < 65min

            if ( self.timeout == -1 or \
              ( int(time.time()) - self.timeout ) > 300 ) and\
              self.status == 'ENABLED':
                self.timeout = int(time.time())
                update['timeout'] = True

        elif self.timeout != -1 and self.status == 'ENABLED':
            self.timeout = -1
            update['timeout'] = True

        self.activeSeconds = int(data[ACTIVE_INDEX])

        if self.lastPaidBlock != int(data[PAIDBLOCK_INDEX]):

            self.lastPaidBlock = int(data[PAIDBLOCK_INDEX])
            self.lastPaidTime = int(data[PAIDTIME_INDEX])

            if self.lastPaidBlock != 0 and self.lastPaidBlock != -1:
                update['lastPaid'] = True

        if self.ip != data[IPINDEX_INDEX]:
            update['ip'] = True
            self.ip = data[IPINDEX_INDEX]

        return update

    def payoutBlockString(self):

        if self.lastPaidBlock > 0:
            return str(self.lastPaidBlock)

        return "No payout yet."

    def payoutTimeString(self):

        if self.lastPaidTime > 0:
            return util.secondsToText( int(time.time()) - self.lastPaidTime )

        return "No payout yet."

    def positionString(self):

        if self.position == POS_CALCULATING:
            return "Calculating..."
        elif self.position == POS_UPDATE_REQUIRED:
            return "Node update required!"
        elif self.position == POS_TOO_NEW:
            return "Initial wait time."
        elif self.position == POS_NOT_QUALIFIED:
            return "Not qualified!"
        else:
            return str(self.position)


    def updateRank(self, rank):
        self.rank = int(rank)

    def updatePosition(self, position):

        if self.position != position:
            self.position = position
            logger.debug("[{}] Position updated {}".format(self.payee, self.position))
            return True

        return False

class SmartNodeList(object):

    def __init__(self, db):

        self.lastBlock = 0
        self.nodeList = {}

        self.chainSynced = False
        self.nodeListSynced = False
        self.winnersListSynced = False

        self.db = db

        self.nodeChangeCB = None
        self.networkCB = None
        self.adminCB = None

        self.load()

        self.startTimer()

    def pushAdmin(self, message):

        if self.adminCB:
            self.adminCB(message)

    def startTimer(self):
        self.timer = threading.Timer(30, self.updateList)
        self.timer.start()

    def load(self):

        dbList = self.db.getNodes()

        for entry in dbList:
                node = SmartNode.fromDb(entry)
                self.nodeList[node.collateral] = node

    def validateAddress(self, address):

        cleanAddress = re.sub('[^A-Za-z0-9]+', '', address)

        validate = None

        try:

            result = subprocess.check_output(['smartcash-cli', 'validateaddress',cleanAddress])
            validate = json.loads(result.decode('utf-8'))

        except Exception as e:

            logging.error('Error at %s', 'json parse', exc_info=e)

        else:

            if "isvalid" in validate and validate["isvalid"] == True:
                return True

        return False

    def isValidDeamonResponse(self,json):

        if 'error' in json:
            logger.warning("could not update list {}".format(json))
            self.startTimer()
            return False

        return True

    def synced(self):
        return self.chainSynced and self.nodeListSynced and self.winnersListSynced

    def updateSyncState(self):

        status = None

        try:

            statusResult = subprocess.check_output(['smartcash-cli', 'snsync','status'])
            status = json.loads(statusResult.decode('utf-8'))

        except Exception as e:

                logging.error('Error at %s', 'isSynced', exc_info=e)

                self.pushAdmin("Exception at isSynced")

                raise RuntimeError("Could not fetch synced status.")
        else:

            if 'error' in status:
                self.pushAdmin("No valid sync state")
                raise RuntimeError("Error in sync list {}".format(statusResult))

            # {
            #   "AssetID": 999,
            #   "AssetName": "SMARTNODE_SYNC_FINISHED",
            #   "Attempt": 0,
            #   "IsBlockchainSynced": true,
            #   "IsMasternodeListSynced": true,
            #   "IsWinnersListSynced": true,
            #   "IsSynced": true,
            #   "IsFailed": false
            # }

            if 'IsBlockchainSynced' in status:
                self.chainSynced = status['IsBlockchainSynced']
            else:
                raise RuntimeError("IsBlockchainSynced missing.")

            if  'IsMasternodeListSynced' in status:
                self.nodeListSynced = status['IsMasternodeListSynced']
            else:
                raise RuntimeError("IsMasternodeListSynced missing.")

            if  'IsWinnersListSynced' in status:
                self.winnersListSynced = status['IsWinnersListSynced']
            else:
                raise RuntimeError("IsWinnersListSynced missing.")

    def updateList(self):

        try:
            self.updateSyncState()
        except RuntimeError as e:
            logger.error("updateList sync exception: {}".format(e))
            self.startTimer()
            return

        else:

            if not self.chainSynced or not self.nodeListSynced or not self.winnersListSynced:
                logger.error("Not synced! C {}, N {} W {}".format(self.chainSynced, self.nodeListSynced, self.winnersListSynced))
                self.startTimer()
                return

        newNodes = []

        nodes = None
        info = None

        try:

            infoResult = subprocess.check_output(['smartcash-cli', 'getinfo'])
            info = json.loads(infoResult.decode('utf-8'))

            nodeResult = subprocess.check_output(['smartcash-cli', 'smartnodelist','full'])
            nodes = json.loads(nodeResult.decode('utf-8'))

        except Exception as e:

                logging.error('Error at %s', 'update list', exc_info=e)

                self.pushAdmin("Error at updateList")

        else:

            if not self.isValidDeamonResponse(nodes):
                self.pushAdmin("No valid nodeList")
                return

            if not self.isValidDeamonResponse(info):
                self.pushAdmin("No valid network info")
                return

            if "blocks" in info:
                self.lastBlock = info["blocks"]

            currentList = []
            positionIndicators = {}
            currentTime = int(time.time())
            minimumUptime = self.minimumUptime()
            protocolRequirement = self.protocolRequirement()

            for key, data in nodes.items():

                collateral = Transaction.fromRaw(key)

                currentList.append(collateral)

                if collateral not in self.nodeList:

                    logger.info("Add node {}".format(key))
                    insert = SmartNode.fromRaw(collateral, data)

                    id = self.db.addNode(collateral,insert)

                    if id:
                        self.nodeList[collateral] = insert
                        newNodes.append(collateral)

                        logger.debug(" => added with collateral {}".format(insert.collateral))
                    else:
                        logger.error("Could not add the node {}".format(key))

                else:

                    sync = False

                    node = self.nodeList[collateral]
                    update = node.update(data)

                    if update['status'] :
                        logger.info("[{}] Status updated {}".format(node.payee, node.status))
                        sync = True

                    if update['protocol'] :
                        logger.info("[{}] Protocol updated {}".format(node.payee, node.protocol))
                        sync = True

                    if update['payee']:
                        logger.info("[{}] Payee updated {}".format(collateral, node.payee))
                        sync = True

                    if update['lastPaid'] :
                        logger.info("[{}] LastPaid updated {}".format(node.payee, node.lastPaidBlock))
                        sync = True

                    if update['ip'] :
                        logger.info("[{}] IP updated {}".format(node.payee, node.ip))

                    if update['timeout'] :
                        logger.debug("[{}] Timeout updated {}".format(node.payee, node.timeout))
                        sync = True

                    if sync:
                        self.db.updateNode(collateral,node)

                    if sum(map(lambda x: x, update.values())):

                        if self.nodeChangeCB != None:
                            self.nodeChangeCB(update, node)

                #####
                ## Update the the position indicator of the node
                #####

                node = self.nodeList[collateral]

                if node.activeSeconds < minimumUptime:
                    node.updatePosition(POS_TOO_NEW)
                elif node.protocol < protocolRequirement:
                    node.updatePosition(POS_UPDATE_REQUIRED)
                elif node.status == 'ENABLED':

                    positionTime = None

                    # If the node got paid we need need to decide further
                    if node.lastPaidTime:

                        # Use the gab between the between now and the last paid
                        gap = currentTime - node.lastPaidTime

                        # Check if the gap is smaller then the active seconds
                        if gap < node.activeSeconds:
                            # If so, use the gap since this means the node is
                            # already active longer then the last paid time
                            positionTime = gap
                        else:
                            # If the gap is smaller this means the node got paid
                            # already but has become restarted for any reason
                            positionTime = node.activeSeconds
                    else:
                        # If not just use the active seconds.
                        positionTime = node.activeSeconds

                    positionIndicators[collateral] = positionTime

                else:
                    node.updatePosition(POS_NOT_QUALIFIED)

            #####
            ## Invoke the callback if we have new nodes
            #####

            if len(newNodes) and self.networkCB:

                self.networkCB(newNodes, True)

                logger.info("Created: {}".format(len(nodes.values())))
                logger.info("Enabled: {}\n".format(sum(map(lambda x: x.split()[STATUS_INDEX]  == "ENABLED", list(nodes.values())))))


            #####
            ## Remove nodes from the DB that are not longer in the global list
            #####

            dbCount = self.db.getNodeCount()

            if dbCount > len(nodes):

                removedNodes = []

                logger.warning("Unequal node count - DB {}, CLI {}".format(dbCount,len(nodes)))

                dbNodes = self.db.getNodes(['collateral'])

                for dbNode in dbNodes:

                    collateral = Transaction.fromString(dbNode['collateral'])

                    if not collateral in currentList:
                        logger.info("Remove node {}".format(dbNode))
                        removedNodes.append(dbNode['collateral'])
                        self.db.deleteNode(collateral)
                        self.nodeList.pop(collateral,None)

                if len(removedNodes) != (dbCount - len(nodes)):
                    logger.warning("Remove nodes - something messed up.")

                if self.networkCB:
                    self.networkCB(removedNodes, False)
            #####
            ## Update positions
            #####

            positions = sorted(positionIndicators, key=positionIndicators.__getitem__, reverse=True)
            value = 0
            for collateral in positions:
                value +=1
                self.nodeList[collateral].updatePosition(value)

        #####
        # Disabled rank updates due to confusion of the users
        #self.updateRanks()
        #####
        self.startTimer()

    def updateRanks(self):

        if not self.chainSynced or not self.nodeListSynced:
            return

        ranks = None

        try:

            rankResult = subprocess.check_output(['smartcash-cli', 'smartnodelist','rank'])
            rankResult = subprocess.check_output(['smartcash-cli', 'smartnodelist','rank'])
            ranks = json.loads(rankResult.decode('utf-8'))

        except Exception as e:
                logging.error('Error at %s', 'update ranks', exc_info=e)
                self.pushAdmin("Exception at ranks")
        else:

            if 'error' in ranks:
                logger.warning("could not update ranks {}".format(rankResult))
                self.pushAdmin("No valid ranklist")
                return

            for key, data in ranks.items():

                rank = data

                collateral = Transaction.fromRaw(key)

                if collateral not in self.nodeList:
                    logger.error("Could not assign rank, node not available {}".format(key))
                else:
                    self.nodeList[collateral].updateRank(data)

    def count(self):
        return len(self.nodeList)

    def protocolRequirement(self):

        if time.time() < 1519824000:
            return 90024
        else:
            return 90025

    def enabledWithMinProtocol(self):
        return self.enabled(self.protocolRequirement())

    def minimumUptime(self):
        return self.enabledWithMinProtocol() * 156 # https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L561

    def qualified(self):
        return sum(list(map(lambda x: x.status == "ENABLED" and x.protocol >= protocol and x.activeSeconds >= self.minimumUptime(), self.nodeList.values())))

    def enabled(self, protocol = -1):
        return sum(list(map(lambda x: x.status == "ENABLED" and x.protocol >= protocol, self.nodeList.values())))

    def getNodeByIp(self, ip):
        return self.db.getNodeByIp(ip)

    def getNodeCountForProtocol(self, protocol):
        return self.db.getNodeCount('protocol={}'.format(protocol))

    def getNodes(self, collaterals):

        nodes = []

        for c in collaterals:

            collateral = None

            if isinstance(c,Transaction):
                collateral = collateral
            else:
                collateral = Transaction.fromString(c)
                logger.debug("collateral from string ")

            if collateral in self.nodeList:
                nodes.append(self.nodeList[collateral])

        return nodes
