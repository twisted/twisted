
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted from Scratch, or The Evolution of Finger
================================================

.. toctree::
   :hidden:

   intro
   protocol
   style
   components
   backends
   web
   pb
   factory
   client
   library
   configuration


Introduction
------------

Twisted is a big system.
People are often daunted when they approach it.
It's hard to know where to start looking.

This guide builds a full-fledged Twisted application from the ground up, using most of the important bits of the framework.
There is a lot of code, but don't be afraid.

The application we are looking at is a "finger" service, along the lines of the familiar service traditionally provided by UNIX™ servers.
We will extend this service slightly beyond the standard, in order to demonstrate some of Twisted's higher-level features.

Each section of the tutorial dives straight into applications for various Twisted topics.
These topics have their own introductory howtos listed in the :doc:`core howto index <../index>` and in the documentation for other Twisted projects like Twisted Web and Twisted Words.
There are at least three ways to use this tutorial: you may find it useful to read through the rest of the topics listed in the :doc:`core howto index <../index>` before working through the finger tutorial, work through the finger tutorial and then go back and hit the introductory material that is relevant to the Twisted project you're working on, or read the introductory material one piece at a time as it comes up in the finger tutorial.


Contents
--------

This tutorial is split into eleven parts:

#. :doc:`The Evolution of Finger: building a simple finger service <intro>`
#. :doc:`The Evolution of Finger: adding features to the finger service <protocol>`
#. :doc:`The Evolution of Finger: cleaning up the finger code <style>`
#. :doc:`The Evolution of Finger: moving to a component based architecture <components>`
#. :doc:`The Evolution of Finger: pluggable backends <backends>`
#. :doc:`The Evolution of Finger: a web frontend <web>`
#. :doc:`The Evolution of Finger: Twisted client support using Perspective Broker <pb>`
#. :doc:`The Evolution of Finger: using a single factory for multiple protocols <factory>`
#. :doc:`The Evolution of Finger: a Twisted finger client <client>`
#. :doc:`The Evolution of Finger: making a finger library <library>`
#. :doc:`The Evolution of Finger: configuration and packaging of the finger service <configuration>`
