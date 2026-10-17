/* WinMM startup and output-format regression probe. No microphone is opened.
 * Playback buffers contain silence. A watchdog bounds device-driver stalls.
 * This checks API completion/conversion, not audible quality or game audio.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#include <mmreg.h>
#include <stdio.h>
#include <string.h>

static DWORD WINAPI watchdog(void *unused)
{
    (void)unused;
    Sleep(45000);
    puts("FAIL: audio probe watchdog expired after 45 seconds");
    fflush(stdout);
    ExitProcess(124);
    return 0;
}

static int output_format(WORD tag, DWORD rate, WORD bits, WORD channels)
{
    WAVEFORMATEX fmt = {0};
    WAVEHDR header = {0};
    HWAVEOUT output = NULL;
    MMRESULT query, opened, prepared, written, reset, unprepared, closed;
    HANDLE event;
    BYTE *buffer;
    DWORD bytes;
    ULONGLONG started, deadline;
    int done;

    fmt.wFormatTag = tag;
    fmt.nChannels = channels;
    fmt.nSamplesPerSec = rate;
    fmt.wBitsPerSample = bits;
    fmt.nBlockAlign = (WORD)(channels * bits / 8);
    fmt.nAvgBytesPerSec = rate * fmt.nBlockAlign;
    started = GetTickCount64();
    query = waveOutOpen(NULL, WAVE_MAPPER, &fmt, 0, 0, WAVE_FORMAT_QUERY);
    printf("query tag=%u rate=%lu bits=%u channels=%u result=%u ms=%llu\n",
           tag, (unsigned long)rate, bits, channels, query, GetTickCount64() - started);
    fflush(stdout);
    if (query != MMSYSERR_NOERROR) return 1;

    event = CreateEventW(NULL, FALSE, FALSE, NULL);
    if (!event) return 1;
    opened = waveOutOpen(&output, WAVE_MAPPER, &fmt, (DWORD_PTR)event, 0, CALLBACK_EVENT);
    if (opened != MMSYSERR_NOERROR) {
        printf("FAIL: open=%u\n", opened);
        CloseHandle(event);
        return 1;
    }
    /* 50ms, aligned frames. PCM8 and mu-law have different silence encodings. */
    bytes = (rate / 20) * fmt.nBlockAlign;
    buffer = HeapAlloc(GetProcessHeap(), 0, bytes);
    if (!buffer) { waveOutClose(output); CloseHandle(event); return 1; }
    memset(buffer, tag == WAVE_FORMAT_MULAW ? 0xff :
           (tag == WAVE_FORMAT_PCM && bits == 8 ? 0x80 : 0), bytes);
    header.lpData = (LPSTR)buffer;
    header.dwBufferLength = bytes;
    prepared = waveOutPrepareHeader(output, &header, sizeof(header));
    ResetEvent(event);
    written = prepared == MMSYSERR_NOERROR ? waveOutWrite(output, &header, sizeof(header)) : prepared;
    deadline = GetTickCount64() + 3000;
    while (written == MMSYSERR_NOERROR && !(header.dwFlags & WHDR_DONE) && GetTickCount64() < deadline)
        WaitForSingleObject(event, 50);
    done = (header.dwFlags & WHDR_DONE) != 0;
    reset = waveOutReset(output);
    unprepared = prepared == MMSYSERR_NOERROR ? waveOutUnprepareHeader(output, &header, sizeof(header)) : prepared;
    closed = waveOutClose(output);
    printf("play tag=%u rate=%lu bits=%u channels=%u open=%u prepare=%u write=%u done=%d reset=%u unprepare=%u close=%u\n",
           tag, (unsigned long)rate, bits, channels, opened, prepared, written, done, reset, unprepared, closed);
    fflush(stdout);
    HeapFree(GetProcessHeap(), 0, buffer);
    CloseHandle(event);
    return prepared || written || !done || reset || unprepared || closed;
}

int main(int argc, char **argv)
{
    static const DWORD rates[] = {11025, 22050, 44100, 48000, 96000};
    HANDLE timer;
    HMIXER mixer;
    UINT devices, mixers;
    MMRESULT result;
    ULONGLONG start;
    unsigned int i, bits, channels;
    int failures = 0;
    WAVEFORMATEX invalid = {0};
    setvbuf(stdout, NULL, _IONBF, 0);
    timer = CreateThread(NULL, 0, watchdog, NULL, 0, NULL);
    if (!timer) return 2;
    CloseHandle(timer);
    puts("stage=enumeration-start");
    start = GetTickCount64();
    devices = waveOutGetNumDevs();
    mixers = mixerGetNumDevs();
    printf("enumeration devices=%u mixers=%u ms=%llu\n", devices, mixers, GetTickCount64() - start);
    if (!devices) return 2;
    for (i = 0; i < devices; i++) {
        WAVEOUTCAPSW caps = {0};
        result = waveOutGetDevCapsW(i, &caps, sizeof(caps));
        printf("caps device=%u result=%u formats=%08lx channels=%u\n", i, result,
               (unsigned long)caps.dwFormats, caps.wChannels);
        failures += result != MMSYSERR_NOERROR;
    }
    if (mixers) {
        result = mixerOpen(&mixer, 0, 0, 0, 0);
        printf("mixer-open result=%u\n", result);
        failures += result != MMSYSERR_NOERROR;
        if (!result) failures += mixerClose(mixer) != MMSYSERR_NOERROR;
    }
    if (argc > 1 && !strcmp(argv[1], "--enumerate-only")) {
        printf("failures=%d\n", failures);
        return failures ? 1 : 0;
    }
    for (i = 0; i < sizeof(rates) / sizeof(rates[0]); i++)
        for (bits = 8; bits <= 16; bits += 8)
            for (channels = 1; channels <= 2; channels++)
                failures += output_format(WAVE_FORMAT_PCM, rates[i], (WORD)bits, (WORD)channels);
    failures += output_format(WAVE_FORMAT_IEEE_FLOAT, 44100, 32, 2);
    failures += output_format(WAVE_FORMAT_IEEE_FLOAT, 48000, 32, 2);
    failures += output_format(WAVE_FORMAT_MULAW, 8000, 8, 1);
    invalid.wFormatTag = 0xffff;
    invalid.nChannels = 2;
    invalid.nSamplesPerSec = 44100;
    invalid.wBitsPerSample = 16;
    invalid.nBlockAlign = 4;
    invalid.nAvgBytesPerSec = 176400;
    result = waveOutOpen(NULL, WAVE_MAPPER, &invalid, 0, 0, WAVE_FORMAT_QUERY);
    printf("invalid-format result=%u\n", result);
    failures += result == MMSYSERR_NOERROR;
    printf("failures=%d\n", failures);
    return failures ? 1 : 0;
}
