import boto3, argparse, datetime, sys, logging, dotenv, os, pprint

import ffmpeg_streaming2
from ffmpeg_streaming2 import Formats, S3, LINODE, CloudManager
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import Flask
from celery import Celery
from dotenv import load_dotenv

load_dotenv()



class S3x(object):
    BUCKET = os.environ.get("S3_BUCKET_NAME")
    connection = None

    def __init__(self):
        try:


            self.connection = boto3.resource('s3',aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
                                                  aws_secret_access_key=os.environ.get("AWS_ACCESS_SECRET"),
                                                  region_name="eu-west-1")
        except(Exception) as error:
            print(error)
            self.connection = None


    def upload_file(self,s3_out_dir, file_name):
        if file_name is None: return False
        file_name = "{}/{}".format(os.environ.get("S3_BUCKET_BASE_PATH"),file_name)
        
        self.connection.Bucket(self.BUCKET).upload_file(s3_out_dir, 
                                                                  file_name)
        print("Upload Successful")
        return True






class Config:
    """
    Load environment variables and assign them to Config class
    Make sure to add the required environment variables to .env file
    """

    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = bool(os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS"))
    AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
    AWS_ACCESS_SECRET = os.environ.get("AWS_ACCESS_SECRET")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    S3_BUCKET_BASE_PATH = os.environ.get("S3_BUCKET_BASE_PATH")
    S3_BUCKET_BASE_URL = os.environ.get("S3_BUCKET_BASE_URL")
    CELERY_CONFIG = {
        "broker_url": os.environ.get("CELERY_BROKER_URL"),
        "result_backend": os.environ.get("CELERY_RESULT_BACKEND"),
    }


#linode = LINODE(aws_access_key_id='YOUR_KEY_ID', aws_secret_access_key='YOUR_KEY_SECRET', region_name='YOUR_REGION')
#save_to_linode = CloudManager().add(linode, bucket_name=linode_bucket-name)

print(Config())

logging.basicConfig(filename='streaming.log', level=logging.NOTSET, format='[%(asctime)s] %(levelname)s: %(message)s')


def monitor(ffmpeg, duration, time_, time_left, process):
    """
       Handling proccess.

       Examples:
       1. Logging or printing ffmpeg command
       logging.info(ffmpeg) or print(ffmpeg)

       2. Handling Process object
       if "something happened":
           process.terminate()

       3. Email someone to inform about the time of finishing process
       if time_left > 3600 and not already_send:  # if it takes more than one hour and you have not emailed them already
           ready_time = time_left + time.time()
           Email.send(
               email='someone@somedomain.com',
               subject='Your video will be ready by %s' % datetime.timedelta(seconds=ready_time),
               message='Your video takes more than %s hour(s) ...' % round(time_left / 3600)
           )
          already_send = True

       4. Create a socket connection and show a progress bar(or other parameters) to your users
       Socket.broadcast(
           address=127.0.0.1
           port=5050
           data={
               percentage = per,
               time_left = datetime.timedelta(seconds=int(time_left))
           }
       )

       :param ffmpeg: ffmpeg command line
       :param duration: duration of the video
       :param time_: current time of transcoded video
       :param time_left: seconds left to finish the video process
       :param process: subprocess object
       :return: None
       """
    per = round(time_ / duration * 100)
    sys.stdout.write(
        "\rTranscoding...(%s%%) %s left [%s%s]" %
        (per, datetime.timedelta(seconds=int(time_left)), '#' * per, '-' * (100 - per))
    )
    sys.stdout.flush()



# Setting up S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.environ.get("AWS_ACCESS_SECRET"),
)


def upload_file(file: FileStorage) -> str:
    """
    Upload file using normal synchronous way
    """
    s3.upload_fileobj(
        file,
        app.config["S3_BUCKET_NAME"],
        file.filename,
        ExtraArgs={
            "ContentType": file.content_type,
        },
    )
    bu = os.environ.get('S3_BUCKET_BASE_URL')
    return f"{bu}/{file.filename}"



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, help='The path to the video file (required).')
    parser.add_argument('-o', '--output', default=None, help='The output to write files.')

    parser.add_argument('-fmp4', '--fragmented', default=False, help='Fragmented mp4 output')

    parser.add_argument('-k', '--key', default=None, help='The full pathname of the file where a random key will be '
                                                          'created (required). Note: The path of the key should be '
                                                          'accessible from your website(e.g. '
                                                          '"/var/www/public_html/keys/enc.key")')
    parser.add_argument('-u', '--url', default=None, help='A URL (or a path) to access the key on your website ('
                                                          'required)')
    parser.add_argument('-krp', '--key_rotation_period', default=0, help='Use a different key for each set of '
                                                                         'segments, rotating to a new key after this '
                                                                         'many segments.')


    AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
    AWS_ACCESS_SECRET = os.environ.get("AWS_ACCESS_SECRET")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    S3_BUCKET_BASE_PATH = os.environ.get("S3_BUCKET_BASE_PATH")
    S3_BUCKET_BASE_URL = os.environ.get("S3_BUCKET_BASE_URL")

    print([AWS_ACCESS_KEY,S3_BUCKET_BASE_URL])
    #s3 = S3(aws_access_key_id= os.environ.get("AWS_ACCESS_KEY"),
    #        aws_secret_access_key= os.environ.get("AWS_ACCESS_SECRET"),
    #        region_name= os.environ.get("AWS_ACCESS_KEY"))
            
    #save_to_s3 = CloudManager().add(s3, bucket_name="lg-image-extender")


    args = parser.parse_args()

    video = ffmpeg_streaming2.input(args.input)

    hls = video.hls(Formats.h264())
    #hls.auto_generate_representations()

    if args.fragmented:
        hls.fragmented_mp4()

    if args.key is not None and args.url is not None:
        hls.encryption(args.key, args.url, args.key_rotation_period)

   

    ofolder='hls'
    s3 = S3(aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("AWS_ACCESS_SECRET"),
            region_name='eu-west-1')

    
    s3x = S3x()
    s3x.upload_file(args.input,args.input)




    #save_to_s3 = CloudManager().add(s3, bucket_name=os.environ.get("S3_BUCKET_NAME"),
     #                                  folder=ofolder,
      #                                 filename=args.input)
    #pprint.pprint(save_to_s3)
    #hls.output(clouds=save_to_s3)
    return 1

    
if __name__ == "__main__":
    sys.exit(main())
