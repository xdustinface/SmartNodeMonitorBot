import os, stat, sys
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
POS_NOT_QUALIFIED = -1
POS_CALCULATING = -2
POS_UPDATE_REQUIRED = -3
POS_TOO_NEW = -4
POS_COLLATERAL_AGE = -5


logger = logging.getLogger("smartnodes")

transactionRawCheck = re.compile("COutPoint\([\d\a-f]{64},.[\d]{1,}\)")
transactionStringCheck = re.compile("[\d\a-f]{64}-[\d]{1,}")

class Transaction(object):

    def __init__(self, txhash, txindex, block):
        self.hash = txhash
        self.index = txindex
        self.block = block

    def updateBlock(self, block):
        self.block = block

    def __str__(self):
        return '{0.hash}-{0.index}'.format(self)

    def __eq__(self, other):
        return self.hash == other.hash and\
                self.index == other.index

    def __lt__(self, other):
        # friend bool operator<(const CTxIn& a, const CTxIn& b)
        # {
        #     return a.prevout<b.prevout;
        # }
        # friend bool operator<(const COutPoint& a, const COutPoint& b)
        # {
        #     int cmp = a.hash.Compare(b.hash);
        #     return cmp < 0 || (cmp == 0 && a.n < b.n);
        # }
        # https://github.com/SmartCash/smartcash/blob/1.1.1/src/uint256.h#L45
        # https://github.com/SmartCash/smartcash/blob/1.1.1/src/primitives/transaction.h#L38
        # https://github.com/SmartCash/smartcash/blob/1.1.1/src/primitives/transaction.h#L126
        compare = util.memcmp(bytes.fromhex(self.hash), bytes.fromhex(other.hash),len(bytes.fromhex(self.hash)))
        return compare < 0 or ( compare == 0 and self.index < other.index )


    def __hash__(self):
        return hash((self.hash,self.index))

    @classmethod
    def fromRaw(cls, s):

        if transactionRawCheck.match(s):
            parts = s[10:-1].split(', ')
            return cls(parts[0], int(parts[1]), -1)

    @classmethod
    def fromString(cls, s):

        if transactionStringCheck.match(s):
            parts = s.split('-')
            return cls(parts[0], int(parts[1]), -1)

####
# Used for the sort of the last paid vector
###
class LastPaid(object):

    def __init__(self, lastPaidBlock, transaction):
        self.transaction = transaction
        self.lastPaidBlock = lastPaidBlock

    def __str__(self):
        return '[{0.lastPaidBlock}] {0.transaction}'.format(self)

    def __lt__(self, other):

        if self.lastPaidBlock != other.lastPaidBlock:
            return self.lastPaidBlock < other.lastPaidBlock

        return self.transaction < other.transaction

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
        collateral.updateBlock(row['collateral_block'])

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
            logger.info("[{}] Status updated {} => {}".format(self.collateral, self.status, status))
            update['status'] = True
            self.status = status

        if int(self.protocol) != int(data[PROTOCOL_INDEX]):
            logger.info("[{}] Protocol updated {} => {}".format(self.collateral, self.protocol, int(data[PROTOCOL_INDEX])))
            update['protocol'] = True
            self.protocol = int(data[PROTOCOL_INDEX])

        if self.payee != data[PAYEE_INDEX]:
            logger.info("[{}] Payee updated {} => {}".format(self.collateral, self.payee, data[PAYEE_INDEX]))
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

        lastPaidBlock = int(data[PAIDBLOCK_INDEX])

        if self.lastPaidBlock != lastPaidBlock:
            logger.info("[{}] LastPaid updated {} => {} - P: {}, UP: {}".format(self.collateral, self.lastPaidBlock, lastPaidBlock, self.position, self.activeSeconds))
            self.lastPaidBlock = lastPaidBlock
            self.lastPaidTime = int(data[PAIDTIME_INDEX])

            if self.lastPaidBlock != 0 and self.lastPaidBlock != -1:
                update['lastPaid'] = True

        if self.ip != data[IPINDEX_INDEX]:
            logger.info("[{}] IP updated {} => {}".format(self.collateral, self.ip, data[IPINDEX_INDEX]))
            update['ip'] = True
            self.ip = data[IPINDEX_INDEX]

        if update['timeout'] :
            logger.debug("[{}] Timeout updated {}".format(self.collateral, self.timeout))

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
            return "Initial wait time!"
        elif self.position == POS_COLLATERAL_AGE:
            return "Collateral too new!"
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

        self.nodeListSem = threading.Lock()
        self.lastBlock = 0
        self.upgradeMode = False
        self.upgradeMode = 0
        self.qualified = 0
        self.protocol_90024 = 0
        self.protocol_90025 = 0
        self.enabled_90024 = 0
        self.enabled_90025 = 0
        self.lastPaidVec = []
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

    def acquire(self):
        logger.info("SmartNodeList acquire")
        self.nodeListSem.acquire()

    def release(self):
        logger.info("SmartNodeList release")
        self.nodeListSem.release()

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

    def getCollateralAge(self, txhash):

        try:

            result = subprocess.check_output(['smartcash-cli', 'getrawtransaction',txhash, '1'])
            rawTx = json.loads(result.decode('utf-8'))

        except Exception as e:

            logging.error('Could not fetch raw transaction', exc_info=e)

        if 'error' in rawTx or not "blockhash" in rawTx:
            return -1

        blockHash = rawTx['blockhash']

        try:

            result = subprocess.check_output(['smartcash-cli', 'getblock',blockHash])
            block = json.loads(result.decode('utf-8'))

        except Exception as e:
            logging.error('Could not fetch block', exc_info=e)

        if 'error' in block or not 'height' in block:
            return -1

        return block['height']


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
            self.lastPaidVec = []
            currentTime = int(time.time())
            protocolRequirement = self.protocolRequirement()

            # Prevent reading during the calculations
            self.acquire()

            # Reset the calculation vars
            self.upgradeMode = False
            self.qualified = 0

            for key, data in nodes.items():

                collateral = Transaction.fromRaw(key)

                currentList.append(collateral)

                if collateral not in self.nodeList:

                    collateral.updateBlock(self.getCollateralAge(collateral.hash))

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

                    node = self.nodeList[collateral]
                    update = node.update(data)

                    if update['status']
                    or update['protocol']
                    or update['payee']
                    or update['lastPaid']
                    or update['timeout']:
                        self.db.updateNode(collateral,node)

                    if sum(map(lambda x: x, update.values())):

                        if self.nodeChangeCB != None:
                            self.nodeChangeCB(update, node)


            #####
            ## Check if the collateral height is already detemined
            ## if not try it!
            #####

            if not collateral.block:
                logger.info("Collateral block missing {}".format(str(collateral)))

                collateral.updateBlock(self.getCollateralAge(collateral.hash))

                if collateral.block:
                    self.db.updateNode(collateral,node)

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

            logger.info("calculatePositions start")

            #####
            ## Update vars for calculations
            #
            ####

            nodes90024 = list(filter(lambda x: x.protocol == 90024, self.nodeList.values()))
            nodes90025 = list(filter(lambda x: x.protocol == 90025, self.nodeList.values()))

            self.protocol_90024 = len(nodes90024)
            self.protocol_90025 = len(nodes90025)

            self.enabled_90024 = len(list(filter(lambda x: x.status == "ENABLED", nodes90024)))
            self.enabled_90025 = len(list(filter(lambda x: x.status == "ENABLED", nodes90025)))

            #####
            ## Update the the position indicator of the node
            #
            # CURRENTL MISSING:
            #   https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L554
            #####

            def calculatePositions(upgradeMode):

                self.lastPaidVec = []

                for collateral, node in self.nodeList.items():

                    if not upgradeMode and node.activeSeconds < self.minimumUptime():# https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L561
                        node.updatePosition(POS_TOO_NEW)
                    elif node.protocol < protocolRequirement:# https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L545
                        node.updatePosition(POS_UPDATE_REQUIRED)
                    elif (self.lastBlock - node.collateral.block) < self.enabledWithMinProtocol():
                        node.updatePosition(POS_COLLATERAL_AGE)
                    elif node.status == 'ENABLED': #https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L539
                        self.lastPaidVec.append(LastPaid(node.lastPaidBlock, collateral))
                    else:
                        node.updatePosition(POS_NOT_QUALIFIED)

                if not upgradeMode and len(self.lastPaidVec) < (self.enabledWithMinProtocol() / 3):
                    calculatePositions(True)
                    return

                self.qualified = len(self.lastPaidVec)
                self.upgradeMode = upgradeMode

            calculatePositions(False)


            #####
            ## Update positions
            #####

            self.lastPaidVec.sort()

            value = 0
            for lastPaid in self.lastPaidVec:
                value +=1
                self.nodeList[lastPaid.transaction].updatePosition(value)

            logger.info("calculatePositions done")

            self.release()

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

    def count(self, protocol = -1):

        if protocol == 90024:
            return self.protocol_90024
        elif protocol == 90025:
            return self.protocol_90025
        else:
            return len(self.nodeList)

    def protocolRequirement(self):

        if int(time.time()) <= 1519824000:
            return 90024
        else:
            return 90025

    def enabledWithMinProtocol(self):
        if self.protocolRequirement() == 90024:
            return self.enabled_90024 + self.enabled_90025
        elif self.protocolRequirement() == 90025:
            return self.enabled_90025

    def minimumUptime(self):
        # https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L561
        return self.enabledWithMinProtocol() * 156

    def enabled(self, protocol = -1):

        if protocol == 90024:
            return self.enabled_90024
        elif protocol == 90025:
            return self.enabled_90025
        else:
            return self.enabled_90024 + self.enabled_90025

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
