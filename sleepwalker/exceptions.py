# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.


class SleepwalkerException(Exception):
    """ Base exception class for sleepwalker errors. """
    pass


class MissingRestSchema(SleepwalkerException):
    """ An error occurred when trying to access the RestSchema. """
    pass


class MissingParameter(SleepwalkerException):
    """ URI template missing one or more parameters. """
    pass


class InvalidParameter(SleepwalkerException): 
    """ URI template found an invalid parameter. """
    pass


class LinkError(SleepwalkerException): 
    """ Raised if invalid link called on Resource. """
    pass


class ConnectionError(SleepwalkerException): 
    """ A connection error occurred. """
    pass


class URLError(ConnectionError): 
    """ An error occurred when building a URL. """
    pass
