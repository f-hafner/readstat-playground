FROM ubuntu:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    r-base r-base-dev \
    curl \
    htop \
    # DuckDB
    git g++ cmake ninja-build libssl-dev libcurl4-openssl-dev \
    # TODO: not sure all this stuff is necessary
    jq lsb-release \
    libfontconfig-dev \
    libfreetype-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    libicu-dev \
    libgit2-dev \
    libjpeg-turbo8-dev \
    libpng-dev \
    libuv1-dev \
    libxml2-dev \
    libxslt1-dev \
    libtiff-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

RUN R --no-save -e 'install.packages(c("haven", "tictoc"))'

RUN git clone https://github.com/duckdb/duckdb && \
    cd duckdb && \
    git checkout v1.5.4 && \
    GEN=ninja make -j 1

ENV PATH="/duckdb/build/release/:/root/.local/bin:${PATH}"
