FROM kszucs/miniconda3:debian

RUN conda install -y nomkl dask bokeh partd s3fs \
                     fastparquet pandas cytoolz distributed \
 && conda clean -y -a \

ADD . /daskathon

RUN pip install --no-cache-dir /daskathon

