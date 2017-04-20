from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch import helpers

es = Elasticsearch()


# es.create(index="test-index", doc_type="test-type", id=1,
#   body={"any":"data", "timestamp": datetime.now()})


j = 0
count = 100
actions = []

while (j < count):
    action = {
        "_index": "tickets-index",
        "_type": "tickets",
        "_id": j + 1,
        "_source": {
            "crawaldate": j,
            "flight": j,
            "price": float(j),
            "discount": float(j),
            "date": j,
            "takeoff": j,
            "land": j,
            "source": j,
            "timestamp": datetime.now()}
    }

    actions.append(action)
    j += 1

if (len(actions) == 500000):
    helpers.bulk(es, actions)
    del actions[0:len(actions)]

if (len(actions) > 0):
    helpers.bulk(es, actions)
    del actions[0:len(actions)]