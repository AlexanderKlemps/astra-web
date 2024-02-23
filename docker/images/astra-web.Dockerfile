FROM python:3.12 AS runtime-image

ENV OMPI_SRC=https://download.open-mpi.org/release/open-mpi/v4.0/openmpi-4.0.7.tar.gz
ENV	PREFIX=/home/.openmpi

RUN	apt update && apt install -y \
		build-essential \
        gfortran \
        curl \
		git \
        nano

RUN curl -SL ${OMPI_SRC} | tar -xz -C /usr/src && \
    mkdir -p /home/build/openmpi && cd /home/build/openmpi \
    && /usr/src/openmpi-*/configure --prefix=${PREFIX} --enable-mpi-fortran=usempi \
    && make -j 4 && make install

RUN ln -s $PREFIX/lib/libmpi_usempi_ignore_tkr.so $PREFIX/lib/libmpi_usempi.so.40

# set library paths
ENV PATH="$PREFIX/bin:$PATH"
ENV LD_LIBRARY_PATH="$PREFIX/lib:$LD_LIBRARY_PATH"

# set env variables so openmpi can be run as root
ENV OMPI_ALLOW_RUN_AS_ROOT=1
ENV OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1