from ffmpeg_streaming2 import Formats, Bitrate, Representation, Size
import ffmpeg_streaming2

video = ffmpeg_streaming2.input(
    'https://qiniu.cuiqingcai.com/%E8%AF%BE%E6%97%B604%EF%BC%9AMySQL%E7%9A%84%E5%AE%89%E8%A3%85.mp4')


_720p = Representation(Size(1280, 720), Bitrate(2048 * 1024, 320 * 1024))

font_file = './files/msyh.ttf'
hls = video.hls(Formats.h264())
hls.representations(_720p)
hls.watermarking('盗版必究', font_file=font_file)
hls.output('./outputs/hls.m3u8')
