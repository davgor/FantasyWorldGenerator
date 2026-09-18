#pragma once
// Conformance drivers exchange exact bytes over stdin/stdout. Windows opens both
// in text mode by default, which rewrites \n as \r\n on the way out, collapses
// \r\n to \n on the way in, and stops reading at a 0x1A byte. Any of those
// silently corrupts a binary corpus, so the fixtures must be read and written
// verbatim. No effect on POSIX, where the streams are already byte exact.
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <cstdio>
#endif

namespace fantasy_world_generator {
inline void use_binary_stdio() {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
}
}
