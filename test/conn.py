#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  6 17:56:42 2017

@author: cmz
"""
from pymongo import *
import jieba
from jieba import analyse
import numpy as np
import pandas as pd
from pandas import DataFrame
import time
import jieba
from jieba import analyse
import sys 
import os
import psutil
import threading
import multiprocessing

reload(sys) 
sys.setdefaultencoding('utf8') 

def freq(cate, data):
    print "run thread %s" % cate

    filename = cate+'.csv'
#    if os.path.isfile(filename):
#        print 'skip'
#        return
#    print "当前分类：%s" % cate
    t2 = time.time()
    cur_data = data[data.sec_cate==cate]#['detail']
    test = cur_data['detail']#[:1000]
    print len(test)
#    print "read data cost %.2f seconds" % (time.time()-t2)

#    print "测试数据集：%s" % test
    freq = {}

    ct = 0
    for text in test: 
        
        ct += 1
        if ct%1000 == 0:
            print "%s:%d / %d" % (cate, ct, len(test))
#        print "当前文本：%s" % text
        
        words = jieba.posseg.dt.cut(text, HMM=False)
        f = {}
        
#        t1 = time.time()
        for w in words: 
            if w.flag in allowPOS:
                f[w.word] = True
#        dt1 += time.time() - t1

        for k in f:
            freq[k] = freq.get(k, 0) + 1

#    print "cut words cost %.2f seconds" % dt1
#    print "total cost %.2f seconds" % (time.time()-t0)
#    for k,v in freq.items():
#        print k, v
    
    df_freq = DataFrame(freq.items())
    df_freq.to_csv(filename, header=False, index=False )
    print "sec_cate %s done" % cate
        
        
print "connecting"
mgclient = MongoClient(host='127.0.0.1')
db_auth = mgclient.npl
db_auth.authenticate("npl", "npl")
db = mgclient.npl
sale_info = db.npl_sale_info
print "connected to npl_sale_info"

#reducer = '''
#                function(obj,prev)
#                {
#                    prev.count++;
#                }
#        '''
#cates = sale_info.group({"sec_cate":1}, None, {"count":0}, reducer)
#cate_rates = DataFrame(list(cates))
#print cate_rates
#cate_rates['count'] = cate_rates['count'].max()/cate_rates['count']
#print cate_rates
#cate_rates.to_csv('cate_rates.csv')
#print "save cate_rates.csv done"

#cate_rates = pd.read_csv('cate_rates.csv', index_col=0 )
#print cate_rates

cursor = sale_info.find({}, {"_id":0, "sec_cate":1, "detail":1}, limit = 10000000)
results = DataFrame(list(cursor), columns = ['sec_cate','detail']) # 待优化
#
data = results[:].dropna() # drop后index可能不连续
length = len(data)
print "data length %d" % length

# allowPOS and stop_words prepared for filtering
jieba.load_userdict("../user_dic") 
allowPOS = ('n','nr','ns','nz','nt','nl','ng','t','a','i')
allowPOS = frozenset(allowPOS)
print "jieba load done"

t0 = time.time()
dt1 = 0

#Threads = []
#
#donelist = pd.read_csv('donelist.txt', header = None)
#
#for cate in data['sec_cate'].unique():
##for cate in ['1015','5001','5002']: 
#    if int(cate) not in list(donelist[0]):
#        th = threading.Thread(target=freq, args=(cate, data))
#        Threads.append(th)
#    
#for t in Threads:
##    t.setDaemon(True)
#    t.start()
#    
#for t in Threads:
#    t.join()
#
#print "done"

Processes = []

donelist = pd.read_csv('donelist.txt', header = None)

for cate in data['sec_cate'].unique():
#for cate in ['1015','5001','5002']: 
    if int(cate) not in list(donelist[0]):
        pc = multiprocessing.Process(target = freq, args = (cate, data))
        Processes.append(pc)
    
for p in Processes:
    p.start()
    
for p in Processes:
    p.join()

print "done"

    






