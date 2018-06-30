##
# Part of `SmartNodeMonitorBot`
#
# Copyright 2018 dustinface
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
##

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

from smartcash.rpc import *

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
        if lastSeenDiff > 3600 and\
            lastSeenDiff < 7200: # > 60min < 120min

            if ( self.timeout == -1 or \
              ( int(time.time()) - self.timeout ) > 600 ) and\
              self.status == 'ENABLED':
                self.timeout = int(time.time())
                update['timeout'] = True

        elif self.timeout != -1 and self.status == 'ENABLED':
            self.timeout = -1
            update['timeout'] = True

        self.activeSeconds = int(data[ACTIVE_INDEX])

        lastPaidBlock = int(data[PAIDBLOCK_INDEX])

        if self.lastPaidBlock != lastPaidBlock and lastPaidBlock != 0:
            logger.info("[{}] Reward {} - Last: {}, P: {}, UP: {}".format(self.collateral, lastPaidBlock, self.payoutTimeString(), self.position, util.secondsToText(self.activeSeconds)))
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

    def positionString(self, minimumUptime, top10 = None):

        if self.position == POS_CALCULATING:
            return "Calculating..."
        elif self.position == POS_UPDATE_REQUIRED:
            return "Node update required!"
        elif self.position == POS_TOO_NEW:
            leftMessage = util.secondsToText(minimumUptime - self.activeSeconds)
            return "Initial wait time! <b>{}<b> left".format(leftMessage)
        elif self.position == POS_COLLATERAL_AGE:
            return "Collateral too new!"
        elif self.position == POS_NOT_QUALIFIED:
            return "Not qualified!"
        elif top10 and self.position <= top10:
            return str(self.position) + " - <b>Payout zone<b>"
        else:
            return str(self.position)

    def cleanIp(self):
        return self.ip.replace(':9678','')

    def updateRank(self, rank):
        self.rank = int(rank)

    def updatePosition(self, position):

        if self.position != position:
            self.position = position
            #logger.debug("[{}] Position updated {}".format(self.payee, self.position))
            return True

        return False

class SmartNodeList(object):

    def __init__(self, db, rpcConfig):

        self.running = False
        self.nodeListSem = threading.Lock()
        self.lastBlock = 0
        self.remainingUpgradeModeDuration = None
        self.qualifiedUpgrade = -1
        self.qualifiedNormal = 0
        self.protocol_90025 = 0
        self.protocol_90026 = 0
        self.enabled_90025 = 0
        self.enabled_90026 = 0
        self.lastPaidVec = []
        self.nodes = {}

        self.syncedTime = -1
        self.waitAfterSync = 1800
        self.chainSynced = False
        self.nodeListSynced = False
        self.winnersListSynced = False

        self.db = db
        self.rpc = SmartCashRPC(rpcConfig)

        self.nodeChangeCB = None
        self.networkCB = None
        self.adminCB = None

        dbList = self.db.getNodes()

        for entry in dbList:
                node = SmartNode.fromDb(entry)
                self.nodes[node.collateral] = node

    def __enter__(self):
        logger.debug("Wait for enter")
        self.acquire()
        logger.debug("Entered")
        return self

    def __exit__(self, type, value, traceback):
        logger.debug("Exit")
        self.release()

    def acquire(self):
        logger.info("SmartNodeList acquire")
        self.nodeListSem.acquire()

    def release(self):
        logger.info("SmartNodeList release")
        self.nodeListSem.release()

    def start(self):

        if not self.running:
            logger.info("Start SmartNodeList!")
            self.running = True
            self.startTimer(5)
        else:
            raise Exception("SmartNodeList already started!")

    def stop(self):

        if self.running:
            # Lock the list
            self.acquire()
            # Inidicate the end
            self.running = False
            # Stop the timer
            self.timer.cancel()
            # Then leave it locked..
            logger.info("Stopped!")

    def pushAdmin(self, message):

        if self.adminCB:
            self.adminCB(message)

    def startTimer(self, timeout = 30):

        if self.running:
            self.timer = threading.Timer(timeout, self.update)
            self.timer.daemon = True
            self.timer.start()

    def synced(self):
        return self.chainSynced and self.nodeListSynced and self.winnersListSynced and self.lastBlock

    def update(self):

        if self.updateSyncState():
            logger.info("Start list update!")
            self.updateProtocolRequirement()
            self.updateList()
            # Disabled rank updates due to confusion of the users
            #self.updateRanks()

        self.startTimer()

    def getCollateralAge(self, txhash):

        rawTx = self.rpc.getRawTransaction(txhash)

        if rawTx.error:
            logging.error('Could not fetch raw transaction: {}'.format(str(rawTx.error)))
            return -1

        if not "blockhash" in rawTx.data:
            logger.error("getCollateralAge missing blockhash{}".format(rawTx.data))
            return -1

        block = self.rpc.getBlockByHash(rawTx.data['blockhash'])

        if block.error:
            logging.error('Could not fetch block: {}'.format(str(block.error)))
            return -1

        if not 'height' in block.data:
            logger.error("getCollateralAge missing height: {}".format(block.data))
            return -1

        return block.data['height']

    def updateProtocolRequirement(self):

        status = self.rpc.raw("spork",['active'])

        if status.error:
            msg = "updateProtocolRequirement failed: {}".format(str(status.error))
            logging.error(msg)
            self.pushAdmin(msg)
            return False

        self.spork10Active = status.data['SPORK_10_SMARTNODE_PAY_UPDATED_NODES']
        logger.info("SPORK_10_SMARTNODE_PAY_UPDATED_NODES {}".format(self.spork10Active))

        return True

    def updateSyncState(self):

        status = self.rpc.getSyncStatus()

        if status.error:
            msg = "updateSyncState failed: {}".format(str(status.error))
            logging.error(msg)
            self.pushAdmin(msg)

            # Reset wait time for next sync
            self.syncedTime = -2

            return False

        self.chainSynced = status.data['IsBlockchainSynced']
        self.nodeListSynced = status.data['IsSmartnodeListSynced']
        self.winnersListSynced = status.data['IsWinnersListSynced']

        return True

    def updateList(self):

        if not self.chainSynced or not self.nodeListSynced or not self.winnersListSynced:
            logger.error("Not synced! C {}, N {} W {}".format(self.chainSynced, self.nodeListSynced, self.winnersListSynced))

            # If nodelist or winnerslist was out of sync
            # wait 5 minutes after sync is done
            # to prevent false positive timeout notifications
            if not self.nodeListSynced or not self.winnersListSynced:
                self.syncedTime = -2

            return False

        if self.syncedTime == -2:
            self.syncedTime = time.time()
            logger.info("Synced now! Wait {} minutes and then start through...".format(self.waitAfterSync / 60))
            return False

        # Wait 5 minutes here to prevent timeout notifications. Past showed that
        # the lastseen times are not good instantly after sync.
        elif self.syncedTime > -1 and (time.time() - self.syncedTime) < self.waitAfterSync:
            logger.info("After sync wait {}".format(util.secondsToText(time.time() - self.syncedTime)))
            return False

        newNodes = []
        removedNodes = []

        info = self.rpc.getInfo()
        rpcNodes = self.rpc.getSmartNodeList('full')

        if info.error:
            msg = "updateList getInfo: {}".format(str(info.error))
            logging.error(msg)
            self.pushAdmin(msg)
            return False
        elif not "blocks" in info.data:
            self.pushAdmin("Block info missing?!")
        else:
            self.lastBlock = info.data["blocks"]

        if rpcNodes.error:
            msg = "updateList getSmartNodeList: {}".format(str(rpcNodes.error))
            logging.error(msg)
            self.pushAdmin(msg)
            return False

        rpcNodes = rpcNodes.data
        node = None

        currentList = []
        self.lastPaidVec = []
        currentTime = int(time.time())
        protocolRequirement = self.protocolRequirement()

        dbCount = self.db.getNodeCount()

        # Prevent mass deletion of nodes if something is wrong
        # with the fetched nodelist.
        if dbCount and len(rpcNodes) and ( dbCount / len(rpcNodes) ) > 1.25:
            self.pushAdmin("Node count differs too much!")
            logger.warning("Node count differs too much! - DB {}, CLI {}".format(dbCount,len(rpcNodes)))
            return False

        # Prevent reading during the calculations
        self.acquire()

        # Reset the calculation vars
        self.qualifiedNormal = 0

        for key, data in rpcNodes.items():

            collateral = Transaction.fromRaw(key)

            currentList.append(collateral)

            if collateral not in self.nodes:

                collateral.updateBlock(self.getCollateralAge(collateral.hash))

                logger.info("Add node {}".format(key))
                insert = SmartNode.fromRaw(collateral, data)

                id = self.db.addNode(collateral,insert)

                if id:
                    self.nodes[collateral] = insert
                    newNodes.append(collateral)

                    logger.debug(" => added with collateral {}".format(insert.collateral))
                else:
                    logger.error("Could not add the node {}".format(key))

            else:

                node = self.nodes[collateral]
                collateral = node.collateral
                update = node.update(data)

                if update['status']\
                or update['protocol']\
                or update['payee']\
                or update['lastPaid']\
                or update['ip']\
                or update['timeout']:
                    self.db.updateNode(collateral,node)

                if sum(map(lambda x: x, update.values())):

                    if self.nodeChangeCB != None:
                        self.nodeChangeCB(update, node)

            #####
            ## Check if the collateral height is already detemined
            ## if not try it!
            #####

            if collateral.block <= 0:
                logger.info("Collateral block missing {}".format(str(collateral)))

                collateral.updateBlock(self.getCollateralAge(collateral.hash))

                if collateral.block > 0:
                    self.db.updateNode(collateral,node)
                else:
                    logger.warning("Could not fetch collateral block {}".format(str(collateral)))

        #####
        ## Remove nodes from the DB that are not longer in the global list
        #####

        dbCount = self.db.getNodeCount()

        if dbCount > len(rpcNodes):

            logger.warning("Unequal node count - DB {}, CLI {}".format(dbCount,len(rpcNodes)))

            dbNodes = self.db.getNodes(['collateral'])

            for dbNode in dbNodes:

                collateral = Transaction.fromString(dbNode['collateral'])

                if not collateral in currentList:
                    logger.info("Remove node {}".format(dbNode))
                    removedNodes.append(dbNode['collateral'])
                    self.db.deleteNode(collateral)
                    self.nodes.pop(collateral,None)

            if len(removedNodes) != (dbCount - len(rpcNodes)):
                err = "Remove nodes - something messed up."
                self.pushAdmin(err)
                logger.error(err)

        logger.info("calculatePositions start")

        #####
        ## Update vars for calculations
        #
        ####

        nodes90025 = list(filter(lambda x: x.protocol == 90025, self.nodes.values()))
        nodes90026 = list(filter(lambda x: x.protocol == 90026, self.nodes.values()))

        self.protocol_90025 = len(nodes90025)
        self.protocol_90026 = len(nodes90026)

        self.enabled_90025 = len(list(filter(lambda x: x.status == "ENABLED", nodes90025)))
        self.enabled_90026 = len(list(filter(lambda x: x.status == "ENABLED", nodes90026)))

        #####
        ## Update the the position indicator of the node
        #
        # CURRENTL MISSING:
        #   https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L554
        #####

        def calculatePositions(upgradeMode):

            self.lastPaidVec = []

            for collateral, node in self.nodes.items():

                if (self.lastBlock - node.collateral.block) < self.minimumConfirmations():
                    node.updatePosition(POS_COLLATERAL_AGE)
                elif node.protocol < protocolRequirement:# https://github.com/SmartCash/Core-Smart/blob/44b5543d0e05be27405bdedcc72b4361cee8129d/src/smartnode/smartnodeman.cpp#L551
                    node.updatePosition(POS_UPDATE_REQUIRED)
                elif not upgradeMode and node.activeSeconds < self.minimumUptime():# https://github.com/SmartCash/Core-Smart/blob/44b5543d0e05be27405bdedcc72b4361cee8129d/src/smartnode/smartnodeman.cpp#L557
                    node.updatePosition(POS_TOO_NEW)
                elif node.status != 'ENABLED': # https://github.com/SmartCash/Core-Smart/blob/44b5543d0e05be27405bdedcc72b4361cee8129d/src/smartnode/smartnodeman.cpp#L548
                    node.updatePosition(POS_NOT_QUALIFIED)
                else:
                    self.lastPaidVec.append(LastPaid(node.lastPaidBlock, collateral))

            if not upgradeMode and len(self.lastPaidVec) < (self.enabledWithMinProtocol() / 3):
                self.qualifiedUpgrade = len(self.lastPaidVec)
                logger.info("Start upgradeMode calculation: {}".format(self.qualifiedUpgrade))
                calculatePositions(True)
                return

            if not upgradeMode:
                self.qualifiedUpgrade = -1

            self.qualifiedNormal = len(self.lastPaidVec)

        calculatePositions(False)


        #####
        ## Update positions
        #####

        self.lastPaidVec.sort()

        value = 0
        for lastPaid in self.lastPaidVec:
            value +=1
            self.nodes[lastPaid.transaction].updatePosition(value)

        logger.info("calculatePositions done")

        if self.qualifiedUpgrade != -1:
            logger.info("calculateUpgradeModeDuration start")
            self.remainingUpgradeModeDuration = self.calculateUpgradeModeDuration()
            logger.info("calculateUpgradeModeDuration done {}".format("Success" if self.remainingUpgradeModeDuration else "Error?"))

        self.release()

        #####
        ## Invoke the callback if we have new nodes or nodes left
        #####

        if len(newNodes) and self.networkCB:
            self.networkCB(newNodes, True)

        if len(removedNodes) and self.networkCB:
            self.networkCB(removedNodes, False)

        return True

    def updateRanks(self):

        if not self.synced():
            return False

        ranks = self.rpc.getSmartNodeList('rank')

        if ranks.error:
            msg = "updateRanks getSmartNodeList: {}".format(str(ranks.error))
            logging.error(msg)
            self.pushAdmin(msg)
            return False

        for key, data in ranks.items():

            rank = data

            collateral = Transaction.fromRaw(key)

            if collateral not in self.nodes:
                logger.error("Could not assign rank, node not available {}".format(key))
            else:
                self.nodes[collateral].updateRank(data)

        return True

    def count(self, protocol = -1):

        if protocol == 90025:
            return self.protocol_90025
        elif protocol == 90026:
            return self.protocol_90026
        else:
            return len(self.nodes)

    def protocolRequirement(self):

        if not self.spork10Active:
            return 90025
        else:
            return 90026

    def enabledWithMinProtocol(self):
        if self.protocolRequirement() == 90025:
            return self.enabled_90025 + self.enabled_90026
        elif self.protocolRequirement() == 90026:
            return self.enabled_90026

    def minimumRequirementsScale(self):

        if self.lastBlock >= 545005:
            return 5 # 10 nodes every other block from here

        return 1

    def minimumUptime(self):
        #https://github.com/SmartCash/Core-Smart/blob/44b5543d0e05be27405bdedcc72b4361cee8129d/src/smartnode/smartnodeman.cpp#L557
        return ( self.enabledWithMinProtocol() * 55 ) / self.minimumRequirementsScale()

    def minimumConfirmations(self):
        #https://github.com/SmartCash/Core-Smart/blob/44b5543d0e05be27405bdedcc72b4361cee8129d/src/smartnode/smartnodeman.cpp#L560
        return self.enabledWithMinProtocol() / self.minimumRequirementsScale()

    def enabled(self, protocol = -1):

        if protocol == 90025:
            return self.enabled_90025
        elif protocol == 90026:
            return self.enabled_90026
        else:
            return self.enabled_90025 + self.enabled_90026

    def calculateUpgradeModeDuration(self):

        # Start with an accuracy of 5 nodes.
        # Will become increased if it takes too long
        accuracy = 20
        # Minimum required nodes to continue with normal mode
        requiredNodes = int(self.enabledWithMinProtocol() / 3)
        # Get the max active seconds to determine a start point
        currentCheckTime = max(list(map(lambda x: x.activeSeconds if x.protocol >= self.protocolRequirement() and x.status == 'ENABLED' else 0, self.nodes.values())))
        logger.debug("Maximum uptime {}".format(currentCheckTime))
        # Start value
        step = currentCheckTime * 0.5
        currentCheckTime -= step

        # Start time for accuracy descrease if needed
        start = int(time.time())
        rounds = 1

        calcCount = None

        while accuracy < 1000:

            step *= 0.5

            calcCount = len(list(filter(lambda x: x.protocol == self.protocolRequirement() and\
                                                  x.status == 'ENABLED' and\
                                                  (self.lastBlock - x.collateral.block) >= self.minimumConfirmations() and\
                                                  x.activeSeconds > currentCheckTime, self.nodes.values() )))

            logger.debug("Current count: {}".format(calcCount))
            logger.debug("Current time: {}".format(currentCheckTime))
            logger.debug("Current accuracy: {}".format(accuracy))
            logger.debug("Current accuracy matched: {}\n".format(abs(requiredNodes - calcCount)))

            if int(time.time()) - start >= 2 * rounds:
                rounds += 1
                accuracy += 20

            if abs(requiredNodes - calcCount) < accuracy:
                logger.info("Final accuracy {}".format(accuracy))
                logger.info("Final accuracy matched {}".format(abs(requiredNodes - calcCount)))
                logger.info("Remaining duration: {}".format( util.secondsToText((self.minimumUptime() - currentCheckTime))))
                logger.info("CalcTime: {}, Rounds: {}".format( int(time.time()) - start,rounds))
                return self.minimumUptime() - currentCheckTime
            elif calcCount > requiredNodes:
                currentCheckTime += step
            else:
                currentCheckTime -= step

        logger.warning("Could not determine duration?!")
        logger.warning("Final accuracy {}".format(accuracy))
        logger.warning("Final accuracy before step out {}".format(abs(requiredNodes - calcCount)))

        return None

    def getNodeByIp(self, ip):

        if not ':9678' in ip:
            ip += ":9678"

        filtered = list(filter(lambda x: x.ip == ip, self.nodes.values()))

        if len(filtered) == 1:
            return filtered[0]

        return None

    def getNodesByPayee(self, payee):
        return list(filter(lambda x: x.payee == payee, self.nodes.values()))

    def getNodeCountForProtocol(self, protocol):
        return self.db.getNodeCount('protocol={}'.format(protocol))

    def getNodes(self, collaterals):

        filtered = []

        for c in collaterals:

            collateral = None

            if isinstance(c,Transaction):
                collateral = collateral
            else:
                collateral = Transaction.fromString(c)
                logger.debug("collateral from string ")

            if collateral in self.nodes:
                filtered.append(self.nodes[collateral])

        return filtered

    def lookup(self, ip):

        result = None

        node = self.getNodeByIp(ip)

        logger.info("lookup {} - found {}".format(ip, node != None))

        if node:

            result = {}

            uptimeString = None

            if node.activeSeconds > 0:
                uptimeString = util.secondsToText(node.activeSeconds)
            else:
                uptimeString = "No uptime!"

            result['ip'] = node.cleanIp()
            result['position'] = node.position < self.enabledWithMinProtocol() * 0.1 and node.position > 0
            result['position_string'] = node.positionString(self.minimumUptime())

            result['status'] = node.status == 'ENABLED'
            result['status_string'] = "{}".format(node.status)

            result['uptime'] = node.activeSeconds >= self.minimumUptime()
            result['uptime_string'] = uptimeString

            result['protocol'] = node.protocol == self.protocolRequirement()
            result['protocol_string'] = "{}".format(node.protocol)

            result['collateral'] = (self.lastBlock - node.collateral.block) >= self.enabledWithMinProtocol()

            result['collateral_string'] = "{}".format((self.lastBlock - node.collateral.block))

            result['upgrade_mode'] = self.qualifiedUpgrade != -1

        return result
