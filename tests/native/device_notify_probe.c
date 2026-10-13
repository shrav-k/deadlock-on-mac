/* Regression probe for Wine's device-notification handle validation.
 * Exercises real Wine exports; SEH catches the old fault in this probe only.
 */
#include <windows.h>
#include <dbt.h>
#include <stdio.h>

#ifndef _WIN64
/* LLVM-MinGW's i686 SEH codegen can crash; use this probe's unhandled filter. */
static const char *active_case;
static LONG CALLBACK probe_exception(EXCEPTION_POINTERS *info)
{
    printf("%s: exception=%08lx\n", active_case, info->ExceptionRecord->ExceptionCode);
    fflush(stdout);
    ExitProcess(2);
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

static int check(HDEVNOTIFY handle, DWORD expected, const char *name)
{
    BOOL result = TRUE;
    DWORD error = 0, exception = 0;
#ifdef _WIN64
    __try {
#else
    active_case = name;
    {
#endif
        SetLastError(0);
        result = UnregisterDeviceNotification(handle);
        error = GetLastError();
    }
#ifdef _WIN64
    __except(EXCEPTION_EXECUTE_HANDLER) {
        exception = GetExceptionCode();
    }
#endif
    printf("%s: result=%d error=%lu exception=%08lx\n", name, result, error, exception);
    fflush(stdout);
    return exception || result || error != expected;
}

int main(void)
{
    static const char garbage[] = "this is a valid but garbage pointer with enough readable bytes";
    int failed = 0;
#ifndef _WIN64
    SetUnhandledExceptionFilter(probe_exception);
#endif
    void *inaccessible = VirtualAlloc(NULL, 4096, MEM_RESERVE, PAGE_NOACCESS);
    if (!inaccessible) return 10;
    failed += check(NULL, ERROR_INVALID_HANDLE, "null");
    failed += check((HDEVNOTIFY)garbage, ERROR_INVALID_HANDLE, "readable-invalid");
    failed += check((HDEVNOTIFY)inaccessible, ERROR_SERVICE_SPECIFIC_ERROR, "inaccessible");
    VirtualFree(inaccessible, 0, MEM_RELEASE);

    HWND window = CreateWindowExW(0, L"STATIC", L"Deadlock notification probe", 0,
                                  0, 0, 0, 0, HWND_MESSAGE, NULL, NULL, NULL);
    DEV_BROADCAST_DEVICEINTERFACE_W filter = {0};
    filter.dbcc_size = sizeof(filter);
    filter.dbcc_devicetype = DBT_DEVTYP_DEVICEINTERFACE;
    HDEVNOTIFY valid = RegisterDeviceNotificationW(window, &filter, DEVICE_NOTIFY_ALL_INTERFACE_CLASSES);
    if (!window || !valid) {
        printf("valid-registration failed: %lu\n", GetLastError());
        failed++;
    } else {
        BOOL ok = UnregisterDeviceNotification(valid);
        printf("valid-registration: unregister=%d\n", ok);
        if (!ok) failed++;
    }
    if (window) DestroyWindow(window);
    printf("failures=%d\n", failed);
    return failed ? 1 : 0;
}
