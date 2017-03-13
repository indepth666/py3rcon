import lib.rconprotocol
import sched
import logging
import time
import threading

"""
RconRestart class module.
Used to setup a shutdown timer with restart messages.

Please note that this module will only exit the server.
You may need an additional script (or watchdog) to get the server back online.
"""
class RconRestart(object):
    def __init__(self, rcon, config):
        # shutdown and shutdown message scheduler
        self.sched = sched.scheduler(time.time, time.sleep)
        self.shutdownTimer = 0
        self.restartMessages = None
        self.exitOnRestart = False
        self.inProgress = False
        self.canceled = False
        self.rcon = rcon

        self.shutdownDelay = config['delay'] if 'delay' in config and config['delay'] >= 5 else 15

        self.setMessages(config['messages'])
        self.setInterval(config['interval'])
        self.setExitOnRestart(config['exitonrestart'])
        
        logging.debug('%s() initialized' % type(self).__name__)

    """
    Set an interval when the server should receive the shutdown command
    @param integer min - no of minutes until server shutdown
    """
    def setInterval(self, min):
        self.shutdownTimer = min * 60

    """
    set a list messages as (multidimensional array) to inform players when the server restart
    The format of this array is as following:
        [<minBeforeRestart|integer>, "<Message|string>"],
        Example:
        [
            [5, "Restart in 5 minutes"],
            [10,"Restart in 10 minutes"]
        ]
    """
    def setMessages(self, messageList):
        self.restartMessages = []
        for m in messageList:
            self.restartMessages.append( RestartMessage(m[0],m[1]) )

    """
    Exit this application (by using Rcon.Abort()) when the restart occured
    @param bool yesNo - true = exit the program when shutdown command has been sent, otherwise not
    """
    def setExitOnRestart(self, yesNo):
        self.exitOnRestart = yesNo

    """
    Event: Called from Rcon.OnConnected()
    When connection is established start the "restart" schedule
    """
    def OnConnected(self):
        if self.shutdownTimer > 0 and self.inProgress == False:
            # a separate thread to handle the restart and restart messages
            # It is set as daemon to be able to stop it using SystemExit or Ctrl + C
            t = threading.Thread(target=self._initRestartScheduler)
            t.daemon = True
            t.start()
            logging.info('OnConnect(): %s ready to restart server every %d seconds' % (type(self).__name__, self.shutdownTimer))
        else:
            logging.info("OnConnect(): %s disabled" % type(self).__name__)

    """
    Event: Called from Rcon.OnReconnected()
    """
    def OnReconnected(self):
        if self.shutdownTimer > 0 and self.inProgress == False:
            # restart the module
            t = threading.Thread(target=self._initRestartScheduler)
            t.daemon = True
            t.start()
            logging.info('OnReconnect(): %s ready to restart server every %d seconds' % (type(self).__name__, self.shutdownTimer))

    """
    private: restart message to warn the players
    """
    def _restartMessageTask(self, msg):
        logging.info('Sending restart message: {}'.format(msg))
        self.rcon.sendCommand("say -1 \"%s\"" % msg)

    """
    private: the actual shutdown call (with some delay to make sure players are disconnected)
    """
    def _shutdownTask(self):
        self.inProgress = True
        self.rcon.lockServer()
        self.rcon.kickAll()

        # wait some seconds before restarting
        logging.info('Delay the shutdown process')
        time.sleep(self.shutdownDelay)

        logging.info('Sending shutdown command')
        self.rcon.sendCommand('#shutdown')
        self.inProgress = False

    """
    private: Clear all schedules
    """
    def _emptyScheduler(self):
        if not self.sched.empty():
            for q in self.sched.queue:
                self.sched.cancel(q)

    """
    public: call to cancel the shutdown process
    """
    def cancelRestart(self):
        self.canceled = True
        self._emptyScheduler()
        self.rcon.sendCommand("say -1 \"RESTART CANCELED\"")

        # Cancel the current shutdown timer, BUT continue with regular restarts
        self.OnConnected()

    """
    private: initialize the scheduler for restart messages and the shutdown itself
    """
    def _initRestartScheduler(self):
        # make sure all previous scheds are being removed
        self._emptyScheduler()
        self.sched.enter(self.shutdownTimer, 1, self._shutdownTask, ())

        if type(self.restartMessages) is list:
            for msg in self.restartMessages:
                if int(self.shutdownTimer - msg.toSecond()) > 0:
                    self.sched.enter( self.shutdownTimer - msg.toSecond(), 1, self._restartMessageTask, (msg.message,) )

        self.sched.run()
        logging.debug('All shutdown tasks executed')
        if self.exitOnRestart and not self.canceled:
            self.rcon.Abort()

        self.canceled = False


"""
RestartMessage Class used to inform the players before shutdown take action
"""
class RestartMessage():
    def __init__(self, min, message):
        self.min = min
        self.message = message

    def toSecond(self):
        return self.min * 60
