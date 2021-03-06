from time import time, sleep

from distributed import Client
from daskathon import MarathonCluster

from marathon import MarathonClient


cg = MarathonClient('http://localhost:8080')
for app in cg.list_apps():
    cg.delete_app(app.id, force=True)


def test_multiple_workers():
    with MarathonCluster(nworkers=2, marathon='http://localhost:8080',
                         scheduler_port=9001, diagnostics_port=9101) as mc:
        while len(mc.scheduler.workers) < 2:
            sleep(0.1)

        with Client(mc.scheduler_address) as c:
            x = c.submit(lambda x: x + 1, 1)
            assert x.result() == 2


def test_manual_scaling():
    with MarathonCluster(marathon='http://localhost:8080',
                         scheduler_port=9002, diagnostics_port=9102) as mc:
        assert not mc.scheduler.ncores

        mc.scale_up(1)
        while len(mc.scheduler.workers) < 1:
            sleep(0.1)

        with Client(mc.scheduler_address) as c:
            x = c.submit(lambda x: x + 1, 1)
            assert x.result() == 2

        mc.scale_down(mc.scheduler.workers)
        while mc.scheduler.workers:
            sleep(0.1)


def test_adapting():
    with MarathonCluster(marathon='http://localhost:8080',
                         cpus=1, mem=512, adaptive=True,
                         scheduler_port=9003, diagnostics_port=9103) as mc:
        with Client(mc.scheduler_address) as c:
            assert not mc.scheduler.ncores
            x = c.submit(lambda x: x + 1, 1)
            assert x.result() == 2
            assert len(mc.scheduler.ncores) == 1

            del x

        start = time()
        while mc.scheduler.ncores:
            sleep(0.01)
            assert time() < start + 5
