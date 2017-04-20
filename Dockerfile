FROM kszucs/miniconda3

RUN apk --no-cache add bash \
 && conda install -y nomkl distributed dask bokeh partd s3fs \
                     fastparquet pandas libgcc cytoolz \
 && conda clean -y -a \
 && apk del bash

ADD . /daskathon
RUN pip install -e /daskathon

