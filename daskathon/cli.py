from __future__ import print_function, division, absolute_import

import atexit
import uuid
import json
import logging
import os
import socket
import signal
import subprocess
import sys
from time import sleep

import click
import distributed
from toolz import concat
from marathon import MarathonClient, MarathonApp
from marathon.models.container import MarathonContainer

from .core import MarathonCluster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def daskathon():
    pass


@daskathon.command()
@click.argument('marathon', type=str)
@click.option('--name', type=str, default='daskathon-workers',
              help="Application name")
@click.option('--worker-cpus', type=int, default=1,
              help="Cpus allocated for each worker")
@click.option('--worker-mem', type=int, default=512,
              help="Memory of workers instances in MiB")
@click.option('--ip', type=str, default='',
              help="IP, hostname or URI of this server")
@click.option('--port', type=int, default=None, help="Serving port")
@click.option('--bokeh-port', type=int, default=8787, help="Bokeh port")
@click.option('--nworkers', type=int, default=0,
              help="Number of worker instances")
@click.option('--nprocs', type=int, default=1,
              help="Number of processing inside a worker")
@click.option('--nthreads', type=int, default=0,
              help="Number of threads inside a process")
@click.option('--docker', type=str, default='kszucs/distributed',
              help="Worker's docker image")
@click.option('--adaptive', is_flag=True,
              help="Adaptive deployment of workers")
@click.option('--constraint', '-c', type=str, default='', 
              help="Marathon constrain in form `field:operator:value`")
def run(marathon, name, worker_cpus, worker_mem, ip, port, bokeh_port, nworkers, nprocs,
        nthreads, docker, adaptive, constraint):
    if sys.platform.startswith('linux'):
        import resource   # module fails importing on Windows
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        limit = max(soft, hard // 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))

    if constraint:
        constraints = [constraint.split(':')[:3]]
    else:
        constraints = []

    mc = MarathonCluster(diagnostics_port=bokeh_port, scheduler_port=port,
                         nworkers=nworkers, nprocs=nprocs, nthreads=nthreads,
                         marathon=marathon, docker=docker, adaptive=adaptive,
                         name=name, cpus=worker_cpus, mem=worker_mem,
                         constraints=constraints,
                         silence_logs=logging.INFO)

    def handle_signal(sig, frame):
        logger.info('Received signal, shutdown...')
        mc.close()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while mc.scheduler.status == 'running':
        sleep(10)

    sys.exit(0)


@daskathon.command()
@click.argument('marathon', type=str)
@click.option('--name', '-n', type=str, default='',
              help="Application name")
@click.option('--worker-cpus', type=int, default=1,
              help="Cpus allocated for each worker")
@click.option('--worker-mem', type=int, default=512,
              help="Memory of workers instances in MiB")
@click.option('--scheduler-cpus', type=int, default=1,
              help="Cpus allocated for each worker")
@click.option('--scheduler-mem', type=int, default=512,
              help="Memory of workers instances in MiB")
@click.option('--ip', type=str, default='',
              help="IP, hostname or URI of this server")
@click.option('--port', type=int, default=None, help="Serving port")
@click.option('--bokeh-port', type=int, default=8787, help="Bokeh port")
@click.option('--nworkers', type=int, default=0,
              help="Number of worker instances")
@click.option('--nprocs', type=int, default=1,
              help="Number of processing inside a worker")
@click.option('--nthreads', type=int, default=0,
              help="Number of threads inside a process")
@click.option('--docker', type=str, default='kszucs/daskathon',
              help="Worker's docker image")
@click.option('--adaptive', '-a', is_flag=True,
              help="Adaptive deployment of workers")
@click.option('--constraint', '-c', type=str, default='', 
              help="Marathon constrain in form `field:operator:value`")
def deploy(marathon, name, docker, scheduler_cpus, scheduler_mem, adaptive,
           port, bokeh_port, constraint, **kwargs):
    name = name or 'daskathon-{}'.format(str(uuid.uuid4())[-4:])

    kwargs['name'] = '{}-workers'.format(name)
    kwargs['docker'] = docker
    kwargs['port'] = '$PORT_SCHEDULER'
    kwargs['bokeh_port'] = '$PORT_BOKEH'
    kwargs['constraint'] = constraint

    args = [('--{}'.format(k.replace('_', '-')), str(v)) for k, v in kwargs.items()
            if v not in (None, '')]
    args = list(concat(args))
    if adaptive:
        args.append('--adaptive')

    client = MarathonClient(marathon)
    container = MarathonContainer({'image': docker})
    args = ['daskathon', 'run'] + args + [marathon]
    cmd = ' '.join(args)

    # healths = [{'portIndex': i,
    #             'protocol': 'TCP',
    #             'gracePeriodSeconds': 300,
    #             'intervalSeconds': 30,
    #             'timeoutSeconds': 20,
    #             'maxConsecutiveFailures': 3}
    #            for i, name in enumerate(['scheduler', 'bokeh', 'http'])]
    healths = []
    ports = [{'port': 0,
              'protocol': 'tcp',
              'name': name}
              for name in ['scheduler', 'bokeh', 'http']]

    if constraint:
        constraints = [constraint.split(':')[:3]]
    else:
        constraints = []

    app = MarathonApp(instances=1, container=container,
                      cpus=scheduler_cpus, mem=scheduler_mem,
                      task_kill_grace_period_seconds=20,
                      port_definitions=ports,
                      health_checks=healths,
                      constraints=constraints,
                      cmd=cmd)
    client.create_app('{}-scheduler'.format(name), app)

