#!/usr/bin/env python3

import logging
import threading
import time
import json
import discord
import asyncio
import uuid

from fuzzywuzzy import process as fuzzy

from src import util
from src import messages
from src.commandhandler import node
from src.commandhandler import user
from src.commandhandler import common
from src.smartexplorer import WebExplorer

from smartcash.rewardlist import SNReward

logger = logging.getLogger("bot")

class SmartNodeBotDiscord(object):

    def __init__(self, botToken, admin, password, db, nodeList, rewardList):

        # Currently only used for markdown
        self.messenger = "discord"

        self.client = discord.Client()
        self.client.on_ready = self.on_ready
        self.client.on_message = self.on_message
        # Create a bot instance for async messaging
        self.token = botToken
        # Set the database of the pools/users/nodes
        self.database = db
        # Store and setup the nodeslist
        self.nodeList = nodeList
        self.nodeList.networkCB = self.networkCB
        self.nodeList.nodeChangeCB = self.nodeUpdateCB
        self.nodeList.adminCB = self.adminCB
        # Store and setup the nodereward list
        self.rewardList = rewardList
        self.rewardList.rewardCB = self.rewardCB
        self.rewardList.errorCB = self.rewardListErrorCB
        # Create the WebExplorer
        self.explorer = WebExplorer(self.balancesCB)
        self.balanceChecks = {}
        # Store the admin password
        self.password = password
        # Store the admin user
        self.admin = admin
        # Semphore to lock the balance check list.
        self.balanceSem = threading.Lock()

        self.aberration = 0

    def runClient(self):

        loop = asyncio.get_event_loop()

        while True:

            try:
                loop.run_until_complete(self.client.start(self.token))
            except KeyboardInterrupt:
                logger.warning("Terminate!")
                self.stop()
                return
            except Exception as e:
                logger.error("Bot crashed?! ", e)

            time.sleep(600)

    ######
    # Starts the bot and block until the programm gets stopped.
    ######
    def start(self):
        logger.info("Start!")
        self.runClient()

    def stop(self):

        self.rewardList.stop()
        self.nodeList.stop()

    ######
    # Send a message :text to a specific user :user
    ######
    async def sendMessage(self, user, text, split = '\n'):

        logger.info("sendMessage - Chat: {}, Text: {}".format(user,text))

        parts = messages.splitMessage(text, split, 2000)

        try:
            for part in parts:
                await self.client.send_message(user, part)
        except discord.errors.Forbidden:
            logging.error('sendMessage user blocked the bot')

            # Remove the user and the assigned nodes.
            self.database.deleteNodesForUser(user.id)
            self.database.deleteUser(user.id)

        except discord.errors.HTTPException as e:
            logging.error('HTTPException', exc_info=e)
        except Exception as e:
            logging.error('sendMessage', exc_info=e)
        else:
            logger.info("sendMessage - OK!")

    async def on_ready(self):

        logger.info('Logged in as')
        logger.info(self.client.user.name)
        logger.info(self.client.user.id)
        logger.info('------')

        # Advise the admin about the start.
        self.adminCB("**Bot started**")

        # Start its task and leave it
        self.rewardList.start()

        while not self.rewardList.running:
            time.sleep(1)
            logger.info("Init: RewardList")

        logger.info("Ready: RewardList")

        # Start its task and leave it
        self.nodeList.start()

        while not self.nodeList.running:
            time.sleep(1)
            logger.info("Init: NodeList")

        logger.info("Ready: NodeList")

        # Lock the nodelist since we iterate over all nodes
        self.nodeList.acquire()

        # Update the sources where the blocks are assigned to the nodelist
        for node in self.nodeList.nodeList.values():

            if node.lastPaidBlock <= 0:
                continue

            reward = self.rewardList.getReward(int(node.lastPaidBlock))

            if not reward:
                continue

            if reward.source == 1:
                continue

            reward = SNReward(block=node.lastPaidBlock,
                              payee = node.payee,
                              txtime=node.lastPaidTime,
                              source=1)

            self.rewardList.updateSource(reward)

        # And finally release it!
        self.nodeList.release()

    ######
    # Discord api coroutine which gets called when a new message has been
    # received in one of the channels or in a private chat with the bot.
    ######
    async def on_message(self,message):

        if message.author == self.client.user:
            # Just jump out if its the bots message.
            return

        # split the new messages by spaces
        parts = message.content.split()

        command = None
        args = None

        # If the first mention in the message is the bot itself
        # and there is a possible command in the message
        if len(message.mentions) == 1 and message.mentions[0] == self.client.user\
            and len(parts) > 1:
            command = parts[1]
            args = parts[2:]
        # If there are multiple mentions send each one (excluded the bot itself)
        # the help message.
        # Like: hey @dustinface and @whoever check out the @SmartNodeMonitorBot
        # The above would send @dustinface and @whoever the help message of the bot.
        elif len(message.mentions) > 1 and self.client.user in message.mentions:

            for mention in message.mentions:
                if not mention == self.client.user:

                    # Check if the user is already in the databse
                    result = common.checkUser(self, mention)

                    if result['response']:
                        await self.sendMessage(mention, result['response'])

                    if result['added']:
                        continue

                    await self.sendMessage(mention, messages.help(self.messenger))

            return
        # If there are no mentions and we are in a private chat
        elif len(message.mentions) == 0 and not isinstance(message.author, discord.Member):
            command = parts[0]
            args = parts[1:]
        # If we got mentioned but no command is available in the message just send the help
        elif len(message.mentions) and message.mentions[0] == self.client.user and\
              len(parts) == 1:
              command = 'help'
        # No message of which the bot needs to know about.
        else:
            logger.debug("on_message - jump out {}".format(self.client.user))
            return

        # If we got here call the command handler to see if there is any action required now.
        await self.commandHandler(message, command.lower(), args)

    ######
    # Handles incomming splitted messages. Check if there are commands which require
    # any action. If so it calls the related methods and sends the response to
    # the author of the command message.
    ######
    async def commandHandler(self, message, command, args):

        logger.info("commandHandler - {}, command: {}, args: {}".format(message.author, command, args))

        # Check if the user is already in the databse
        result = common.checkUser(self, message)

        if result['response']:
            await self.sendMessage(message.author, result['response'])

        if result['added'] and not isinstance(message.author, discord.Member):
            return

        # per default assume the message gets back from where it came
        receiver = message.author

        ####
        # List of available commands
        # Public = 0
        # DM-Only = 1
        # Admin only = 2
        ####
        commands = {
                    # Common commands
                    'help':0, 'info':0,
                    # User commmands
                    'me':1,'status':1,'reward':1,'network':1, 'timeout':1,
                    # Node commands
                    'add':1,'update':1,'remove':1,'nodes':1, 'detail':1,'history':1, 'balance':1, 'lookup':1,
                    # Admin commands
                    'stats':2, 'broadcast':2, 'payouts':2
        }

        choices = fuzzy.extract(command,commands.keys(),limit=2)

        if choices[0][1] == choices[1][1] or choices[0][1] < 60:
            logger.debug('Invalid fuzzy result {}'.format(choices))
            command = 'unknown'
        else:
            command = choices[0][0]

        # If the command is DM only
        if command in commands and commands[command] == 1:

            if isinstance(message.author, discord.Member):
             await self.client.send_message(message.channel,\
             message.author.mention + ', the command `{}` is only available in private chat with me!'.format(command))
             await self.client.send_message(message.author, messages.markdown('<b>Try it here!<b>\n', self.messenger))
             await self.client.send_message(message.author, messages.help(self.messenger))
             return

        else:
            receiver = message.channel

        # If the command is admin only
        if command in commands and commands[command] == 2:

            # Admin command got fired in a public chat
            if isinstance(message.author, discord.Member):
                # Just send the unknown command message and jump out
                await self.sendMessage(receiver, (message.author.mention + ", " + common.unknown(self)))
                logger.info("Admin only, public")
                return

            # Admin command got fired from an unauthorized user
            if int(message.author.id) == int(self.admin) and\
                len(args) >= 1 and args[0] == self.password:
                receiver = message.author
            else:
                logger.info("Admin only, other")

                # Just send the unknown command message and jump out
                await self.sendMessage(receiver, (message.author.mention + ", " + common.unknown(self)))
                return

        ### Common command handler ###
        if command == 'info':
            response = common.info(self,message)
            await self.sendMessage(receiver, response)
        ### Node command handler ###
        elif command == 'add':
            response = node.nodeAdd(self,message,args)
            await self.sendMessage(receiver, response)
        elif command == 'update':
            response = node.nodeUpdate(self,message,args)
            await self.sendMessage(receiver, response)
        elif command == 'remove':
            response = node.nodeRemove(self,message,args)
            await self.sendMessage(receiver, response)
        elif command == 'nodes':
            response = node.nodes(self,message)
            await self.sendMessage(receiver, response)
        elif command == 'detail':
            response = node.detail(self,message)
            await self.sendMessage(receiver, response)
        elif command == 'history':
            response = node.history(self,message)
            await self.sendMessage(receiver, response)
        elif command == 'balance':

            failed = None
            nodes = []

            dbUser = self.database.getUser(message.author.id)
            userNodes = self.database.getAllNodes(message.author.id)

            # If there is no nodes added yet send an error and return
            if dbUser == None or userNodes == None or len(userNodes) == 0:

                response = messages.markdown("<u><b>Balances<b><u>\n\n",self.messenger)
                response += messages.nodesRequired(self.messenger)

                await self.sendMessage(message.author, response)
                return

            collaterals = list(map(lambda x: x['collateral'],userNodes))
            nodes = self.nodeList.getNodes(collaterals)
            check = self.explorer.balances(nodes)

            # Needed cause the balanceChecks dict also gets modified from other
            # threads.
            self.balanceSem.acquire()

            if check:
                self.balanceChecks[check] = message.author.id
            else:
                logger.info("Balance check failed instant.")
                failed = uuid.uuid4()
                self.balanceChecks[failed] = message.author.id

            # Needed cause the balanceChecks dict also gets modified from other
            # threads.
            self.balanceSem.release()

            if failed:
                self.balancesCB(failed,None)

        elif command == 'lookup':
            response = messages.markdown(node.lookup(self,message, args),self.messenger)
            await self.sendMessage(receiver, response)
        ### User command handler ###
        elif command == 'me':
            response = user.me(self,message)
            await self.sendMessage(receiver, response)
        elif command == 'status':
            response = user.status(self,message, args)
            await self.sendMessage(receiver, response)
        elif command == 'reward':
            response = user.reward(self,message, args)
            await self.sendMessage(receiver, response)
        elif command == 'timeout':
            response = user.timeout(self,message, args)
            await self.sendMessage(receiver, response)
        elif command == 'network':
            response = user.network(self,message, args)
            await self.sendMessage(receiver, response)

        ### Admin command handler ###
        elif command == 'stats':
            response = common.stats(self)
            await self.sendMessage(receiver, response)
        elif command == 'payouts':
            response = common.payouts(self,args[1:])
            await self.sendMessage(receiver, response)
        elif command == 'broadcast':

            response = " ".join(args[1:])

            for dbUser in self.database.getUsers():

                member = self.findMember(dbUser['id'])

                if member:
                    await self.sendMessage(member, response)

        # Help message
        elif command == 'help':
            await self.sendMessage(receiver, messages.help(self.messenger))

        # Could not match any command. Send the unknwon command message.
        else:
            await self.sendMessage(receiver, (message.author.mention + ", " + common.unknown(self)))

    ######
    # Unfortunately there is no better way to send messages to a user if you have
    # only their userId. Therefor this method searched the discord user object
    # in the global member list and returns is.
    ######
    def findMember(self, userId):

        for member in self.client.get_all_members():
            if int(member.id) == int(userId):
                return member

        logger.info ("Could not find the userId in the list?! {}".format(userId))

        return None


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

        responses = node.handleNodeUpdate(self, update, n)

        for userId, messages in responses.items():

            member = self.findMember(userId)

            if member:

                for message in messages:
                        asyncio.run_coroutine_threadsafe(self.sendMessage(member, message), loop=self.client.loop)

    ######
    # Callback for evaluating if someone in the database has won the reward
    # and send messages to all chats with activated notifications
    #
    # Called by: SNRewardList from python-smartcash
    #
    ######
    def rewardCB(self, reward, distance):

        responses = node.handleReward(self, reward, distance)

        for userId, messages in responses.items():

            member = self.findMember(userId)

            if member:

                for message in messages:
                        asyncio.run_coroutine_threadsafe(self.sendMessage(member, message), loop=self.client.loop)

        start = int(time.time() - 43200) # 12 hours of collecting
        total = self.rewardList.getRewardCount(start = start)
        nList = self.rewardList.getRewardCount(start = start, source=1)
        if nList and total:
            self.aberration = 1 - ( nList / total)


    ######
    # Callback for SNRewardList errors
    #
    # Called by: SNRewardList from python-smartcash
    #
    ######
    def rewardListErrorCB(self, error):
        self.adminCB(str(error))

    #####
    # Callback for evaluating if someone has enabled network notifications
    # and send messages to all relevant chats
    #
    # Called by: SmartNodeList
    #
    ######
    def networkCB(self, collaterals, added):

        response = common.networkUpdate(self, collaterals, added)

        # Handle the network update notifications.
        for dbUser in self.database.getUsers('where network_n=1'):

            member = self.findMember(dbUser['id'])

            if member:
                asyncio.run_coroutine_threadsafe(self.sendMessage(member, response), loop=self.client.loop)

        if added:
            # If the callback is related to new nodes no need for
            # the continue here.
            return

        # Remove the nodes also from the user database
        for collateral in collaterals:

            # Before chec if a node from anyone got removed and let him know about it.
            for userNode in self.database.getNodes(collateral):

                member = self.findMember(userNode['user_id'])

                if member:
                    response = messages.nodeRemovedNotification(self.messenger, userNode['name'])
                    asyncio.run_coroutine_threadsafe(self.sendMessage(member, response), loop=self.client.loop)

            # Remove all entries containing this node in the db
            self.database.deleteNodesWithId(collateral)

    ######
    # Callback which gets called from the SmartNodeList when a balance request triggered by any user
    # is done. It sends the result to the related user.
    #
    # Called by: SmartExplorer
    #
    ######
    def balancesCB(self, check, results):

        # Needed cause the balanceChecks dict also gets modified from other
        # threads.
        self.balanceSem.acquire()

        if not check in self.balanceChecks:
            logger.error("Ivalid balance check received {} - count {}".format(check,len(results)))
            self.balanceSem.release()
            return

        userId = self.balanceChecks[check]
        self.balanceChecks.pop(check)

        # Needed cause the balanceChecks dict also gets modified from other
        # threads.
        self.balanceSem.release()

        response = node.balances(self, userId, results)

        member = self.findMember(userId)

        if member:
            asyncio.run_coroutine_threadsafe(self.sendMessage(member, response), loop=self.client.loop)

    ######
    # Push the message to the admin
    #
    # Called by: SmartNodeList
    #
    ######
    def adminCB(self, message):

        admin = self.findMember(self.admin)

        if admin:
            asyncio.run_coroutine_threadsafe(self.sendMessage(admin, message), loop=self.client.loop)
        else:
            logger.warning("adminCB - Could not find admin.")
