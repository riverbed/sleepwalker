# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.


#
# General exception and base class
#
class SleepwalkerException(Exception):
    """ Base exception class for sleepwalker errors. """


#
# Service Exceptions
#
class ServiceException(SleepwalkerException): 
    """ Sleepwalker Service error. """


class MissingRestSchema(ServiceException):
    """ An error occurred when trying to access the RestSchema. """


class ResourceException(ServiceException): 
    """ An error occurred with a Resource. """


class TypeException(ServiceException): 
    """ An error occurred with a Type. """


#
# Schema and operational exceptions
#
class MissingParameter(SleepwalkerException):
    """ URI template missing one or more parameters. """


class InvalidParameter(SleepwalkerException): 
    """ URI template found an invalid parameter. """


class RelationError(SleepwalkerException): 
    """ Raised if invalid relation called on Resource. """


class LinkError(SleepwalkerException): 
    """ Raised if invalid link called on Resource. """


class DataPullError(SleepwalkerException): 
    """ Raised if an attempt to pull data failed. """


class NoDataError(SleepwalkerException): 
    """ Raised if an attempt to push data when not set. """


#
# Connection related exceptions
#
class ConnectionError(SleepwalkerException): 
    """ A connection error occurred. """


class URLError(ConnectionError): 
    """ An error occurred when building a URL. """

