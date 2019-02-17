#!/usr/bin/env python
# -*- encoding: utf-8

import copy
import datetime as dt

import attr
import elasticsearch


@attr.s
class SearchResponse:
    query = attr.ib()
    documents = attr.ib()
    tags = attr.ib()
    total = attr.ib()


class DocumentIndex:

    def __init__(self):
        self.index_name = "documents" + dt.datetime.now().isoformat().lower()
        self.es = elasticsearch.Elasticsearch()
        self.page_size = 48

        self.es.indices.create(
            index=self.index_name,
            body={
                "mappings": {
                    self.index_name: {
                        "properties": {
                            "indexed_at": {"type": "date"},
                            "tags": {"type": "keyword"},
                            "name": {"type": "keyword"},
                        }
                    }
                }
            }
        )

    def index_document(self, doc):
        enriched_doc = copy.deepcopy(doc)
        enriched_doc["name"] = doc.get("title", doc["filename"])

        self.es.index(
            index=self.index_name,
            doc_type=self.index_name,
            id=doc["id"],
            body=enriched_doc
        )

    def search_documents(self, tags, include_tag_aggs, sort_order, page):
        field, order = sort_order.split(":")
        body = {
            "sort": [
                {field: {"order": order}}
            ],
            "from": (page - 1) * self.page_size,
            "size": self.page_size,
        }

        if include_tag_aggs:
            body["aggregations"] = {
                "tags": {
                    "terms": {
                        "field": "tags",
                        "size": 1000
                    },
                }
            }

        if tags:
            es_filter = {
                "bool": {
                    "must": [
                        {"term": {"tags": t}} for t in tags
                    ]
                }
            }
            body["query"] = {
                "bool": {"filter": es_filter}
            }

        resp = self.es.search(
            index=self.index_name,
            doc_type=self.index_name,
            body=body
        )

        return SearchResponse(
            query=tags,
            documents=[h["_source"] for h in resp["hits"]["hits"]],
            tags={
                bucket["key"]: bucket["doc_count"]
                for bucket in resp["aggregations"]["tags"]["buckets"]
            },
            total=resp["hits"]["total"]
        )
