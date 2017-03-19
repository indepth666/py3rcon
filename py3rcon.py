#!/usr/bin/python -B

import os, signal, sys, argparse, threading, json, logging, tempfile, time
import lib
from lib.rconprotocol import Rcon

pid = str(os.getpid())

_DESC = 'Python Rcon CLI for Arma servers'
_VER = '0.2.1'

parser = argparse.ArgumentParser(description=_DESC)
parser.add_argument('configfile', help='configuration file in JSON')
parser.add_argument('-g','--gui',action='store_true', help='open the GUI - no other events are enabled')
parser.add_argument('-w', '--web',action='store_true', help='initialize a webserver providing some rcon features')
args = parser.parse_args()

GUI = args.gui
WEB = args.web

if not os.path.isfile(args.configfile):
    print('')
    print(' -- Configuration not found: "{}" --\n').format(args.configfile)
    exit(1)

with open(args.configfile) as json_config:
    config = json.load(json_config)

print("py3rcon version: %s - running on %s\n" % (_VER, os.name))

# Logging tool configuration
print('Logging to: {}'.format(config['logfile']))
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(filename=config['logfile'], level=config['loglevel'], format=FORMAT)
pidfile = '{}/py3rcon.{}.run'.format(tempfile.gettempdir(),config['server']['port'])

if not(GUI) and not(WEB):
    if os.path.isfile(pidfile):
        _tmp = 'pyrcon is already running for %s:%s' % (config['server']['host'], config['server']['port'])
        print(_tmp)
        logging.info(_tmp)
        exit()

    open(pidfile, 'w').write(pid)

try:
    ##
    # Initialize the rconprotocol class
    ##
    rcon = Rcon(config['server']['host'], config['server']['rcon_password'], config['server']['port'])

    if not(GUI) and not(WEB):
        # Load the rconrestart module and setup from configuration
        rcon.loadmodule('rconrestart', 'RconRestart', config['restart'])
        # Load the rconmessage module and setup from configuration
        rcon.loadmodule('rconmessage', 'RconMessage', config['repeatMessage'])
        # Load the rcon admin commands module
        if 'commands' in config: rcon.loadmodule('rconcommand', 'RconCommand', config['commands'])
        if 'whitelist' in config:
            rcon.loadmodule('rconwhitelist', 'RconWhitelist', config['whitelist'], GUI)
        
    if GUI:
        rcon.loadmodule('rcongui', 'RconGUI', config)
    elif WEB:
        if sys.version_info.major <= 2:
            logging.error('PYTHON 3 IS REQUIRED')
            print("PYTHON 3 IS REQUIRED")
            exit()
        rcon.loadmodule('rconweb', 'RconWEB', config)

    # connect to server (async)
    rcon.connectAsync()
    print("Press CTRL + C to Exit")
    while rcon.isExit == False:
        time.sleep(1)
except (KeyboardInterrupt, SystemExit):
    rcon.Abort()
except:
    raise
finally:
    if not(GUI) and not(WEB): os.unlink(pidfile)
