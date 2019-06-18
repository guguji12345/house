# -*- coding: utf-8 -*-
import scrapy
from scrapy import Request
import re
from fangtianxia.items import FangtianxiaItem
from lxml import etree
from scrapy_redis.spiders import RedisSpider

class HouseSpiderSpider(RedisSpider):
    name = 'house_spider'
    allowed_domains = ['fang.com']
    # start_urls = ['https://www.fang.com/SoufunFamily.htm']
    redis_key="fang:start_urls"

    def parse(self, response):
        trs = response.xpath("//div[@class='outCont']//tr")
        province = None
        for tr in trs:
            tds = tr.xpath(".//td[not(@class)]")
            province_td = tds[0]
            province_text = province_td.xpath(".//text()").extract_first()
            province_text = re.sub(r'\s','',province_text)
            if province_text:
                province = province_text
            #排除海外城市
            if province=="其它":
                continue
            citys_td = tds[1]
            citys = citys_td.xpath(".//a")
            for city in citys:
                info = {}
                city_name = city.xpath(".//text()").extract_first()
                city_url = city.xpath(".//@href").extract_first()
                info["city"]=city_name
                info["province"]=province
                city_ab_name = re.findall(r'.*?//(.*?)\.fang\.co.*?',city_url)[0]
                if city_ab_name == "bj":
                    new_house_url = "https://newhouse.fang.com/house/s/"#bj
                else:
                    new_house_url = 'https://{}.newhouse.fang.com/house/s/'.format(city_ab_name)#other place
                yield Request(url=new_house_url,callback=self.parse_page,meta={"info":info},dont_filter=True)

    def parse_page(self,response):
        info = response.meta["info"]
        url = response.url
        next_max_url = response.xpath("//li[@class='fr']/a[last()]/@href").extract_first()
        if next_max_url:
            next_max_num = re.findall(r'[0-9]+',next_max_url)[0][1:]
            for i in range(1, int(next_max_num)+1):
                next_page_url = url + "b9" + str(i) + str("/")
                yield Request(url=next_page_url, callback=self.parse_newhouse, meta={"info": info}, dont_filter=True)

    def parse_newhouse(self,response):
        info = response.meta["info"]
        houses_id = re.findall(r"{.*?'vwn.showhouseid':'(.*?)'}",response.text)[0]
        houses_id = houses_id.split(",")
        lis = response.xpath("//div[@class='nl_con clearfix']/ul/li")
        urls = []
        for li in lis:
            house_url = li.xpath(".//div[@class='nlcd_name']/a/@href").extract_first()
            if house_url==None:
                continue
            house_url = house_url.replace("?from=xflist_xfgg","")
            house_url = "https:"+house_url
            urls.append(house_url)
        all_url = list(zip(urls,houses_id))
        for each_url in all_url:
            exce = re.findall(r"house/[\d]+",each_url[0])#例外url中带有house_id
            if exce == []:
                detail_url = each_url[0]+"house/"+each_url[1]+"/housedetail.htm"
            else:
                detail_url = each_url[0].replace(".htm","/housedetail.htm")
            yield Request(url=detail_url,callback=self.parse_detail,meta={"info":info},dont_filter=True)

    def parse_detail(self,response):
        info = response.meta["info"]
        city = info["city"]
        province = info["province"]
        item = FangtianxiaItem()
        item["url"]=response.url
        item["city"]=city
        item["province"]=province
        name = response.xpath("//div[@class='lpbt']/h1/a/text()").extract_first()
        if name==None:
            name = response.xpath("//div[@class='lpbt tf jq_nav']/h1/a/text()").extract_first()
        item["name"]=name
        price = response.xpath("//div[@class='main-info-price']/em/text()").extract_first()
        price = price.replace("\n","").replace("\t","").strip()
        item["price"]=price
        score = response.xpath("//div[@class='main-info-comment']/a/span[2]/text()").extract_first()
        if score==None:
            score = '没有评分'
        item["score"]=score
        params = response.xpath("//div[@class='main-left']//ul[@class='list clearfix']/li").extract()[1]#存储于第二个li下
        params = params.replace('<div class="list-right"></div>', '<div class="list-right">暂无资料</div>')#无
        params = re.sub(r'<div class="list-right"><a.*?>\[.*?\]', '<div class="list-right">暂无资料<a>', params, re.DOTALL)#无发布时间
        params = re.sub(r'<div class="list-right-text w730">暂无资料</div>', '<div class="list-right-text w730"></div>',
                        params, re.DOTALL)#无预售证
        params = re.sub(r'<p style="width: 130px;float: left;">', '', params, re.DOTALL)#多个年限
        params = re.sub(r'</p>', '', params, re.DOTALL)
        params = re.sub(r'<div class="list-right-floor"></div>', '<div class="list-right-floor">暂无资料</div>', params,
                        re.DOTALL)#无楼层说明
        params = re.sub(r'<br />', "", params, re.DOTALL)#多个电梯参数
        params = re.sub(r'<a\shref=".*?\.htm">', "", params, re.DOTALL)#额外户型
        params = re.sub(r'<a\shref=".*?"_blank">', "", params, re.DOTALL)#多个物业公司
        html = etree.HTML(params)
        types = html.xpath("//li/div[@class='list-left']/text()")
        param = html.xpath("//li/div[contains(@class,'list-right')]//text()")
        chara = html.xpath("//span[@class='tag']//text()")#项目特色
        flag = len(types)
        while flag:#移除两个列表中相同的元素
            for i in types:
                if i in param:
                    param.remove(i)
            flag -= 1
        param = [i + "@" for i in param]
        all_param = "".join(param).replace("\n", "").replace("\t", "").replace("\r", "").replace(" ", "").replace(
            "\xa0", "").strip()
        all_param = re.sub(r'\[.*?\]', "", all_param, re.DOTALL)
        all_param = all_param.split("@")
        all_param = list(filter(None, all_param))#除去空白字符
        [all_param.pop(0) for i in range(len(chara))]
        chara = "/".join(chara)#以"/"连接多个项目特色
        all_param.insert(0, chara)#无特色时会插入空白字符,需要进一步除去
        all_param = list(filter(None, all_param))#除去空白字符
        h_t = 0#统计户型数
        nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        for num, info in enumerate(all_param):
            if all_param[num][0]in nums and len(all_param[num])<=7 and "居" in all_param[num] and "居" in all_param[num + 1]:#只需要户型中的居室
                h_t += 1
        for num, info in enumerate(all_param):
            if all_param[num][0]in nums and len(all_param[num])<=7 and "居" in all_param[num] and "居" in all_param[num + 1]:
                for i in range(1, h_t + 1):
                    all_param[num] += all_param[num + 1]
                    del all_param[num + 1]
        types = "".join(types).replace("\n","").replace("\r","").replace("\t","").replace(" ","").split("：")
        types = list(filter(None, types))#除去列表空白字符
        all_params = list(zip(types,all_param))
        paramss = []
        for each_params in all_params:
            types,all_param=each_params
            each_param={
                types:all_param
            }
            paramss.append(each_param)
        item["infomation"]=paramss
        yield item



