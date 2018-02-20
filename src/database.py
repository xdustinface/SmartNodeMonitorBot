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

    def addNode(self, collateral,name,userId,userName):

        user = self.addUser(userId, userName)
        node = self.getNodes(nodeId, user)

        if node == None or node['user_id'] != user:

            with self.connection as db:

                db.cursor.execute("INSERT INTO nodes( collateral, name, user_id  )  values( ?, ?, ? )", ( nodeId, name, user ) )

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

    def updateUsername(self, name, userId):

        with self.connection as db:

            db.cursor.execute("UPDATE users SET name=? WHERE id=?",(name,userId))

    def updateNode(self, collateral, userId, name):

        with self.connection as db:

            db.cursor.execute("UPDATE nodes SET name=? WHERE collateral=? and user_id=?",(name, collateral, userId))

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

    def deleteNode(self, collateral, userId):

        with self.connection as db:

            db.cursor.execute("DELETE FROM nodes WHERE collateral=? and user_id=?",(collateral,userId))

    def deleteNodesForUser(self, userId):

        with self.connection as db:
            db.cursor.execute("DELETE FROM nodes WHERE user_id=?",[userId])

    def deleteNodesWithId(self, collateral):

        with self.connection as db:
            db.cursor.execute("DELETE FROM nodes WHERE collateral=?",[collateral])

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

        self.connection = util.ThreadedSQLite(dburi)

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
                        payee, \
                        status,\
                        activeseconds,\
                        last_paid_block,\
                        last_paid_time,\
                        last_seen,\
                        protocol,\
                        ip,\
                        timeout ) \
                        values( ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )"

                db.cursor.execute(query, (
                                  str(tx),
                                  node.payee,
                                  node.status,
                                  node.activeSeconds,
                                  node.lastPaidBlock,
                                  node.lastPaidTime,
                                  node.lastSeen,
                                  node.protocol,
                                  node.ip,
                                  node.timeout))

                return db.cursor.lastrowid

        except Exception as e:
            logger.error("Duplicate?!", exc_info=e)

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

    def getNodeByIp(self, ip):

        node = None

        search = "{}:9678".format(ip)

        with self.connection as db:

            db.cursor.execute("SELECT * FROM nodes WHERE ip=?",[search])

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
                                timeout=?\
                                WHERE collateral=?"

                db.cursor.execute(query, (\
                                  node.payee,\
                                  node.status,\
                                  node.activeSeconds,\
                                  node.lastPaidBlock,\
                                  node.lastPaidTime,\
                                  node.lastSeen,\
                                  node.protocol,\
                                  node.ip,
                                  node.timeout,
                                  str(tx)))

    def deleteNode(self, tx):

        with self.connection as db:

            db.cursor.execute("DELETE FROM nodes WHERE collateral=?",[tx])

    def reset(self):

        sql = '\
        BEGIN TRANSACTION;\
        CREATE TABLE "nodes" (\
        	`collateral` TEXT NOT NULL PRIMARY KEY,\
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
