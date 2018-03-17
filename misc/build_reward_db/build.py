#!/usr/bin/env python3

import logging
import threading
import sqlite3 as sql
import os
import subprocess
import json

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger("reward")

directory = os.path.dirname(os.path.realpath(__file__))

######
# THIS SCRIPT IS  NEEDED TO
# .....
######

def build():

    rewardDB = ThreadedSQLite(directory + '/rewards.db')

    firstBlock = getBlockByNumber(300001)

    if firstBlock:
        nextBlock = firstBlock['nextblockhash']

        reward = getRewardForBlock(firstBlock)

        logger.info("Reward: {}".format(str(reward)))

    # while nextBlock:

def getRewardForBlock(block):

    if not block or 'tx' not in block:
        return None

    blockHeight = block['height']
    expectedPayout = 5000  * ( 143500 / int(blockHeight) ) * 0.1
    expectedUpper = expectedPayout * 1.01
    expectedLower = expectedPayout * 0.99

    # Search the new coin transaction of the block
    for tx in block['tx']:
        rawTx = getRawTransaction(tx)

        if not rawTx:
            return None

        # We found the new coin transaction of the block
        if len(rawTx['vin']) == 1 and 'coinbase' in rawTx['vin'][0]:

            for out in rawTx['vout']:

                amount = int(out['value'])

                if amount <= expectedUpper and amount >= expectedLower:
                   #We found the node payout for this block!

                   txtime = rawTx['time']
                   payee = out['addresses'][0]

                   return Reward(blockHeight, txtime, payee, amount)

    return None


def getBlockByNumber(number):

    block = None

    try:

        result = subprocess.check_output(['smartcash-cli', 'getblockhash',number])
        blockHash = result.decode('utf-8')

    except Exception as e:

        logging.error('Could not fetch raw transaction', exc_info=e)

    if "error" in blockHash:
        return None

    try:

        result = subprocess.check_output(['smartcash-cli', 'getblock',blockHash])
        block = json.loads(result.decode('utf-8'))

    except Exception as e:
        logging.error('Could not fetch block', exc_info=e)

    if not 'tx' in block or not isValidDeamonResponse(block):
        return None

    return block


def getRawTransaction(txhash):

    block = None

    try:

        result = subprocess.check_output(['smartcash-cli', 'getrawtransaction',txhash, '1'])
        rawTx = json.loads(result.decode('utf-8'))

    except Exception as e:

        logging.error('Could not fetch raw transaction', exc_info=e)

    if not "vin" in rawTx or not isValidDeamonResponse(rawTx):
        return None

    return rawTx



def isValidDeamonResponse(json):

    if 'error' in json:
        logger.warning("could not update list {}".format(json))
        return False

    return True

def getCollateralAge(txhash):

    rawTx = None

    try:

        result = subprocess.check_output(['smartcash-cli', 'getrawtransaction',txhash, '1'])
        rawTx = json.loads(result.decode('utf-8'))

    except Exception as e:

        logging.error('Could not fetch raw transaction', exc_info=e)

    if not "blockhash" in rawTx or not isValidDeamonResponse(rawTx):
        return None

    blockHash = rawTx['blockhash']

    try:

        result = subprocess.check_output(['smartcash-cli', 'getblock',blockHash])
        block = json.loads(result.decode('utf-8'))

    except Exception as e:
        logging.error('Could not fetch block', exc_info=e)

    if not 'height' in block or not isValidDeamonResponse(block):
        return None

    return block['height']

def getCollateralAge(txhash):

    rawTx = None

    try:

        result = subprocess.check_output(['smartcash-cli', 'getrawtransaction',txhash, '1'])
        rawTx = json.loads(result.decode('utf-8'))

    except Exception as e:

        logging.error('Could not fetch raw transaction', exc_info=e)

    if not "blockhash" in rawTx or not isValidDeamonResponse(rawTx):
        return None

    blockHash = rawTx['blockhash']

    try:

        result = subprocess.check_output(['smartcash-cli', 'getblock',blockHash])
        block = json.loads(result.decode('utf-8'))

    except Exception as e:
        logging.error('Could not fetch block', exc_info=e)

    if not 'height' in block or not isValidDeamonResponse(block):
        return None

    return block['height']

class Reward(object):

    def __init__(self, block, txtime, address, amount):
        self.block = block
        self.txtime = txtime
        self.address = address
        self.amount = amount

    def __str__(self):
        return '[{0.address}] {0.block} - {0.amount}'.format(self)

    def __eq__(self, other):
        return self.block == other.block

    def __hash__(self):
        return hash(self.block)

class Transaction(object):

    def __init__(self, txhash, txindex, block):
        self.hash = txhash
        self.index = txindex
        self.block = block

    def __str__(self):
        return '{0.hash}-{0.index}'.format(self)

    def __eq__(self, other):
        return self.hash == other.hash and\
                self.index == other.index

    def __hash__(self):
        return hash((self.hash,self.index))

class ThreadedSQLite(object):
    def __init__(self, dburi):
        self.lock = threading.Lock()
        self.connection = sql.connect(dburi, check_same_thread=False)
        self.connection.row_factory = sql.Row
        self.cursor = None
    def __enter__(self):
        self.lock.acquire()
        self.cursor = self.connection.cursor()
        return self
    def __exit__(self, type, value, traceback):
        self.lock.release()
        self.connection.commit()
        if self.cursor is not None:
            self.cursor.close()
            self.cursor = None

#####
#
# Wrapper for the node database where all the nodes from the
# global nodelist are stored.
#
#####

class RewardDatabase(object):

    def __init__(self, dburi):

        self.connection = util.ThreadedSQLite(dburi)

        if self.isEmpty():
            self.reset()

    def isEmpty(self):

        tables = []

        with self.connection as db:

            db.cursor.execute("SELECT name FROM sqlite_master")

            tables = db.cursor.fetchall()

        return len(tables) == 0

    def raw(self, query):

        with self.connection as db:
            db.cursor.execute(query)
            return db.cursor.fetchall()

        return None


    def addPayout(self, block, paidTime, collateral, source):

        try:

            with self.connection as db:
                query = "INSERT INTO rewards(\
                        block,\
                        paidTime,\
                        collateral,\
                        source) \
                        values( ?, ?, ?, ? )"

                db.cursor.execute(query, (
                                  block,
                                  paidTime,
                                  str(collateral),
                                  source))

                return db.cursor.lastrowid

        except Exception as e:
            logger.debug("Duplicate?!", exc_info=e)

        return None

    def getPayouts(self, filter = None):

        nodes = []
        rows = '*' if filter == None else ",".join(filter)

        with self.connection as db:

            db.cursor.execute("SELECT {} FROM nodes".format(rows))

            nodes = db.cursor.fetchall()

        return nodes

    def getNodeCount(self, where = None):

        count = 0

        with self.connection as db:

            if where:
                db.cursor.execute("SELECT COUNT(collateral) FROM nodes WHERE {}".format(where))
            else:
                db.cursor.execute("SELECT COUNT(collateral) FROM nodes")

            count = db.cursor.fetchone()[0]

        return count

    def getPayoutsForCollateral(self, collateral):

        payouts = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM rewards WHERE collateral=?",[str(collateral)])

            payouts = db.cursor.fetchall()

        return payouts

    def reset(self):

        sql = '\
        BEGIN TRANSACTION;\
        CREATE TABLE "rewards" (\
        	`block` INTEGER NOT NULL PRIMARY KEY,\
        	`paidTime`	INTEGER,\
        	`collateral` TEXT,\
            `source` INTEGER\
        );\
        COMMIT;'

        with self.connection as db:
            db.cursor.executescript(sql)

if __name__ == '__main__':
    build()
