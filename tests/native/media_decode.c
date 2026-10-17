/* Decode an owned, generated WAV; no audio device, game or network is used. */
#include <stdio.h>
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>

int main(int argc, char **argv) {
    AVFormatContext *format = NULL;
    const AVCodec *codec = NULL;
    if (argc != 2 || avformat_version() >> 16 != 63 || avcodec_version() >> 16 != 63 || avutil_version() >> 16 != 61) return 1;
    if (avformat_open_input(&format, argv[1], NULL, NULL) < 0 || avformat_find_stream_info(format, NULL) < 0) return 2;
    int stream = av_find_best_stream(format, AVMEDIA_TYPE_AUDIO, -1, -1, &codec, 0);
    if (stream < 0 || !codec) return 3;
    AVCodecContext *decoder = avcodec_alloc_context3(codec);
    if (!decoder || avcodec_parameters_to_context(decoder, format->streams[stream]->codecpar) < 0 ||
        avcodec_open2(decoder, codec, NULL) < 0) return 4;
    AVPacket *packet = av_packet_alloc();
    AVFrame *frame = av_frame_alloc();
    int samples = 0, result;
    while ((result = av_read_frame(format, packet)) >= 0) {
        if (packet->stream_index == stream) {
            if (avcodec_send_packet(decoder, packet) < 0) return 5;
            while ((result = avcodec_receive_frame(decoder, frame)) >= 0) {
                samples += frame->nb_samples;
                av_frame_unref(frame);
            }
            if (result != AVERROR(EAGAIN) && result != AVERROR_EOF) return 6;
        }
        av_packet_unref(packet);
    }
    if (result != AVERROR_EOF) return 7;
    avcodec_send_packet(decoder, NULL);
    while (avcodec_receive_frame(decoder, frame) >= 0) { samples += frame->nb_samples; av_frame_unref(frame); }
    printf("Decoded samples=%d; FFmpeg ABI format=%u codec=%u util=%u\n", samples,
           avformat_version() >> 16, avcodec_version() >> 16, avutil_version() >> 16);
    av_frame_free(&frame); av_packet_free(&packet); avcodec_free_context(&decoder); avformat_close_input(&format);
    return samples == 48000 ? 0 : 8;
}
