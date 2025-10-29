
add_library(usermod_sound INTERFACE)

# Add our source files to the lib
target_sources(usermod_sound INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/sound.c
    ${CMAKE_CURRENT_LIST_DIR}/bitstream.c
    ${CMAKE_CURRENT_LIST_DIR}/buffers.c
    ${CMAKE_CURRENT_LIST_DIR}/dct32.c
    ${CMAKE_CURRENT_LIST_DIR}/dequant.c
    ${CMAKE_CURRENT_LIST_DIR}/dqchan.c
    ${CMAKE_CURRENT_LIST_DIR}/huffman.c
    ${CMAKE_CURRENT_LIST_DIR}/hufftabs.c
    ${CMAKE_CURRENT_LIST_DIR}/imdct.c
    ${CMAKE_CURRENT_LIST_DIR}/mp3dec.c
    ${CMAKE_CURRENT_LIST_DIR}/mp3tabs.c
    ${CMAKE_CURRENT_LIST_DIR}/polyphase.c
    ${CMAKE_CURRENT_LIST_DIR}/scalfact.c
    ${CMAKE_CURRENT_LIST_DIR}/stproc.c
    ${CMAKE_CURRENT_LIST_DIR}/subband.c
    ${CMAKE_CURRENT_LIST_DIR}/trigtabs.c
)

# Add the current directory as an include directory.
target_include_directories(usermod_sound INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

# Link our INTERFACE library to the usermod target.
target_link_libraries(usermod INTERFACE usermod_sound)
