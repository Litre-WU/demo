# 项目运行

`pip install -r requirements.txt -i https://pypi.doubanio.com/simple/`

`uvicorn main:app`

# docker启动项目

`docker pull litrewu/demo`

`docker run -d -p 80:80 --name demo-test litrewu/demo`
