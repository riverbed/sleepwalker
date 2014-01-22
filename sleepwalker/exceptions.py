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
class MissingVar(SleepwalkerException):
    """ URI template missing one or more variables. """


class InvalidParameter(SleepwalkerException): 
    """ URI template found an invalid parameter. """


class RelationError(SleepwalkerException): 
    """ Raised if invalid relation called on Resource. """


class LinkError(SleepwalkerException): 
    """ Raised if invalid link called on Resource. """


class DataPullError(SleepwalkerException): 
    """ Raised if an attempt to pull data failed. """


class DataNotSetError(SleepwalkerException):
    """ Raised if an attempt to push data when not set. """

class FragmentError(SleepwalkerException):
    """ Raised if fragment settings are inconsistent. """

#
# Connection related exceptions
#
class ConnectionError(SleepwalkerException): 
    """ A connection error occurred. """


class URLError(ConnectionError): 
    """ An error occurred when building a URL. """

#
# Request/Response related exceptions
#
class HTTPError(SleepwalkerException):
    """ Links an HTTP status with an optional DataRep for error the body. """
    # TODO: For now response is expected to be a requests.Response object,
    #       do we need to squash this interface leak as well?  Make it
    #       self._response to discourage casual use but allow if necessary.
    def __init__(self, response):
        self._response = response

        # TODO: Build a datarep if the schema fits.
        #       For now, set to None anyway.
        self.datarep = None

    @classmethod
    def raise_by_status(cls, response):
        # globals() accesses symbols, in this case classes, defined in
        # this module.
        # TODO: Less of a hack?
        exception_class = globals().get('Error%d' % response.status_code, None)
        if exception_class is None:
            if response.status_code >= 400 and response.status_code < 500:
                exception_class = ClientHTTPError
            elif response.status_code >= 500 and response.status_code < 600:
                exception_class = ServerHTTPError
            else:
                exception_class = HTTPError
        raise exception_class(response)


class ClientHTTPError(HTTPError):
    """ Client-side errors (4xx codes). """

class Error400(ClientHTTPError):
    pass

class Error401(ClientHTTPError):
    pass

class Error402(ClientHTTPError):
    pass

class Error403(ClientHTTPError):
    pass

class Error404(ClientHTTPError):
    pass

class Error405(ClientHTTPError):
    pass

class Error406(ClientHTTPError):
    pass

class Error407(ClientHTTPError):
    pass

class Error408(ClientHTTPError):
    pass

class Error409(ClientHTTPError):
    pass

class Error410(ClientHTTPError):
    pass

class Error411(ClientHTTPError):
    pass

class Error412(ClientHTTPError):
    pass

class Error413(ClientHTTPError):
    pass

class Error414(ClientHTTPError):
    pass

class Error415(ClientHTTPError):
    pass

class Error416(ClientHTTPError):
    pass

class Error417(ClientHTTPError):
    pass

# RFC 2324
class Error418(ClientHTTPError):
    """ I am a teapot. """
    pass

# RFC 2817
class Error426(ClientHTTPError):
    pass

# RFC 6586
class Error428(ClientHTTPError):
    pass

class Error429(ClientHTTPError):
    pass

class Error431(ClientHTTPError):
    pass


class ServerHTTPError(HTTPError):
    """ Server-side errors (5xx codes). """

class Error500(ServerHTTPError):
    pass

class Error501(ServerHTTPError):
    pass

class Error502(ServerHTTPError):
    pass

class Error503(ServerHTTPError):
    pass

class Error504(ServerHTTPError):
    pass

class Error505(ServerHTTPError):
    pass

# RFC 2295
class Error506(ServerHTTPError):
    pass

# RFC 2774
class Error510(ServerHTTPError):
    pass

# RFC 6585
class Error511(ServerHTTPError):
    pass

