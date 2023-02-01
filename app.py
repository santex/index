#!/usr/bin/env python3
from flask import session, redirect, url_for, render_template, request

import ffmpeg_streaming2
from ffmpeg_streaming2 import Formats, Bitrate, Representation, Size, FFProbe

import os, base64, json, sqlite3, urllib3, argparse, requests, io, csv, pprint, re
import dateutil.parser

from flask import Flask, request, redirect, url_for, render_template, json, jsonify, send_from_directory

import os, sys, json, sqlalchemy, enum, json, glob
from uuid import uuid4
from http import HTTPStatus
from threading import Thread
from uuid import uuid1, uuid4
from sqlalchemy import Enum
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import shutil, pprint
from datetime import datetime
import ffmpeg,tqdm, argparse
from elasticsearch import Elasticsearch 





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




from util import *

  
app = Flask(__name__)
cf = Config()
print(cf)
app.config.from_object(cf)  # Set Flask app configuration from Config class
db = SQLAlchemy(app)
print(db);
class UploadStatus(enum.Enum):
    """
    Serves as enum values for upload_status column of files table
    (either PENDING, PROCESSING, COMPLETE OR ERROR)
    """

    PENDING = 1
    PROCESSING = 2
    COMPLETE = 3
    ERROR = 4


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(255), unique=False, nullable=False)
    profile = db.Column(db.String(255), unique=False, nullable=False)
    name = db.Column(db.String(255), unique=False, nullable=False)
    url = db.Column(db.String(255), unique=False, nullable=True)
    content_type= db.Column(db.String(255), unique=False, nullable=True)
    content_length= db.Column(db.String(255), unique=False, nullable=True)
    upload_status = db.Column(
        Enum(UploadStatus), nullable=False, default=UploadStatus.PENDING
    )

    def __repr__(self):
        return f"<File {self.name}>"



# Used if you want to play with databse through flask shell
@app.shell_context_processor
def make_shell_context():
    return {"db": db, "File": File}


@app.route("/")
def hello_world():
    return render_template('home.html', data=[])

@app.route("/f2")
def front2():
    data=ElasticSearchUtil().callData(1000)
    conf = {'ASSET_ROOT':os.environ.get('ASSET_ROOT')}
    return render_template('front2.html',ASSETS_ROOT=os.environ.get('ASSETS_ROOT'), data=data)

@app.route("/f")
def front():
    data=ElasticSearchUtil().callData(1000)
    conf = {'ASSET_ROOT':os.environ.get('ASSET_ROOT')}
    return render_template('front.html', data=data)


@app.route("/files/<uuid>", methods=['POST','PUT','GET'])
def upload_complete(uuid):
    """The location we send them to at the end of the upload."""


    print(uuid)
    # Get their files.
    root = "./static/uploads/{}".format(uuid)
   
    files = []
    for file in glob.glob("{}*".format(root)):
        fname = file.split(os.sep)[-1]

        result = {
          "name": file.name,
          "filename": rename_file(file.filename),
          "content_type": file.content_type,
          "content_length": file.content_length
        }
        print(result)
        files.append(result)


    data = [files,uuid]
    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )

    
    
    return response



def prepare_probe(path,doc):


  ffprobe= FFProbe(doc['name'])
  
  current_dir = path
  ffprobe.save_as_json(os.path.join(current_dir, 'probe.json'))


  
  
def prepare_hls(doc):

  

  video = ffmpeg_streaming2.input(doc['name'])

  hls = video.hls(Formats.h264())
  hls.auto_generate_representations()  
        
  _360p  = Representation(Size(640, 360), Bitrate(276 * 1024, 128 * 1024))
  _480p  = Representation(Size(854, 480), Bitrate(750 * 1024, 192 * 1024))
  _720p  = Representation(Size(1280, 720), Bitrate(2048 * 1024, 320 * 1024))
  _1080p = Representation(Size(1920, 1080), Bitrate(4096 * 1024, 320 * 1024))
  _2k    = Representation(Size(2560, 1440), Bitrate(6144 * 1024, 320 * 1024))
  _4k    = Representation(Size(3840, 2160), Bitrate(17408 * 1024, 320 * 1024))

  hls = video.hls(Formats.h264())
  hls.representations(_480p, _720p)
  hls.output("{}/{}/{}".format(doc['target'],'hls',doc['basename'].replace('.mp4','.m3u8')))

  
def upload(request,target):
    """Handle the upload of a file."""
    form = request.form
    base=request.base_url.split("/add_file")[0]
    user=form.get("user")
    profile=form.get("profile")
    # Create a unique "session ID" for this particular batch of uploads.
    
    # Is the upload using Ajax, or a direct POST by the form?
    is_ajax = False
    if form.get("__ajax", None) == "true":
        is_ajax = True


    try:
      os.makedirs( target);
    except:
        if is_ajax:
            return ajax_response(False, "Couldn't create upload directory: {}".format(target))
        else:
            return "Couldn't create upload directory: {}".format(target)

    print("=== Form Data ===")
    for key, value in list(form.items()):
        print(key, "=>", value)

    files = []
    send=[]
    
    for upload in request.files.getlist("file"):
        filename = upload.filename.rsplit("/")[0]
        destination = "/".join([target, rename_file(filename)])
        send.append(destination)
        print("Accept incoming file:", filename)
        print("renamed",rename_file(os.path.basename(destination)))
        print("Save it to:", destination)
        upload.save(destination)
        ctype=filename.split(".")[1]
        length=os.path.getsize(destination)

            
        basename = os.path.basename(destination)
        data={"user":user,
              "profile":profile,
              "target":target,
              "name":destination,
              "host":base,
              "basename":basename,
              "content_type":ctype,
              "content_length":length,
              "url":"{}/{}".format(base,destination[2:]),
              "hls":"",
              "tags":re.findall(r'\w+', basename),
              "upload_status":200}

        
        new_file = File(user=user,profile=profile,name=destination,content_type=ctype,content_length=length,url=destination,upload_status=UploadStatus.PROCESSING)
        
        files.append(data)
        try:
          db.session.add(new_file)
          db.session.commit()
        except:
          pass
        
              
        basen=str(data["basename"])
        if data["basename"].endswith(".mp4"):
          data["hls"]="{}/{}/hls/{}".format(data["host"],data["target"][2:],basen.replace(".mp4",".m3u8"))
          prepare_hls(data)
          prepare_probe(data["target"],data)

        if data["basename"].endswith(".mov"):
          data["hls"]="{}/{}/hls/{}".format(data["host"],data["target"][2:],basen.replace(".mov",".m3u8"))
          prepare_hls(data)
          prepare_probe(data["target"],data)

        if data["basename"].endswith(".AVI"):
          data["hls"]="{}/{}/hls/{}".format(data["host"],data["target"][2:],basen.replace(".AVI",".m3u8"))
          prepare_hls(data)
          prepare_probe(data["target"],data)
          
        ElasticSearchUtil().add_to_index("app","published",data)
        


                            
    """
    e = ExifTool()
    exifdata=e.load_metadata_lookup(destination)
    """
    response = app.response_class(
        response=json.dumps({'probe':send,'files':files}),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route("/add_file", methods=['POST','PUT'])
def add_filename():
  file = request.files['file']
  form = request.form

  user =form.get('user')
  profile = form.get('profile')
  filename=secure_filename(file.filename)

  upload_key =  uuid4()
  target = "./static/uploads/{}/{}/{}".format(user,profile,upload_key)
  data = upload(request, target)



  return data


def do_search(q, limit=200,index="_all", do_highlight=False, do_files=False):
    
    username = ''
    password = ''


    print("Search hit: " + q)
    if limit > 1000:
        # Sanity check
        limit = 1000

    search_request = {
       "query" : {
    "multi_match" : {
      "query":     q,
      "type":       "best_fields",
      "fields":     ["tags","title","description", "*"],
      "operator":   "and" 
    }
  }
    }

    if do_highlight:
        search_request['highlight'] = {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {
                "_all": {},
            },
        }


    host = os.environ.get('ELASTIC_HOST')
    requestHeaders = {'user-agent': 'my-python-app/0.0.1', 'content-type': 'application/json'}
    requestURL = 'http://%s:82/%s/_search?pretty&size=%s' % (host,index,limit)


    resp = requests.post(requestURL,
    json=search_request,
    auth=(os.environ.get('ELASTIC_USER'), os.environ.get('ELASTIC_PASS')),
    verify=False,
    headers=requestHeaders)



    if resp.status_code != 200:
        print("elasticsearch non-200 status code: " + str(resp.status_code))
        print(resp.content)
        abort(resp.status_code)

    content = resp.json()
    #'_index': 'papers',
    pprint.pprint(content)
    data = []
    res = {"data":{},"index":""}
  
    found = content['hits']['total']
   
    for h in content['hits']['hits']:
      res["data"]=h['_source']
      res["id"]=h['_id']
      res["index"]=h['_index']
      data.append(res)


    return {"query": {
                "q": q,
                "highlight": do_highlight},
            "count_returned": len(data),
            "count_found": found,
            "results": data }

def lookup_identifier(id_type, identifier, do_paper=True):

    paper = None
    if do_paper:
        resp = do_search('doi:"%s"' % identifier, limit=1, do_files=False)
        if resp['count_returned'] >= 1:
            paper = resp['results'][0]

    manifest_db = get_manifest_db()
    file_list = list(
        manifest_db.execute("SELECT doi, sha1, type FROM files_id_doi WHERE doi=?;",
                        [identifier.lower()]))
    file_list = [{"doi": f[0], "sha1": f[1], "work_type": f[2]} for f in file_list]

    for f in file_list:
        links = lookup_links_by_hash("sha1", f['sha1'])
        f['links'] = links
        meta = list(manifest_db.execute(
            "SELECT sha1, mimetype, size_bytes, md5 FROM files_metadata WHERE sha1=? LIMIT 1;",
            [f['sha1']]))[0]
        f['mimetype'] = meta[1]
        f['size_bytes'] = meta[2]
        f['md5'] = meta[3]
    return {"query": {"type": id_type, "identifier": identifier}, "paper": paper, "files": file_list,
            "count_files": len(file_list)}

def lookup_links_by_hash(hash_type, hash_value):
    if hash_type != "sha1":
        abort(400)

    manifest_db = get_manifest_db()
    url_list = list(
        manifest_db.execute("SELECT sha1, url FROM urls WHERE sha1=?;",
                       [hash_value.lower()]))
    url_list = [{"url": u[1], "domain": url_domain(u[1])} for u in url_list]
    return url_list

def lookup_ids_by_hash(hash_type, hash_value):
    if hash_type != "sha1":
        abort(400)

    manifest_db = get_manifest_db()
    file_list = list(
        manifest_db.execute("SELECT doi, sha1 FROM files_id_doi WHERE sha1=?;",
                        [hash_value.lower()]))
    if len(file_list) > 0:
        f = file_list[0]
        return {"doi": f[0], "sha1": f[1]}
    else:
        return None


### Search and API ##########################################################


# create a helper class for each tree node
class Node(object):
    # generate new node
    def __init__(self, cluster):
        self.cluster = cluster
        self.children = []

    # append a child node to parent (self)
    def child(self, child_cluster):
        # check if child already exists in parent
        child_found = [c for c in self.children if c.cluster == child_cluster]
        if not child_found:
            # if it is a new child, create new node for this child
            _child = Node(child_cluster)
            # append new child node to parent's children list
            self.children.append(_child)
        else:
            # if the same, save this child
            _child = child_found[0]
        # return child object for later add
        return _child

    # convert the whole object to dict
    def as_dict(self):
        res = {'cluster': self.cluster}
        res['children'] = [c.as_dict() for c in self.children]
        return res


@app.route('/tree')
def create_tree():
    root = Node('data')
    cluster_levels = 3

    with open('./Books.csv', 'r') as f:
        reader = csv.reader(f)
        # skip header row
        #reader.next()
        # scan data by row
        for row in reader:
            parent = root
            # cluster info: from column 1 to 3
            for level in range(1, (cluster_levels + 1)):
                parent = parent.child(row[level])
    # print(json.dumps(root.as_dict(), indent=4))
    return render_template('treemap.html', data = json.dumps(root.as_dict()))


@app.route('/treemap')
def treemap():
    return render_template("treemap.html", name="John")



@app.route('/data')
def tree_data():
    hierarchyList =request.args.get("hierarchy", "Dpto,Table Name").split(",")
    hierarchy = ",".join(['"%s"'%x for x in hierarchyList])
    print(hierarchy)

    conn = sqlite3.connect('main.db')
    cursor = conn.cursor()


    query = "select %s, count(*) from fuerza group by %s;"%(hierarchy,hierarchy)
    print(query)

    csvList = list(cursor.execute(query))

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerows([tuple(hierarchyList + ["count"])] + csvList)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'ok': True})

@app.route('/search', methods=['GET', 'POST'])
def search():

    do_highlight = is_truthy(request.args.get('highlight'))
    try:
        limit = int(request.args.get('limit'))
        # limit must be between 0 and 100
        limit = min(max(0, limit), 100)
    except:
        limit = 1000

    query = request.args.get('q')
    index = request.args.get('index')

    if index is None:
      index = "_all"
      
    # Convert "author:" query to "authors:"
    if query is not None:
        query = query.replace("author:", "authors:")

    # For a JSON/API request, must have a query string
    if request_wants_json():
        if 'q' not in request.args.keys():
            abort(400, "Need query parameter (q)")
        return jsonify(
            do_search(
                query,
                limit,
                index,
                do_highlight,
                is_truthy(request.args.get('files'))))

    # For HTML request, it's optional
    if 'q' in request.args.keys():
        # always do files for HTML
        found = do_search(
            query,
            limit,
            index,
            do_highlight,
            do_files=True)

        if found is None:
          found = {"query": {
                    "q": q,
                    "index":index,
                    "highlight": do_highlight},
                "count_returned": len(results),
                "count_found": found,
                "results": results }
          
        return render_template('search.html', found=found)
    else:
        return render_template('search.html')

@app.route('/id/<id_type>/<path:identifier>', methods=['GET'])
def identifier(id_type, identifier):
    if id_type != "doi":
        abort(400)
    info = lookup_identifier(id_type, identifier)
    if info is None:
        abort(404)
    if request_wants_json():
        return jsonify(info)
    return render_template('paper.html',
        paper=info['paper'], files=info['files'], lookup=info['query'],
        best_pdf_url=best_pdf_url(info['files']),
        best_html_url=best_html_url(info['files']),
        archive_item_url=archive_item_url(info['files']))

@app.route('/redirect/<id_type>/<path:identifier>', methods=['GET'])
def id_redirect(id_type, identifier):
    if id_type != "doi":
        abort(400)
    info = lookup_identifier(id_type, identifier)
    if len(info['files'] > 0):
        return redirect(info['files'][0]['url'])
    else:
        abort(404)

@app.route('/file/<hash_type>/<hash_val>', methods=['GET'])
def get_file(hash_type, hash_val):
    if hash_type != "sha1" or len(hash_val) != 40:
        abort(400)
    try:
        base64.b16decode(hash_val.upper())
    except:
        abort(400)
    hash_val = hash_val.lower()

    file_info = {
        'hashes': [ {'type': 'sha1', 'value': hash_val } ],
        'urls': lookup_links_by_hash("sha1", hash_val),
    }
    if is_truthy(request.args.get('redirect')):
        if len(file_info) > 0 and file_info[0].get('url'):
            return redirect(file_info[0]['url'])
        else:
            abort(404)
    identifiers = lookup_ids_by_hash("sha1", hash_val)
    if identifiers:
        identifiers = [{'type': 'doi', 'id': identifiers['doi']}]
    file_info['identifiers'] = identifiers
    return jsonify(file_info)


### Helpers #################################################################
from requests.auth import HTTPBasicAuth 
TRUTHY = ('true', 'yes', 'y', '1')

def is_truthy(raw):
    if raw is None:
        return False
    elif type(raw) is bool:
        return raw
    elif type(raw) is int:
        return bool(raw)
    else:
        return bool(raw.lower() in TRUTHY)

def request_wants_json():
    best = request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        request.accept_mimetypes[best] > \
        request.accept_mimetypes['text/html']

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    date = dateutil.parser.parse(date)
    native = date.replace(tzinfo=None)
    format='%b %d, %Y'
    return native.strftime(format) 


def url_domain(url):
    """Extracts the domain from a URL, with some heuristics"""
    domain = urllib3.get_host(url)[1]
    if domain.endswith("us.archive.org"):
        domain = "archive.org"
    return domain

def best_pdf_url(file_list):
    """From a file list, choses a default PDF URL to use, or None"""
    for f in file_list:
        mt = f['mimetype']
        if mt is None or 'pdf' in mt or 'postscript' in mt:
            for link in f.get('links'):
                # TODO: defaulting to 'None' as PDF for now
                return link['url']

def best_html_url(file_list):
    """From a file list, choses a default HTML URL to use, or None"""
    for f in file_list:
        mt = f['mimetype']
        if mt and 'html' in f['mimetype']:
            for link in f.get('links'):
                return link['url']

def archive_item_url(file_list):
    """From a file list, returns an archive.org item if there is one, or None"""
    for f in file_list:
        for link in f.get('links'):
            if 'archive.org/download' in link['url'] and link['url'].count('/') == 5:
                # Don't return deeplinks into individual files, files that are
                # items, and drop the filename for browsing
                components = link['url'].split("/")
                item = components[4]
                return "https://archive.org/details/" + item

### Backends ################################################################

def do_search(q, limit=200,index="_all", do_highlight=False, do_files=False):
    
    username = os.environ.get('ELASTIC_USER')
    password = os.environ.get('ELASTIC_PASS')


    print("Search hit: " + q)
    if limit > 1000:
        # Sanity check
        limit = 1000

    search_request = {
       "query" : {
    "multi_match" : {
      "query":     q,
      "type":       "best_fields",
      "fields":     ["tags","title","description", "*"],
      "operator":   "and" 
    }
  }
    }

    if do_highlight:
        search_request['highlight'] = {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {
                "_all": {},
            },
        }


    host = os.environ.get('ELASTIC_HOST')
    port = os.environ.get('ELASTIC_PORT')
    requestHeaders = {'user-agent': 'my-python-app/0.0.1', 'content-type': 'application/json'}
    requestURL = 'http://%s:%s/%s/_search?pretty&size=%s' % (host,port,index,limit)


    resp = requests.post(requestURL,
    json=search_request,
    auth=(os.environ.get('ELASTIC_USER'), os.environ.get('ELASTIC_PASS')),
    verify=False,
    headers=requestHeaders)



    if resp.status_code != 200:
        print("elasticsearch non-200 status code: " + str(resp.status_code))
        print(resp.content)
        abort(resp.status_code)

    content = resp.json()
    #'_index': 'papers',
    pprint.pprint(content)
    data = []
    res = {"data":{},"index":""}
  
    found = content['hits']['total']
   
    for h in content['hits']['hits']:
      res["data"]=h['_source']
      res["id"]=h['_id']
      res["index"]=h['_index']
      data.append(res)


    return {"query": {
                "q": q,
                "highlight": do_highlight},
            "count_returned": len(data),
            "count_found": found,
            "results": data }

def lookup_identifier(id_type, identifier, do_paper=True):

    paper = None
    if do_paper:
        resp = do_search('doi:"%s"' % identifier, limit=1, do_files=False)
        if resp['count_returned'] >= 1:
            paper = resp['results'][0]

    manifest_db = get_manifest_db()
    file_list = list(
        manifest_db.execute("SELECT doi, sha1, type FROM files_id_doi WHERE doi=?;",
                        [identifier.lower()]))
    file_list = [{"doi": f[0], "sha1": f[1], "work_type": f[2]} for f in file_list]

    for f in file_list:
        links = lookup_links_by_hash("sha1", f['sha1'])
        f['links'] = links
        meta = list(manifest_db.execute(
            "SELECT sha1, mimetype, size_bytes, md5 FROM files_metadata WHERE sha1=? LIMIT 1;",
            [f['sha1']]))[0]
        f['mimetype'] = meta[1]
        f['size_bytes'] = meta[2]
        f['md5'] = meta[3]
    return {"query": {"type": id_type, "identifier": identifier}, "paper": paper, "files": file_list,
            "count_files": len(file_list)}

def lookup_links_by_hash(hash_type, hash_value):
    if hash_type != "sha1":
        abort(400)

    manifest_db = get_manifest_db()
    url_list = list(
        manifest_db.execute("SELECT sha1, url FROM urls WHERE sha1=?;",
                       [hash_value.lower()]))
    url_list = [{"url": u[1], "domain": url_domain(u[1])} for u in url_list]
    return url_list

def lookup_ids_by_hash(hash_type, hash_value):
    if hash_type != "sha1":
        abort(400)

    manifest_db = get_manifest_db()
    file_list = list(
        manifest_db.execute("SELECT doi, sha1 FROM files_id_doi WHERE sha1=?;",
                        [hash_value.lower()]))
    if len(file_list) > 0:
        f = file_list[0]
        return {"doi": f[0], "sha1": f[1]}
    else:
        return None


### Static Routes ###########################################################

@app.route('/', methods=['GET'])
def homepage():
    return render_template('home.html')

@app.route('/about/', methods=['GET'])
def aboutpage():
    return render_template('about.html')

@app.route('/api/', methods=['GET'])
def apipage():
    return render_template('api.html')

@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')

@app.route('/robots.txt', methods=['GET'])
def robots():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'robots.txt',
                               mimetype='text/plain')


### Entry Point #############################################################

if __name__=="__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug',
        action='store_true',
        help="enable debugging interface")
    parser.add_argument('--host',
        default="127.0.0.1",
        help="listen on this host/IP")
    parser.add_argument('--elasticsearch',
        default="61.35.14.248:82",
        help="elasticsearch backend to connect to")
    parser.add_argument('--search-index',
        default="_all",
        help="elasticsearch index to query")
    parser.add_argument('--manifest-db',
        default="dynamic.db",
        help="sqlite database of file/identifier cross-references")
    parser.add_argument('--port',
        type=int,
        default=5050,
        help="listen on this port")
    args = parser.parse_args()
  
    ElasticSearchUtil().create_index()
    app.run(host="0.0.0.0",port=6969, debug=True)


"""
CREATE TABLE file(
   user          CHAR(50),
   profile       CHAR(50),
   content_type   CHAR(50),
   content_length   INT,
   name         CHAR(50),
   url           CHAR(50),
   upload_status   CHAR(50)
);


curl  -F "user=default" -F "profile=default" -X POST -F file=@"output.mp4" http://161.35.14.248:6969/add_file
curl  -F "user=default" -F "profile=default" -X POST -F file=@"data/movie3.mp4" http://161.35.14.248:6969/add_file

xout-AlienContactAboveandBelow-i66ihNWFiMg_merged
"""
