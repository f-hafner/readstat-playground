#!/bin/bash

declare myhome=${SUDO_HOME:-$HOME}
declare repeat=${1:-100}

exec 2>&1 1>/dev/null $myhome/.local/bin/duckdb -unsigned <<EOF
LOAD 'duckdb-read-stat/build/reldebug/read_stat.duckdb_extension';
SET threads=1;
$(for _ in $(seq 1 $repeat); do
    echo "SELECT count(*) FROM read_stat('data/test_small.sav');"
  done)
.quit
EOF
