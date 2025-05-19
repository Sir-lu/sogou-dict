import os
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import urllib.request
import time
import random

# 格式：分类名，对应的链接，页数
cates = [
    ["城市信息", 360, 8],
    ["自然科学", 1, 31],
    ["社会科学", 76, 36],
    ["工程应用", 96, 81],
    ["农林渔畜", 127, 10],
    ["医学医药", 132, 35],
    ["电子游戏", 436, 124],
    ["艺术设计", 154, 17],
    ["生活百科", 389, 77],
    ["运动休闲", 367, 17],
    ["人文科学", 31, 88],
    ["娱乐休闲", 403, 103]
]
 
sets = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']  # windows文件命名不能有这些字符
 
# 添加请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_html_with_retry(url, max_retries=3):
    for i in range(max_retries):
        try:
            req = Request(url, headers=headers)
            response = urlopen(req)
            return response
        except Exception as e:
            if i == max_retries - 1:
                print(f"访问失败 {url}: {str(e)}")
                raise
            print(f"重试 {i+1}/{max_retries}")
            time.sleep(random.uniform(2, 5))

def file_exists_with_same_size(file_path, download_url):
    """检查文件是否存在且大小相同"""
    if not os.path.exists(file_path):
        return False
    
    try:
        # 获取已存在文件的大小
        existing_size = os.path.getsize(file_path)
        
        # 获取要下载文件的大小
        req = Request(download_url, headers=headers)
        response = urlopen(req)
        download_size = int(response.headers.get('content-length', 0))
        
        return existing_size == download_size
    except Exception as e:
        print(f"检查文件大小时出错: {str(e)}")
        return False

for cate in cates:
    count = 0
    os.makedirs("./scel/" + cate[0], exist_ok=True)
    for i in range(1, cate[2] + 1):
        try:
            url = f"https://pinyin.sogou.com/dict/cate/index/{str(cate[1])}/default/{str(i)}"
            html = get_html_with_retry(url)
            bsObj = BeautifulSoup(html.read(), "html.parser")
            nameList = bsObj.findAll("div", {"class": "detail_title"})
            urlList = bsObj.findAll("div", {"class": "dict_dl_btn"})
            
            for name, url in zip(nameList, urlList):
                count += 1
                name = name.a.get_text()
                for char in sets:
                    name = name.replace(char, "")  # 去除windows文件命名中非法的字符
                
                download_url = url.a.attrs['href']
                save_path = f"./scel/{cate[0]}/{str(count)}{name}.scel"
                
                # 检查文件是否已存在且大小相同
                if file_exists_with_same_size(save_path, download_url):
                    print(f"跳过已存在的文件: {save_path}")
                    continue
                
                # 添加下载重试机制
                req = Request(download_url, headers=headers)
                urllib.request.urlretrieve(download_url, save_path)
                print(cate[0], count, name)
                
                # 添加随机延时
                time.sleep(random.uniform(1, 3))
                
        except Exception as e:
            print(f"处理分类 {cate[0]} 第 {i} 页时出错: {str(e)}")
            continue