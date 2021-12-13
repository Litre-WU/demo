# -*- coding: utf-8 -*-
# Author: Litre WU
# E-mail: litre-wu@tutanota.com
# Software: PyCharm
# File: demo.py
# Time: 8月 26, 2021
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
import aiohttp
import requests
from user_agent import generate_user_agent
from time import time, sleep
from random import randint, sample
from lxml import etree
from json import loads, dumps
from math import ceil
from sys import platform
import os
import uuid
from Cryptodome.Cipher import AES
from binascii import b2a_hex, a2b_hex
from boltons.cacheutils import LRI, LRU
import base64
from loguru import logger

douban_cache = LRU(max_size=50)

logger.add(f'{os.path.basename(__file__)[:-3]}.log', rotation='200 MB', compression='zip', enqueue=True,
           serialize=False, encoding='utf-8', retention='7 days')

if platform == "win32":
    asyncio.set_event_loop(asyncio.ProactorEventLoop())
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

semaphore = asyncio.Semaphore(50)

tags_metadata = [
    {
        "name": "在线资源搜索",
        "description": "音乐(咪咕音乐), 视频(优酷、腾讯、爱奇艺、搜狐、芒果、乐视、PPTV、M1905等)",
        "externalDocs": {
            "description": "More",
            "url": "http://121.37.209.113",
        },
    },
]

app = FastAPI(openapi_url="/api/v1/api.json", title="在线影音", openapi_tags=tags_metadata)


app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# 加密
async def encrypt(*args, **kwargs):
    key, content = None, None
    if args:
        if len(args) == 2:
            key, content = str(args[0]), str(args[1])
        else:
            content = str(kwargs)
    else:
        if kwargs.get("_key", ""):
            key = str(kwargs.popitem()[-1])
            content = str(kwargs)
        else:
            content = str(kwargs)
    if not content: return False
    add = 16 - (len(content.encode()) % 16) if len(content.encode()) % 16 else 0
    content = content + ' ' * add
    # 加密
    key = key if key else "".join(sample('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', 16))
    encrypt_value = b2a_hex(AES.new(key.encode(), AES.MODE_ECB).encrypt(content.encode())).decode()
    return {"key": key, "encrypt_value": encrypt_value}


# 解密
async def decrypt(*args, **kwargs):
    key, encrypt_value = args if args else list(kwargs.items())[0]
    if key and encrypt_value:
        decrypt_value = AES.new(key.encode(), AES.MODE_ECB).decrypt(a2b_hex(encrypt_value)).decode().strip()
        return decrypt_value
    else:
        return False


# 生成token
async def token():
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "".join(str(uuid.uuid1()).split("-"))))


# 签名
async def sign(**kwargs):
    _key = "r4ZxqaG7tcP5SjLU"
    encrypt_value = await encrypt(**{**kwargs, **{"_time": int(time.time()), "_key": _key}})
    return encrypt_value["encrypt_value"]


# 日志
async def log(request, **kwargs):
    ritems = dict(request.items())
    if not kwargs: kwargs = ""
    log_info = f'{ritems["client"][0]} {ritems["method"]} {ritems["path"]} {ritems["type"]}/{ritems["http_version"]} {kwargs}'
    logger.info(log_info)


# 首页
@app.get('/', response_class=HTMLResponse, tags=["首页"])
async def index(request: Request):
    await log(request)
    return templates.TemplateResponse("main.html", {"request": request, "title": "首页", "url": "/music/"})


# 格言
@app.get('/adage/', tags=["格言"])
async def adage(request: Request):
    meta = {
        "url": "https://sp0.baidu.com/8aQDcjqpAAV3otqbppnN2DJv/api.php",
        "params": {
            "from_mid": "1",
            "format": "json",
            "ie": "utf-8",
            "oe": "utf-8",
            "subtitle": "格言",
            "query": "格言",
            "rn": "8",
            "pn": str(randint(0, 95) * 8),
            "resource_id": "6844",
            "_": str(int(time() * 1000)),
        }
    }
    res = await pub_http(**meta)
    res = loads(res.decode())
    result = [{"adage": d["ename"], "author": d["author"]} for d in res["data"][0]["disp_data"]]
    return result


# 电影
@app.get("/movie/", response_class=HTMLResponse, tags=["电影"])
async def movie(request: Request):
    await log(request)
    meta = {
        "url": "https://frodo.douban.com/api/v2/subject_collection/movie_hot_gaia/items",
        "params": {
            "start": "NaN",
            "count": "50",
            "apiKey": "0ac44ae016490db2204ce0a042db2916"
        },
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36 MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat",
            "Content-Type": "application/json",
            "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/82/page-frame.html",
        }
    }
    res = await pub_http(**meta)
    if not res: return None
    try:
        result = loads(res.decode())
        for m in result["subject_collection_items"]:
            if not douban_cache.get(m["id"]):
                meta["url"] = m["cover"]["url"]
                res = await pub_http(**meta)
                douban_cache[m["id"]] = base64.b64encode(res).decode()
            m["imgB64"] = douban_cache[m["id"]]
        context = {"request": request, 'title': "搜索", "url": "/movie/search", "result": result}
        return templates.TemplateResponse("movie.html", context)
    except Exception as e:
        logger.info(f'movie {e}')
        return JSONResponse({"code": 501, "msg": "服务异常", "result": res.decode()})


# 电影搜索
@app.get('/movie/search', response_class=HTMLResponse, tags=["电影"])
async def movie_search(request: Request, keyword: Optional[str] = None):
    await log(request, **{"keyword":keyword})
    if not keyword: return {"code": 401, "msg": "请输入关键字"}

    # result_list = await qq_video_search(**{"keyword": keyword})
    # result_list = await yk_video_search(**{"keyword": keyword})
    # result_list = await aqy_video_search(**{"keyword": keyword})
    # result_list = await sohu_video_serach(**{"keyword": keyword})

    tasks = [
        asyncio.create_task(qq_video_search(**{"keyword": keyword})),  # 腾讯
        # asyncio.create_task(yk_video_search(**{"keyword": keyword})),  # 优酷
        # asyncio.create_task(aqy_video_search(**{"keyword": keyword})),  # 爱奇艺
        asyncio.create_task(sohu_video_serach(**{"keyword": keyword})),  # 搜狐
    ]
    result = await asyncio.gather(*tasks)
    result_list = []
    for r in result:
        if r: result_list += r
    if not result_list: return JSONResponse({"code": 402, "msg": "未找到相关资源！"})
    context = {"request": request, 'title': "电影", "url": "/movie/search", "result_list": result_list}
    return templates.TemplateResponse('search.html', context=context)


# 音乐
@app.get('/music/', response_class=HTMLResponse, tags=["音乐"])
async def music(request: Request, keyword: Optional[str] = "周杰伦"):
    await log(request, **{"keyword":keyword})
    meta = {
        "url": "http://121.37.209.113:8090/search",
        "params": {
            "keyword": keyword
        }
    }
    res = await pub_http(**meta)
    if not res: return JSONResponse({"code": 402, "msg": "未找到相关资源！"})
    res = loads(res.decode())
    context = {
        "request": request,
        "title": "音乐",
        "url": "/music/",
        "data": res.get("data", "")
    }
    return templates.TemplateResponse('music.html', context=context)


# 音乐下载
@app.get('/music/download', response_class=JSONResponse, tags=["音乐"])
async def music_download(request: Request, singer: Optional[str] = None, song: Optional[str] = None,
                         tone: Optional[str] = None):
    await log(request, **{"singer": singer, "song": song, "tone": tone})
    if not (singer and song and tone): return {"code": 401, "msg": "请输入关键字"}
    meta = {
        "url": "http://121.37.209.113:8090/song/find",
        "params": {
            "keyword": f'{singer}+{song}'
        }
    }
    res = await pub_http(**meta)
    if not res: return {"code": 402, "msg": "未找到相关资源！"}
    res = loads(res.decode())
    return {"result": res["data"].get(tone, "128")}


# 公共请求函数
def pub_req(**kwargs):
    method = kwargs.get("method", "GET")
    url = kwargs.get("url", "")
    params = kwargs.get("params", {})
    data = kwargs.get("data", {})
    headers = {"User-Agent": generate_user_agent()} | kwargs.get("headers", {})
    proxy = kwargs.get("proxy", {})
    timeout = kwargs.get("timeout", 20)
    try:
        with requests.Session() as client:
            with client.request(method=method, url=url, params=params, data=data, headers=headers, proxies=proxy,
                                timeout=timeout) as rs:
                if rs.status_code == 200 or 201:
                    return rs.content
                else:
                    sleep(randint(1, 2))
                    retry = kwargs.get("retry", 0)
                    retry += 1
                    if retry >= 2:
                        return None
                    kwargs["retry"] = retry
                    return pub_req(**kwargs)
    except Exception as e:
        logger.info(e)
        sleep(randint(1, 2))
        retry = kwargs.get("retry", 0)
        retry += 1
        if retry >= 2:
            return None
        kwargs["retry"] = retry
        return pub_req(**kwargs)


# 公共请求函数
async def pub_http(**kwargs):
    method = kwargs.get("method", "GET")
    url = kwargs.get("url", "")
    params = kwargs.get("params", {})
    data = kwargs.get("data", {})
    headers = {**{"User-Agent": generate_user_agent()}, **kwargs.get("headers", {})}
    proxy = kwargs.get("proxy", "")
    timeout = kwargs.get("timeout", 20)
    try:
        async with semaphore:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3),
                                             connector=aiohttp.TCPConnector(ssl=False),
                                             trust_env=True) as client:
                async with client.request(method=method, url=url, params=params, data=data, headers=headers,
                                          proxy=proxy,
                                          timeout=timeout) as rs:
                    if rs.status == 200:
                        return await rs.read()
                    else:
                        sleep(randint(1, 2))
                        retry = kwargs.get("retry", 0)
                        retry += 1
                        if retry >= 2:
                            return None
                        kwargs["retry"] = retry
                        return await pub_http(**kwargs)
    except Exception as e:
        logger.info(f'pub_http {kwargs} {e}')
        sleep(randint(1, 2))
        retry = kwargs.get("retry", 0)
        retry += 1
        if retry >= 2:
            return None
        kwargs["retry"] = retry
        return await pub_http(**kwargs)


# vip_parse_url = 'https://dmjx.m3u8.tv'


# 腾讯视频搜索
async def qq_video_search(**kwargs):
    meta = {
        "url": "https://v.qq.com/x/search/",
        "params": {
            "q": kwargs.get("keyword", "斗罗大陆"),
            "stag": "101",
            "smartbox_ab": ""
        },
    }
    res = await pub_http(**meta)
    html = etree.HTML(res.decode())
    try:
        divs = html.xpath('//div[@data-index]')
        data_list = [{
            "id": div.xpath('div/@data-id')[0],
            "cover": "https:" + div.xpath('div/div[@class="_infos"]/div/a/img/@src')[0],
            "name": "".join(div.xpath('div/div[@class="_infos"]/div/h2/a//text()')[:-1]).strip(),
            "type": div.xpath('div/div[@class="_infos"]/div/h2/a/span[last()]/text()')[0],
            "info": {x.xpath('span[1]/text()')[0].replace("\u3000", ""): "".join(x.xpath('span[2]//text()')).strip() for x
                     in div.xpath('div/div[@class="_infos"]/div/div[@class="result_info"]/div') if
                     x.xpath('span[1]/text()')},
        } for div in divs]
        tasks = [asyncio.create_task(qq_video_play_list(**{"id": t["id"]})) for t in data_list]
        result = await asyncio.gather(*tasks)
        data_list = [d | {"play_list": {"腾讯": t[d["id"]]}} for d in data_list for t in result if t and t.get(d["id"], "")]
        return data_list
    except Exception as e:
        return None


# 腾讯视频播放列表
async def qq_video_play_list(**kwargs):
    _id = kwargs.get("id", "")
    if not _id: return None
    page = kwargs.get("page", 0)
    meta = {
        "method": "POST",
        "url": "https://pbaccess.video.qq.com/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData",
        "params": {
            "video_appid": "3000010",
            "vplatform": "2"
        },
        "data": dumps({
            "page_params": {"req_from": "web", "page_type": "detail_operation", "page_id": "vsite_episode_list",
                            "id_type": "1", "cid": _id, "lid": "", "vid": "", "page_num": "",
                            "page_size": "100",
                            "page_context": f"cid={_id}&page_num={page}&page_size=100&id_type=1&req_type=6&req_from=web&req_from_second_type="},
            "has_cache": 1}),
        "headers": {
            "Referer": "https://v.qq.com/",
            "Content-Type": "application/json",
            "Cookie": "vversion_name=8.2.95;"
        }
    }
    if _id.isdigit():
        meta["data"] = dumps({
            "page_params": {"req_from": "web", "page_type": "detail_operation", "page_id": "vsite_past_list",
                            "cid": "", "lid": _id}, "has_cache": 1})
    res = await pub_http(**meta)
    res = loads(res.decode())
    if res["data"]["module_list_datas"]:
        play_list = [{"name": x["item_params"]["play_title"],
                      "url": f'https://v.qq.com/x/cover/{_id}/{x["item_params"]["vid"]}.html'}
                     for x in
                     res["data"]["module_list_datas"][0]["module_datas"][0][
                         "item_data_lists"]["item_datas"] if x["item_params"].get("play_title", "")]
        if not play_list:
            play_list = [
                {"name": x["item_params"]["title"], "url": f'https://v.qq.com/x/cover/{x["item_params"]["cid"]}.html'}
                for x in
                res["data"]["module_list_datas"][0]["module_datas"][0][
                    "item_data_lists"]["item_datas"] if x["item_params"].get("cid", "")]
        if not page:
            total = loads(res["data"]["module_list_datas"][0]["module_datas"][0][
                              "module_params"]["tabs"])[-1]["end"] if \
                res["data"]["module_list_datas"][0]["module_datas"][0][
                    "module_params"].get("tabs", "") else 0
            pages = ceil(total / 100)
            tasks = [asyncio.create_task(qq_video_play_list(**{"id": _id, "page": p})) for p in range(1, pages)]
            result_list = await asyncio.gather(*tasks)
            for result in result_list:
                play_list += result
            return {kwargs.get("id", ""): play_list}
        return play_list


# 优酷视频搜索
async def yk_video_search(**kwargs):
    meta = {
        "url": "https://search.youku.com/api/search",
        "params": {
            "keyword": kwargs.get("keyword", "斗罗大陆"),
            "aaid": "",
            "cna": ""
        },
    }
    res = await pub_http(**meta)
    if not res: return None
    try:
        res = loads(res.decode())
        data_list = [{
            "id": r["commonData"].get("showId", ""),
            "name": r["commonData"]["titleDTO"].get("displayName", ""),
            "cover": r["commonData"]["posterDTO"].get("vThumbUrl", ""),
            "type": r["commonData"].get("feature", ""),
            "info": {
                "简介": r["commonData"].get("desc", ""),
                "更新": r["commonData"].get("updateNotice", ""),
            }
        } for r in res["pageComponentList"] if r.get("commonData", "")]
        tasks = [asyncio.create_task(yk_video_play_list(**{"id": d.get("id", ""), "keyword": d.get("name", "")})) for d in
                 data_list]
        result = await asyncio.gather(*tasks)
        data_list = [d | {"play_list": t[d["id"]]} for d in data_list for t in result if t.get(d["id"], "")]
        return data_list
    except Exception as e:
        return None


# 优酷视频播放列表
async def yk_video_play_list(**kwargs):
    if not kwargs.get("id", ""): return None
    meta = {
        "url": "https://search.youku.com/api/search",
        "params": {
            "appScene": "show_episode",
            "keyword": kwargs.get("keyword", "柯南"),
            "showIds": kwargs.get("id", "cc003400962411de83b1"),
            "appCaller": "h5"
        },
    }
    res = await pub_http(**meta)
    if not res: return None
    res = loads(res.decode())
    data_list = [
        {
            "name": r.get("title", ""),
            "url": f'https://v.youku.com/v_show/id_{r.get("videoId", "")}.html' if r.get("videoId",
                                                                                         "") else 'https://v.youku.com/v_show/id_XMzk1NjM1MjAw.html',
        } for r in res["serisesList"] if res.get("serisesList", "")
    ]
    return {kwargs.get("id", ""): data_list}


# 爱奇艺视频搜索
async def aqy_video_search(**kwargs):
    meta = {
        "url": "https://m.iqiyi.com/search.html",
        "params": {
            "source": "suggest",
            "key": kwargs.get("keyword", "中国好声音"),
            "pos": "1",
            "vfrm": "2-3-3-1"
        }
    }
    res = await pub_http(**meta)
    if not res: return None
    try:
        res = etree.HTML(res.decode()).xpath('//body/script[1]/text()')[0].split("__=")[1].split(";(")[0]
        res = loads(res)
        data_list = [
            {
                "id": r.get("qipu_id", "") if r.get("qipu_id", "") else r.get("docId", ""),
                "name": r.get("title", ""),
                "cover": r.get("albumImg", ""),
                "type": r.get("channelName", ""),
                "info": {
                    "分类": " ".join(r["video_lib_meta"].get("category", "")),
                    "区域": " ".join(r["video_lib_meta"].get("region", "")),
                    "主持人": r.get("star", ""),
                    "简介": r["video_lib_meta"].get("description", ""),
                    "发布时间": r["video_lib_meta"].get("start_update_time", ""),
                    "更新至": r["video_lib_meta"].get("filmtv_update_strategy", ""),
                    "更新时间": r.get("stragyTime", ""),
                },
                "play_list": [{
                    "name": v.get("itemTitle", ""),
                    "url": v.get("itemLink", ""),
                } for v in r["videoinfos"] if r.get("videoinfos", "")]
            } for r in res["search"]["searchResult"]["docs"] if r.get("siteId", "") == "iqiyi"]
        tasks = [asyncio.create_task(aqy_video_play_list(**{"id": d.get("id", "")})) for d in
                 data_list]
        result = await asyncio.gather(*tasks)
        result = [r for r in result if r]
        if result:
            data_list = [d | {"play_list": t[d["id"]]} for d in data_list for t in result if t.get(d["id"], "")]
        return data_list
    except Exception as e:
        return None


# 爱奇艺播放列表
async def aqy_video_play_list(**kwargs):
    if not kwargs.get("id", "") or not str(kwargs.get("id", "")).isdigit(): return None
    meta = {
        "url": "https://pub.m.iqiyi.com/h5/main/videoList/album/",
        "params": {
            "albumId": kwargs.get("id", ""),
            "size": kwargs.get("size", 1),
            "page": kwargs.get("page", 1),
            "needPrevue": "true",
            "needVipPrevue": "false",
        }
    }
    res = await pub_http(**meta)
    if not res: return None
    res = loads(res.decode())
    if not res.get("data", ""): return None
    total = res["data"].get("total", 0)
    if not total: return None
    data_list = [{
        "name": r.get("subTitle", ""),
        "url": "https:" + r.get("pageUrl", ""),
        "vt": r.get("vt", ""),
        "desc": r.get("desc", ""),
    } for r in res["data"]["videos"]]
    if not kwargs.get("size", ""):
        data_list = await aqy_video_play_list(**{"id": kwargs.get("id", ""), "size": total})
        data_list = {kwargs.get("id", ""): data_list}
        return data_list
    return data_list


# 搜狐视频视频搜索
async def sohu_video_serach(**kwargs):
    meta = {
        "url": "https://pv.sohu.com/suv/",
    }
    res = await pub_http(**meta)
    suv = res.decode().split('"')[-2]
    meta = {
        "url": "https://so.tv.sohu.com/mts",
        "params": {
            "wd": kwargs.get("keyword", "斗罗大陆"),
            "time": int(time() * 1000)
        },
        "headers": {
            "Cookie": f"SUV={suv};",
        }
    }
    res = await pub_http(**meta)
    if not res: return None
    try:
        divs = etree.HTML(res.decode()).xpath('//div[@class="area "]')
        divs += etree.HTML(res.decode()).xpath('//div[@class="area  special"]')
        data_list = [{
            "cover": "https:" + div.xpath('div/div/div/a/img/@src')[0],
            "name": div.xpath('div/div[@class="center"]/div/h2/a/@title')[0],
            "type": div.xpath('div/div[@class="center"]/div/span/em/text()')[0],
            "info": {
                        "".join(x.xpath('text()')).split("：")[0]: " ".join(x.xpath('a/text()')) for x in
                        div.xpath('div/div[@class="center"]/ul/li/div')
                    } | {div.xpath('div/div[@class="center"]/p/text()')[0].split("：")[0].strip():
                             div.xpath('div/div[@class="center"]/p/text()')[0].split("：")[1].strip()},
            "play_list": dict(
                zip(div.xpath('div/div[@class="center"]/div[@class="lan_resource"]/div/div/ul/li/em/text()'),
                    [[{
                        "name": a.xpath('text()')[0],
                        "url": "https:" + a.xpath('@href')[0]
                    } for a in div.xpath('div//a') if a.xpath('@href')[0].strip("#")] for div in
                        div.xpath('div/div[@class="center"]/div[@class="lan_resource"]/div')[1:]]
                    )),
        } for div in divs]
        return data_list
    except Exception as e:
        logger.info(f'sohu_video_serach {e}')
        return None


# 比特英雄视频搜索
async def bt_video_search(**kwargs):
    meta = {
        "url": "https://www.btdx8.com/",
        "params": {
            "s": kwargs.get("keyword", "")
        }
    }
    res = await pub_http(**meta)
    if not res: return None
    # logger.info(res.decode())
    divs = etree.HTML(res.decode()).xpath('//div[@id="content"]/div/div')
    if not divs: return None
    data_list = [{
        "id": div.xpath('h3/a/@href')[0].split("/")[-1].split(".")[0],
        "cover": div.xpath('a/img/@src')[0],
        "name": "".join(div.xpath('h3//text()')),
        "type": div.xpath('div/span/a/text()')[0],
        "info": {
                    x.split("：")[0]: x.split("：")[1] for x in div.xpath('div/span/text()') if "：" in x
                } | {"简介": div.xpath('div/p/text()')[0]},
    } for div in divs]
    logger.info(data_list)
    return data_list


# 比特英雄播放列表
async def bt_video_play_list(**kwargs):
    meta = {
        "url": f'https://www.btdx8.com/torrent/{kwargs.get("id", "dldl_2019")}.html',
    }
    res = await pub_http(**meta)
    if not res: return None
    # logger.info(res.decode())
    play_list = {
                    "磁力链接": [{"name": a.xpath('text()')[0].split("]")[-1].split(".")[0], "url": a.xpath('@href')[0]} for
                             a in
                             etree.HTML(res.decode()).xpath('//div[@id="zdownload"]/a')]} | {
                    "荐片播放器": [{"name": a.xpath("text()")[0], "url": a.xpath("@href")[0].split("=")[-1]} for a in
                              etree.HTML(res.decode()).xpath('//div[@id="play_list"]/a') if a.xpath("@href")]}
    logger.info(play_list)
    return play_list


# 迅播
async def xb_video(**kwargs):
    meta = {
        "url": f'https://www.imxbp.com/vodsearch/{kwargs.get("", "斗罗大陆")}----------{kwargs.get("page", "1")}---.html',
    }
    res = await pub_http(**meta)
    if not res: return None
    lis = etree.HTML(res.decode()).xpath('//ul[@class="searchmlist"]/li')
    if not lis: return None
    data_list = [
        {
            "id": li.xpath('div/h2/a/@href')[0].split("/")[-1].split(".")[0],
            "cover": li.xpath('a/img/@src')[0],
            "name": li.xpath('div/h2/a/text()')[0],
            "type": "",
            "info": {
                x.split("：")[0]: x.split("：")[1] for x in li.xpath('div/p/text()')
            }
        } for li in lis
    ]
    if data_list:
        tasks = [asyncio.create_task(xb_video_list(**{"id": data_list[i]["id"]})) for i in range(len(data_list))]
        result_list = await asyncio.gather(*tasks)
        data_list = [data | {"play_list": result[data["id"]]} for data in data_list for result in result_list if
                     result.get(data["id"], "")]
    return data_list


# 迅播播放列表
async def xb_video_list(**kwargs):
    if not kwargs.get("id", ""): return None
    meta = {
        "url": f'https://www.imxbp.com/html/{kwargs.get("id", "")}.html'
    }
    res = await pub_http(**meta)
    try:
        data_list = [{"name": a.xpath('text()')[0], "id": a.xpath('@href')[0].split("/")[-1].split(".")[0]} for a in
                     etree.HTML(res.decode()).xpath('//div[@class="content"]/div[@class="play-list"]/a')]
        if data_list:
            tasks = [asyncio.create_task(xb_video_link(**{"id": data_list[i]["id"]})) for i in range(len(data_list))]
            result_list = await asyncio.gather(*tasks)
            data_list = [data | {"url": result[data["id"]]} for data in data_list for result in result_list if
                         result.get(data["id"], )]
        return {kwargs.get("id", ""): data_list}
    except Exception as e:
        return None


# 迅播播放链接
async def xb_video_link(**kwargs):
    if not kwargs.get("id", ""): return None
    meta = {"url": f'https://www.imxbp.com/play/{kwargs.get("id", "")}.html'}
    res = await pub_http(**meta)
    try:
        info = etree.HTML(res.decode()).xpath('//div[@class="player-box"]/script/text()')
        info = info[0].split("_data=")[1] if info else ""
        if not info: return None
        return {kwargs.get("id", ""): loads(info).get("url", "")}
    except Exception as e:
        return None


if __name__ == '__main__':
    # rs = asyncio.run(adage(Request))
    rs = asyncio.run(movie(Request))
    # rs = asyncio.run(qq_video_search(**{"keyword": "斗罗大陆"}))
    # rs = asyncio.run(qq_video_search(**{"keyword": "这！就是街舞"}))
    # rs = asyncio.run(qq_video_play_list(**{"id": "m441e3rjq9kwpsc"}))
    # rs = asyncio.run(qq_video_search(**{"keyword": "脱口秀大会"}))
    # rs = asyncio.run(qq_video_search(**{"keyword": "当男人恋爱时"}))
    # rs = asyncio.run(yk_video_search(**{"keyword": "这！就是街舞 第四季"}))
    # rs = asyncio.run(yk_video_search(**{"keyword": "斗罗大陆"}))
    # rs = asyncio.run(yk_video_play_list(**{"id": "cedb35b8e3574edebf39"}))
    # rs = asyncio.run(aqy_video_search(**{"keyword": "中国好声音"}))
    # rs = asyncio.run(aqy_video_search(**{"keyword": "柯南"}))
    # rs = asyncio.run(aqy_video_search(**{"keyword": "斗罗大陆"}))
    # rs = asyncio.run(aqy_video_play_list(**{"id": "106741901"}))
    # rs = asyncio.run(aqy_video_play_list(**{"id": "5729569838039801"}))
    # rs = asyncio.run(sohu_video_serach(**{"keyword": "脱口秀大会"}))
    # rs = asyncio.run(bt_video_search(**{"keyword": "斗罗大陆"}))
    # rs = asyncio.run(bt_video_play_list(**{"id": "dldl_2019"}))
    # rs = asyncio.run(xb_video(**{"keyword": "斗罗大陆"}))
    # rs = asyncio.run(xb_video_list(**{"id": "401572"}))
    # rs = asyncio.run(xb_video_link(**{"id": "402000-2-1"}))
    # rs = asyncio.run(music_download(Request, singer="周杰伦", song="告白气球", tone="flac"))
    logger.info(rs)
