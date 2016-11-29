#!/usr/bin/python -B

import os, signal, sys, argparse, threading, json, logging, tempfile, time
import lib
from lib.rconprotocol import Rcon

pid = str(os.getpid())

_DESC = 'Python Rcon CLI for Arma servers'
_VER = '0.2'

parser = argparse.ArgumentParser(description=_DESC)
parser.add_argument('configfile', help='configuration file in JSON')
parser.add_argument('-g','--gui', action='store_true',help='open the GUI - no other events are enabled')
args = parser.parse_args()

GUI = args.gui

if not os.path.isfile(args.configfile):
    print('')
    print(' -- Configuration not found: "{}" --\n').format(args.configfile)
    exit(1)

with open(args.configfile) as json_config:
    config = json.load(json_config)

_bstr = os.path.basename(args.configfile)
_n = 48 - len(_bstr)

#print('{} using configuration {}').format(_DESC, _bstr)
print('py3rcon version: %s - running on %s' % (_VER, os.name))
print('')

# Logging tool configuration
print('Logging to: {}'.format(config['logfile']))
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(filename=config['logfile'], level=config['loglevel'], format=FORMAT)
pidfile = '{}/py3rcon.{}.run'.format(tempfile.gettempdir(),config['server']['port'])



if not(GUI):
    if os.path.isfile(pidfile):
        _tmp =('pyrcon is already running for {}:{}'.format(config['server']['host'], config['server']['port']))
        print(_tmp)
        logging.info(_tmp)
        exit()

    open(pidfile, 'w').write(pid)

##
# Initialize the rconprotocol class
##
rcon = Rcon(config['server']['host'], config['server']['rcon_password'], config['server']['port'], True)

##
# Load the rconrestart module and setup from configuration
##
if not(GUI):
    modRestart = rcon.loadmodule('rconrestart', 'RconRestart')
    modRestart.setMessages(config['restart']['messages'] )
    modRestart.setInterval(config['restart']['interval'] )
    modRestart.setExitOnRestart(config['restart']['exitonrestart'])

##
# Load the rconmessage module and setup from configuration
##
if not(GUI):
    modMessage = rcon.loadmodule('rconmessage', 'RconMessage')
    modMessage.setInterval(config['repeatMessage']['interval'] )
    modMessage.setMessages(config['repeatMessage']['messages'] )

##
# Load the rcon admin commands module
##
if not(GUI) and 'commands' in config:
    modCommand = rcon.loadmodule('rconcommand', 'RconCommand')
    _p = os.path.abspath(os.path.dirname(sys.argv[0]))
    modCommand.setConfig(_p + '/' + config['commands'] )

if GUI:
    modGUI = rcon.loadmodule('rcongui', 'RconGUI')
    modGUI.setLogfile( config['logfile'] )


##
# Connect to server
##
try:
    rcon.connectAsync()
    print("Press CTRL + C to Exit")
    while rcon.IsAborted() == False:
        time.sleep(1)
except (KeyboardInterrupt, SystemExit):
    rcon.Abort()

if not(GUI): os.unlink(pidfile)
