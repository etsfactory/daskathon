Daskathon
=========

|Build Status|

.. |Build Status| image:: https://travis-ci.org/daskos/daskathon.svg
   :target: https://travis-ci.org/daskos/daskathon

Deploy ``dask-worker`` processes on Marathon in response to load on a Dask
scheduler.  This creates a Marathon application of dask-worker processes.  It
watches a Dask Scheduler object in the local process and, based on current
requested load, scales the Marathon application up and down.


Run
---

It's not yet clear how to expose all of the necessary options to a command line
interface.  For now we're doing everything manually.

Make an IOLoop running in a separate thread:

.. code-block:: python

    with MarathonCluster(marathon='http://localhost:8080',
                         cpus=1, mem=512, adaptive=True) as mc:
        with Client(mc.scheduler_address) as c:
            x = c.submit(lambda x: x + 1, 1)
            assert x.result() == 2


Create a Client and submit work to the scheduler.  Marathon will scale workers
up and down as neccessary in response to current workload.

.. code-block:: python

   from distributed import Client
   c = Client(s.address)

   future = c.submit(lambda x: x + 1, 10)


TODO
----

-  Deploy the scheduler on the cluster
-  Support a command line interface


Docker Testing Harness
----------------------

This sets up a docker cluster of one Mesos master and two Mesos agents using
docker-compose.

**Requires**:

- docker version >= 1.11.1
- docker-compose version >= 1.7.1

::

   docker-compose up

Run py.test::

   py.test dask-marathon


Web UIs
~~~~~~~

- http://localhost:5050/ for Mesos master UI
- http://localhost:5051/ for the first Mesos agent UI
- http://localhost:8080/ for Marathon UI


History
~~~~~~~

Dask-marathon originally forked from https://github.com/mrocklin/dask-marathon
