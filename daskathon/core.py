from __future__ import print_function, division, absolute_import

from concurrent.futures import ThreadPoolExecutor
import logging
import uuid
from distributed import Client, Scheduler
from marathon import MarathonClient, MarathonApp
from marathon.models.container import MarathonContainer

from tornado.iostream import StreamClosedError
from distributed.utils import sync, ignoring, All
from distributed.deploy import Adaptive
from tornado import gen
from tornado.ioloop import IOLoop
from threading import Thread
from distributed.utils import sync

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MarathonWorkers(object):

    def __init__(self, scheduler, marathon, name=None, nprocs=1, nthreads=0,
                 docker='kszucs/distributed',
                 **kwargs):
        self.scheduler = scheduler
        self.executor = ThreadPoolExecutor(1)
        self.client = MarathonClient(marathon)
        self.name = name or 'dask-%s' % uuid.uuid4()
        self.docker = docker
        self.nprocs = nprocs
        self.nthreads = nthreads
        self.options = kwargs

    def start(self, nworkers=0):
        address = self.scheduler.address.replace('tcp://', '')
        args = ['dask-worker', address,
                '--name', '$MESOS_TASK_ID',  # use Mesos task ID as worker name
                '--worker-port', '$PORT_WORKER',
                '--bokeh-port', '$PORT_BOKEH',
                '--nanny-port', '$PORT_NANNY',
                '--http-port', '$PORT_HTTP',
                '--nprocs', str(self.nprocs),
                '--nthreads', str(self.nthreads)]

        ports = [{'port': 0,
                  'protocol': 'tcp',
                  'name': name}
                 for name in ['worker', 'nanny', 'http', 'bokeh']]

        # healths = [{'portIndex': i,
        #             'protocol': 'TCP',
        #             'gracePeriodSeconds': 300,
        #             'intervalSeconds': 60,
        #             'timeoutSeconds': 20,
        #             'maxConsecutiveFailures': 3}
        #            for i, name in enumerate(['worker', 'nanny', 'http', 'bokeh'])]
        healths = []

        if 'mem' in self.options:
            args.extend(['--memory-limit',
                         str(int(self.options['mem'] * 0.8 * 1e6))])

        container = MarathonContainer({'image': self.docker,
                                       'forcePullImage': True})
        command = ' '.join(args)

        app = MarathonApp(instances=nworkers, container=container,
                          port_definitions=ports, cmd=command,
                          health_checks=healths,
                          **self.options)
        self.app = self.client.create_app(self.name, app)
        logger.info('Started marathon workers {}'.format(self.app.id))

    def close(self):
        logger.info('Stopping marathon workers {}'.format(self.app.id))
        self.client.delete_app(self.app.id, force=True)
        del self.app

    def scale_up(self, nworkers):
        self.executor.submit(self.client.scale_app, self.app.id,
                             instances=nworkers)

    def scale_down(self, workers):
        for worker in workers:
            self.executor.submit(self.client.kill_task, self.app.id,
                                 self.scheduler.worker_info[worker]['name'],
                                 scale=True)


class MarathonCluster(object):

    def __init__(self, loop=None, nworkers=0, ip='127.0.0.1',
                 scheduler_port=8786, diagnostics_port=8787,
                 services = {}, adaptive=False, silence_logs=logging.CRITICAL,
                 **kwargs):
        if silence_logs:
            for l in ['distributed.scheduler',
                      'distributed.worker',
                      'distributed.core',
                      'distributed.nanny']:
                logging.getLogger(l).setLevel(silence_logs)

        self.loop = loop or IOLoop()
        if not self.loop._running:
            self._thread = Thread(target=self.loop.start)
            self._thread.daemon = True
            self._thread.start()
            while not self.loop._running:
                sleep(0.001)

        self.scheduler = Scheduler(loop=self.loop, services=services)
        self.workers = MarathonWorkers(self.scheduler, **kwargs)

        if adaptive:
            self.adaptive = Adaptive(self.scheduler, self.workers)

        self.scheduler_port = scheduler_port
        self.diagnostics_port = diagnostics_port
        self.diagnostics = None

        self.scheduler.start(self.scheduler_port)
        self.workers.start(nworkers)
        self.status = 'running'
        if self.diagnostics_port is not None:
            self._start_diagnostics(self.diagnostics_port, silence=silence_logs)

    def _start_diagnostics(self, port=8787, show=False, silence=logging.CRITICAL):
        try:
            from distributed.bokeh.application import BokehWebInterface
        except ImportError:
            logger.info("To start diagnostics web server please install Bokeh")
            return
        from distributed.http.scheduler import HTTPScheduler

        assert self.diagnostics is None
        if 'http' not in self.scheduler.services:
            self.scheduler.services['http'] = HTTPScheduler(
                self.scheduler, io_loop=self.scheduler.loop)
            self.scheduler.services['http'].listen(0)
        self.diagnostics = BokehWebInterface(
            scheduler_address=self.scheduler_address,
            http_port=self.scheduler.services['http'].port,
            bokeh_port=port, show=show,
            log_level=logging.getLevelName(silence).lower())

    def scale_up(self, nworkers):
        self.workers.scale_up(nworkers)

    def scale_down(self, workers):
        self.workers.scale_down(workers)

    def __str__(self):
        return 'MarathonCluster({}, workers={}, ncores={})'.format(
            self.scheduler.address, len(self.scheduler.workers),
            self.scheduler.total_ncores)

    __repr__ = __str__

    @gen.coroutine
    def _close(self):
        logging.info('Stopping workers...')
        self.workers.close()
 
        with ignoring(gen.TimeoutError, StreamClosedError, OSError):
            logging.info('Stopping scheduler...')
            yield self.scheduler.close(fast=True)

        if self.diagnostics:
            logging.info('Stopping diagnostics...')
            self.diagnostics.close()

    def close(self):
        """ Close the cluster """
        if self.status == 'running':
            self.status = 'closed'
            if self.loop._running:
                sync(self.loop, self._close)
            if hasattr(self, '_thread'):
                sync(self.loop, self.loop.stop)
                self._thread.join(timeout=1)
                self.loop.close()
                del self._thread

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def scheduler_address(self):
        return self.scheduler.address
