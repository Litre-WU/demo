# 在线影音

在线资源搜索(音乐(咪咕音乐), 视频(优酷、腾讯、爱奇艺、搜狐、芒果、乐视、PPTV、M1905等))

接口文档(http://127.0.0.1:52/docs)

`pip install -r requirements.txt -i https://pypi.doubanio.com/simple/`

`uvicorn main:app`

# docker启动项目

`docker pull litrewu/demo`

`docker run -d -p 80:52 --name demo-test litrewu/demo`
