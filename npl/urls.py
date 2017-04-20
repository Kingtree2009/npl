# coding:utf-8
"""npl URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url,include

from django.contrib import admin
from genDic import views as genDic_views


urlpatterns = [
    url(r'^getkwForUri/$', genDic_views.getkwForUri, name='getkwForUri'),
    url(r'^delESindexId/$', genDic_views.delESindexId, name='delESindexId'),
    url(r'^getESrst/$', genDic_views.getESrst, name='getESrst'),
    url(r'^setKeywordsRds/$', genDic_views.setKeywordsRds, name='setKeywordsRds'),
    url(r'^findKeyword/$', genDic_views.findKeyword, name='findKeyword'),
    url(r'^dashboard/$', genDic_views.dashboard, name='dashboard'),
    url(r'^delKeyWord/$', genDic_views.delKeyWord, name='delKeyWord'),
    url(r'^addKeyWord/$', genDic_views.addKeyWord, name='addKeyWord'),
    url(r'^$', genDic_views.index),  # new
    url(r'^getDict/$', genDic_views.getDict, name='getDict'),
    url(r'^admin/', admin.site.urls),
    url(r'^preSepWordTask/$', genDic_views.preSepWordTask, name='preSepWordTask'),
    url(r'^getEsData/$', genDic_views.getEsData, name='getEsData'),
    url(r'^getDicFile/$', genDic_views.getDicFile, name='getDicFile'),

]
