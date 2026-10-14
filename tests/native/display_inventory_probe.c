/* Read-only display inventory through Win32, DXGI and the game's SDL3 build.
 * Creates no game/window, changes no display mode, and never loads Steam APIs.
 * SDL functions are resolved dynamically; signatures follow the SDL3 public API.
 * Usage: display-inventory-probe.exe Z:\absolute\path\to\SDL3.dll
 */
#define COBJMACROS
#include <windows.h>
#include <dxgi.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

static unsigned monitor_count;

static BOOL CALLBACK monitor(HMONITOR handle, HDC dc, RECT *rect, LPARAM user)
{
    (void)dc; (void)rect; (void)user;
    MONITORINFOEXW info = {0}; info.cbSize = sizeof(info);
    if (!GetMonitorInfoW(handle, (MONITORINFO *)&info)) return FALSE;
    DEVMODEW mode = {0}; mode.dmSize = sizeof(mode);
    if (!EnumDisplaySettingsW(info.szDevice, ENUM_CURRENT_SETTINGS, &mode)) return FALSE;
    printf("win32 index=%u device=%ls primary=%u bounds=%ld,%ld,%ld,%ld current=%lux%lu refresh=%lu\n",
           monitor_count++, info.szDevice, !!(info.dwFlags & MONITORINFOF_PRIMARY),
           info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom,
           mode.dmPelsWidth, mode.dmPelsHeight, mode.dmDisplayFrequency);
    return TRUE;
}

static int dxgi(void)
{
    IDXGIFactory *factory = NULL;
    HRESULT result = CreateDXGIFactory(&IID_IDXGIFactory, (void **)&factory);
    if (FAILED(result)) return 1;
    int failed = 0;
    for (UINT a = 0; a < 16; ++a) {
        IDXGIAdapter *adapter = NULL;
        result = IDXGIFactory_EnumAdapters(factory, a, &adapter);
        if (result == DXGI_ERROR_NOT_FOUND) break;
        if (FAILED(result)) { failed = 1; break; }
        for (UINT o = 0; o < 32; ++o) {
            IDXGIOutput *output = NULL;
            result = IDXGIAdapter_EnumOutputs(adapter, o, &output);
            if (result == DXGI_ERROR_NOT_FOUND) break;
            if (FAILED(result)) { failed = 1; break; }
            DXGI_OUTPUT_DESC desc = {0};
            result = IDXGIOutput_GetDesc(output, &desc);
            if (FAILED(result)) failed = 1;
            else printf("dxgi adapter=%u output=%u device=%ls attached=%d bounds=%ld,%ld,%ld,%ld\n",
                        a, o, desc.DeviceName, desc.AttachedToDesktop,
                        desc.DesktopCoordinates.left, desc.DesktopCoordinates.top,
                        desc.DesktopCoordinates.right, desc.DesktopCoordinates.bottom);
            IDXGIOutput_Release(output);
        }
        IDXGIAdapter_Release(adapter);
    }
    IDXGIFactory_Release(factory);
    return failed;
}

#define LOAD(ret, name, args) \
    ret (__cdecl *name) args = (void *)GetProcAddress(module, #name); \
    if (!name) { fprintf(stderr, "Missing SDL3 export: %s\n", #name); FreeLibrary(module); return 2; }

int wmain(int argc, wchar_t **argv)
{
    if (argc != 2) { fprintf(stderr, "Pass the absolute Windows path to SDL3.dll\n"); return 2; }
    if (!SetProcessDPIAware()) { fprintf(stderr, "Could not set probe DPI awareness\n"); return 2; }
    UINT (WINAPI *dpi_for_system)(void) = (void *)GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForSystem");
    if (!dpi_for_system) { fprintf(stderr, "GetDpiForSystem unavailable\n"); return 2; }
    printf("win32 dpi_awareness=system dpi=%u\n", dpi_for_system());
    if (!EnumDisplayMonitors(NULL, NULL, monitor, 0) || !monitor_count) return 1;
    int failed = dxgi();
    HMODULE module = LoadLibraryExW(argv[1], NULL,
                                   LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!module) { fprintf(stderr, "SDL3 load failed: %lu\n", GetLastError()); return 2; }
    typedef struct { int x, y, w, h; } Rect;
    LOAD(bool, SDL_Init, (uint32_t));
    LOAD(void, SDL_Quit, (void));
    LOAD(uint32_t *, SDL_GetDisplays, (int *));
    LOAD(uint32_t, SDL_GetPrimaryDisplay, (void));
    LOAD(const char *, SDL_GetDisplayName, (uint32_t));
    LOAD(bool, SDL_GetDisplayBounds, (uint32_t, Rect *));
    LOAD(uint32_t, SDL_GetDisplayProperties, (uint32_t));
    LOAD(void *, SDL_GetPointerProperty, (uint32_t, const char *, void *));
    LOAD(void, SDL_free, (void *));
    LOAD(const char *, SDL_GetError, (void));
    LOAD(int, SDL_GetVersion, (void));
    printf("sdl version=%d\n", SDL_GetVersion());
    if (!SDL_Init(0x20u)) { fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError()); FreeLibrary(module); return 1; }
    int count = 0;
    uint32_t *ids = SDL_GetDisplays(&count);
    if (!ids || count < 1 || count > 32) failed = 1;
    else for (int i = 0; i < count; ++i) {
        Rect rect = {0};
        MONITORINFOEXW info = {0}; info.cbSize = sizeof(info);
        HMONITOR handle = SDL_GetPointerProperty(SDL_GetDisplayProperties(ids[i]), "SDL.display.windows.hmonitor", NULL);
        const char *name = SDL_GetDisplayName(ids[i]);
        if (!SDL_GetDisplayBounds(ids[i], &rect) || !handle || !GetMonitorInfoW(handle, (MONITORINFO *)&info) || !name) {
            failed = 1; break;
        }
        printf("sdl index=%d instance=%u primary=%u name=%s device=%ls bounds=%d,%d,%d,%d\n",
               i, ids[i], ids[i] == SDL_GetPrimaryDisplay(), name, info.szDevice,
               rect.x, rect.y, rect.w, rect.h);
    }
    SDL_free(ids);
    SDL_Quit();
    FreeLibrary(module);
    printf("inventory_collected=%s visual_placement_verified=no game_selection_verified=no\n", failed ? "no" : "yes");
    return failed;
}
