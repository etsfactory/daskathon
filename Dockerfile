FROM kszucs/miniconda3

RUN conda install -y nomkl distributed dask bokeh partd s3fs fastparquet pandas libgcc cytoolz \
 && conda clean -y -a

ADD . /daskathon
RUN pip install -e /daskathon

