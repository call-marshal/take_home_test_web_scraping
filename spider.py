import re
import time
from datetime import datetime

import pandas as pd
from lxml import etree
from fake_useragent import UserAgent

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service as ChromeService


class NewsSpider(object):
    def __init__(self):
        self.proxies = {
            'http': 'http://127.0.0.1:80000',  # HTTP代理IP
        }
        
        # 初始化Selenium的Chrome选项
        options = webdriver.ChromeOptions()
        options.binary_location=r'path\to\chrome.exe'
        options.add_argument(r'--user-data-dir=path\to\user-data-dir')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # options.add_argument(f'user-agent={UserAgent().chrome}')  # 使用随机的UserAgent
        # options.add_argument('--headless')  # 无头模式
        # options.add_argument('--proxy-server=%s' % self.proxies['http'])  # 设置代理
        # driver_path = r'path\to\driver'
        # service = ChromeService(executable_path=driver_path)
        self.driver = webdriver.Chrome(
            options=options,
            # service=service
        )
    
    def get_html(self, url):
        # 打开网页
        self.driver.get(url)
        
        # 尝试获取网站最后修改时间，如果没有则使用当前时间
        try:
            last_modified = self.driver.execute_script("return document.lastModified")
            timestamp = datetime.strptime(last_modified, "%m/%d/%Y, %I:%M:%S %p").timestamp()
        except:
            timestamp = datetime.now().timestamp()  # 使用当前时间作为时间戳
        
        # 等待网页加载完成，直到header中出现元素
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/header/div[1]/div/div[1]/a[1]'))
        )
        
        # 返回整个页面内容
        return self.driver.page_source, timestamp

    def extract_issue_num(self, parse_html):
        """
        从HTML中提取期号
        """
        issue_href = parse_html.xpath('/html/body/header/div[1]/div/div[1]/a[1]/@href')[0].strip('\n')
        issue_num = re.findall(r'(?<=issues/)(.*)(?=#)', issue_href)[0]
        return int(issue_num)
    
    def extract_news_content(self, parse_html, timestamp):
        """
        从HTML中提取新闻内容
        """
        news_list = parse_html.xpath('//*[@id="news"]/div') + parse_html.xpath('//*[@id="inthenews2"]/div')
        news_content = []

        for news in news_list:
            item = {
                'title': news.xpath('./h3/a/text()')[0].strip('\n'),
                'text': news.xpath('./p/text()')[0].strip('\n'),
                'website': news.xpath('./span/span/a/text()')[0].strip('\n'),
                'link': news.xpath('./span/span/a/@href')[0].strip('\n'),
                'timestamp': timestamp
            }
            news_content.append(item)

        return news_content

    def get_html_info(self, url, n_issue=0):
        """
        获取指定期号范围内的新闻信息
        """
        # 获取初始网页HTML及时间戳
        html, timestamp = self.get_html(url)
        time.sleep(5)
        parse_html = etree.HTML(html)

        # 提取期号
        issue_num = self.extract_issue_num(parse_html)

        # 验证请求的期号范围是否有效
        if n_issue > issue_num:
            raise ValueError('Requested issue number exceeds the available issues')

        # 提取当前期号新闻内容
        news_content = self.extract_news_content(parse_html, timestamp)

        # 获取历史期号的新闻
        for n in range(n_issue - 1):
            previous_issue = issue_num - n - 1
            prev_url = f'https://aiweekly.co/issues/{previous_issue}#start'
            try:
                news_content.extend(self.get_html_info(prev_url))
            except:
                continue

        return news_content

    def close(self):
        # 关闭浏览器
        self.driver.quit()


# 使用示例
if __name__ == "__main__":
    url = f'https://aiweekly.co/'
    csv_path = r'.\selenium_scraped_data.csv'
    
    spider = NewsSpider()
    news_content = spider.get_html_info(url, 50)
    spider.close()
    
    columns = ['id', 'title', 'text', 'website', 'link', 'timestamp']
    datas = []
    for idx, news in enumerate(news_content):
        data = [value for value in news.values()]
        data.insert(0, idx)
        if len(data) != len(columns):
            continue
        datas.append(data)
        print(news)
        
    print(len(news_content))
    
    # 将数据转换为 DataFrame 并保存为 CSV 文件
    df = pd.DataFrame(datas, columns=columns)
    df.to_csv(csv_path, index=False)
