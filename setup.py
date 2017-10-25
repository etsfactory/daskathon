#!/usr/bin/env python

import versioneer
from os.path import exists
from setuptools import setup

setup(name='daskathon',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      description='Deploy Dask on Marathon',
      url='http://github.com/daskos/daskathon/',
      maintainer='Krisztian Szucs',
      maintainer_email='szucs.krisztian@gmail.com',
      license='BSD',
      keywords='',
      packages=['daskathon'],
      tests_require=['pytest'],
      setup_requires=['pytest-runner'],
      install_requires=['distributed', 'marathon', 'click'],
      long_description=(open('README.rst').read() if exists('README.rst')
                        else ''),
      entry_points='''
          [console_scripts]
          daskathon=daskathon.cli:daskathon
      ''',
      zip_safe=False)
