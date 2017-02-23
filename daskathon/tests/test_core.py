import pytest
from time import time, sleep

from distributed import Client, Scheduler
from distributed.deploy import Adaptive
from daskathon import MarathonCluster
from threading import Thread

from marathon import MarathonClient
cg = MarathonClient('http://localhost:8080')

for app in cg.list_apps():
    cg.delete_app(app.id, force=True)


@pytest.mark.skip
def test_multiple_workers():
    with MarathonCluster(nworkers=2, marathon='http://localhost:8080') as mc:
        while len(mc.scheduler.workers) < 2:
            sleep(0.1)

        with Client(mc.scheduler_address) as c:
            x = c.submit(lambda x: x + 1, 1)
            assert x.result() == 2


def test_manual_scaling():
    with MarathonCluster(marathon='http://localhost:8080') as mc:
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
                         cpus=1, mem=512, adaptive=True) as mc:
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
