#!/usr/bin/env bash
# Run from repository root. Point OPUS_SOURCE/OPUS_LIBRARY at a native fixed-point
# Opus build. This does not use the ARM archive from the Vita build.
set -eu
native_out=$(mktemp -d /tmp/vita-native.XXXXXX)
trap 'rm -rf "$native_out"' EXIT
export ASAN_OPTIONS=detect_leaks=0
native_flags='-std=c11 -Wall -Wextra -g -fsanitize=address,undefined -fno-omit-frame-pointer'
cc $native_flags tests/capture_policy_test.c -o "$native_out/capture-policy"
"$native_out/capture-policy"
cc $native_flags tests/audio_reset_test.c -o "$native_out/audio-reset"
"$native_out/audio-reset"
cc $native_flags -D_POSIX_C_SOURCE=200809L tests/audio_quality_test.c src/audio_quality.c -o "$native_out/audio-quality"
"$native_out/audio-quality"
cc $native_flags -D_POSIX_C_SOURCE=200809L tests/settings_menu_test.c src/settings_menu.c src/display_settings.c src/audio_quality.c -o "$native_out/settings-menu"
"$native_out/settings-menu"
cc $native_flags tests/search_keyboard_test.c src/search_keyboard.c -o "$native_out/search-keyboard"
"$native_out/search-keyboard"
cc $native_flags -ffunction-sections -fdata-sections -Wl,--gc-sections -Itests tests/pc_link_state_test.c src/remote_profile.c src/audio_quality.c src/display_settings.c -o "$native_out/pc-link"
"$native_out/pc-link"
cc $native_flags tests/remote_profile_test.c src/remote_profile.c -o "$native_out/remote-profile"
"$native_out/remote-profile"
cc $native_flags tests/protocol_test.c -o "$native_out/protocol"
"$native_out/protocol"
cc $native_flags tests/audio_buffers_test.c -o "$native_out/audio-buffers"
"$native_out/audio-buffers"
cc $native_flags tests/control_state_test.c src/control_state.c -o "$native_out/controls"
"$native_out/controls"
cc $native_flags -ffunction-sections -fdata-sections -Wl,--gc-sections -Itests tests/control_input_test.c src/control_state.c src/search_keyboard.c -o "$native_out/control-input"
"$native_out/control-input"
cc $native_flags tests/screen_policy_test.c src/screen_policy.c -o "$native_out/screen-policy"
"$native_out/screen-policy"
cc $native_flags -DUI_HOST_TEST -Itests tests/ui_startup_test.c src/ui.c src/ui_render.c src/ui_draw.c src/ui_font_data.c src/search_keyboard.c -lm -o "$native_out/ui-startup"
"$native_out/ui-startup"
cc $native_flags tests/oled_render_test.c src/ui_render.c src/ui_draw.c src/ui_font_data.c src/search_keyboard.c -lm -o "$native_out/oled"
"$native_out/oled"
cc $native_flags -I"${OPUS_SOURCE:?}/include" tests/opus_stream_test.c src/opus_stream.c "${OPUS_LIBRARY:?}" -lm -o "$native_out/opus"
"$native_out/opus"
