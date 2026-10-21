# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.14-slim-bookworm

FROM ${PYTHON_IMAGE} AS mpi-build

# Retain the MPI version used by this project for the precompiled ASTRA binary.
ARG OMPI_VERSION=4.0.7
ARG OMPI_SHA256=269a4106312c80a9a6991da7f7c342195b73deea387048887e77e7aedc6dbf2d
ARG BUILD_JOBS=8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl gfortran \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/openmpi
RUN curl --fail --show-error --location --retry 3 \
        "https://download.open-mpi.org/release/open-mpi/v4.0/openmpi-${OMPI_VERSION}.tar.gz" \
        --output openmpi.tar.gz \
    && echo "${OMPI_SHA256}  openmpi.tar.gz" | sha256sum --check - \
    && tar -xzf openmpi.tar.gz --strip-components=1 \
    && ./configure --prefix=/opt/openmpi \
        --enable-mpi-fortran=usempi --disable-static \
    && make -j "${BUILD_JOBS}" \
    && make install-strip \
    && ln -s libmpi_usempi_ignore_tkr.so /opt/openmpi/lib/libmpi_usempi.so.40 \
    && rm -rf /opt/openmpi/include /opt/openmpi/share/man /opt/openmpi/lib/pkgconfig

FROM ${PYTHON_IMAGE} AS astra-download
ARG TARGETARCH
RUN test "${TARGETARCH}" = amd64 \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/astra \
    && curl --fail --show-error --location --retry 3 \
        https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/generator \
        --output /opt/astra/generator \
    && curl --fail --show-error --location --retry 3 \
        https://www.desy.de/~mpyflo/Astra_for_64_Bit_Linux/Astra \
        --output /opt/astra/astra \
    && curl --fail --show-error --location --retry 3 \
        https://www.desy.de/~mpyflo/Parallel_Astra_for_Linux/Astra \
        --output /opt/astra/parallel_astra \
    && chmod 755 /opt/astra/*

FROM ${PYTHON_IMAGE} AS runtime-image

# libgfortran5 supplies the GNU Fortran runtime (including libquadmath).
# Compilers, download tools, and their dependencies stay in the build stages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=mpi-build /opt/openmpi /opt/openmpi
COPY --from=astra-download /opt/astra /opt/astra
ENV PATH="/opt/openmpi/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/openmpi/lib" \
    ASTRA_BINARY_PATH="/opt/astra" \
    OMPI_ALLOW_RUN_AS_ROOT=1 \
    OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

# Fail the build if a DESY binary changes its shared-library requirements.
RUN set -eu; \
    mpirun --version; \
    for binary in /opt/astra/astra /opt/astra/generator /opt/astra/parallel_astra; do \
        ldd -r "$binary" > /tmp/astra-libraries.txt 2>&1; \
        cat /tmp/astra-libraries.txt; \
        if grep -Eq 'not found|undefined symbol' /tmp/astra-libraries.txt; then exit 1; fi; \
    done; \
    rm /tmp/astra-libraries.txt
