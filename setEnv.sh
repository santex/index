#! /bin/bash
export LC_ALL=en_US.UTF-8


apt install exiftool;
apt install sqlite3;


python3.9 -m pip uninstall 'ffmpeg-streaming2==0.1.0'
cd  /mnt/volume_nyc1_01/content/vid/data/lib/;
tar -czvf ffmpeg-streaming2-0.1.0.tar.gz ffmpeg-streaming2-0.1.0/*;
python3.9 -m pip  install  ffmpeg-streaming2-0.1.0.tar.gz

#python3.9 -m pip uninstall 'python-ffmpeg-video-streaming==0.1.15';
#cd  /Users/hagen.geissler/funke/repos/index/data/lib/;

#tar -czvf python-ffmpeg-video-streaming-0.1.15.tar.gz python-ffmpeg-video-streaming-0.1.15/*;

#python3.9 -m pip  install python-ffmpeg-video-streaming-0.1.15.tar.gz;


