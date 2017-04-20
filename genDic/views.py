# coding:utf-8
from django.http import HttpResponse
from django.shortcuts import render
import redis
import json
import jieba.analyse
import datetime
import time
from functools import wraps
from multiprocessing import Pool
from elasticsearch import Elasticsearch
from elasticsearch import helpers
import psutil
import shutil
import re
from multiprocessing import cpu_count
from django.core.cache import cache
from pymongo import *
import jieba.analyse
import jieba.posseg as pseg
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# import jieba.posseg as pseg
# from optparse import OptionParser

fc = 'first_classify'
rdsHost = 'local.redis'
rdsPort = 60000
secKeyList = 'sec_key_list'

# 批量处理分词数据
bulk = 100
lst = []
user_dic = 'user_dic'
timeout = 60*60*24

devRdsIp = '10.105.250.202'
devRdsPort = 6379
devRdsPwd = 'F8=qvOt]1[FDy]hL'
SALE_INFO_LIST = 'wx_sale_info_list'
SALE_INFO_PRE = 'wx_sale_info_data_'
productRdsIp = '10.105.220.165'
productRdsPort = 6386
productRdsPwd = 'TqWhCdNx0Zg1t#ya'
productRdsTmPort = 6384


PDT_SALE_INFO_LIST = 'wx_sale_parse_list'
PDT_SALE_INFO_PRE = 'wx_sale_parse_data_'

global DLYCNT
DLYCNT = 0


def fn_timer(function):
    @wraps(function)
    def function_timer(*args, **kwargs):
        t0 = time.time()
        result = function(*args, **kwargs)
        t1 = time.time()
        print ("Total time running %s: %s seconds" %
               (function.func_name, str(t1 - t0))
               )
        return result

    return function_timer


def jiebathread(detail):
    # print detail
    seg_list = jieba.analyse.extract_tags(detail, allowPOS=('n', 'nd', 'nr', 'ns', 'nt', 'nz', 'ng', 'nl','i'))
    return seg_list

def jiebaKeywordSep(detail):
    words = pseg.cut(detail)
    wl = []
    for w in words:
        if w.flag[0] == 'n' and 0 == wl.count(w.word):
            wl.append(w.word)
    return wl


def getDiskDic():
    wlist = []

    with open(user_dic, 'r') as file:
        for line in file:
            end = line.find(' ')
            word = line[:end]
            wlist.append(word)

    return wlist


def cacheDic(wlist):
    wlistr = json.dumps(wlist)
    cache.set(user_dic, wlistr, timeout)


def getDicFile():
    w = cache.get(user_dic)
    if w :
        return json.loads(w)


    wlist = getDiskDic()
    # wlistJcode = json.dumps(wlist)
    cacheDic(wlist)

    return wlist


def isInArray(dicWords,word):
    for tem in dicWords:
        if tem == word:
            return True

    return False


def getKeyWords(words):
    dicWords = getDicFile()
    res = set()
    for word in words:
        if isInArray(dicWords,word):
            res.add(word)
    res = list(res)
    return res


def multi_set_sale_info(rds, p, words_list):
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    p.multi()

    for item in words_list:
        key = item[0]
        words = item[1]


        res =p.hset(key,'keywords',words)
        res = p.hset(key,'create_time',now)
        res = p.hset(key,'max_keywords',item[2])

    p.execute()

    return
    # for item in wordsList:
    #     key = item[0]
    #     keywords = rds.hget(key,'keywords')
    #     klist.append(keywords)



def bulkSetSaleinfoHash(rds,p,hnamelist):
    wordsList = []
    global DLYCNT

    for hname in hnamelist:
        key = PDT_SALE_INFO_PRE + hname
        detail = rds.hget(key,'content')

        if detail is None :

                time.sleep(1)
                detail = rds.hget(key, 'content')




        if detail:
            detail = rds.hget(key, 'content')
            maxKeywords = jiebathread(detail)
            str_max_words = ','.join(maxKeywords)
            words = getKeyWords(maxKeywords)
            str_words= ','.join(words)
            wordsList.append([key,str_words,str_max_words])
    if wordsList:
        multi_set_sale_info(rds,p,wordsList)
    else:

        return [False,key]


    return [True,1]


def bulkSaveMongoSaleinfo(rds,collection,hnamelist):
    mylist = []
    for hname in hnamelist:

        key = PDT_SALE_INFO_PRE + hname
        detail = rds.hget(key,'content')
        if detail is not None:
            first_cate = rds.hget(key,'category')
            sec_cate = rds.hget(key,'secCategory')
            keyword  = rds.hget(key,'keywords')
            now = rds.hget(key,'create_time')
            maxwords = rds.hget(key,'max_keywords')

            mydict = {"uri":hname,'fir_cate':first_cate,'sec_cate':sec_cate,'detail':detail,'keyword':keyword,'max_keywords':maxwords,'create_time':now}
            mylist.append(mydict)
    if mylist:
        collection.insert_many(mylist)



# @fn_timer
def bulk_es_index(actions,es):
    helpers.bulk(es, actions)


def bulkSaveEsSaleinfo(rds,es_client,hnamelist):
    actions = []
    for hname in hnamelist:

        key = PDT_SALE_INFO_PRE + hname
        content = rds.hget(key,'content')
        if content is not None:
            first_cate = rds.hget(key,'category')
            sec_cate = rds.hget(key,'secCategory')
            keywords  = rds.hget(key,'keywords')
            now = rds.hget(key,'create_time')
            maxwords = rds.hget(key,'max_keywords')

            action = {
                # "_op_type": "update",
                "_index": "npl_sale_alias",
                "_type": "keyword_search",
                "_id": hname,
                "_source": {
                    "uri": hname,
                    "first_cate": first_cate,
                    "sec_cate": sec_cate,
                    "content": content,
                    "keywords": keywords,
                    "max_keywords":maxwords,
                    "create_time":now
                }
            }
            actions.append(action)
    from elasticsearch import helpers
    if actions:
        helpers.bulk(es_client, actions)





def redisListBulkGet(rds,es_client,p):
    while 1:

        num = rds.llen(SALE_INFO_LIST)
        if num:
            st_index = 0
            end_index = bulk-1

            mgclient = MongoClient(host='127.0.0.1')
            db_auth = mgclient.npl
            db_auth.authenticate("npl", "npl")
            db = mgclient.npl
            collection = db.npl_sale_info
            while st_index < num:
                hnamelist = rds.lrange(SALE_INFO_LIST,st_index,end_index)

                bulkSetSaleinfoHash(rds,p,hnamelist)
                bulkSaveMongoSaleinfo(rds,collection,hnamelist)
                bulkSaveEsSaleinfo(rds,es_client,hnamelist)
                st_index = end_index +1
                end_index += bulk

            mgclient.close()
            break
        time.sleep(3)
#根据redis list中的uri获取hashtable name,找到对应的hashtable and set keywords to it
def setKeywordsRds(request):
    jieba.load_userdict("user_dic")
    import time
    # rds = redis.Redis(host=devRdsIp, port=devRdsPort, db=0,password=devRdsPwd)

    rds = redis.Redis(host=productRdsIp, port=productRdsPort, db=0,password=productRdsPwd)
    rdsTmp = redis.Redis(productRdsIp,productRdsTmPort,db=0,password=productRdsPwd)
    p = rdsTmp.pipeline(False)
    es_client = Elasticsearch()
    mgclient = MongoClient(host='127.0.0.1')
    db_auth = mgclient.npl
    db_auth.authenticate("npl", "npl")
    db = mgclient.npl
    collection = db.npl_sale_info


    while 1:

        data = rds.blpop(PDT_SALE_INFO_LIST)
        datalist = [data[1]]

        status,key = bulkSetSaleinfoHash(rdsTmp, p, datalist)
        if status == False:
            print 'Keywords is empty:'+key
            continue


        bulkSaveMongoSaleinfo(rdsTmp, collection, datalist)
        bulkSaveEsSaleinfo(rdsTmp, es_client, datalist)





    return HttpResponse(key)


def getkwForUri(request):
    res = {}

    if request.POST.has_key(u'uri') :
        _id = request.POST[u'uri']
        if _id =='':
            return HttpResponse("please post uri content")

    else:
        return HttpResponse("please post uri content")
    # _id = "['1702081746t7og42','1702101518gz9ouy','17021015183rbx3e']"
    ids = eval(_id)

    mgclient = MongoClient(host='127.0.0.1')
    db_auth = mgclient.npl
    db_auth.authenticate("npl", "npl")
    db = mgclient.npl
    collection = db.npl_sale_info

    dsl = {"uri":{"$in":ids}}

    origin = collection.find(dsl)
    if origin:
        for v in origin:

            uri= v[u'uri'].encode("UTF-8")
            keyword = v[u'keyword'].encode("UTF-8")
            res[uri] = keyword

    res = json.dumps(res)
    return HttpResponse(res)

#search es and get result

def getESrst(request):


    # if request.POST.has_key(u'words') and request.POST.has_key(u'sec_cate'):
    #
    #     keyword_cdn = request.POST[u'words'].strip()
    #     sec_cate_cdn = request.POST[u'sec_cate'].strip()
    #
    #     if keyword_cdn =='' or sec_cate_cdn == '':
    #         return HttpResponse("please post uri content")
    # else:
    #
    #     return HttpResponse("please post uri content")
    # if request.POST.has_key(u'or_words'):
    #     or_keyword_cdn = request.POST[u'or_words'].strip()
    # else:
    #     or_keyword_cdn = ''

    # return HttpResponse(request.POST)
    if request.POST.has_key(u'words') and request.POST.has_key(u'sec_cate'):

        words = request.POST[u'words'].strip()
        sec_cate_cdn = request.POST[u'sec_cate'].strip()

        if words =='' or sec_cate_cdn == '':
            return HttpResponse("please post words and sec_cate content")
    else:

        return HttpResponse("please post words and sec_cate  content")



    # 先获得时间数组格式的日期
    threeDayAgo = (datetime.datetime.now() - datetime.timedelta(days=4))

    # 转换为其他字符串格式:
    date_cdn = threeDayAgo.strftime("%Y-%m-%d %H:%M:%S")

    # if or_keyword_cdn == '':
    #     dsl_query = {
    #   "size": 10,
    #   "query": {
    #     "bool": {
    #       "must": [
    #         { "match": { "keywords":{"query":keyword_cdn ,"analyzer": "ik_smart","operator": "and"}          }},
    #                 { "match": { "sec_cate":   sec_cate_cdn        }},
    #         {"range" : {
    #             "create_time" : {
    #                 "gte" : date_cdn
    #
    #             }
    #         }}
    #       ]
    #
    #     }
    #   },
    # "sort": [{"create_time": "desc"}]
    # }
    # else:
    #     dsl_query = {
    #   "size": 10,
    #   "query": {
    #     "bool": {
    #       "must": [
    #         { "match": { "keywords":{"query":keyword_cdn ,"analyzer": "ik_smart","operator": "or"}          }},
    #                 { "match": { "sec_cate":   sec_cate_cdn        }},
    #         {"range" : {
    #             "create_time" : {
    #                 "gte" : date_cdn
    #
    #             }
    #         }},
    #
    #         {"bool": {"should": [
    #             {"match": {
    #                 "keywords": {"query": or_keyword_cdn, "operator": "or", "analyzer": "ik_smart", "boost": 3}
    #             }}
    #         ]}}
    #       ]
    #
    #     }
    #   },
    # "sort": [{"create_time": "desc"}]
    # }
    # words = ['玻璃种,冰糯种','观音,生肖,貔貅']

    dsl_query = {
        "size": 10,
        "query": {
            "bool": {
                "must": [

                    {"match": {"sec_cate": sec_cate_cdn}},
                    {"range": {
                        "create_time": {
                            "gte": date_cdn

                        }
                    }}
                ]

            }
        },
        "sort": [{"create_time": "desc"}]
    }
    # words = eval(words)
    words = json.loads(words)
    print words

    for v in words:
        cond = {"match": {"keywords": {"query": v, "analyzer": "ik_smart", "operator": "or"}}}
        dsl_query['query']['bool']['must'].append(cond)
    print dsl_query

    es_client = Elasticsearch()
    res = es_client.search(index="npl_sale_alias", body=dsl_query)
    print("Got %d Hits:" % res['hits']['total'])
    hits_list = []
    for hit in res['hits']['hits']:
        # print("%(keywords)s %(content)s: %(max_keywords)s" % hit["_source"])
        ve ={"uri":hit["_source"][u'uri'],"keywords":hit["_source"][u'keywords'],"maxkeywords":hit["_source"]["max_keywords"]}

        hits_list.append(ve)
    # for v in hits_list:
    #     print v[u'keywords']
    jn_res = json.dumps(hits_list)


    return HttpResponse(jn_res)


#Delete the index id
@fn_timer
def delESindexId(request):

    res = "OK"
    if request.POST.has_key(u'uri') :
        _id = request.POST[u'uri']
        if _id =='':
            return HttpResponse("please post uri content")

    else:
        return HttpResponse("please post uri content")

    ids = eval(_id)

    es_client = Elasticsearch()
    for _id in ids:
        try:
            rdt = es_client.delete("npl_sale_alias","keyword_search",_id)
            print "Deleted: "+_id
        except:
            print "Not found "+_id

    return HttpResponse(res)


#将商品描述信息用接巴分词找出关键字并将其输出到有序集合中
#test git


# @fn_timer
def jieba_multi_zincr(p,key,words):
    p.multi()

    for word in words:
        res =p.zincrby(key,word)
    p.execute()
    # print "redis insert%d times" % (len(words))
    return


    # print "es index %d" %(len(actions))


def to_utf8_list(cwords):
    words = []
    for word in cwords:
        word.decode('utf8')
        words.append(word)
    return words

#批量分词,并写入es

def jiebaSep(store_obj,offset,list_len,lots_key,es):
    # print detail
    # p1 = psutil.Process(os.getpid())
    # print ('直接打印内存占用： ' + (str)(psutil.virtual_memory()))
    # print ('直接打印内存占用： ' + (str)(p1.memory_info()))

    words = []
    actions = []

    # print("lots_key is %s" % (lots_key))
    while offset < list_len:
        detail = store_obj[offset]['detail']
        cwords = jiebathread(detail)
        cwords = to_utf8_list(cwords)
        words.extend(cwords)
        json_words = json.dumps(cwords)
        store_obj[offset]['words'] = json_words

        es_id =store_obj[offset]['uri'].decode('utf8')


        action = {
            # "_op_type": "update",
            "_index": "npld",
            "_type": lots_key,
            "_id": es_id,
            "_source": {
                "uri": es_id,
                "category_name": store_obj[offset]['category_name'].decode('utf8'),
                "secCategory_name": store_obj[offset]['secCategory_name'].decode('utf8'),
                "userinfoUri": store_obj[offset]['userinfoId'].decode('utf8'),
                "detail": store_obj[offset]['detail'].decode('utf8'),
                "words" : cwords

            }
        }
        actions.append(action)
        offset+=1

    bulk_es_index(actions,es)


    # print "jieSep end offset is %d"%(offset)
    return words




@fn_timer
def getHkeys(key):
    import time
    print "%s start" % key
    es = Elasticsearch()
    begin = datetime.datetime.now()
    begin = time.mktime(begin.timetuple())

    r = redis.Redis(host=rdsHost, port=rdsPort, db=0)

    hs = r.hgetall(key)
    # hs = r.hscan(key,count=10)
    if hs:
        lots_key = 'default_lots'

        for (k, v) in hs.items():
            dv = json.loads(v)
            sec_name = dv['secCategory_name']
            lots_key = 'npl' + key+sec_name
            break

        if r.exists(lots_key):
            r.delete(lots_key)

        r.sadd(secKeyList,lots_key)

        #批量处理分词

        store_obj = []
        icounter = 0
        counter = 0
        p = r.pipeline(False)
        tag = 0;

        for (k, v) in hs.items():

            dv = json.loads(v)

            store_obj.append(dv)
            icounter +=1
            counter +=1
            # print "counter11 is %d" % (counter)
            if ( icounter == bulk):
                offset = tag * bulk
                words = jiebaSep(store_obj,offset,counter,key,es)
                jieba_multi_zincr(p,lots_key,words)
                icounter = 0
                tag += 1



        if icounter != 0:
            offset = tag * bulk

            words = jiebaSep(store_obj,offset,counter,key,es)
            jieba_multi_zincr(p, lots_key, words)

        lst.append(lots_key)
        outfile = open(lots_key, 'w')
        key_list = r.zrevrangebyscore(lots_key, "inf",0,withscores=True)
        file_str = ''
        for v in key_list:
            v = list(v)
            line = ''
            for w in v:
                if isinstance(w,float):
                    w = str(w)
                line+=w+','
            file_str +=line+"\n"

        # print file_str

        outfile.write(file_str.encode('UTF-8'))
        outfile.close()
        end = datetime.datetime.now()
        end = time.mktime(end.timetuple())
        time = end - begin
        print("The %s run time is %f"%(lots_key,time))
    return lst

#只存储到es
@fn_timer
def buildEsLots(key):
    import time
    print "%s start" % key
    es = Elasticsearch()
    begin = datetime.datetime.now()
    begin = time.mktime(begin.timetuple())

    r = redis.Redis(host=rdsHost, port=rdsPort, db=0)

    hs = r.hgetall(key)

    if hs:


        #批量处理分词

        store_obj = []
        icounter = 0
        counter = 0
        tag = 0;

        for (k, v) in hs.items():

            dv = json.loads(v)

            store_obj.append(dv)
            icounter +=1
            counter +=1

            if ( icounter == bulk):
                offset = tag * bulk
                words = jiebaSep(store_obj,offset,counter,key,es)
                icounter = 0
                tag += 1


        if icounter != 0:
            offset = tag * bulk

            words = jiebaSep(store_obj,offset,counter,key,es)


        end = datetime.datetime.now()
        end = time.mktime(end.timetuple())
        time = end - begin
        print("The %s run time is %f"%(key,time))
    return lst

def isInList(list,item):
    item ='npl'+item
    item = item.decode('utf8')
    for v in list:

        if v==item:
            return True
    return False

@fn_timer
def rdsPool(r,fir_set):

    core_num = int(cpu_count()*0.6)

    p = Pool(processes=core_num)
    result_list = []

    edList = [u'nplsecond_classify1000' , u'nplsecond_classify0',u'nplsecond_classify1006',u'nplsecond_classify1007',
              u'nplsecond_classify1010',u'nplsecond_classify1011',u'nplsecond_classify1012',u'nplsecond_classify1013',
              u'nplsecond_classify1014',u'nplsecond_classify1016',u'nplsecond_classify1018',u'nplsecond_classify1021',
              u'nplsecond_classify1',u'nplsecond_classify2000',u'nplsecond_classify2002',u'nplsecond_classify2004',
              u'nplsecond_classify2005',u'nplsecond_classify3000',u'nplsecond_classify3001',u'nplsecond_classify3003',
              u'nplsecond_classify3',u'nplsecond_classify4',u'nplsecond_classify5',u'nplsecond_classify7',u'nplsecond_classify8',
              u'nplsecond_classify9',u'nplsecond_classify0',u'nplsecond_classify1020',u'nplsecond_classify1009',
              u'nplsecond_classify1017',u'nplsecond_classify1019',u'nplsecond_classify7003',
              u'nplsecond_classify7002',u'nplsecond_classify6000',u'nplsecond_classify7000',u'nplsecond_classify4004',
              u'nplsecond_classify1002',u'nplsecond_classify1015',u'nplsecond_classify4000',u'nplsecond_classify5016',
              u'nplsecond_classify5010',u'nplsecond_classify5003',u'nplsecond_classify5014',u'nplsecond_classify5015',
              u'nplsecond_classify5011',u'nplsecond_classify5017',u'nplsecond_classify5008',u'nplsecond_classify5018',
              u'nplsecond_classify5019',u'nplsecond_classify5000']
    for item in fir_set:
        sec_set = r.smembers(item)
        for lots in sec_set:
            if isInList(edList,lots):
                print "%s has in list" % lots
                continue

            result_list.append(p.apply_async(getHkeys,(lots,)))
    p.close()
    p.join()


@fn_timer
def esbuildPool(r,fir_set):

    core_num = int(cpu_count()*0.6)

    p = Pool(processes=core_num)
    result_list = []

    for item in fir_set:
        sec_set = r.smembers(item)
        for lots in sec_set:

            result_list.append(p.apply_async(buildEsLots,(lots,)))
    p.close()
    p.join()

def preSepWordTask(request):
    rds = redis.Redis(host=rdsHost, port=rdsPort, db=0)
    r = rds
    fir_set = r.smembers(fc)
    jieba.load_userdict("user_dic")

    jieba.enable_parallel(2)
    jieba.initialize()
    # rdsPool(r, fir_set)
    esbuildPool(r, fir_set)




    return HttpResponse('OK')

def index(request):
    return HttpResponse("微拍堂NPL")


def test_jieba():
    jieba.load_userdict("user_dic")
    text = "16121418精品重器来袭天然翡翠老坑A货山水意境作品 冰种绿、淡绿吊坠大挂件 尺寸约73.5x50.7x5.5MM重约37.8g 玉质通透起光老坑料子，天然山水飘花料子山水意境牌子，配送证书!自留送人高端大气！ 配送证书，查看证书参考色差大小点击右上角红条框，支持全国各地鉴定中心复检，非A包退假一罚十！ 买家必读:请您当快递面确认与成交拍品无误再签收，事后发生破损和少件本店不负责。全国快递包邮只发邮政，要求其他快递请留言并到付，12点前发货，12点后付款次日发。 0元起竞价拍卖，看好再出价，出价不退换。 当天收货五星好评截图返现金红包"

    seg_list = jieba.analyse.extract_tags(text, allowPOS=('n', 'nd', 'nr', 'ns', 'nt', 'nz', 'ng', 'nl'))
    return "Key words: " + "/ ".join(seg_list)  # 关键字




def addKeyWord(request):
    if request.POST.has_key('word') and request.POST.has_key('wp') :
        word = request.POST['word'].strip()
        wp = request.POST['wp'].strip()
        if word =='' or wp =='':
            return HttpResponse("请输入关键字和词性")
    else:
        return HttpResponse("请输入关键字和词性")
    if ','== word[-1]:
        word = word[:-1]
    wordlist = word.split(',')
    # print wordlist
    appenDic = {}
    wi = u'n'
    blank = u' '
    for word in wordlist:
        word = word.strip()
        new_line = word + blank +wp +blank +wi +u'\n'
        appenDic[word] = new_line

    res = "Add success!"
    tag = 1
    import copy
    appenDicCpy = copy.copy(appenDic)
    # print appenDicCpy
    for (key,word) in appenDicCpy.items():

        with open(user_dic, 'r') as file:

                for line in file.readlines():
                    line = unicode(line, "utf-8")
                    matchObj = re.match(word, line)
                    if matchObj:
                        if 1 == tag:
                            print word
                            print line
                            res = word+"已经存在"
                            tag = 2
                            del[appenDic[key]]

                            break
                        res = word +','+ res
                        del [appenDic[key]]

                        break


    with open(user_dic, 'a') as file:
        for (k,new_line) in appenDic.items():
            file.write(new_line)

    wlist = getDiskDic()
    cacheDic(wlist)
    # res = test_jieba()

    return HttpResponse(res)


def delKeyWord(request):

    if request.POST.has_key('word') :
        word = request.POST['word'].strip()
        if word =='':
            return HttpResponse("请输入关键字和词性")
    else:
        return HttpResponse("请输入关键字和词性")
    word = word+' '


    fresult = user_dic+'new'
    tag =1
    with open(user_dic, 'r') as f:
        with open(fresult, 'w') as g:
            for line in f.readlines():
                line = unicode(line, "utf-8")
                matchObj = re.match(word, line)
                if not matchObj:
                    g.write(line)
                else:
                    tag = 2
    shutil.move(fresult, user_dic)

    if tag == 2:
        echo = '关键字'+ word +'删除成功'
        wlist = getDiskDic()
        cacheDic(wlist)
    else:
        echo = '关键字'+ word +'在字典中不存在'
    return HttpResponse(echo)

def getDict(request):
    file = open(user_dic)
    dic_list = []
    for line in file:
        dic_list.append(line)
    res = json.dumps(dic_list)
    return HttpResponse(res)

def dashboard(request):
    return render(request, 'dashboard.html')


#以迭代方式获取数据
def getEsData(request):
    es = Elasticsearch()
    inx = 'npl'
    docType = "second_classify4003"

    page = es.search(
        index=inx,
        doc_type=docType,
        scroll = '2m',
        search_type = 'query_then_fetch',
        size = 1000,
        body={"query": {"match_all": {}}}
    )
    sid = page['_scroll_id']
    scroll_size = page['hits']['total']

    # Start scrolling
    while (scroll_size > 0):
        print "Scrolling..."
        page = es.scroll(scroll_id=sid, scroll='2m')
        # Update the scroll ID
        sid = page['_scroll_id']
        # Get the number of results that we returned in the last scroll
        scroll_size = len(page['hits']['hits'])
        itemList = page['hits']['hits']
        for item in itemList:
            # res = item['_source']['detail']
            res = item['_source']['words']
            res = ','.join(res)
            break
        break

    return HttpResponse(res)






@fn_timer
def findKeyword(request):
    import jieba.posseg as pseg
    jieba.load_userdict("user_dic")
    # text = u"16121418精品重器来袭天然翡翠老坑A货山水意境作品 冰种绿、淡绿吊坠大挂件 尺寸约73.5x50.7x5.5MM重约37.8g 玉质通透起光老坑料子，天然山水飘花料子山水意境牌子，配送证书!自留送人高端大气！ 配送证书，查看证书参考色差大小点击右上角红条框，支持全国各地鉴定中心复检，非A包退假一罚十！ 买家必读:请您当快递面确认与成交拍品无误再签收，事后发生破损和少件本店不负责。全国快递包邮只发邮政，要求其他快递请留言并到付，12点前发货，12点后付款次日发。 0元起竞价拍卖，看好再出价，出价不退换。 当天收货五星好评截图返现金红包"
    if request.POST.has_key('words') :
        text = request.POST['words'].strip()

        if text =='' :
            return HttpResponse("请输入拍品描述信息")
    else:
        return HttpResponse("请输入拍品描述信息")
    words = pseg.cut(text)
    wl = []
    for w in words:
        if w.flag[0] == 'n' and 0 == wl.count(w.word):
            wl.append(w.word)
    keywords = getKeyWords(wl)

    rst = " ".join(keywords)
    print(u"关键字: " +rst )
    return HttpResponse(rst)
