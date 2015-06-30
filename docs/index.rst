.. Sleepwalker documentation master file, created by
   sphinx-quickstart on Wed Sep 25 08:44:41 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Sleepwalker's documentation!
=======================================

The Sleepwalker Python module simplifies interaction with a RESTful
server.  It is designed to abstract all HTTP specific details of
interaction with a REST server.  In particular, the client should not
be manually constructing URIs nor defining the specific HTTP methods
used to manipulate resources.  The URIs and HTTP methods are instead
specified in a rest-schema file.

All interaction with the server is through a :py:class:`DataRep`
object, which maps to a concrete addressable resource exposed by the
server.  

Contents:

.. toctree::
   :maxdepth: 2

   service
   datarep
   connection

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

License
-------

This Sleepwalker documentation is provided "AS IS"
and without any warranty or indemnification.  Any sample code or
scripts included in the documentation are licensed under the terms and
conditions of the MIT License.  See the :doc:`license` page for more
information.
