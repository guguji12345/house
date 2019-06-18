# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html
import pymongo
from scrapy.exceptions import DropItem

class FangtianxiaPipeline(object):
    def process_item(self, item, spider):
        return item

class MongoPipeline(object):
    def __init__(self,mongo_uri,mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db

    @classmethod
    def from_crawler(cls,crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DB")
        )

    def open_spider(self,spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]

    def process_item(self,item,spider):
        name = item.__class__.__name__
        condition = {"url":item["url"]}
        result = self.db[name].find_one(condition)
        if result:
            del result["_id"]
            if result == item:
                raise DropItem("数据库中已有该组数据")
            else:
                self.db[name].update_one(result,{"$set":item})
                print("数据更新成功")
                return item
        else:
            print("数据插入成功")
            self.db[name].insert(dict(item))
            return item

    def close_spider(self,spider):
        self.client.close()