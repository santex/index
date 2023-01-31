#!/usr/local/bin/python3
#! -*- coding: utf-8-mb4 -*-
from __future__ import absolute_import

import sys
import os, sys, csv, tqdm, urllib3
import subprocess
from dotenv import load_dotenv
import json
from bs4 import BeautifulSoup
import requests
import xml.etree.ElementTree as ET
import feedparser
from os.path import abspath, join, dirname, exists
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from datetime import datetime
import sqlalchemy, enum, json, glob
from werkzeug.utils import secure_filename
import hashlib

headers_infos = """
.:.
.:. box33 | systems | platform |
.:. [   Renan Moura     ]
.:. [   ver.: 9.1.2-b   ]
.:.
"""


load_dotenv()

RAW_DATA = {
    "published":"http://161.35.14.248:8000/storage/content/vid/static/data/published.csv",
    "tools":"http://161.35.14.248:8000/storage/content/vid/static/data/tools.csv",
    "default-data":"http://161.35.14.248:8000/storage/content/vid/static/data/default-data.csv",
    "feeds":"http://161.35.14.248:8000/storage/content/vid/static/data/feeds.csv",
    "spiral-courses":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/courses.csv",
    "spiral-domains":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/domains.csv",
    "spiral-ecologies":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/ecologies.csv",
    "spiral-grades":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/grades.csv",
    "spiral-integrations":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/integrations.csv",
    "spiral-les":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/les.csv",
    "spiral-mentalities":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/mentalities.csv",
    "spiral-settings":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/settings.csv",
    "spiral-threads":"http://161.35.14.248:8000/storage/content/vid/static/data/spiral/threads.csv"
}
CHUNK_SIZE = 16384

RSS_FEEDS = {'cnn': 'http://rss.cnn.com/rss/edition.rss','me':'https://studio.twitter.com/1/library/mrss.xml?owner_id=264579898','local':'mrss.rss'}
 
headers = {
            'User-Agent': 'your-user-agent-here'
        }
 

class UploadStatus(enum.Enum):
    """
    Serves as enum values for upload_status column of files table
    (either PENDING, PROCESSING, COMPLETE OR ERROR)
    """

    PENDING = 1
    PROCESSING = 2
    COMPLETE = 3
    ERROR = 4




def rename_file(filename: str):
    """
    Rename a file using its original name (modified) and current timestamp
    """
    uploaded_date = datetime.utcnow()

    if filename is None:
        raise ValueError("Filename is required")

    splitted = filename.rsplit(".", 1)
    if len(splitted) < 2:
        raise ValueError("Filename must have an extension")

    updated_filename = splitted[0]
    file_extension = splitted[1]

    # Make sure that filename is secure
    updated_filename = secure_filename(updated_filename.lower())

    # Combining filename and timestamp
    updated_filename = f"{uploaded_date.strftime('%Y%m%d%H%M%S')}--{updated_filename}"

    # Combining the updated filename and file extension
    updated_filename = f"{updated_filename}.{file_extension}"

    return updated_filename



class Config:
    """
    Load environment variables and assign them to Config class
    Make sure to add the required environment variables to .env file
    """


    SQLALCHEMY_DATABASE_URI = "sqlite:///data/db.sqlite3" # os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = bool(False)
    AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
    AWS_ACCESS_SECRET = os.environ.get("AWS_ACCESS_SECRET")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    S3_BUCKET_BASE_PATH = os.environ.get("S3_BUCKET_BASE_PATH")
    S3_BUCKET_BASE_URL = os.environ.get("S3_BUCKET_BASE_URL")



class ExifTool(object):
    sentinel = "{ready}\n"
    def __init__(self):
        self.executable         = "exiftool"
        self.metadata_lookup    = {}

    def  __exit__(self, exc_type, exc_value, traceback):
        self.process.stdin.write("-stay_open\nFalse\n")
        self.process.stdin.flush()

    def execute(self, *args):
        self.process = subprocess.Popen([self.executable, "-stay_open", "True",  "-@", "-"],
            universal_newlines  = True                          ,
            stdin               = subprocess.PIPE               ,
            stdout              = subprocess.PIPE               ,
            stderr              = subprocess.STDOUT
        )

        args = (args + ("-execute\n",))

        self.process.stdin.write(str.join("\n", args))
        self.process.stdin.flush()

        output  = ""
        fd      = self.process.stdout.fileno()

        while not output.endswith(self.sentinel):
            output += os.read(fd, 4096).decode('utf-8')

        return output[:-len(self.sentinel)]

    def get_metadata(self, *FileLoc):
        return json.loads(self.execute("-G", "-j", "-n", *FileLoc))

    def load_metadata_lookup(self, locDir):
        self.metadata_lookup = {}
        fset=[]
        for dirname, dirnames, filenames in os.walk(locDir):
            for filename in filenames:
                FileLoc=(dirname + '/' + filename)
                print(  '\n FILENAME    > ', filename,
                        '\n DIRNAMES    > ', dirnames,
                        '\n DIRNAME     > ', dirname,
                        '\n FILELOC     > ', FileLoc, '\n')

                fset.append(self.get_metadata(FileLoc)[0])


        return fset


class ReadRss:
 
    def __init__(self, rss_url, headers):
 
        self.url = rss_url
        self.headers = headers
        try:
            self.r = requests.get(rss_url, headers=self.headers)
            self.status_code = self.r.status_code
        except Exception as e:
            print('Error fetching the URL: ', rss_url)
            print(e)
        try:    
            self.soup = BeautifulSoup(self.r.text, 'xml')
            #mrss2.rss
            tree = ET.parse("data/absinthe-three.xml")
            root = tree.getroot()
            for child in root.findall("channel/item"):
              new_dec = ET.SubElement(child, 'media')
              item = BeautifulSoup(ET.tostring(child, encoding='utf8').decode('utf8'), 'xml')
              #print(type(item.findAll('content')))

              
              xtitle = item.findAll('title')[0].text
              #print(xtitle)
              pubDate=item.findAll('pubDate')[0].text
              url = ""
              ftype = ""
              title=""
              br = 0
              dur = 0
              for state in item.findAll('content'):
                
                              
                url = state.get('url')
                ftype = state.get('type')
                br = state.get('bitrate')
                dur=state.get('duration')
                print("'{}','{}','{}','{}','{}','{}'".format(str(xtitle),str(pubDate),url,ftype,br,dur))
                
        except Exception as e:
            print('Could not parse the xml: ', self.url)
            print(e)


        self.articles = self.soup.findAll('media')
        self.articles_dicts = [{'title':a.find('title').text,'link':a.link.next_sibling.replace('\n','').replace('\t',''),'description':a.find('description').text,'pubdate':a.find('pubdate').text} for a in self.articles]
        self.pub_dates = [d['pubdate'] for d in self.articles_dicts if 'pubdate' in d]
 
def get_source(publication="me"):
    return RSS_FEEDS[publication]
    
def get_news_test(publication="cnn"):
  try:      
    feed = feedparser.parse(RSS_FEEDS[publication])
    print(feed)
    articles_cnn = feed['channel']['entries']

    for article in articles_cnn:
        print(article)
  except:
    pass
    
def connect2ES():    
    try:
      es = Elasticsearch(['http://{}:{}@{}:{}'.format(os.environ.get('ELASTIC_USER'),os.environ.get('ELASTIC_PASS'),os.environ.get('ELASTIC_HOST'),os.environ.get('ELASTIC_PORT'))])
      print ("Connected", es.info())
    except Exception as ex:
      print( "Error:", ex)

    print("*********************************************************************************");
    return es


class ElasticSearchUtil:
    def __init__(self):
        self.host = os.environ.get('ELASTIC_HOST')
        self.es = Elasticsearch(['http://{}:{}@{}:{}'.format(os.environ.get('ELASTIC_USER'),os.environ.get('ELASTIC_PASS'),os.environ.get('ELASTIC_HOST'),os.environ.get('ELASTIC_PORT'))])
      

    def __del__(self):
        self.es.close()



    def add_to_index(self,appname = "app",index_name = "published",doc = {}):

         self.es.index(index="{}-{}".format(appname,index_name),
                     doc_type="_doc",
                     body = doc,
                     )
        
    
                      

    def create_index(self,appname = "app"):
      """Creates an set of indices in Elasticsearch if one isn't already there."""

      self.es.indices.create(
          index="{}-upload".format(appname),
          body={
              "settings": {"number_of_shards": 1,"number_of_replicas": 0},
              "mappings": {
                  "properties": {
                      "user": {"type": "keyword"},
                      "profile": {"type": "keyword"},
                      "content_type": {"type": "keyword"},
                      "content_length": {"type": "keyword"},
                      "title": {"type": "keyword"},
                      "url": {"type": "keyword"},
                      "upload_status": {"type": "keyword"},
                      "tags": {"type": "keyword"}
                  }
              },
          },
          ignore=400,
      );    

      self.es.indices.create(
          index="{}-published".format(appname),
          body={
              "settings": {"number_of_shards": 1,"number_of_replicas": 0},
              "mappings": {
                  "properties": {
                      "user": {"type": "keyword"},
                      "profile": {"type": "keyword"},
                      "content_type": {"type": "keyword"},
                      "title": {"type": "keyword"},
                      "url": {"type": "keyword"},
                      "tags": {"type": "keyword"}
                  }
              },
          },
          ignore=400,
      );


      self.es.indices.create(
          index="{}-user".format(appname),
          body={
              "settings": {"number_of_shards": 1,"number_of_replicas": 0},
              "mappings": {
                  "properties": {
                      "user": {"type": "keyword"},
                      "title": {"type": "keyword"},
                      "profile": {"type": "keyword"},
                      "config": {"type": "keyword"},
                      "tags": {"type": "keyword"}
                  }
              },
          },
          ignore=400,
      )

      
      self.es.indices.create(
          index="{}-default-data".format(appname),
          body={
              "settings": {"number_of_shards": 1,"number_of_replicas": 0},
              "mappings": {
                  "properties": {
                      "title": {"type": "keyword"},
                      "description": {"type": "keyword"},
                      "config": {"type": "keyword"},
                      "tags": {"type": "keyword"}
                  }
              },
          },
          ignore=400,
      )
      
      self.es.indices.create(
          index="{}-tools".format(appname),
          body={
              "settings": {"number_of_shards": 1,"number_of_replicas": 0},
              "mappings": {
                  "properties": {
                      "title": {"type": "keyword"},
                      "description": {"type": "keyword"},
                      "icon": {"type": "keyword"},
                      "url": {"type": "keyword"},
                      "tags": {"type": "keyword"}
                  }
              },
          },
          ignore=400,
      )
      self.es.indices.create(
          index="{}-feeds".format(appname),
          body={
              "settings": {"number_of_shards": 1,"number_of_replicas": 0},
              "mappings": {
                  "properties": {
                      "title": {"type": "keyword"},
                      "description": {"type": "keyword"},
                      "icon": {"type": "keyword"},
                      "url": {"type": "keyword"},
                      "tags": {"type": "keyword"},
                      "user": {"type": "keyword"},
                      "bakey": {"type": "keyword"}
                  }
              },
          },
          ignore=400,
      )

      for u in RAW_DATA:          
        self.es.indices.create(
            index="{}-{}".format(appname,u),
            body={
                "settings": {"number_of_shards": 1,"number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "title": {"type": "keyword"},
                        "tags": {"type": "keyword"}
                    }
                },
            },
            ignore=400,
        )

def insert_one_data(self,_index, data):
    # index and doc_type you can customize by yourself
    res = self.es.index(index=_index, doc_type='_doc',  body=data)
    # index will return insert info: like as created is True or False
    print(res)

def download_dataset(key):
    """Downloads the public dataset if not locally downlaoded
    and returns the number of rows are in the .csv file.
    """

    url = RAW_DATA[key]
    DATASET_PATH = join(dirname(abspath(__file__)),"data", "{}.csv".format(key))
    if 1 or not exists(DATASET_PATH):
        http = urllib3.PoolManager()
        resp = http.request("GET", url, preload_content=False)

        if resp.status != 200:
            raise RuntimeError("Could not download dataset")

        with open(DATASET_PATH, mode="wb") as f:
            chunk = resp.read(CHUNK_SIZE)
            while chunk:
                f.write(chunk)
                chunk = resp.read(CHUNK_SIZE)

    with open(DATASET_PATH) as f:
        return sum([1 for _ in f]) - 1

       

def generate_actions(key):
    """Reads the file through csv.DictReader() and for each row
    yields a single document. This function is passed into the bulk()
    helper to create many documents in sequence.
    """

    
    print("Creating default data..."+key)
    DATASET_PATH = join(dirname(abspath(__file__)),"data", "{}.csv".format(key))
    with open(DATASET_PATH, mode="r") as f:
      reader = csv.DictReader(f)

      for row in reader:
          print(row)
          doc = {
              "_id": hashlib.md5(','.join(row['title']).encode('utf-8')).hexdigest(),
              "_source": row
          }

          yield doc


def main():
    print("Creating an index...")
    ElasticSearchUtil().create_index(appname = "app")
    for u in RAW_DATA:            
      successes = 0        
      t = download_dataset(u)  
      print("[{}]".format(t))
      for ok, action in streaming_bulk(client=connect2ES(), index="app-{}".format(u), actions=generate_actions(u)):
        successes += ok
          

if __name__ == "__main__":
    main()
    get_news_test(publication="me") 
    feed = ReadRss(get_source(publication="me"), headers)
    print(str(feed))
        
#    curl  -F "user=default" -F "profile=default" -X POST -F file=@"data/movie.mp4" http://161.35.14.248:6969/add_file
#    curl  -F "user=default" -F "profile=default" -X POST -F file=@"data/movie.mp4" http://127.0.0.1:6969/add_file






"""

if __name__ == '__main__':

    #

http://localhost:6969/static/uploads/default/default/6f33144a-8b9a-47de-9df6-d47fe757ba71/stream.m3u8
"""
