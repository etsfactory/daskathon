from __future__ import print_function, division, absolute_import

import atexit
import json
import logging
import os
import socket
import subprocess
import sys
from time import sleep

import click
import distributed
from toolz import concat
from marathon import MarathonClient, MarathonApp
from marathon.models.container import MarathonContainer

from .core import MarathonCluster


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
def run(marathon, name, worker_cpus, worker_mem, ip, port, bokeh_port, nworkers, nprocs,
        nthreads, docker, adaptive):
    if sys.platform.startswith('linux'):
        import resource   # module fails importing on Windows
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        limit = max(soft, hard // 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))

    with MarathonCluster(diagnostics_port=bokeh_port, scheduler_port=port,
                         nworkers=nworkers, nprocs=nprocs, nthreads=nthreads,
                         marathon=marathon, docker=docker, adaptive=adaptive,
                         name=name, cpus=worker_cpus, mem=worker_mem) as mc:
        while True:
            sleep(10)


@daskathon.command()
@click.argument('marathon', type=str)
@click.option('--name', type=str, default='daskathon',
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
@click.option('--adaptive', is_flag=True,
              help="Adaptive deployment of workers")
def deploy(marathon, name, docker, scheduler_cpus, scheduler_mem, adaptive,
           **kwargs):
    name = name or 'daskathon-{}'.format(uuid.uuid4()[-4:])

    kwargs['name'] = '{}-workers'.format(name)
    kwargs['docker'] = docker

    args = [('--{}'.format(k.replace('_', '-')), str(v)) for k, v in kwargs.items()
            if v not in (None, '')]
    args = list(concat(args))
    if adaptive:
        args.append('--adaptive')

    client = MarathonClient(marathon)
    container = MarathonContainer({'image': docker})
    args = ['daskathon', 'run'] + args + [marathon]

    app = MarathonApp(instances=1, container=container,
                      cpus=scheduler_cpus, mem=scheduler_mem,
                      #port_definitions=ports,
                      args=args)
    client.create_app('{}-scheduler'.format(name), app)
