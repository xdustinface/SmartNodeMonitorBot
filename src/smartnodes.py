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

logger = logging.getLogger("smartnodes")

transactionCheck = re.compile("COutPoint\([\d\a-f]{64},.[\d]{1,}\)")

class Transaction(object):

    def __init__(self, txhash, txindex):
        self.hash = txhash
        self.index = txindex

    def __str__(self):
        return '{0.hash} - {0.index}'.format(self)

    def __eq__(self, other):
        return self.hash == other.hash and\
                self.index == other.index

    def __hash__(self):
        return hash((self.hash,self.index))

    @classmethod
    def fromString(cls, s):

        if transactionCheck.match(s):
            parts = s[10:-1].split(', ')
            return cls(parts[0], int(parts[1]))

class SmartNode(object):

    def __init__(self, id, tx, payee, status,\
                activeSeconds, lastPaidBlock,\
                lastPaidTime,lastSeen, protocol, ip, rank, position, timeout):

        self.id = id
        self.tx = tx
        self.payee = str(payee)
        self.status = str(status)
        self.activeSeconds = int(activeSeconds)
        self.lastPaidBlock = int(lastPaidBlock)
        self.lastPaidTime = int(lastPaidTime)
        self.lastSeen = int(lastSeen)
        self.protocol = int(protocol)
        self.rank = int(rank)
        self.ip = str(ip)
        self.position = int(position)
        self.timeout = int(timeout)

    @classmethod
    def fromRaw(cls,tx, raw):

        data = raw.split()

        return cls(None, tx,
                   data[PAYEE_INDEX],
                   data[STATUS_INDEX].replace('_','-'), # Avoid markdown problems
                   data[ACTIVE_INDEX],
                   data[PAIDBLOCK_INDEX],
                   data[PAIDTIME_INDEX],
                   data[SEEN_INDEX],
                   data[PROTOCOL_INDEX],
                   data[IPINDEX_INDEX],
                   -1,
                   -1,
                   -1 )

    @classmethod
    def fromDb(cls, row):

        tx = Transaction(row['txhash'], row['txindex'])

        return cls(row['id'],
                   tx,
                   row['payee'],
                   row['status'],
                   row['activeseconds'],
                   row['last_paid_block'],
                   row['last_paid_time'],
                   row['last_seen'],
                   row['protocol'],
                   row['ip'],
                   row['rank'],
                   row['position'],
                   row['timeout'] )

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
            self.protocol = data[PROTOCOL_INDEX]

        if self.payee != data[PAYEE_INDEX]:
            update['payee'] = True
            self.payee = data[PAYEE_INDEX]

        self.lastSeen = int(data[SEEN_INDEX])

        if ( int(time.time()) - self.lastSeen ) > 1800:

            if ( self.timeout == -1 or self.timeout and\
              ( int(time.time()) - self.timeout ) > 300 ) and\
              self.status == 'ENABLED':
                self.timeout = int(time.time())
                update['timeout'] = True

        elif self.timeout:
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

    def updateRank(self, rank):
        self.rank = int(rank)

    def updatePosition(self, position):

        if self.position != position:
            self.position = position
            return True

        return False

class SmartNodeList(object):

    def __init__(self, db):

        self.lastBlock = 0
        self.nodelist = {}

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
                self.nodelist[node.tx] = node

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
                self.pushAdmin("No valid nodelist")
                return

            if not self.isValidDeamonResponse(info):
                self.pushAdmin("No valid network info")
                return

            if "blocks" in info:
                self.lastBlock = info["blocks"]

            currentList = []
            positionIndicators = {}


            for key, data in nodes.items():

                tx = Transaction.fromString(key)

                currentList.append(tx)

                if tx not in self.nodelist:

                    logger.info("Add node {}".format(key))
                    insert = SmartNode.fromRaw(tx, data)

                    id = self.db.addNode(tx,insert)

                    if id:
                        insert.id = id
                        self.nodelist[tx] = insert
                        newNodes.append(id)

                        logger.info(" => added with id {}".format(insert.id))
                    else:
                        logger.error("Could not add the node {}".format(key))

                else:

                    sync = False

                    node = self.nodelist[tx]
                    update = node.update(data)

                    if update['status'] :
                        logger.info("[{}] Status updated {}".format(node.payee, node.status))
                        sync = True

                    if update['protocol'] :
                        logger.info("[{}] Protocol updated {}".format(node.payee, node.protocol))

                    if update['payee']:
                        logger.info("[{}] Payee updated {}".format(txid, node.payee))
                        sync = True

                    if update['lastPaid'] :
                        logger.info("[{}] LastPaid updated {}".format(node.payee, node.lastPaidBlock))
                        sync = True

                    if update['ip'] :
                        logger.info("[{}] IP updated {}".format(node.payee, node.ip))

                    if update['position'] :
                        logger.debug("[{}] Position updated {}".format(node.payee, node.position))

                    if update['timeout'] :
                        logger.debug("[{}] Timeout updated {}".format(node.payee, node.timeout))
                        sync = True

                    if sync:
                        self.db.updateNode(tx,node)

                    if sum(map(lambda x: x, update.values())):
                        #logger.info("Write to DB {}".format(txid))

                        if self.nodeChangeCB != None:
                            self.nodeChangeCB(update, node)

                #####
                ## Update the the position indicator of the node
                #####
                
                node = self.nodelist[tx]

                # Use the active seconds per default
                posititionTime = node.activeSeconds
                diff = int(time.time()) - node.lastPaidTime

                # If the node got paid we need to decide further
                if node.lastPaidTime and diff < node.activeSeconds:
                    posititionTime = diff

                positionIndicators[tx] = posititionTime

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

                dbNodes = self.db.getNodes(('id','txhash','txindex'))

                for dbNode in dbNodes:

                    tx = Transaction(dbNode['txhash'],dbNode['txindex'])

                    if not tx in currentList:
                        logger.info("Remove node {}".format(dbNode))
                        removedNodes.append(dbNode['id'])
                        self.db.deleteNode(tx)

                if len(removedNodes) != (dbCount - len(nodes)):
                    logger.warning("Remove nodes - something messed up.")

                if self.networkCB:
                    self.networkCB(removedNodes, False)
            #####
            ## Update positions
            #####

            positions = sorted(positionIndicators, key=positionIndicators.__getitem__)
            value = 0
            for tx in positions:
                value +=1
                if self.nodelist[tx].updatePosition(value):
                    self.db.updateNode(tx,self.nodelist[tx])

        self.updateRanks()

        self.startTimer()

    def updateRanks(self):

        if not self.chainSynced or not self.nodeListSynced:
            return

        ranks = None

        try:

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

                tx = Transaction.fromString(key)

                if tx not in self.nodelist:
                    logger.error("Could not assign rank, node not available {}".format(key))
                else:
                    self.nodelist[tx].updateRank(data)

    def count(self):
        return len(self.nodelist)

    def enabled(self):
        return sum(list(map(lambda x: x.status == "ENABLED", self.nodelist.values())))

    def getNodeByPayee(self, payee):
        return self.db.getNodeByPayee(payee)

    def getNodeByIp(self, ip):
        return self.db.getNodeByIp(ip)

    def getNodeById(self, id):

        for node in self.nodelist.values():
            if node.id == id:
                return node

        return None

    def getNodeByTx(self, tx):
        return self.nodelist[tx] if txid in self.nodelist else None
