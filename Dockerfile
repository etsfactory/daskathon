FROM kszucs/miniconda3

RUN conda install -y nomkl distributed dask bokeh partd s3fs hdfs3 fastparquet pandas libgcc \
 && conda clean -y -a

ADD . /daskathon
RUN pip install -e /daskathon

