# Copyright (c) 2015 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the MIT License
# accompanying the software ("License").  This software is distributed "AS IS"
# as set forth in the License.

# NOTE: If any imports are made in this module, please add an
# __all__ = []
# definition as __init__.py does a from .exceptions import *.


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


class MissingServiceDef(ServiceException):
    """ An error occurred when trying to access the service definition. """


class ResourceException(ServiceException):
    """ An error occurred with a Resource. """


class TypeException(ServiceException):
    """ An error occurred with a Type. """


#
# Schema and operational exceptions
#
class MissingVariable(SleepwalkerException):
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
    code_map = {}

    """ Links an HTTP status with an optional DataRep for error the body. """
    # TODO: For now response is expected to be a requests.Response object,
    #       do we need to squash this interface leak as well?  Make it
    #       self._response to discourage casual use but allow if necessary.
    def __init__(self, response):
        self._response = response

        # These fields are likely to be of immediate interest for handling
        # errors that are not DataRep-friendly.  We do not expose the entire
        # response directly since if the user is digging that deeply they
        # probably need to be using requests directly.
        self.http_code = response.status_code
        self.headers = response.headers

        # We won't know enough to create a DataRep when this is raised,
        # but if we have JSON data higher sleepwalker layers will add one.
        # So figure that out, and fall back to storing the response text
        # if we can't decode some JSON.  500 errors will generally not
        # have service definiton schemas, for instance, and will probably
        # have text from the web server or generic framework.
        self.datarep = None
        try:
            self.json_data = response.json()
            self.text = None
        except ValueError:
            self.json_data = None
            self.text = response.text

        # Call the parent class constructor with a useful error message,
        # so that our inherited __str__() method returns this message.
        # Look for an error message in json_data.  Otherwise use the HTTP
        # reason string, e.g. 'Bad Request', which comes right from the HTTP
        # response header.
        try:
            error_text = self.json_data['error_text']
        except (TypeError, KeyError):
            # Fall back on the stock HTTP reason
            error_text = response.reason
        super(HTTPError, self).__init__(error_text)

    @classmethod
    def raise_by_status(cls, response):
        exception_class = cls.code_map.get(response.status_code, None)
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
HTTPError.code_map[400] = HTTPBadRequest


class HTTPUnauthorized(ClientHTTPError):
    pass
HTTPError.code_map[401] = HTTPUnauthorized


class HTTPPaymentRequired(ClientHTTPError):
    pass
HTTPError.code_map[402] = HTTPPaymentRequired


class HTTPForbidden(ClientHTTPError):
    pass
HTTPError.code_map[403] = HTTPForbidden


class HTTPNotFound(ClientHTTPError):
    pass
HTTPError.code_map[404] = HTTPNotFound


class HTTPMethodNotAllowed(ClientHTTPError):
    pass
HTTPError.code_map[405] = HTTPMethodNotAllowed


class HTTPNotAcceptable(ClientHTTPError):
    pass
HTTPError.code_map[406] = HTTPNotAcceptable


class HTTPProxyAuthenticationRequired(ClientHTTPError):
    pass
HTTPError.code_map[407] = HTTPProxyAuthenticationRequired


class HTTPRequestTimeout(ClientHTTPError):
    pass
HTTPError.code_map[408] = HTTPRequestTimeout


class HTTPConflict(ClientHTTPError):
    pass
HTTPError.code_map[409] = HTTPConflict


class HTTPGone(ClientHTTPError):
    pass
HTTPError.code_map[410] = HTTPGone


class HTTPLengthRequired(ClientHTTPError):
    pass
HTTPError.code_map[411] = HTTPLengthRequired


class HTTPPreconditionFailed(ClientHTTPError):
    pass
HTTPError.code_map[412] = HTTPPreconditionFailed


class HTTPRequestEntityTooLarge(ClientHTTPError):
    pass
HTTPError.code_map[413] = HTTPRequestEntityTooLarge


class HTTPRequestURITooLong(ClientHTTPError):
    pass
HTTPError.code_map[414] = HTTPRequestURITooLong


class HTTPUnsupportedMediaType(ClientHTTPError):
    pass
HTTPError.code_map[415] = HTTPUnsupportedMediaType


class HTTPRequestedRangeNotSatisfiable(ClientHTTPError):
    pass
HTTPError.code_map[416] = HTTPRequestedRangeNotSatisfiable


class HTTPExpectationFailed(ClientHTTPError):
    pass
HTTPError.code_map[417] = HTTPExpectationFailed


# RFC 2324
class HTTPImATeapot(ClientHTTPError):
    pass
HTTPError.code_map[418] = HTTPImATeapot


# RFC 2817
class HTTPUpgradeRequired(ClientHTTPError):
    pass
HTTPError.code_map[426] = HTTPUpgradeRequired


# RFC 6586
class HTTPPreconditionRequired(ClientHTTPError):
    pass
HTTPError.code_map[428] = HTTPPreconditionRequired


class HTTPTooManyRequests(ClientHTTPError):
    pass
HTTPError.code_map[429] = HTTPTooManyRequests


class HTTPRequestHeaderFieldsTooLarge(ClientHTTPError):
    pass
HTTPError.code_map[431] = HTTPRequestHeaderFieldsTooLarge


class ServerHTTPError(HTTPError):
    """ Server-side errors (5xx codes). """


class HTTPInternalServerError(ServerHTTPError):
    pass
HTTPError.code_map[500] = HTTPInternalServerError


class HTTPNotImplemented(ServerHTTPError):
    pass
HTTPError.code_map[501] = HTTPNotImplemented


class HTTPBadGateway(ServerHTTPError):
    pass
HTTPError.code_map[502] = HTTPBadGateway


class HTTPServiceUnavailable(ServerHTTPError):
    pass
HTTPError.code_map[503] = HTTPServiceUnavailable


class HTTPGatewayTimeout(ServerHTTPError):
    pass
HTTPError.code_map[504] = HTTPGatewayTimeout


class HTTPVersionNotSupported(ServerHTTPError):
    pass
HTTPError.code_map[505] = HTTPVersionNotSupported


# RFC 2295
class HTTPVariantAlsoNegotiates(ServerHTTPError):
    pass
HTTPError.code_map[506] = HTTPVariantAlsoNegotiates


# RFC 2774
class HTTPNotExtended(ServerHTTPError):
    pass
HTTPError.code_map[510] = HTTPNotExtended


# RFC 6585
class HTTPNetworkAuthenticationRequired(ServerHTTPError):
    pass
HTTPError.code_map[511] = HTTPNetworkAuthenticationRequired
