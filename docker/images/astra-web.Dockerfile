FROM python:3.12 AS runtime-image

ENV OMPI_SRC=https://download.open-mpi.org/release/open-mpi/v4.0/openmpi-4.0.7.tar.gz
ENV	PREFIX=/home/.openmpi

RUN curl -Lo- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor -o /usr/share/keyrings/oneapi-archive-keyring.gpg
RUN /bin/bash -c 'echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main"' | tee /etc/apt/sources.list.d/oneAPI.list

RUN	apt-get update && apt-get install -y \
		build-essential \
        gfortran \
        curl \
		git \
        intel-oneapi-compiler-fortran \
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

ENV I_MPI_F90="ifort"

# Download most recent ASTRA binaries from sources
RUN wget https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/generator  \
    && mkdir /opt/astra \
    && chmod 777 generator && mv generator /opt/astra/generator \
    && wget https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/Astra \
    && chmod 777 Astra && mv Astra /opt/astra/astra \
    && wget https://www.desy.de/~mpyflo/Parallel_Astra_for_Linux/Astra \
    && chmod 777 Astra && mv Astra /opt/astra/parallel_astra