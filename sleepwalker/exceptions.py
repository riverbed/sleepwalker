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

        # An error datarep would also likely have this, but non-datarep
        # errors should have an easy way to get to it.
        self.http_code = response.status_code

        # TODO: Build a datarep if the schema fits.
        #       For now, set to None anyway.
        self.datarep = None

    @classmethod
    def raise_by_status(cls, response):
        # globals() accesses symbols, in this case classes, defined in
        # this module.
        # TODO: Less of a hack?
        exception_class = globals().get('_HTTP%d' % response.status_code, None)
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

class HTTPBadRequest(ClientHTTPError):
    pass
class _HTTP400(HTTPBadRequest):
    pass

class HTTPUnauthorized(ClientHTTPError):
    pass
class _HTTP401(HTTPUnauthorized):
    pass

class HTTPPaymentRequired(ClientHTTPError):
    pass
class _HTTP402(HTTPPaymentRequired):
    pass

class HTTPForbidden(ClientHTTPError):
    pass
class _HTTP403(HTTPForbidden):
    pass

class HTTPNotFound(ClientHTTPError):
    pass
class _HTTP404(HTTPNotFound):
    pass

class HTTPMethodNotAllowed(ClientHTTPError):
    pass
class _HTTP405(HTTPMethodNotAllowed):
    pass

class HTTPNotAcceptable(ClientHTTPError):
    pass
class _HTTP406(HTTPNotAcceptable):
    pass

class HTTPProxyAuthenticationRequired(ClientHTTPError):
    pass
class _HTTP407(HTTPProxyAuthenticationRequired):
    pass

class HTTPRequestTimeout(ClientHTTPError):
    pass
class _HTTP408(HTTPRequestTimeout):
    pass

class HTTPConflict(ClientHTTPError):
    pass
class _HTTP409(HTTPConflict):
    pass

class HTTPGone(ClientHTTPError):
    pass
class _HTTP410(HTTPGone):
    pass

class HTTPLengthRequired(ClientHTTPError):
    pass
class _HTTP411(HTTPLengthRequired):
    pass

class HTTPPreconditionFailed(ClientHTTPError):
    pass
class _HTTP412(HTTPPreconditionFailed):
    pass

class HTTPRequestEntityTooLarge(ClientHTTPError):
    pass
class _HTTP413(HTTPRequestEntityTooLarge):
    pass

class HTTPRequestURITooLong(ClientHTTPError):
    pass
class _HTTP414(HTTPRequestURITooLong):
    pass

class HTTPUnsupportedMediaType(ClientHTTPError):
    pass
class _HTTP415(HTTPUnsupportedMediaType):
    pass

class HTTPRequestedRangeNotSatisfiable(ClientHTTPError):
    pass
class _HTTP416(ClientHTTPError):
    pass

class HTTPExpectationFailed(ClientHTTPError):
    pass
class _HTTP417(HTTPExpectationFailed):
    pass

# RFC 2324
class HTTPImATeapot(ClientHTTPError):
    pass
class _HTTP418(HTTPImATeapot):
    pass

# RFC 2817
class HTTPUpgradeRequired(ClientHTTPError):
    pass
class _HTTP426(HTTPUpgradeRequired):
    pass

# RFC 6586
class HTTPPreconditionRequired(ClientHTTPError):
    pass
class _HTTP428(HTTPPreconditionRequired):
    pass

class HTTPTooManyRequests(ClientHTTPError):
    pass
class _HTTP429(HTTPTooManyRequests):
    pass

class HTTPRequestHeaderFieldsTooLarge(ClientHTTPError):
    pass
class _HTTP431(HTTPRequestHeaderFieldsTooLarge):
    pass


class ServerHTTPError(HTTPError):
    """ Server-side errors (5xx codes). """

class HTTPInternalServerError(ServerHTTPError):
    pass
class _HTTP500(HTTPInternalServerError):
    pass

class HTTPNotImplemented(ServerHTTPError):
    pass
class _HTTP501(HTTPNotImplemented):
    pass

class HTTPBadGateway(ServerHTTPError):
    pass
class _HTTP502(HTTPBadGateway):
    pass

class HTTPServiceUnavailable(ServerHTTPError):
    pass
class _HTTP503(HTTPServiceUnavailable):
    pass

class HTTPGatewayTimeout(ServerHTTPError):
    pass
class _HTTP504(ServerHTTPError):
    pass

class HTTPVersionNotSupported(ServerHTTPError):
    pass
class _HTTP505(HTTPVersionNotSupported):
    pass

# RFC 2295
class HTTPVariantAlsoNegotiates(ServerHTTPError):
    pass
class _HTTP506(HTTPVariantAlsoNegotiates):
    pass

# RFC 2774
class HTTPNotExtended(ServerHTTPError):
    pass
class _HTTP510(HTTPNotExtended):
    pass

# RFC 6585
class HTTPNetworkAuthenticationRequired(ServerHTTPError):
    pass
class _HTTP511(HTTPNetworkAuthenticationRequired):
    pass

