# Copyright 2014, Oliver Nagy <olitheolix@gmail.com>
#
# This file is part of Azrael (https://github.com/olitheolix/azrael)
#
# Azrael is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Azrael is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Azrael. If not, see <http://www.gnu.org/licenses/>.

"""
Global configuration parameters.

.. note::
   This module has no side effects and can be imported from anywhere by anyone.

.. warning::
   To keep this module free of side effects it is paramount to not import other
   Azrael modules here (circular imports), *and* that *no* other module
   modifies any variables here during run time.
"""
import os
import sys
import pymongo
import logging
import netifaces

# ---------------------------------------------------------------------------
# Configure logging.
# ---------------------------------------------------------------------------

# Specify the log level for Azrael.
log_file = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_file, '..', 'volume', 'azrael.log')
logger = logging.getLogger('azrael')

# Prevent it from logging to console no matter what.
logger.propagate = False

# Create a handler instance to log the messages to stdout.
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.DEBUG)
#console.setLevel(logging.ERROR)

logFormat = '%(levelname)s - %(name)s - %(message)s'
console.setFormatter(logging.Formatter(logFormat))

# Install the handler.
logger.addHandler(console)

# Specify a file logger.
logFormat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(logFormat)
fileHandler = logging.FileHandler(log_file, mode='a')
fileHandler.setLevel(logging.DEBUG)
fileHandler.setFormatter(formatter)
fileHandler.setLevel(logging.DEBUG)

# Install the handler.
logger.addHandler(fileHandler)

del console, logFormat, formatter, fileHandler

# ---------------------------------------------------------------------------
# Global variables.
# ---------------------------------------------------------------------------

# Determine the host IP address. Try eth0  first. Use localhost is a fallback
# option if no configured ethernet card was found.
try:
    host_ip = netifaces.ifaddresses('eth0')[2][0]['addr']
except (ValueError, KeyError):
    try:
        host_ip = netifaces.ifaddresses('lo')[2][0]['addr']
    except (ValueError, KeyError):
        logger.critical('Could not find a valid network interface')
        sys.exit(1)

# Database host.
if 'INSIDEDOCKER' in os.environ:
    addr_database = 'database'
    port_database = 27017
else:
    addr_database = 'localhost'
    port_database = 27017

# Addresses of the various Azrael services.
addr_clacks = host_ip
port_clacks = 8080

addr_dibbler = host_ip
port_dibbler = 8081

addr_clerk = host_ip
port_clerk = 5555

addr_leonard_repreq = 'tcp://' + host_ip + ':5556'

# Clacks URLs for the model- templates and instances. These *must not* include
# the trailing slash.
url_templates = '/templates'
url_instances = '/instances'
assert not url_templates.endswith('/') and not url_templates.endswith('/')


def getMongoClient():
    """
    Return a connected `MongoClient` instance.

    This is a convenience method that automatically connects to the correct
    host on the correct address.

    This function does intercept any errors. It is the responsibility of the
    caller to use the correct try/except statement.

    :return: connection to MongoDB
    :rtype: `pymongo.MongoClient`.
    :raises: pymongo.errors.*
    """
    return pymongo.MongoClient(host=addr_database, port=port_database)
