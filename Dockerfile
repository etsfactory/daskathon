FROM kszucs/miniconda3

RUN apk --no-cache add bash \
 && conda update --all -y \
 && conda install -y nomkl dask bokeh partd s3fs \
                     fastparquet pandas libgcc cytoolz \
 && conda clean -y -a \
 && apk del bash

ADD . /daskathon

RUN apk --no-cache add git \
 && pip install --no-cache-dir git+https://github.com/dask/distributed \
 && pip install -e /daskathon \
 && apk del git

