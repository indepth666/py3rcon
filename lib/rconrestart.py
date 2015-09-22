import rconprotocol
import sched
import logging
import time
import threading

class RestartMessage():

    def __init__(self, min, message):
        self.min = min
        self.message = message

    def toSecond(self):
        return self.min * 60


class RconRestart():

    def __init__(self, rcon):
        # shutdown and shutdown message scheduler
        self.sched = sched.scheduler(time.time, time.sleep)
        self.shutdownTimer = 0
        self.restartMessages = None
	self.exitOnRestart = False


	self.rcon = rcon

	logging.debug('RconRestart() initialized')

    def setInterval(self, min):
	self.shutdownTimer = min * 60

    def setMessages(self, messageList):
	self.restartMessages = messageList

    def setExitOnRestart(self, yesNo):
	self.exitOnRestart = yesNo

    def OnConnected(self):
	if self.shutdownTimer > 0:
	    # a separate thread to handle the restart and restart messages
    	    # It is set as daemon to be able to stop it using SystemExit or Ctrl + C
	    t = threading.Thread(target=self._initRestartScheduler)
	    t.daemon = True
	    t.start()
	    logging.info('OnConnect(): Initialized the restarter thread')
	else:
	    logging.info("OnConnect(): Restart module disabled")

    def _restartMessageTask(self, msg):
        logging.info('Sending restart message: {}'.format(msg))
        self.rcon.sendCommand("say -1 \"%s\"" % msg)

    def _shutdownTask(self):
        self.rcon.lockServer();
        self.rcon.kickAll()

        # wait some seconds before restarting
        logging.info('Delay the shutdown process')
        time.sleep(30)

        logging.info('Sending shutdown command')
        self.rcon.sendCommand('#shutdown')

    def _emptyScheduler(self):
        if not self.sched.empty():
            for q in self.sched.queue:
                self.sched.cancel(q)

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
        if self.exitOnRestart:
            self.rcon.Abort()

