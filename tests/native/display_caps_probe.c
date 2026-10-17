/* Read-only comparison for Wine Retina GDI sizing regressions.
 * No windows, mode changes, Steam calls or game input. Values are evidence,
 * not a fullscreen pass: compare both Retina policies and native host inventory.
 */
#include <windows.h>
#include <stdio.h>

static unsigned count;

static BOOL CALLBACK inspect(HMONITOR monitor, HDC unused, RECT *rect, LPARAM data)
{
    (void)unused; (void)rect; (void)data;
    MONITORINFOEXW info = {0}; info.cbSize = sizeof(info);
    DEVMODEW mode = {0}; mode.dmSize = sizeof(mode);
    if (!GetMonitorInfoW(monitor, (MONITORINFO *)&info) ||
        !EnumDisplaySettingsW(info.szDevice, ENUM_CURRENT_SETTINGS, &mode)) return FALSE;
    HDC dc = CreateDCW(L"DISPLAY", info.szDevice, NULL, NULL);
    if (!dc) return FALSE;
    printf("device=%ls primary=%u monitor=%ldx%ld mode=%lux%lu "
           "horzres=%d vertres=%d desktop=%dx%d dpi=%dx%d\n",
           info.szDevice, !!(info.dwFlags & MONITORINFOF_PRIMARY),
           info.rcMonitor.right - info.rcMonitor.left, info.rcMonitor.bottom - info.rcMonitor.top,
           mode.dmPelsWidth, mode.dmPelsHeight, GetDeviceCaps(dc, HORZRES), GetDeviceCaps(dc, VERTRES),
           GetDeviceCaps(dc, DESKTOPHORZRES), GetDeviceCaps(dc, DESKTOPVERTRES),
           GetDeviceCaps(dc, LOGPIXELSX), GetDeviceCaps(dc, LOGPIXELSY));
    DeleteDC(dc);
    ++count;
    return TRUE;
}

int main(void)
{
    if (!SetProcessDPIAware()) { fprintf(stderr, "DPI awareness failed\n"); return 1; }
    printf("awareness=system primary_metrics=%dx%d\n", GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN));
    if (!EnumDisplayMonitors(NULL, NULL, inspect, 0) || !count) return 1;
    puts("inventory_collected=yes visual_output_verified=no");
    return 0;
}
