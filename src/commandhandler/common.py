#!/usr/bin/env python3

import logging
from src import messages
from src import util
import requests
import json

import telegram
import discord

logger = logging.getLogger("common")

######
# Telegram command handler for printing the help text
#
# Command: /help
#
# Gets only called by the telegram bot api
######
def info(bot, update):

    logger.info("network")

    response = messages.markdown("<u><b>SmartNode Network<b><u>\n\n",bot.messenger)

    if bot.nodeList.synced() and bot.nodeList.lastBlock:

        lastBlock = bot.nodeList.lastBlock
        upgradeMode = bot.nodeList.upgradeMode
        created = bot.nodeList.count()
        enabled = bot.nodeList.enabled()
        qualified = bot.nodeList.qualified()
        protocolRequirement = bot.nodeList.protocolRequirement()
        protocol90024 = bot.nodeList.count(90024)
        protocol90025 = bot.nodeList.count(90025)
        initialWait = bot.nodeList.minimumUptime()

        response += messages.networkState(bot.messenger,
                                          lastBlock,
                                          upgradeMode,
                                          created,
                                          enabled,
                                          qualified,
                                          protocolRequirement,
                                          protocol90024,
                                          protocol90025,
                                          util.secondsToText(initialWait))

    else:
        response += "*Sorry, the server is currently not synced with the network.*"

    return response

def networkUpdate(bot, ids, added):

    count = len(ids)

    logger.info("networkUpdate {}, {}".format(count,added))

    response = messages.markdown("<u><b>Network update<b><u>\n\n",bot.messenger)

    if added:
        response += "{} new node{} detected\n\n".format(count,"s" if count > 1 else "")
    else:
        response += "{} node{} left us!\n\n".format(abs(count),"s" if count < 1 else "")

    response += messages.markdown("We have <b>{}<b> created nodes now!\n\n".format(bot.nodeList.count()),bot.messenger)
    response += messages.markdown("<b>{}<b> of them are enabled.".format(bot.nodeList.enabled()), bot.messenger)

    return response

######
# Telegram command handler for printing the help text
#
# Command: /help
#
# Gets only called by the telegram bot api
######
def stats(bot):

    logger.info("stats")

    response = messages.markdown("<u><b>Statistics<b><u>\n\n",bot.messenger)

    response += "User: {}\n".format(len(bot.database.getUsers()))
    response += "Nodes: {}\n".format(len(bot.database.getAllNodes()))

    response += "90024: {}\n".format(bot.nodeList.getNodeCountForProtocol(90024))
    response += "90025: {}\n".format(bot.nodeList.getNodeCountForProtocol(90025))

    return response


######
# Telegram command handler for printing unknown command text
#
# Command: All invalid commands
#
# Gets only called by the telegram bot api
######
def unknown(bot):

    logger.info("help")

    return messages.markdown("I'm not sure what you mean? Try <cb>help<ca>",bot.messenger)

######
# Telegram command handler for logging errors from the bot api
#
# Command: No command, will get called on errors.
#
# Gets only called by the telegram bot api
######
def error(bot, update, error):
    logger.error('Update "%s" caused error "%s"' % (update, error))
    logger.error(error)
