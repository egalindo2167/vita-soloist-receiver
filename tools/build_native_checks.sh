#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
native_dir=${1:-/tmp/vita-receiver-native}
mkdir -p "$native_dir"
opus_source=$(python "$project_dir/tools/fetch_build_sources.py" opus "$native_dir/sources")
tls_source=$(python "$project_dir/tools/fetch_build_sources.py" mbedtls "$native_dir/sources")
cmake -S "$opus_source" -B "$native_dir/opus" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DOPUS_FIXED_POINT=ON \
  -DOPUS_BUILD_TESTING=OFF -DOPUS_BUILD_PROGRAMS=OFF -DOPUS_DRED=OFF -DOPUS_OSCE=OFF
cmake --build "$native_dir/opus" -j2
cmake -S "$tls_source" -B "$native_dir/tls" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DENABLE_TESTING=OFF -DENABLE_PROGRAMS=OFF \
  -DMBEDTLS_USER_CONFIG_FILE="$project_dir/src/tls_config.h"
cmake --build "$native_dir/tls" -j2
cd "$project_dir"
cc -O2 -shared -fPIC -DSECURE_NET_HOST_TEST -D_POSIX_C_SOURCE=200809L \
  -DMBEDTLS_USER_CONFIG_FILE=\""$project_dir/src/tls_config.h"\" -I"$tls_source/include" \
  src/secure_net.c "$native_dir/tls/library/libmbedtls.a" \
  "$native_dir/tls/library/libmbedx509.a" "$native_dir/tls/library/libmbedcrypto.a" \
  -lpthread -o "$native_dir/vita-tls.so"
cc -shared -fPIC -O2 src/remote_profile.c -o "$native_dir/remote-profile.so"
cc -O2 -I"$opus_source/include" tests/opus_stream_test.c src/opus_stream.c \
  "$native_dir/opus/libopus.a" -lm -o "$native_dir/opus-decode"
cc -shared -Wl,--whole-archive "$native_dir/opus/libopus.a" -Wl,--no-whole-archive -lm -o "$native_dir/libopus.so.0"
export LD_LIBRARY_PATH="$native_dir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
OPUS_SOURCE="$opus_source" OPUS_LIBRARY="$native_dir/opus/libopus.a" bash tests/run_native.sh
VITA_TLS_TEST_LIB="$native_dir/vita-tls.so" VITA_REMOTE_TEST_LIB="$native_dir/remote-profile.so" \
VITA_OPUS_TEST_DECODER="$native_dir/opus-decode" \
python -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py' -v
