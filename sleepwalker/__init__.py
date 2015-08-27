# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

from sleepwalker.service import Service, ServiceManager
from sleepwalker.connection import Connection, ConnectionManager
from sleepwalker.datarep import Schema, DataRep
from sleepwalker.exceptions import *

from reschema.servicedef import ServiceDefManager


mgr = ServiceManager(ServiceDefManager(), ConnectionManager())
