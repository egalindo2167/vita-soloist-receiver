cmake_minimum_required(VERSION 3.16)
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
  set(CMAKE_TOOLCHAIN_FILE "$ENV{VITASDK}/share/vita.toolchain.cmake" CACHE PATH "Vita toolchain")
endif()
project(vita_audio_receiver C)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
include("$ENV{VITASDK}/share/vita.cmake" REQUIRED)
set(CMAKE_C_STANDARD 11)
include(FetchContent)
# Fixed-point decoder, no optional machine-learning extensions. The archive is
# pinned and verified; no additional decoder installation is needed on the Vita.
set(OPUS_FIXED_POINT ON CACHE BOOL "" FORCE)
set(OPUS_ENABLE_FLOAT_API OFF CACHE BOOL "" FORCE)
set(OPUS_BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(OPUS_BUILD_PROGRAMS OFF CACHE BOOL "" FORCE)
set(OPUS_BUILD_SHARED_LIBRARY OFF CACHE BOOL "" FORCE)
set(OPUS_DRED OFF CACHE BOOL "" FORCE)
set(OPUS_OSCE OFF CACHE BOOL "" FORCE)
set(OPUS_PRESUME_NEON ON CACHE BOOL "" FORCE)
set(OPUS_MAY_HAVE_NEON OFF CACHE BOOL "" FORCE)
FetchContent_Declare(opus
 URL https://downloads.xiph.org/releases/opus/opus-1.6.1.tar.gz
 URL_HASH SHA256=6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1)
FetchContent_MakeAvailable(opus)
target_compile_options(opus PRIVATE -O3 -ffunction-sections -fdata-sections)
set(ENABLE_PROGRAMS OFF CACHE BOOL "" FORCE)
set(ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(MBEDTLS_USER_CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/src/tls_config.h" CACHE FILEPATH "" FORCE)
FetchContent_Declare(mbedtls
 URL https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-3.6.7/mbedtls-3.6.7.tar.bz2
 URL_HASH SHA256=a7e8bcbec0e6f761b4af24f25677626b35f762f68eef79c08677a363212d11f6)
FetchContent_MakeAvailable(mbedtls)
add_executable(receiver src/main.c src/debugScreen.c src/ui.c src/ui_render.c src/ui_draw.c src/ui_font_data.c src/control.c src/control_state.c src/pc_link.c src/screen_policy.c src/opus_stream.c src/secure_net.c src/remote_profile.c src/audio_quality.c src/settings_menu.c src/display_settings.c src/search_keyboard.c)
target_compile_options(receiver PRIVATE -Wall -Wextra)
target_link_libraries(receiver opus mbedtls mbedx509 mbedcrypto SceAudio_stub SceNet_stub SceNetCtl_stub SceCtrl_stub
 SceDisplay_stub SceSysmem_stub SceSysmodule_stub ScePower_stub SceKernelThreadMgr_stub SceTouch_stub m)
vita_create_self(eboot.bin receiver UNSAFE)
vita_create_vpk(vita-audio-receiver.vpk VRXA00001 eboot.bin VERSION 01.17 NAME "Vita Audio Receiver"
 FILE sce_sys/icon0.png sce_sys/icon0.png
 FILE sce_sys/pic0.png sce_sys/pic0.png
 FILE sce_sys/livearea/contents/bg.png sce_sys/livearea/contents/bg.png
 FILE sce_sys/livearea/contents/startup.png sce_sys/livearea/contents/startup.png
 FILE sce_sys/livearea/contents/template.xml sce_sys/livearea/contents/template.xml
 FILE MBEDTLS-LICENSE.txt licenses/mbedtls.txt
 FILE OPUS-LICENSE.txt licenses/opus.txt
 FILE PSPSDK-LICENSE.txt licenses/pspsdk-font.txt
 FILE VitaSpotify-MIT-LICENSE.txt licenses/debugscreen.txt
 FILE UI-FONT-LICENSE.txt licenses/ui-font.txt)
