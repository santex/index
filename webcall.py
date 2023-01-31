import json, requests, urllib3, argparse, os
urllib3.disable_warnings()

def populateJson(nameSearchTerm="", limit=100, operator="or"):
    return {
  "size": limit,
  "query": {
    "multi_match": {
      "query": nameSearchTerm,
      "fields": [
        "domain",
        "topic",
        "tags",
        "title",
        "type",
        "source",
        "tags"
      ],
      "operator":operator,
      "type": "best_fields"
    }
  },
  "aggs": {
    "Domain Filter": {
      "terms": {
        "field": "domain.keyword",
        "size": 10
      }
    },
    "Topic Filter": {
      "terms": {
        "field": "topic.keyword",
        "size": 10
      }
    },
    "Tags Filter": {
      "terms": {
        "field": "tags.keyword",
        "size": 3
      }
    },
    "Title Filter": {
      "terms": {
        "field": "title.keyword",
        "size": 10
      }
    },
    "Type Filter": {
      "terms": {
        "field": "type.keyword",
        "size": 10
      }
    },
    "Source Filter": {
      "terms": {
        "field": "source.keyword",
        "size": 10
      }
    }
  }
}

def main():
  parser = argparse.ArgumentParser()
  
  parser.add_argument('--index',
      default="papers-small",
      help="elasticsearch index to query")
  parser.add_argument('--operator',
      default="or",
      help="elasticsearch index to query")
  parser.add_argument('--search',
      default="desert+water",
      help="elasticsearch index to query")
  parser.add_argument('--limit',
      default="1000",
      help="response size")

  esport = os.environ.get('ELASTIC_PORT')
  eshost = os.environ.get('ELASTIC_HOST')
  args = parser.parse_args()
  requestHeaders = {'user-agent': 'my-python-app/0.0.1', 'content-type': 'application/json'}
  requestURL = 'http://%s:%s/%s/_search' % (eshost,esport,args.index)

  requestBody = populateJson(args.search, args.limit, args.operator)
  r = requests.get(requestURL,
               json=requestBody,
               auth=(os.environ.get('ELASTIC_USER'), os.environ.get('ELASTIC_PASS')),
               verify=False,
               headers=requestHeaders)
  r = r.json()
  print(json.dumps(r , sort_keys = True, indent = 2, ensure_ascii = False))


if __name__ == '__main__':


        
    main()

