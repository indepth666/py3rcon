#!/usr/bin/python -B

import os, signal, sys, argparse, threading, json, logging
import lib
from lib.rconprotocol import Rcon

def signal_term_handler(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_term_handler)

pid = str(os.getpid())

parser = argparse.ArgumentParser(description='Python Rcon cmdlet for ARMA3 Servers')
parser.add_argument('configfile', help='configuration file in JSON')

args = parser.parse_args()

if not os.path.isfile(args.configfile):
    print ''
    print ' -- Configuration not found: "{}" --\n'.format(args.configfile)
    exit(1)

with open(args.configfile) as json_config:
    config = json.load(json_config)

_bstr = os.path.basename(args.configfile)
_n = 48 - len(_bstr)

print 'PyRcon for ARMA3 CLI v0.1'
print ''
print '#'.ljust(71, '#')
print '# Configuration file: {}{}#'.format(_bstr , ''.ljust(_n, ' '))
print '#'.ljust(71, '#')
print '# DO NOT FORGET TO SETUP THE beserver.cfg LOCATED IN battleye/ FOLDER #'
print '#'.ljust(71, '#')
print ''

# Logging tool configuration
print 'Logging to: {}'.format(config['logfile'])
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(filename=config['logfile'], level=config['loglevel'], format=FORMAT)

pidfile = '/tmp/pyrcon.{}.run'.format(config['server']['port'])

if os.path.isfile(pidfile):
    _tmp = 'pyrcon is already running for {}:{}'.format(config['server']['host'], config['server']['port'])
    print _tmp
    logging.info(_tmp)
    exit()

open(pidfile, 'w').write(pid)

logging.debug("Initialize rconprotocol class object")

##
# Initialize the rconprotocol class
##
rcon = Rcon(config['server']['host'], config['server']['rcon_password'], config['server']['port'], True)

##
# Load the rconrestart module and setup from configuration
##
modRestart = rcon.loadmodule('rconrestart', 'RconRestart', ['RestartMessage'])
_rlist = []
for m in config['restart']['messages']:
    _rlist.append( lib.rconrestart.RestartMessage(m[0],m[1]) )

modRestart.setMessages( _rlist )
modRestart.setInterval( config['restart']['interval'] )
modRestart.setExitOnRestart(config['restart']['exitonrestart'])

##
# Load the rconmessage module and setup from configuration
##
modMessage = rcon.loadmodule('rconmessage', 'RconMessage')
modMessage.setInterval( config['repeatMessage']['interval'] )
modMessage.setMessages( config['repeatMessage']['messages'] )

##
# Connect to server
##
rcon.connect()

# remove PID
os.unlink(pidfile)
