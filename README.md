py3rcon
============
<sup>Version: 0.2.1 | Authors: indepth666 (Basic protocol design), ole1986 (CLI)</sup>

py3rcon is a Python3 client for Battleye Rcon protocol. 
It's designed with ARMA2 and ARMA3 in mind but may also work with other implemenation of the protocol.


How to use?
===========

Configuration example can be found in configexample.json.

<pre>Usage: ./py3rcon.py &lt;configfile&gt;</pre>

**PLEASE NOTE:**<br />
Since version 1.58.1* of Arma 3 it is REQUIRED to add the line `RConPort <port>` into the beserver.cfg<br />
Otherwise Rcon will possible not work.

Configuration explained
=======================

PLEASE NOTE: The configuration is stored JSON file. This format usually does not allow comments.

Config entry            | Example        | Description
----------------------- | -------------- | -----------
logfile                 | pyrcon.log     | File name of the pyrcon log
loglevel                | 10             | Loglevel (10 = show debug info, 20 = exclude debug info, 30 = display only error and warnings)
server : host           | 127.0.0.1      | Hostname of the armaX server
server : port           | 2402           | Port of the armaX server
server : rcon_password  | yourPW         | Rcon password
commands                | commands.json  | Commands configuration file in JSON format (rconcommand module)
whitelist               | whitelist.json | stores the whitelisted players used by rconwhitelist module
restart : interval      | 240            | Restart interval in minutes
restart : delay         | 15             | Wait x seconds until shutdown after players have been kicked
restart : exitonrestart | true           | End the application when restart interval has reached

GUI
========================
Use the following command to display the GUI.

To run the py3rcon GUI on WINDOWS an unofficial version of curses is REQUIRED: 
Download Link: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses

**PLEASE NOTE:**<br /> 
When using the `--gui` argument, schedules like **repeating messages** and **restart** become disabled

<pre>Usage: ./py3rcon.py --gui &lt;configfile&gt;</pre>

<pre>
#---------------------------# #-------------------------------------------------------------------------------#
| Refresh Players           | |                                                                               |
| Manage Whitelist          | |                                                                               |
| Restart Mission...        | |                                                                               |
| Kick All                  | |                                                                               |
| Shutdown Server           | |                                                                               |
| Restart Server (v1.65)    | |                                                                               |
| Exit                      | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
|                           | |                                                                               |
#---------------------------# #-------------------------------------------------------------------------------#
#-  Enter command --------------------------------------------------------------------------------------------#
|                                                                                                             |
#-------------------------------------------------------------------------------------------------------------#
#-------------------------------------------------------------------------------------------------------------#
| 2016-12-01 21:20:11,927 INFO [Server: xxxxxxxxxxx.xx:10501]: Authenticated                                  |
| 2016-12-01 21:20:11,986 INFO [Server: xxxxxxxxxxx.xx:10501]: RCon admin #0 (xx.xx0.xx1.97:54410) logged in  |
| 2016-12-01 21:20:12,018 INFO [Server: xxxxxxxxxxx.xx:10501]: Players on server:                             |
| [#] [IP Address]:[Port] [Ping] [GUID] [Name]                                                                |
| --------------------------------------------------                                                          |
| (0 players in total)                                                                                        |
#-------------------------------------------------------------------------------------------------------------#
</pre>
