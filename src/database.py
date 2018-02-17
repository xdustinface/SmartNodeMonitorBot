#!/usr/bin/env python3

import logging
from src import util
import threading
import sqlite3 as sql

logger = logging.getLogger("database")

#####
#
# Wrapper for the user database where all the users
# and their added nodes are stored.
#
#####

class BotDatabase(object):

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

    def addNode(self, nodeId,name,userId,userName):

        user = self.addUser(userId, userName)
        node = self.getNode(nodeId, user)

        if node == None or node['user_id'] != user:

            logger.info("addNode: Not found, try to add {} ".format(nodeId))

            with self.connection as db:

                db.cursor.execute("INSERT INTO nodes( node_id, name, user_id  )  values( ?, ?, ? )", ( nodeId, name, user ) )

                return True

        return False

    def getUsers(self):

        users = []

        with self.connection as db:

            db.cursor.execute("SELECT * FROM users")

            users = db.cursor.fetchall()

        return users

    def getUser(self, userId):

        user = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM users WHERE id=?",[userId])

            user = db.cursor.fetchone()

        return user

    def getAllNodes(self):

        users = []

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes")

            users = db.cursor.fetchall()

        return users

    def getNodes(self, userId):

        nodes = []

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes WHERE user_id=? ORDER BY name",[userId])

            nodes = db.cursor.fetchall()

        return nodes

    def getNode(self, nodeId, userId):

        node = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes WHERE node_id=? and user_id=?",(nodeId,userId))

            node = db.cursor.fetchone()

        return node

    def updateUsername(self, name, userId):

        with self.connection as db:

            db.cursor.execute("UPDATE users SET name=? WHERE id=?",(name,userId))

    def updateNode(self, nodeId, userId, name):

        with self.connection as db:

            db.cursor.execute("UPDATE nodes SET name=? WHERE node_id=? and user_id=?",(name, nodeId, userId))

    def updateChatId(self, chatId, newChatId):

        with self.connection as db:

            db.cursor.execute("UPDATE users SET id = ? WHERE id=?",(newChatId,chatId))

    def updateStatusNotification(self, userId, state):

        with self.connection as db:

            db.cursor.execute("UPDATE users SET status_n = ? WHERE id=?",(state,userId))

    def updateTimeoutNotification(self, userId, state):

        with self.connection as db:

            db.cursor.execute("UPDATE users SET timeout_n = ? WHERE id=?",(state,userId))

    def updateRewardNotification(self, userId, state):

        with self.connection as db:

            db.cursor.execute("UPDATE users SET reward_n = ? WHERE id=?",(state,userId))

    def updateNetworkNotification(self, userId, state):

        with self.connection as db:

            db.cursor.execute("UPDATE users SET network_n = ? WHERE id=?",(state,userId))

    def deleteUser(self, userId):

        with self.connection as db:

            db.cursor.execute("DELETE FROM users WHERE id=?",[userId])

    def deleteNode(self, nodeId, userId):

        with self.connection as db:

            db.cursor.execute("DELETE FROM nodes WHERE node_id=? and user_id=?",(nodeId,userId))

    def deleteNodesForUser(self, userId):

        with self.connection as db:
            db.cursor.execute("DELETE FROM nodes WHERE user_id=?",[userId])

    def deleteNodesWithId(self, nodeId):

        with self.connection as db:
            db.cursor.execute("DELETE FROM nodes WHERE node_id=?",[nodeId])

    def reset(self):

        sql = 'BEGIN TRANSACTION;\
        CREATE TABLE "users" (\
        	`id`	INTEGER NOT NULL PRIMARY KEY,\
        	`name`	INTEGER,\
        	`status_n`	INTEGER,\
        	`reward_n`	INTEGER,\
        	`timeout_n`	INTEGER,\
        	`network_n` INTEGER\
        );\
        CREATE TABLE "nodes" (\
        	`id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,\
        	`user_id` INTEGER,\
        	`node_id`	INTEGER NOT NULL,\
        	`name`	TEXT NOT NULL,\
        	`last_activity`	INTEGER\
        );\
        CREATE INDEX `node_id` ON `nodes` (`node_id` );\
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

        self.connection = util.ThreadedSQLite(dburi)

        if self.isEmpty():
            self.reset()

        # Add the new rows in 1.1 if needed
        self.patchVersion1_1()

    def isEmpty(self):

        tables = []

        with self.connection as db:

            db.cursor.execute("SELECT name FROM sqlite_master")

            tables = db.cursor.fetchall()

        return len(tables) == 0

    def addNode(self, tx, node):

        if self.getNodeByTx(tx) == None:

            with self.connection as db:
                query = "INSERT INTO nodes(\
                        txhash,\
                        txindex,\
                        payee, \
                        status,\
                        activeseconds,\
                        last_paid_block,\
                        last_paid_time,\
                        last_seen,\
                        protocol,\
                        ip,\
                        rank,\
                        position,\
                        timeout ) \
                        values( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )"

                db.cursor.execute(query, (
                                  tx.hash,
                                  tx.index,
                                  node.payee,
                                  node.status,
                                  node.activeSeconds,
                                  node.lastPaidBlock,
                                  node.lastPaidTime,
                                  node.lastSeen,
                                  node.protocol,
                                  node.ip,
                                  node.rank,
                                  node.position,
                                  node.timeout))

                return db.cursor.lastrowid

        return None

    def getNodes(self, filter = None):

        nodes = []
        rows = '*' if filter == None else ",".join(filter)

        with self.connection as db:

            db.cursor.execute("SELECT {} FROM nodes".format(rows))

            nodes = db.cursor.fetchall()

        return nodes

    def getNodeCount(self):

        count = 0

        with self.connection as db:

            db.cursor.execute("SELECT COUNT(id) FROM nodes")

            count = db.cursor.fetchone()[0]

        return count

    def getNodeByTx(self, tx):

        node = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes WHERE txhash=? AND txindex=?",(tx.hash,tx.index))

            node = db.cursor.fetchone()

        return node

    def getNodeById(self, id):

        node = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes WHERE id=?",[id])

            node = db.cursor.fetchone()

        return node

    def getNodeByIp(self, ip):

        node = None

        search = "{}:9678".format(ip)

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes WHERE ip=?",[search])

            node = db.cursor.fetchone()

        return node

    def getNodeByPayee(self, payee):

        node = None

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes WHERE payee=?",[payee])

            node = db.cursor.fetchone()

        return node

    def updateNode(self, tx, node):

        if not self.addNode(tx, node):

            with self.connection as db:

                query = "UPDATE nodes SET\
                                payee=?,\
                                status=?,\
                                activeseconds=?,\
                                last_paid_block=?,\
                                last_paid_time=?,\
                                last_seen=?,\
                                protocol=?,\
                                ip=?,\
                                rank=?,\
                                position=?,\
                                timeout=?\
                                WHERE txhash=? AND txindex=?"

                db.cursor.execute(query, (\
                                  node.payee,\
                                  node.status,\
                                  node.activeSeconds,\
                                  node.lastPaidBlock,\
                                  node.lastPaidTime,\
                                  node.lastSeen,\
                                  node.protocol,\
                                  node.ip,
                                  node.rank,
                                  node.position,
                                  node.timeout,
                                  tx.hash,tx.index))

    def deleteNode(self, tx):

        with self.connection as db:

            db.cursor.execute("DELETE FROM nodes WHERE txhash=? AND txindex=?",(tx.hash,tx.index))

    def reset(self):

        sql = '\
        BEGIN TRANSACTION;\
        CREATE TABLE "nodes" (\
            `id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,\
        	`txhash` TEXT NOT NULL,\
        	`txindex` INTEGER NOT NULL,\
        	`payee`	TEXT,\
        	`status` TEXT,\
        	`activeseconds`	INTEGER,\
        	`last_paid_block` INTEGER,\
        	`last_paid_time` INTEGER,\
        	`last_seen`	INTEGER,\
        	`protocol`	INTEGER,\
        	`ip` TEXT,\
        	`rank`	INTEGER\
        );\
        CREATE INDEX `payee` ON `nodes` (`payee`);\
        COMMIT;'

        with self.connection as db:
            db.cursor.executescript(sql)

    def patchVersion1_1:

        with self.connection as db:

            db.cursor.execute('PRAGMA table_info(nodes)')
            columns = db.cursor.fetchall()

            names = list(map(lambda x: x[1],columns ))

            if 'position' not in names:
                db.cursor.execute('ALTER TABLE nodes ADD COLUMN position INTEGER;')

            if 'timeout' not in names:
                db.cursor.execute('ALTER TABLE nodes ADD COLUMN timeout INTEGER;')
