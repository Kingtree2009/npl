#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 13 16:53:59 2017

@author: cmz
"""
import jieba
from jieba import analyse
import pandas as pd
from pandas import DataFrame
import time
import math
import sys
import os
import re
import multiprocessing
from pymongo import *

filepath = "/Users/cmz/work/npl_freq/"
clfs_name = pd.read_csv('clf_name.txt', header=None)

def myidf():
    
    filenames =  os.listdir(filepath)
    
#    string = pd.read_csv('/Users/cmz/work/100w.csv', header=None)
#    data = string.ix[:,:1].dropna()
#    myclfs = data[0].unique().tolist()
#    print list(set(myclfs).difference(set(clfs)))
#    clf_rate = data.groupby(by=0)[0].count()
#    clf_rate = clf_rate.max()/clf_rate 

#    从文件读取 cate_rates.csv
    rates = pd.read_csv("/Users/cmz/work/npl/test/cate_rates.csv", index_col=0)
    cate_rates=DataFrame(list(rates['count']), index=list(rates['sec_cate']))
    
    total = 10000000.0
    freq = DataFrame()
    for filename in filenames:
        csv_path = os.path.join('%s%s' % (filepath, filename))
        data = pd.read_csv(csv_path, header=None)
        clf = int(re.search(r'(\d)+', filename, re.I).group())
        data[1] = data[1]*cate_rates.ix[clf][0]#???
        freq = pd.concat([freq,data], ignore_index=True)
    freq = freq.groupby(0).sum()
    f = lambda x: math.log(total/x+math.e)
    freq = freq.applymap(f)
    
    freq.to_csv('idf.txt', header=None, sep=' ')
    
        
    
def oldidf():
    
    reload(sys)
    sys.setdefaultencoding('utf-8')
    
    # load and preprocess the goods descriptions 
    string = pd.read_csv('test_data.csv', header=None)
    data = string.ix[:,:1].dropna()
    length = len(data)# total docs num
    clfs = data.groupby(by=0)[0].count()
    clfs = clfs.max()/clfs
    total = clfs.count()*clfs.max()
    
    # allowPOS and stop_words prepared for filtering
    jieba.load_userdict("user_dic") 
    allowPOS = ('n','nr','ns','nz','nt','nl','ng','t','v','vn','a','i')
    allowPOS = frozenset(allowPOS)
#    load stop_words 

    freq = {} 
    
    t0 = time.time()
    # find how many docs a word exists in
    for i in range(length):
        cur_data = data.ix[data.index[i]] 
        words = jieba.posseg.dt.cut(cur_data[1]) 
        # mark first, then add 1 to freq
        f = {} 
        for w in words:
            if w.flag in allowPOS:
                f[w.word] = True
        for k in f:
            freq[k] = freq.get(k, 0) + clfs[cur_data[0]]
        if i%1000 == 0:
            print "%d sec" % (time.time()-t0)
    
    # calc idf with log
    for k in freq:
#        freq[k] = math.log(total) / math.log(freq[k]+1)
        freq[k] = math.sqrt(total*1.0 / freq[k])
    # transform dict 'freq' to list
    idf_list = []
    for k,v in freq.items():
        idf_list.append(k+" "+str(v))
       
    # write to idf.txt
    out = "\n".join(idf_list)
#    print out
    file = open('idf1.txt','w')
    file.write(out)
    file.close()
    
    print "done"
        
    
def extract(clf, data):
    
    text = data[data[0]==clf][1]
    s = []
    for line in text:
        s.append(line)
    sentence = "".join(s)
    
    print 'extracting %d...' % clf
#    t1 = time.time()
    kw = keywordsbytfidf(sentence)
#    t2 = time.time()
#    print "%d seconds" % (t2-t1)

    print '品类 '+str(clf)+' '+clfs_name.ix[clfs_name[0]==clf,1].values[0]
    for w in kw[0]:
        print w,  
        
    print "\n"
        
    
def getkeywords():
    
    jieba.load_userdict("../user_dic") 
    analyse.set_idf_path("idf.txt") #file_name为自定义语料库的路径    
#    analyse.set_stop_words("stop_words.txt") #file_name为自定义语料库的路径。  
    
    string = pd.read_csv('100w.csv', header=None)
    data = string.ix[:,:1].dropna()
    clfs = data[0].unique()
    
    k = len(clfs)/12
    for i in range(k):
        print "..."
        t1 = time.time()
        Processes = []
        if i == k-1:
            for clf in clfs[i*12:]:
                pc = multiprocessing.Process(target = extract, args = (clf, data))
                Processes.append(pc)
        else:
            for clf in clfs[i*12:(i+1)*12]:
                pc = multiprocessing.Process(target = extract, args = (clf, data))
                Processes.append(pc)
            
        for p in Processes:
            p.start()
            
        for p in Processes:
            p.join()
            
        t2 = time.time()
        print "%d seconds" % (t2-t1)            
        
    # FILE


def getkeywords2():
    
    jieba.load_userdict("../user_dic") 
    analyse.set_idf_path("idf.txt") #file_name为自定义语料库的路径    
#    analyse.set_stop_words("stop_words.txt") #file_name为自定义语料库的路径。  
    
    print "connecting"
    mgclient = MongoClient(host='127.0.0.1')
    db_auth = mgclient.npl
    db_auth.authenticate("npl", "npl")
    db = mgclient.npl
    sale_info = db.npl_sale_info
    print "connected to npl_sale_info"
    
    cursor = sale_info.find({}, {"_id":0, "sec_cate":1, "detail":1}, limit = 10000000)
    results = DataFrame(list(cursor), columns=["sec_cate","detail"]) 
    data = results[:].dropna() # drop后index可能不连续
    data.columns=[0,1]
    print data[:10]
    clfs = pd.read_csv('recalc.txt', header=None)
    
    t1 = time.time()
    Processes = []
    for clf in clfs[0]:
        pc = multiprocessing.Process(target = extract, args = (clf, data))
        Processes.append(pc)

    for p in Processes:
        p.start()
        
    for p in Processes:
        p.join()
        
    t2 = time.time()
    print "%d seconds" % (t2-t1)            
        
    # FILE
    
    
        
def keywordsbytextrank(text):
    
    textrank = analyse.textrank
    
#    file = open('corpus.txt','r')
#    text = file.read()
    
    allowPOS = ('n','nr','ns','nz','nt','nl','ng','t','v','vn','a','i')
    keywords = textrank(text, topK=50, allowPOS=allowPOS, withFlag=True)
    results = DataFrame(keywords)
    
#    print 'top50 keywords by textrank'
#    for keyword in keywords:
#        print keyword.word, keyword.flag + "/",
#    print '\n'
    
    return results

def keywordsbytfidf(text):
    
    tfidf = analyse.tfidf
    
#    allowPOS = ('n','nr','ns','nz','nt','nl','ng','t','v','vn','a','i')
    allowPOS = ('n','nr','ns','nz','nt','nl','ng','t','a','i')
    keywords = tfidf(text, topK=300, allowPOS=allowPOS, withFlag=True)
    results = DataFrame(keywords)
    
#    print 'top50 keywords by tfidf'
#    for keyword in keywords:
#        print keyword.word, keyword.flag + "/",
#    print '\n'
    
    return results
        
getkeywords2()
#myidf()

