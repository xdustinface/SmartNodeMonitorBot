#!/usr/bin/env python3

import logging
import telegram
import json
import time
import threading
import uuid

from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError, RetryAfter)
from telegram.ext import CommandHandler,MessageHandler,Filters
from telegram.ext import Updater

from src import util
from src import messages
from src.commandhandler import node
from src.commandhandler import user
from src.commandhandler import common
from src.smartexplorer import WebExplorer

logger = logging.getLogger("bot")

####
# Message which gets used in the MessageQueue
####
class Message(object):

    def __init__(self, text):
        self.text = text
        self.attempts = 1

    def __str__(self):
        return self.text

####
# Message queue for the telegram api rate limit management: MessagingMachine
####
class MessageQueue(object):

    def __init__(self, chatId):

        self.chatId = chatId
        self.queue = []
        self.messagesPerSecond = 1
        self.leftover = self.messagesPerSecond
        self.lastCheck = time.time()

    ######
    # Makes the queue printable
    ######
    def __str__(self):
        return "MessageQueue chat {}, len {}, left {}".format(self.chatId, len(self.queue),self.leftover)

    ######
    # Refresh the current rate limit state
    ######
    def refresh(self):

        current = time.time()
        passed = current - self.lastCheck
        self.lastCheck = current

        self.leftover += passed * self.messagesPerSecond

        if self.leftover > self.messagesPerSecond:
            self.leftover = self.messagesPerSecond

        #logger.debug("[{}] leftover {}".format(self.chatId, self.leftover))

    ######
    # Check if the queue has messages and has not hit the rate limit yet
    ######
    def ready(self):

        self.refresh()

        return len(self.queue) and int(self.leftover) > 0

    ######
    # Add a message to the queue
    ######
    def add(self, message):
        self.queue.append(message)

    ######
    # Get the next message, remove those with 3 send attempts.
    ######
    def next(self):

        if self.queue[0].attempts >= 3:
            logger.info("Delete due to max attemts. After {}".format(len(self.queue)))
            self.pop()

        return self.queue[0] if len(self.queue) else None

    ######
    # Remove a message and decrease the ratelimit counter
    ######
    def pop(self):

        self.leftover -= 1

        if not len(self.queue):
            return

        del self.queue[0]

    ######
    # Lock the queue for a given number of seconds.
    ######
    def lock(self, seconds):
        self.leftover -= seconds * self.messagesPerSecond

    ######
    # Called when an error occured. Give the highest rated message a shot.
    ######
    def error(self):

        self.leftover -= 1

        if not len(self.queue):
            return

        self.queue[0].attempts += 1


####
# Telegram API Rate limit management. Handles all the user queues and tries
# to send messages periodically.
####
class MessagingMachine(object):

    def __init__(self, bot, database):
        self.sem = threading.Lock()
        self.bot = bot
        self.database = database
        self.queues = {}
        self.sendInterval = 0.25 # Seconds
        self.timer = None
        self.maxLength = 2000
        self.messagesPerSecond = 30
        self.leftover = self.messagesPerSecond
        self.lastCheck = time.time()

        self.startTimer()


    ######
    # Start the messaging timer
    ######
    def startTimer(self):

        self.timer = threading.Timer(self.sendInterval, self.run)
        self.timer.start()

    ######
    # Stop the messaging timer
    ######
    def stopTimer(self):
        if self.timer:
            self.timer.cancel()

    ######
    # Refresh the current rate limit state
    ######
    def refresh(self):

        current = time.time()
        passed = current - self.lastCheck
        self.lastCheck = current

        self.leftover += passed * self.messagesPerSecond

        if self.leftover > self.messagesPerSecond:
            self.leftover = self.messagesPerSecond

    ######
    # Check if the queue has messages and has not hit the rate limit yet
    ######
    def ready(self):

        self.refresh()

        return int(self.leftover) > 0

    ######
    # Add a message for a specific userId. If there is a queue it gets just
    # added to it otherwise one will be created.
    ######
    def addMessage(self, chatId, text, split = '\n'):

        self.sem.acquire()

        logger.info("addMessage - Chat: {}, Text: {}".format(chatId,text))

        if chatId not in self.queues:
            self.queues[chatId] = MessageQueue(chatId)

        for part in messages.splitMessage(text, split, self.maxLength ):
            self.queues[chatId].add(Message(part))

        logger.info(self.queues[chatId])

        self.sem.release()

    ######
    # Timer Callback. Main part of this class. Goes through all the queues, checks
    # if any rate limit got hit and sends messages if its allowed to.
    ######
    def run(self):

        self.sem.acquire()

        for chatId, queue in self.queues.items():

            if not self.ready():
                logger.debug("MessagingMachine not ready {}".format(self.leftover))
                break

            if not queue.ready():
                logger.debug("Queue not ready {}".format(queue))
                continue

            err = True

            message = queue.next()

            if message == None:
                continue

            try:
                self.bot.sendMessage(chat_id=chatId, text = str(message),parse_mode=telegram.ParseMode.MARKDOWN )

            except Unauthorized as e:
                logger.warning("Exception: Unauthorized {}".format(e))

                self.database.deleteNodesForUser(chatId)
                self.database.deleteUser(chatId)

                err = False

            except TimedOut as e:
                logger.warning("Exception: TimedOut {}".format(e))
            except NetworkError as e:
                logger.warning("Exception: NetworkError {}".format(e))
            except ChatMigrated as e:
                logger.warning("Exception: ChatMigrated from {} to {}".format(chatId, e.new_chat_id))
            except BadRequest as e:
                logger.warning("Exception: BadRequest {}".format(e))
            except RetryAfter as e:
                logger.warning("Exception: RetryAfter {}".format(e))

                queue.lock(e.retry_after)

                self.bot.sendMessage(chat_id=chatId, text = messages.rateLimitError.format(util.secondsToText(int(e.retry_after))),parse_mode=telegram.ParseMode.MARKDOWN )

            except TelegramError as e:
                logger.warning("Exception: TelegramError {}".format(e))
            else:
                logger.debug("sendMessage - OK!")
                err = False

            if err:
                queue.error()
            else:
                queue.pop()

            self.leftover -= 1

        self.sem.release()

        self.startTimer()


class SmartNodeBotTelegram(object):

    def __init__(self, botToken, admin, password, db, nodeList):

        # Currently only used for markdown
        self.messenger = "telegram"

        # Create a bot instance for async messaging
        self.bot = telegram.Bot(token=botToken)
        # Create the updater instance for configuration
        self.updater = Updater(token=botToken)
        # Set the database of the pools/users/nodes
        self.database = db
        # Store and setup the nodeslist
        self.nodeList = nodeList
        self.nodeList.networkCB = self.networkCB
        self.nodeList.nodeChangeCB = self.nodeUpdateCB
        self.nodeList.adminCB = self.adminCB
        # Create the WebExplorer
        self.explorer = WebExplorer(self.balancesCB)
        self.balanceChecks = {}
        # Store the admins id
        self.admin = admin
        # Store the admin password
        self.password = password
        # Create the message queue
        self.messageQueue = MessagingMachine(self.bot, db)
        # Semphore to lock the balance check list.
        self.balanceSem = threading.Lock()

        # Get the dispather to add the needed handlers
        dp = self.updater.dispatcher

        #### Setup node related handler ####
        dp.add_handler(CommandHandler('add', self.nodeAdd, pass_args=True))
        dp.add_handler(CommandHandler('update', self.nodeUpdate, pass_args=True))
        dp.add_handler(CommandHandler('remove', self.nodeRemove, pass_args=True))
        dp.add_handler(CommandHandler('detail', self.detail))
        dp.add_handler(CommandHandler('nodes', self.nodes))
        dp.add_handler(CommandHandler('balance', self.balance))

        #### Setup user related handler ####
        dp.add_handler(CommandHandler('username', self.username, pass_args=True))
        dp.add_handler(CommandHandler('me', self.me))
        dp.add_handler(CommandHandler('status', self.status, pass_args=True))
        dp.add_handler(CommandHandler('reward', self.reward, pass_args=True))
        dp.add_handler(CommandHandler('timeout', self.timeout, pass_args=True))
        dp.add_handler(CommandHandler('network', self.network, pass_args=True))

        #### Setup common handler ####
        dp.add_handler(CommandHandler('start', self.started))
        dp.add_handler(CommandHandler('help', self.help))
        dp.add_handler(CommandHandler('info', self.info))
        dp.add_handler(MessageHandler(Filters.command, self.unknown))

        #### Setup admin handler, Not public ####
        dp.add_handler(CommandHandler('broadcast', self.broadcast, pass_args=True))
        dp.add_handler(CommandHandler('stats', self.stats, pass_args=True))
        dp.add_handler(CommandHandler('loglevel', self.loglevel, pass_args=True))
        dp.add_handler(CommandHandler('settings', self.settings, pass_args=True))

        dp.add_error_handler(self.error)

        self.sendMessage(self.admin, "*Bot Started*")

    ######
    # Starts the bot and block until the programm will be stopped.
    ######
    def start(self):
        logger.info("Start!")
        self.updater.start_polling()
        self.updater.idle()

    def isGroup(self, update):

        if update.message.chat_id != update.message.from_user.id:
            logger.warning("not allowed group action")
            response = messages.notAvailableInGroups
            self.sendMessage(update.message.chat_id, response )
            return True

        return False

    ######
    # Add a message to the queue
    ######
    def sendMessage(self, chatId, text, split = '\n'):
        self.messageQueue.addMessage(chatId, text, split)


    def adminCheck(self, chatId, password):
        logger.warning("adminCheck - {} == {}, {} == {}".format(self.admin, chatId, self.password, password))
        return int(self.admin) == int(chatId) and self.password == password


    ############################################################
    #                 Node handler calls                       #
    ############################################################

    def nodeAdd(self, bot, update, args):

        if not self.isGroup(update):
            response = node.nodeAdd(self, update, args)
            self.sendMessage(update.message.chat_id, response)

    def nodeUpdate(self, bot, update, args):

        if not self.isGroup(update):
            response = node.nodeUpdate(self, update, args)
            self.sendMessage(update.message.chat_id, response)

    def nodeRemove(self, bot, update, args):

        if not self.isGroup(update):
            response = node.nodeRemove(self, update, args)
            self.sendMessage(update.message.chat_id, response)

    def detail(self, bot, update):

        if not self.isGroup(update):
            response = node.detail(self, update)
            self.sendMessage(update.message.chat_id, response,'\n\n')

    def nodes(self, bot, update):

        response = node.nodes(self, update)
        self.sendMessage(update.message.chat_id, response,'\n\n')

    def balance(self, bot, update):

        if not self.isGroup(update):

            failed = None
            nodes = []

            dbNodes = self.database.getNodes(update.message.chat_id)
            user = self.database.getUser(update.message.chat_id)

            if user == None or dbNodes == None or len(dbNodes) == 0:

               response +=  messages.nodesRequired

               self.sendMessage(update.message.chat_id, response)
               return

            for node in dbNodes:
                nodes.append(self.nodeList.getNodeById(node['node_id']))

            check = self.explorer.balances(nodes)

            self.balanceSem.acquire()

            if check:
                self.balanceChecks[check] = update.message.chat_id
            else:
                failed = uuid.uuid4()
                self.balanceChecks[failed] = update.message.chat_id

            self.balanceSem.release()

            if failed:
                self.balancesCB(failed,None)

    ############################################################
    #                 User handler calls                     #
    ############################################################

    def username(self, bot, update, args):

        if not self.isGroup(update):
            response = user.username( self, update, args)
            self.sendMessage(update.message.chat_id, response)

    def me(self, bot, update):

        if not self.isGroup(update):
            response = user.me( self, update )
            self.sendMessage(update.message.chat_id, response)

    def status(self, bot, update, args):

        if not self.isGroup(update):
            response = user.status( self, update, args )
            self.sendMessage(update.message.chat_id, response)

    def reward(self, bot, update, args):

        if not self.isGroup(update):
            response = user.reward( self, update, args )
            self.sendMessage(update.message.chat_id, response)

    def timeout(self, bot, update, args):

        if not self.isGroup(update):
            response = user.timeout( self, update, args )
            self.sendMessage(update.message.chat_id, response)

    def network(self, bot, update, args):

        if not self.isGroup(update):
            response = user.network( self, update, args )
            self.sendMessage(update.message.chat_id, response)

    ############################################################
    #                 Common handler calls                     #
    ############################################################

    def started(self, bot, update):

        self.sendMessage(update.message.chat_id, '**Welcome**\n\n' + messages.helpMsgTelegram)

    def help(self, bot, update):

        self.sendMessage(update.message.chat_id, messages.help(self.messenger))

    def info(self, bot, update):

        response = common.info( self, update )
        self.sendMessage(update.message.chat_id, response)

    def broadcast(self, bot, update, args):

        if len(args) >= 2 and\
           self.adminCheck(update.message.chat_id, args[0]):

            logger.warning("broadcast - access granted")

            response = " ".join(args[1:])

            for user in self.database.getUsers():
                self.sendMessage(user['id'], response)
        else:
            response = common.unknown(self, update)
            self.sendMessage(update.message.chat_id, response)

    def stats(self, bot, update, args):

        if len(args) == 1 and\
           self.adminCheck(update.message.chat_id, args[0]):

            logger.warning("stats - access granted")

            response = common.stats(self)

            self.sendMessage(self.admin, response)
        else:
            response = common.unknown(self)
            self.sendMessage(update.message.chat_id, response)

    def loglevel(self, bot, update, args):

        if len(args) >= 2 and\
           self.adminCheck(update.message.chat_id, args[0]):

            logger.warning("loglevel - access granted")

            response = "*Loglevel*"

            self.sendMessage(self.admin, response)
        else:
            response = common.unknown(self)
            self.sendMessage(update.message.chat_id, response)

    def settings(self, bot, update, args):

        if len(args) == 1 and\
           self.adminCheck(update.message.chat_id, args[0]):

            logger.warning("settings - access granted")

            response = "*Settings*"

            self.sendMessage(self.admin, response)
        else:
            response = common.unknown(self)
            self.sendMessage(update.message.chat_id, response)

    def unknown(self, bot, update):

        response = common.unknown(self)
        self.sendMessage(update.message.chat_id, response)

    def error(self, bot, update, error):

        common.error(self, update, error)


    ############################################################
    #                        Callbacks                         #
    ############################################################


    ######
    # Callback which get called when there is a new releases in the smartcash repo.
    #
    # Called by: Nothing yet, SmartGitHubUpdates later.
    #
    ######
    def updateCheckCallback(self, tag):

        for user in self.database.getUsers():
            self.sendMessage(user['id'], ("*Node update available*\n\n"
                                         "https://github.com/SmartCash/smartcash/releases/tag/{}").format(tag))

    ######
    # Callback for evaluating if someone in the database had an upcomming event
    # and send messages to all chats with activated notifications
    #
    # Called by: SmartNodeList
    #
    ######
    def nodeUpdateCB(self, update, n):

        for user in self.database.getUsers():

            userNode = self.database.getNode(n.id, user['id'])

            if userNode == None:
                continue

            logger.info("nodeUpdateCB {}".format(n.payee))

            for response in node.nodeUpdated(self, update, user, userNode, n):
                self.sendMessage(user['id'], response)

    ######
    # Callback for evaluating if someone has enabled network notifications
    # and send messages to all relevant chats
    ######
    def networkCB(self, ids, added):

        response = common.networkUpdate(self, ids, added)

        for user in self.database.getUsers():

            if user['network_n']:
                self.sendMessage(user['id'], response)


    ######
    # Callback which gets called from the SmartNodeList when a balance request triggered by any user
    # is done. It sends the result to the related user.
    #
    # Called by: SmartExplorer
    #
    ######
    def balancesCB(self, check, results):

        self.balanceSem.acquire()

        if not check in self.balanceChecks:
            logger.error("Ivalid balance check received {} - count {}".format(check,len(results)))
            return

        userId = self.balanceChecks[check]
        self.balanceChecks.pop(check)

        self.balanceSem.release()

        response = node.balances(self, userId, results)

        self.sendMessage(userId, response)

    ######
    # Push the message to the admin
    #
    # Called by: SmartNodeList
    #
    ######
    def adminCB(self, message):
        self.sendMessage(self.admin, message)
