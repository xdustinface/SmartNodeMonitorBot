#!/usr/bin/env python3

import logging
import time
from src import util
from src import messages

import telegram
import discord

logger = logging.getLogger("node")

def payoutTimeToString(t):
    if t:
        return util.secondsToText( int(time.time()) - t )
    else:
        return "No payout yet."

def positionToString(position):
    if position == -1:
        return 'Calculating...'
    elif position == -2:
        return "Not qualified for payouts"
    else:
        return "{}".format(position)

######
# Telegram command handler for adding nodes for the user who fired the command.
#
# Command: /node :ip0;name0 ... :ipN;nameN
#
# Command parameter: :ip0 - Address of the first node to add
#                    :name0 - Name of the first node
#                    :ipN - Address of the last node to add
#                    :nameN - Name of the last node
#
# Gets only called by the telegram bot api
######
def nodeAdd(bot, update, args):

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    response = messages.markdown("<u><b>Add<b><u>\n\n",bot.messenger)

    logger.debug("add - " + " ".join(args))
    logger.debug("add - user: {}".format(userId))

    if len(args) == 0:

        response += messages.markdown(("<b>ERROR<b>: Arguments required: <b>IPAddress_0;name_0 ... IPAddress_n;name_n<b>\n\n"
                     "Example: <cb>add<ca> 43.121.56.87;Node1 56.76.27.100;Node2\n"),bot.messenger)
        valid = False

    else:

        for arg in args:

            valid = True

            newNode = arg.split(";")

            if len(newNode) != 2:

                response += messages.invalidParameterError(bot.messenger,arg)
                valid = False
            else:

                if not util.validateIp( newNode[0] ):

                    response += messages.invalidIpError(bot.messenger, newNode[0])
                    valid = False

                if not util.validateName( newNode[1] ):

                    response += messages.invalidNameError(bot.messenger, newNode[1])
                    valid = False

            if valid:

                ip = newNode[0]
                name = newNode[1]

                node = bot.nodeList.getNodeByIp(ip)

                if node == None:
                    response += messages.nodeNotInListError(bot.messenger,ip)
                else:

                    if bot.database.addNode( node['id'], name, userId,userName):

                        response += "Added node {}!\n".format(ip)

                    else:

                        response += messages.nodeExistsError(bot.messenger,ip)

    return response

######
# Telegram command handler for updating nodes for the user who fired the command.
#
# Command: /add :ip :newname
#
# Command parameter: :ip - Address of the node to update
#                    :newname - New name for the node
#
# Gets only called by the telegram bot api
######
def nodeUpdate(bot, update, args):

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    response = messages.markdown("<u><b>Update<b><u>\n\n",bot.messenger)

    logger.debug("update - " + " ".join(args))
    logger.debug("update - user: {}".format(userId))

    user = bot.database.getUser(userId)

    if user == None:

        response += messages.notActiveError(bot.messenger)

    elif not len(args):

        response += messages.markdown(("<b>ERROR<b>: Argument(s) required: <b>ip0;newname0 ipN;newnameN<b>\n\n"
                     "Where <b>ip<b> is the IP-Address of the node to update and <b>newname<b> the"
                     " new name of the node.\n\n"
                     "Example: <cb>update<ca> 23.132.143.34;MyNewNodeName\n"),bot.messenger)

    else:

        for arg in args:

            nodeEdit = arg.split(";")

            valid = True

            if len(nodeEdit) != 2:

                response += messages.invalidParameterError(bot.messenger,arg)
                valid = False
            else:

                ip = nodeEdit[0]
                name = nodeEdit[1]

                if not util.validateIp( ip ):

                    response += messages.invalidIpError(bot.messenger, ip)
                    valid = False

                if not util.validateName( name ):

                    response += messages.invalidNameError(bot.messenger, name)
                    valid = False

            if valid:

                logger.info("update - {} {}".format(ip, user['id']))

                node = bot.nodeList.getNodeByIp(ip)

                if node == None:
                    response += messages.nodeNotInListError(bot.messenger, ip)
                else:

                    userNode = bot.database.getNodes(node['id'],userId)

                    if userNode == None:
                        response += messages.nodeNotExistsError(bot.messenger, ip)
                    else:

                        bot.database.updateNode(node['id'],user['id'], name)

                        response += "Node successfully updated. {}\n".format(ip)

    return response

######
# Telegram command handler for removing nodes for the user who fired the command.
#
# Command: /remove :ip
#
# Command parameter: :ip - Address of the node to remove
#
#
# Gets only called by the telegram bot api
######
def nodeRemove(bot, update, args):

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    response = messages.markdown("<u><b>Remove<b><u>\n\n",bot.messenger)

    logger.debug("remove - " + " ".join(args))
    logger.debug("remove - user: {}".format(userId))

    user = bot.database.getUser(userId)

    if user == None:

        response += messages.notActiveError(bot.messenger)

    elif len(args) < 1:

        response += messages.markdown(("<b>ERROR<b>: Argument(s) required: <b>:ip0 :ipN<b>\n\n"
                     "Example remove one: <cb>remove<ca> 21.23.34.44\n"
                     "Example remove more: <cb>remove<ca> 21.23.34.44 21.23.34.43\n"
                     "Example remove all: <cb>remove<ca> all\n"),bot.messenger)

    else:

        # Check if the user wants to remove all nodes.
        if len(args) == 1 and ip == 'all':

            bot.database.deleteNodesForUser(userId)
            response += "Node successfully all your nodes!\n"

        else:
            # Else go through the parameters
            for arg in args:

                ip = arg

                if not util.validateIp(ip):

                    response += messages.invalidIpError(bot.messenger, ip)
                    valid = False

                else:

                    logger.info("remove - valid {}".format(ip))

                    node = bot.nodeList.getNodeByIp(ip)

                    if node == None:
                        response += messages.nodeNotInListError(bot.messenger, ip)
                    else:

                        userNode = bot.database.getNodes(node['id'],userId)

                        if userNode == None:
                            response += messages.nodeNotExistsError(bot.messenger, ip)
                        else:
                            bot.database.deleteNode(node['id'],user['id'])
                            response += "Node successfully removed. {}\n".format(ip)

    return response

######
# Telegram command handler for reading the amounts of each node of the users
# in the pool
#
# Command: /nodes
#
# Gets only called by the telegram bot api
######
def detail(bot, update):

    response = messages.markdown("<u><b>Detail<b><u>\n\n",bot.messenger)

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else update.message.from_user.name

    logger.debug("detail - user: {}".format(userId))

    nodesFound = False

    user = bot.database.getUser(userId)
    nodes = bot.database.getAllNodes(userId)

    if user == None or nodes == None or len(nodes) == 0:

       response +=  messages.nodesRequired(bot.messenger)

    else:

        for node in nodes:

            smartnode = bot.nodeList.getNodeById(node['node_id'])

            response += messages.markdown(("<b>" + node['name'] + " - " + smartnode.ip + "<b>")  ,bot.messenger)
            response += "\n  `Status` " + smartnode.status
            response += "\n  `Position` " + positionToString(smartnode.position)
            response += "\n  `Payee` " + smartnode.payee
            response += "\n  `Active since` " + util.secondsToText(smartnode.activeSeconds)
            response += "\n  `Last seen` " + util.secondsToText( int(time.time()) - smartnode.lastSeen)
            response += "\n  `Last payout (Block)` {}".format(smartnode.lastPaidBlock if smartnode.lastPaidBlock else "No payout yet.")
            response += "\n  `Last payout (Time)` " + payoutTimeToString(smartnode.lastPaidTime)
            response += "\n  `Protocol` {}".format(smartnode.protocol)
            response += "\n  `Rank` {}".format(smartnode.rank)
            response += "\n  " + messages.link(bot.messenger, 'https://explorer3.smartcash.cc/address/{}'.format(smartnode.payee),'Open the explorer!')
            response += "\n\n"

    return response

######
# Telegram command handler for printing the details of each node of the users
#
# Command: /nodes
#
# Gets only called by the telegram bot api
######
def nodes(bot, update):

    response = messages.markdown("<u><b>Nodes<b><u>\n\n",bot.messenger)

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    logger.debug("nodes - user: {}".format(userId))

    nodesFound = False

    user = bot.database.getUser(userId)
    nodes = bot.database.getAllNodes(userId)

    if user == None or nodes == None or len(nodes) == 0:

       response +=  messages.nodesRequired(bot.messenger)

    else:

        for node in nodes:

            smartnode = bot.nodeList.getNodeById(node['node_id'])

            payoutText = util.secondsToText(smartnode.lastPaidTime)
            response += messages.markdown("<b>" + node['name'] + "<b> - `" + smartnode.status + "`\n",bot.messenger)
            response += "Last seen {}\n".format(util.secondsToText( int(time.time()) - smartnode.lastSeen))
            response += "Last payout {}\n".format(payoutTimeToString(smartnode.lastPaidTime))
            response += "Position {}\n".format(positionToString(smartnode.position))
            response += messages.link(bot.messenger, 'https://explorer3.smartcash.cc/address/{}'.format(smartnode.payee),'Open the explorer!')
            response += "\n\n"

    return response

def balances(bot, userId, results):

    response = messages.markdown("<u><b>Balances<b><u>\n\n",bot.messenger)

    if results != None:

        userNodes = bot.database.getAllNodes(userId)

        total = 0
        error = False

        for result in results:
            for node in userNodes:
                if result.node.id == node['node_id']:

                    if not util.isInt(result.data) and "error" in result.data:
                        response += "{} - Error: {}\n".format(node['name'], result.data["error"])
                        logger.warning("Balance response error: {}".format(result.data))
                        error = True
                    else:

                        try:
                            total += int(result.data)
                            response += "{} - {} SMART\n".format(node['name'], result.data)
                        except:
                            error = True
                            logger.warning("Balance response invalid: {}".format(result.data))
                            response += "{} - Error: Could not fetch this balance.\n".format(node['name'])

        response += messages.markdown("\nTotal: <b>{} SMART<b>".format(total),bot.messenger)

        # Only show the profit if there was no error since it would make not much sense otherwise.
        if not error:
            response += messages.markdown("\nProfit: <b>{} SMART<b>".format(total%10000),bot.messenger)

    else:
        response += "Sorry, could not check your balances! Looks like all explorers are down. Try it again later.\n\n"

    return response


def nodeUpdated(bot, update, user, userNode, node):

    responses = []

    nodeName = userNode['name']

    if update['status'] and user['status_n']:

        response = messages.statusNotification(bot.messenger,nodeName, node.status)
        responses.append(response)

    if update['timeout'] and user['timeout_n']:

        if node.timeout != -1:
            timeString = util.secondsToText( int(time.time()) - node.lastSeen)
            response = messages.panicNotification(bot.messenger, nodeName, timeString)
        else:
            response = messages.relaxNotification(bot.messenger, nodeName)

        responses.append(response)

    if update['lastPaid'] and user['reward_n']:

        # Prevent zero division if for any reason lastPaid is 0
        calcBlock = node.lastPaidBlock if node.lastPaidBlock != 0 else bot.nodeList.lastBlock
        reward = 5000 * ( 143500 / calcBlock ) * 0.1

        response = messages.rewardNotification(bot.messenger, nodeName, calcBlock, reward)
        responses.append(response)

    return responses
