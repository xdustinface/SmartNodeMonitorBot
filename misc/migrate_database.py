#!/usr/bin/env python3

import logging
import threading
import sqlite3 as sql
import os
import subprocess

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger("database")

directory = os.path.dirname(os.path.realpath(__file__))

######
# THIS SCRIPT WAS ONLY  NEEDED TO
# migrate the database from version 1.0 to
# 1.1 since the i removed the nodeid as primary key which
# was a weird idea.
######
def migrate():

    botDB_v10 = ThreadedSQLite(directory + '/bot.db')
    nodesDB_v10 = ThreadedSQLite(directory + '/nodes.db')

    botDB_v11 = BotDatabase(directory + '/bot_11.db')
    nodesDB_v11 = NodeDatabase(directory + '/nodes_11.db')

    botDB_v10_users = None
    botDB_v10_nodes = None

    with botDB_v10 as db:

        db.cursor.execute("SELECT * FROM users")
        botDB_v10_users = db.cursor.fetchall()

        db.cursor.execute("SELECT * FROM nodes")
        botDB_v10_nodes = db.cursor.fetchall()

    nodesDB_10_nodes = None

    with nodesDB_v10 as db:

        db.cursor.execute("SELECT * FROM nodes")
        nodesDB_v10_nodes = db.cursor.fetchall()

    for node in nodesDB_v10_nodes:

        blockHeight = getCollateralAge(node['txhash'], node['txindex'])

        if not blockHeight:
            logger.warning("Could not fetch blockHeight for tx: {}-{}".format(node['txhash'], node['txindex']))
        tx = Transaction(node['txhash'], node['txindex'], blockHeight)
        logger.info("Add {}".format(nodesDB_v11.addNode(tx, node)))


    for user in botDB_v10_users:
        botDB_v11.addUser(user['id'],user['name'])

    logger.info("{} user in 1.0".format(len(botDB_v10_users)))
    logger.info("{} user-nodes in 1.0".format(len(botDB_v10_nodes)))
    logger.info("{} smartnodes in 1.0\n".format(len(nodesDB_v10_nodes)))

    for node in botDB_v10_nodes:

        with nodesDB_v10 as db:

            db.cursor.execute("SELECT * FROM nodes where id=?",[node['node_id']])
            userNode = db.cursor.fetchone()
            tx = Transaction(userNode['txhash'], userNode['txindex'])

        logger.info("Add {}".format(botDB_v11.addNode(str(tx), node['name'], node['user_id'])))

    logger.info("{} users in 1.1".format(len(botDB_v11.getUsers())))
    logger.info("{} user-nodes in 1.1".format(len(botDB_v11.getAllNodes())))
    logger.info("{} smartnodes in 1.1".format(len(nodesDB_v11.getNodes())))



def isValidDeamonResponse(json):

    if 'error' in json:
        logger.warning("could not update list {}".format(json))
        return False

    return True

def getCollateralAge(txhash, txindex):

    rawTx = None

    try:

        result = subprocess.check_output(['smartcash-cli', 'getrawtransaction',txhash, txindex])
        rawTx = json.loads(result.decode('utf-8'))

    except Exception as e:

        logging.error('Could not fetch raw transaction', exc_info=e)

        if result:
            logger.error("Output {}".format(result))

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
# Wrapper for the user database where all the users
# and their added nodes are stored.
#
#####

class BotDatabase(object):

    def __init__(self, dburi):

        self.connection = ThreadedSQLite(dburi)

        if self.isEmpty():
            self.reset()

    def isEmpty(self):

        tables = []

        with self.connection as db:

            db.cursor.execute("SELECT name FROM sqlite_master")

            tables = db.cursor.fetchall()

        return len(tables) == 0

    def addUser(self, userId, userName):

        user = self.getUser(userId)

        if user == None:

            if userName == None or userName == '':
                userName = 'Unknown'

            with self.connection as db:

                logger.debug("addUser: New user {} {}".format(userId,userName))

                db.cursor.execute("INSERT INTO users( id, name, status_n, timeout_n, reward_n, network_n  ) values( ?, ?, 1, 1, 1, 0 )", ( userId, userName ))

                user = db.cursor.lastrowid

        else:

            user = user['id']

        return user

    def addNode(self, collateral,name,userId):

        user = self.getUser(userId)
        node = self.getNodes(collateral, userId)

        if node == None or node['user_id'] != user['id']:

            with self.connection as db:

                db.cursor.execute("INSERT INTO nodes( collateral, name, user_id  )  values( ?, ?, ? )", ( collateral, name, userId ) )

                return True

        return False

    def getUsers(self, condition = None ):

        users = []

        with self.connection as db:
            query = "SELECT * FROM users"

            if condition:
                query += (' ' + condition)

            db.cursor.execute(query)
            users = db.cursor.fetchall()

        return users

    def getUser(self, userId):

        user = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM users WHERE id=?",[userId])

            user = db.cursor.fetchone()

        return user

    def getAllNodes(self, userId = None):

        nodes = []

        with self.connection as db:

            if userId:
                db.cursor.execute("SELECT * FROM nodes WHERE user_id=? ORDER BY name",[userId])
            else:
                db.cursor.execute("SELECT * FROM nodes")

            nodes = db.cursor.fetchall()

        return nodes

    def getNodes(self, collateral, userId = None):

        nodes = None

        with self.connection as db:

            if userId:
                db.cursor.execute("SELECT * FROM nodes WHERE collateral=? and user_id=?",(collateral,userId))
                nodes = db.cursor.fetchone()
            else:
                db.cursor.execute("SELECT * FROM nodes WHERE collateral=?",[collateral])
                nodes = db.cursor.fetchall()

        return nodes

    def reset(self):

        sql = 'BEGIN TRANSACTION;\
        CREATE TABLE "users" (\
        	`id`	INTEGER NOT NULL PRIMARY KEY,\
        	`name`	INTEGER,\
        	`status_n`	INTEGER,\
        	`reward_n`	INTEGER,\
        	`timeout_n`	INTEGER,\
        	`network_n` INTEGER,\
            `detail_n` INTEGER,\
            `last_activity`	INTEGER\
        );\
        CREATE TABLE "nodes" (\
        	`id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,\
        	`user_id` INTEGER,\
        	`collateral` STRING NOT NULL,\
        	`name` TEXT NOT NULL\
        );\
        CREATE INDEX `node_id` ON `nodes` (`collateral` );\
        CREATE INDEX `node_user` ON `nodes` (`user_id` );\
        COMMIT;'

        with self.connection as db:
            db.cursor.executescript(sql)


#####
#
# Wrapper for the node database where all the nodes from the
# global nodelist are stored.
#
#####

class NodeDatabase(object):

    def __init__(self, dburi):

        self.connection = ThreadedSQLite(dburi)

        if self.isEmpty():
            self.reset()

    def isEmpty(self):

        tables = []

        with self.connection as db:

            db.cursor.execute("SELECT name FROM sqlite_master")

            tables = db.cursor.fetchall()

        return len(tables) == 0

    def addNode(self, tx, node):

        try:

            with self.connection as db:
                query = "INSERT INTO nodes(\
                        collateral,\
                        collateral_block,\
                        payee, \
                        status,\
                        activeseconds,\
                        last_paid_block,\
                        last_paid_time,\
                        last_seen,\
                        protocol,\
                        ip,\
                        timeout ) \
                        values( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )"

                db.cursor.execute(query, (
                                  str(tx),
                                  tx.block,
                                  node['payee'],
                                  node['status'],
                                  node['activeSeconds'],
                                  node['last_paid_block'],
                                  node['last_paid_time'],
                                  node['last_seen'],
                                  node['protocol'],
                                  node['ip'],
                                  node['timeout']))

                return db.cursor.lastrowid

        except Exception as e:
            logger.error("Duplicate?!" , exc_info=e)

        return None

    def getNodes(self, filter = None):

        nodes = []
        rows = '*' if filter == None else ",".join(filter)

        with self.connection as db:

            db.cursor.execute("SELECT {} FROM nodes".format(rows))

            nodes = db.cursor.fetchall()

        return nodes

    def reset(self):

        sql = '\
        BEGIN TRANSACTION;\
        CREATE TABLE "nodes" (\
        	`collateral` TEXT NOT NULL PRIMARY KEY,\
            `collateral_block` INTEGER,\
        	`payee`	TEXT,\
        	`status` TEXT,\
        	`activeseconds`	INTEGER,\
        	`last_paid_block` INTEGER,\
        	`last_paid_time` INTEGER,\
        	`last_seen`	INTEGER,\
        	`protocol`	INTEGER,\
            `timeout` INTEGER,\
        	`ip` TEXT\
        );\
        COMMIT;'

        with self.connection as db:
            db.cursor.executescript(sql)

if __name__ == '__main__':
    migrate()
