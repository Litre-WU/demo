# 在线影音

在线资源搜索(音乐(咪咕音乐), 视频(优酷、腾讯、爱奇艺、搜狐、芒果、乐视、PPTV、M1905等))

tip:资源来自网络爬虫,项目仅供娱乐！

接口文档(http://127.0.0.1/docs)

演示地址(http://127.0.0.1/movie/)

(页面写的比较简单，效果如下)

音乐页面效果图

![Image text](https://github.com/Litre-WU/demo/blob/master/static/images/%E6%95%88%E6%9E%9C%E5%9B%BE3.png)

影视页面效果图

![Image text](https://github.com/Litre-WU/demo/blob/master/static/images/%E6%95%88%E6%9E%9C%E5%9B%BE.png)

影视搜索页面效果图

![Image text](https://github.com/Litre-WU/demo/blob/master/static/images/%E6%95%88%E6%9E%9C%E5%9B%BE2.png)

# 运行项目

`pip install -r requirements.txt -i https://pypi.doubanio.com/simple/`

`uvicorn demo:app`

# docker运行项目

`docker pull litrewu/demo`

`docker run -d -p 80:52 --name demo-test litrewu/demo`
