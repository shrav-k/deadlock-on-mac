/* Exercise Wine's PE -> Unix -> FFmpeg call path in both guest architectures. */
#include <windows.h>
#include <stdio.h>
typedef LONG (__cdecl *check_fn)(const char *mime);
int main(void) {
    HMODULE module = LoadLibraryW(L"winedmo.dll");
    if (!module) { printf("LoadLibrary failed: %lu\n", GetLastError()); return 1; }
    check_fn check = (check_fn)GetProcAddress(module, "winedmo_demuxer_check");
    if (!check) return 2;
    const char *types[] = {"video/mp4", "video/avi", "audio/wav", "audio/x-ms-wma", "video/mpeg", "audio/mp3"};
    for (unsigned i = 0; i < sizeof(types)/sizeof(types[0]); ++i) {
        LONG status = check(types[i]);
        printf("%s: %08lx\n", types[i], (unsigned long)status);
        if (status) return 3;
    }
    if ((unsigned long)check("application/not-a-media-format") != 0xc00000bbUL) return 4;
    FreeLibrary(module);
    puts("PASS Wine media bridge");
    return 0;
}
