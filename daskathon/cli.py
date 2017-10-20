from __future__ import print_function, division, absolute_import

import sys
import uuid
import click
import signal
import logging

from time import sleep
from copy import deepcopy

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
              help='Application name')
@click.option('--worker-cpus', type=float, default=1.0,
              help='Cpus allocated for each worker')
@click.option('--worker-mem', type=int, default=512,
              help='Memory of workers instances in MiB')
@click.option('--ip', type=str, default=None,
              help='IP, hostname or URI of this server')
@click.option('--port', type=int, default=0, help='Serving port')
@click.option('--bokeh-port', type=int, default=8787, help='Bokeh port')
@click.option('--nworkers', type=int, default=0,
              help='Number of worker instances')
@click.option('--nprocs', type=int, default=1,
              help='Number of processing inside a worker')
@click.option('--nthreads', type=int, default=0,
              help='Number of threads inside a process')
@click.option('--docker', type=str, default='daskos/daskathon',
              help="Worker's docker image")
@click.option('--volume', type=str, multiple=True,
              help="Shared volume from host machine in form "
              "host_path:container_path")
@click.option('--adaptive', is_flag=True,
              help='Adaptive deployment of workers')
@click.option('--constraint', '-c', type=str, default='', multiple=True,
              help='Marathon constrain in form `field:operator:value`')
@click.option('--maximum-over-capacity', type=float, default=None,
              help='maximum percent of instances kept healthy on deploy')
@click.option('--minimum-health-capacity', type=float, default=None,
              help='minimum percent of instances kept healthy on deploy')
@click.option('--uri', type=str, multiple=True,
              help='Mesos uri')
def run(marathon, name, worker_cpus, worker_mem, ip, port, bokeh_port,
        nworkers, nprocs, nthreads, docker, volume, adaptive, constraint,
        maximum_over_capacity, minimum_health_capacity, uri):
    if sys.platform.startswith('linux'):
        import resource   # module fails importing on Windows
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        limit = max(soft, hard // 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))

    constraints = [c.split(':')[:3] for c in constraint]

    upgrade_strategy = {'maximum_over_capacity': maximum_over_capacity,
                        'minimum_health_capacity': minimum_health_capacity}

    mc = MarathonCluster(diagnostics_port=bokeh_port, scheduler_port=port,
                         nworkers=nworkers, nprocs=nprocs, nthreads=nthreads,
                         marathon=marathon, docker=docker, volumes=volume,
                         adaptive=adaptive, name=name, cpus=worker_cpus,
                         mem=worker_mem, constraints=constraints, uris=uri,
                         upgrade_strategy=upgrade_strategy,
                         ip=ip, silence_logs=logging.INFO)

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
              help='Application name')
@click.option('--worker-cpus', type=float, default=1.0,
              help='Cpus allocated for each worker')
@click.option('--worker-mem', type=int, default=512,
              help='Memory of workers instances in MiB')
@click.option('--scheduler-cpus', type=float, default=1.0,
              help='Cpus allocated for each worker')
@click.option('--scheduler-mem', type=int, default=512,
              help='Memory of workers instances in MiB')
@click.option('--ip', type=str, default=None,
              help='IP, hostname or URI of this server')
@click.option('--port', type=int, default=0, help='Serving port')
@click.option('--bokeh-port', type=int, default=8787, help='Bokeh port')
@click.option('--nworkers', type=int, default=0,
              help='Number of worker instances')
@click.option('--nprocs', type=int, default=1,
              help='Number of processing inside a worker')
@click.option('--nthreads', type=int, default=0,
              help='Number of threads inside a process')
@click.option('--docker', type=str, default='daskos/daskathon',
              help="Worker's docker image")
@click.option('--volume', type=str, multiple=True,
              help="Shared volume from host machine in form "
              "host_path:container_path")
@click.option('--adaptive', '-a', is_flag=True,
              help='Adaptive deployment of workers')
@click.option('--constraint', '-c', type=str, multiple=True,
              help='Marathon constraint in form `field:operator:value`')
@click.option('--maximum-over-capacity', type=float, default=None,
              help='maximum percent of instances kept healthy on deploy')
@click.option('--minimum-health-capacity', type=float, default=None,
              help='minimum percent of instances kept healthy on deploy')
@click.option('--label', '-l', type=str, multiple=True,
              help='Marathon label in form `key:value`')
@click.option('--uri', type=str, multiple=True,
              help='Mesos uri')
@click.option('--jupyter', '-j', is_flag=True,
              help='Start a jupyter notebook client on the cluster')
def deploy(marathon, name, docker, volume, scheduler_cpus, scheduler_mem,
           adaptive, port, bokeh_port, constraint,
           maximum_over_capacity, minimum_health_capacity, label, uri, jupyter,
           **kwargs):
    name = name or 'daskathon-{}'.format(str(uuid.uuid4())[-4:])

    kwargs['name'] = '{}-workers'.format(name)
    kwargs['docker'] = docker
    kwargs['port'] = port
    kwargs['bokeh_port'] = bokeh_port

    args = [('--{}'.format(k.replace('_', '-')), str(v))
            for k, v in kwargs.items() if v not in (None, '')]

    for c in constraint:
        args.append(('--constraint', c))
    for u in uri:
        args.append(('--uri', u))
    for v in volume:
        args.append(('--volume', v))

    if maximum_over_capacity:
        args.append(('--maximum-over-capacity',
                     str(maximum_over_capacity)))

    if minimum_health_capacity:
        args.append(('--minimum-health-capacity',
                     str(minimum_health_capacity)))

    args = list(concat(args))
    if adaptive:
        args.append('--adaptive')

    client = MarathonClient(marathon)
    docker_parameters = [{"key": "volume", "value": v} for v in volume]
    container = MarathonContainer({'image': docker,
                                   'forcePullImage': True,
                                   'parameters': docker_parameters})
    args = ['daskathon', 'run'] + args + [marathon]
    cmd = ' '.join(args)

    healths = [{'portIndex': i, 'protocol': 'TCP'}
               for i, _ in enumerate(['scheduler', 'bokeh'])]

    services = [('scheduler', port), ('bokeh', bokeh_port)]
    ports = [{'port': p, 'protocol': 'tcp', 'name': service}
             for (service, p) in services]

    constraints = [c.split(':')[:3] for c in constraint]
    labels = dict([l.split(':') for l in label])
    upgrade_strategy = {'maximum_over_capacity': maximum_over_capacity,
                        'minimum_health_capacity': minimum_health_capacity}

    scheduler = MarathonApp(instances=1, container=container,
                            cpus=scheduler_cpus, mem=scheduler_mem,
                            task_kill_grace_period_seconds=20,
                            port_definitions=ports,
                            health_checks=healths,
                            constraints=constraints,
                            upgrade_strategy=upgrade_strategy,
                            labels=labels,
                            uris=uri,
                            require_ports=True,
                            cmd=cmd)
    client.update_app('{}-scheduler'.format(name), scheduler)

    if jupyter:
        cmd = ('jupyter notebook --allow-root --no-browser '
               '--NotebookApp.token=\'\' --ip 0.0.0.0 --port $PORT_NOTEBOOK')
        ports = [{'port': 0, 'protocol': 'tcp', 'name': 'notebook'}]
        jupyter = deepcopy(scheduler)
        jupyter.cmd = cmd
        jupyter.port_definitions = ports
        client.update_app('{}-jupyter'.format(name), jupyter)
