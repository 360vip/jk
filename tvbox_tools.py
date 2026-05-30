# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import pprint
import random
import string
import time
import hashlib
import json
import re
import base64
import requests
from requests.adapters import HTTPAdapter, Retry
import os
import ssl
from pathlib import Path
ssl._create_default_https_context = ssl._create_unverified_context
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

global pipes
pipes = set()

class GetSrc:
    def __init__(self, repo=None, num=10, target=None, timeout=3, mirror=None, jar_suffix=None):
        self.jar_suffix = jar_suffix if jar_suffix else 'jar'
        self.mirror = int(str(mirror).strip()) if mirror else 1
        self.registry = 'github.com'
        self.mirror_proxy = 'https://gh.927223.xyz/https://raw.githubusercontent.com'
        self.num = int(num)
        self.sep = os.path.sep
        self.timeout = float(timeout)  # 确保timeout是float类型
        self.repo = repo if repo else 'tvbox'
        self.target = f'{target.split(".json")[0]}.json' if target else 'tvbox.json'
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.s = requests.Session()
        retries = Retry(total=3, backoff_factor=1)
        self.s.mount('http://', HTTPAdapter(max_retries=retries))
        self.s.mount('https://', HTTPAdapter(max_retries=retries))
        self.size_tolerance = 15
        self.main_branch = 'main'
        
        self.get_current_repo_info()
        
        self.gh1 = [
            'https://gh.927223.xyz/https://raw.githubusercontent.com',
            'https://gitdl.cn/https://raw.githubusercontent.com',
            'https://ghproxy.net/https://raw.githubusercontent.com',
            'https://github.moeyy.xyz/https://raw.githubusercontent.com',
            'https://gh-proxy.com/https://raw.githubusercontent.com',
            'https://ghproxy.cc/https://raw.githubusercontent.com',
            'https://raw.yzuu.cf',
            'https://raw.nuaa.cf',
            'https://raw.kkgithub.com',
            'https://mirror.ghproxy.com/https://raw.githubusercontent.com',
            'https://gh.llkk.cc/https://raw.githubusercontent.com',
            'https://gh.ddlc.top/https://raw.githubusercontent.com',
            'https://gh-proxy.llyke.com/https://raw.githubusercontent.com',
        ]

    def get_current_repo_info(self):
        """获取当前仓库信息"""
        github_repository = os.getenv('GITHUB_REPOSITORY', '')
        if github_repository:
            self.username, self.repo_name = github_repository.split('/')
        else:
            self.repo_name = os.path.basename(os.getcwd())
            self.username = 'github'
        
        # 修复：在slot中包含repo目录路径
        self.slot = f'{self.mirror_proxy}/{self.username}/{self.repo_name}/{self.main_branch}/{self.repo}'
        print(f"当前仓库: {self.username}/{self.repo_name}")
        print(f"资源路径: {self.slot}")

    def safe_request(self, url, method='GET', **kwargs):
        """安全的请求方法，处理超时参数"""
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        # 确保timeout是数字类型
        if isinstance(kwargs['timeout'], str):
            kwargs['timeout'] = float(kwargs['timeout'])
        return self.s.request(method, url, **kwargs)

    def file_hash(self, filepath):
        with open(filepath, 'rb') as f:
            file_contents = f.read()
            return hashlib.sha256(file_contents).hexdigest()

    def remove_duplicates(self, folder_path):
        folder_path = Path(folder_path)
        jar_folder = f'{folder_path}/jar'
        excludes = {'.json', '.git', 'jar', '.idea', 'ext', '.DS_Store', '.md'}
        files_info = {}

        self.rename_jar_suffix(jar_folder)

        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix not in excludes:
                file_size = file_path.stat().st_size
                file_hash = self.file_hash(file_path)
                files_info[file_path.name] = {'path': str(file_path), 'size': file_size, 'hash': file_hash}

        keep_files = []
        for file_name, info in sorted(files_info.items(), key=lambda item: item[1]['size']):
            if not keep_files or abs(info['size'] - files_info[keep_files[-1]]['size']) > self.size_tolerance:
                keep_files.append(file_name)
                self.remove_all_except_jar(jar_folder)
            else:
                os.remove(info['path'])
                self.remove_jar_file(jar_folder, file_name.replace('.txt', f'{self.jar_suffix}'))

        keep_files.sort()
        return keep_files

    def rename_jar_suffix(self, jar_folder):
        if not os.path.exists(jar_folder):
            return
        for root, dirs, files in os.walk(jar_folder):
            for file in files:
                old_file = os.path.join(root, file)
                new_file = os.path.join(root, os.path.splitext(file)[0] + f'.{self.jar_suffix}')
                if old_file != new_file:
                    os.rename(old_file, new_file)

    def remove_all_except_jar(self, jar_folder):
        if not os.path.exists(jar_folder):
            return
        for file_name in os.listdir(jar_folder):
            full_path = os.path.join(jar_folder, file_name)
            if os.path.isfile(full_path):
                _, file_extension = os.path.splitext(file_name)
                if file_extension != f'.{self.jar_suffix}':
                    self.remove_jar_file(jar_folder, file_name)

    def remove_jar_file(self, jar_folder, file_name):
        jar_file_path = os.path.join(jar_folder, file_name)
        if os.path.isfile(jar_file_path):
            os.remove(jar_file_path)

    def remove_emojis(self, text):
        emoji_pattern = re.compile("["
                                   u"\U0001F600-\U0001F64F"
                                   u"\U0001F300-\U0001F5FF"
                                   u"\U0001F680-\U0001F6FF"
                                   u"\U0001F1E0-\U0001F1FF"
                                   "]+", flags=re.UNICODE)
        text = text.replace('/', '_').replace('多多', '').replace('┃', '').replace('线路', '').replace('匚','').strip()
        return emoji_pattern.sub('', text)

    def json_compatible(self, text):
        """JSON兼容性处理"""
        if not text:
            return "{}"
        
        # 移除BOM头
        if text.startswith('\ufeff'):
            text = text[1:]
        
        # 移除注释
        lines = []
        for line in text.split('\n'):
            line = line.split('//')[0].strip()
            if line:
                lines.append(line)
        text = ''.join(lines)
        
        # 修复常见的JSON格式错误
        text = text.replace("'", '"')
        text = re.sub(r'(\w+):', r'"\1":', text)  # 将 key: 转换为 "key":
        
        return text

    def ghproxy(self, text):
        """替换ghproxy"""
        proxies = [
            'https://ghproxy.net/',
            'https://ghproxy.com/', 
            'https://gh-proxy.com/',
            'https://mirror.ghproxy.com/'
        ]
        for proxy in proxies:
            text = text.replace(proxy, 'https://gh.927223.xyz/')
        return text

    def set_hosts(self):
        """设置hosts（可选）"""
        pass

    def picparse(self, url):
        """解析图片中的base64数据"""
        try:
            r = self.safe_request(url, timeout=10.0)
            pattern = r'([A-Za-z0-9+/]+={0,2})'
            matches = re.findall(pattern, r.text)
            if matches:
                decoded_data = base64.b64decode(matches[-1])
                return decoded_data.decode('utf-8')
        except Exception as e:
            print(f"图片解析失败: {e}")
        return ""

    def js_render(self, url):
        """JS渲染处理"""
        try:
            # 使用多个JS渲染服务尝试
            proxies = [
                f'http://lige.unaux.com/?url={url}',
                f'https://api.94speed.com/web/parse?url={url}',
            ]
            
            for proxy_url in proxies:
                try:
                    r = self.safe_request(proxy_url, timeout=15.0)
                    if r.status_code == 200 and r.text.strip():
                        return r.text
                except:
                    continue
                    
        except Exception as e:
            print(f"JS渲染失败: {e}")
        return ""

    def get_jar(self, name, url, text):
        """获取jar文件"""
        try:
            pattern = r'\"spider\":\s*\"([^\"]+)\"'
            matches = re.search(pattern, text)
            if matches:
                jar_url = matches.group(1).replace('./', f'{url}/').split(';')[0]
                jar_name = f'{name}.{self.jar_suffix}'
                
                print(f"下载Jar文件: {jar_url}")
                r = self.safe_request(jar_url, timeout=15.0)
                
                os.makedirs(f'{self.repo}/jar', exist_ok=True)
                jar_path = f'{self.repo}/jar/{jar_name}'
                with open(jar_path, 'wb') as f:
                    f.write(r.content)
                
                # 替换文本中的jar路径 - 修复：包含repo目录路径
                new_jar_url = f'{self.slot}/jar/{jar_name}'
                text = text.replace(matches.group(1), new_jar_url)
                print(f"Jar文件已更新: {new_jar_url}")
                
        except Exception as e:
            print(f'【jar下载失败】{name} error:{e}')
        return text

    def download(self, url, name, filename, cang=True):
        """下载单个线路"""
        item = {}
        try:
            print(f"开始下载【线路】{name}: {url}")
            path = os.path.dirname(url)
            
            # 尝试直接请求
            r = self.safe_request(url, timeout=self.timeout)
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}")
                
            content = r.text
            
            # 检查是否是有效的配置
            if 'searchable' not in content:
                print(f"【{name}】直接请求无searchable字段，尝试JS渲染")
                content = self.js_render(url)
                if not content or 'searchable' not in content:
                    print(f"【{name}】JS渲染无searchable字段，尝试图片解析")
                    content = self.picparse(url)
                    if not content or 'searchable' not in content:
                        raise Exception("无法获取有效的配置内容")
            
            # 处理内容
            content = content.replace('./', f'{path}/')
            content = self.ghproxy(content)
            content = self.get_jar(name, url, content)
            
            # 保存文件
            with open(f'{self.repo}{self.sep}{filename}', 'w+', encoding='utf-8') as f:
                f.write(content)
            
            pipes.add(name)
            print(f"【线路】{name} 下载成功")
            
            # 添加到items列表 - 修复：URL包含repo目录路径
            if cang:
                item['name'] = name
                item['url'] = f'{self.slot}/{filename}'
                items.append(item)
                
        except Exception as e:
            print(f"【线路】{name}: {url} 下载错误：{e}")

    def down(self, data, s_name):
        """下载单仓"""
        global items
        items = []
        
        urls = data.get("urls") or data.get("sites") or []
        if not urls:
            print(f"【{s_name}】未找到有效的urls或sites字段")
            return
            
        print(f"【{s_name}】找到 {len(urls)} 个线路")
        
        for u in urls:
            name = u.get("name", "").strip()
            url = u.get("url", "").strip()
            if not name or not url:
                continue
                
            name = self.remove_emojis(name)
            filename = f'{name}.txt'
            
            if name in pipes:
                print(f"【线路】{name} 已存在，跳过")
                continue
                
            self.download(url, name, filename)
        
        # 生成单仓配置文件
        if items:
            newJson = {'urls': items}
            with open(f'{self.repo}{self.sep}{s_name}', 'w+', encoding='utf-8') as f:
                json.dump(newJson, f, ensure_ascii=False, indent=2)
            print(f"【单仓】{s_name} 生成成功，包含 {len(items)} 个线路")

    def all(self):
        """生成all.json"""
        if not os.path.exists(self.repo):
            print(f"目录 {self.repo} 不存在")
            return
            
        files = [f for f in os.listdir(self.repo) if f.endswith('.txt')]
        if not files:
            print("未找到任何线路文件")
            return
            
        items = []
        for file in files:
            item = {
                'name': file.split('.txt')[0],
                'url': f'{self.slot}/{file}'  # 修复：URL包含repo目录路径
            }
            items.append(item)
        
        newJson = {'urls': items}
        with open(f'{self.repo}{self.sep}all.json', 'w+', encoding='utf-8') as f:
            json.dump(newJson, f, ensure_ascii=False, indent=2)
        print(f"【all.json】生成成功，包含 {len(items)} 个线路")

    def read_urls_from_file(self):
        """从data/url.txt读取URL配置"""
        urls = []
        try:
            if not os.path.exists('data/url.txt'):
                print("data/url.txt 文件不存在")
                return urls
                
            with open('data/url.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        name, url = line.split(':', 1)
                        urls.append({
                            'name': name.strip(), 
                            'url': url.strip()
                        })
            print(f"从data/url.txt读取到 {len(urls)} 个配置源")
            return urls
        except Exception as e:
            print(f"读取data/url.txt失败: {e}")
            return []

    def process_single_source(self, name, url):
        """处理单个配置源"""
        print(f"\n====== 处理配置源: {name} ======")
        
        content = ""
        # 尝试多种方式获取内容
        try:
            # 1. 直接请求
            r = self.safe_request(url, timeout=10.0)
            if r.status_code == 200:
                content = r.text
                print(f"【{name}】直接请求成功")
        except Exception as e:
            print(f"【{name}】直接请求失败: {e}")
        
        # 2. 如果直接请求失败，尝试JS渲染
        if not content:
            print(f"【{name}】尝试JS渲染...")
            content = self.js_render(url)
            if content:
                print(f"【{name}】JS渲染成功")
        
        # 3. 如果还是失败，尝试图片解析
        if not content:
            print(f"【{name}】尝试图片解析...")
            content = self.picparse(url)
            if content:
                print(f"【{name}】图片解析成功")
        
        if not content:
            print(f"【{name}】所有获取方式都失败，跳过")
            return
        
        # 检查是否是线路配置（包含searchable字段）
        if 'searchable' in content:
            print(f"【{name}】识别为线路配置")
            filename = f'{name}.txt'
            try:
                path = os.path.dirname(url)
                content = content.replace('./', f'{path}/')
                content = self.ghproxy(content)
                content = self.get_jar(name, url, content)
                
                with open(f'{self.repo}{self.sep}{filename}', 'w+', encoding='utf-8') as f:
                    f.write(content)
                print(f"【{name}】线路配置保存成功")
            except Exception as e:
                print(f"【{name}】线路配置保存失败: {e}")
            return
        
        # 尝试解析为JSON配置
        try:
            # 先进行JSON兼容处理
            json_text = self.json_compatible(content)
            data = json.loads(json_text)
            print(f"【{name}】JSON解析成功")
            
            # 判断是多仓还是单仓
            if 'storeHouse' in data:
                print(f"【{name}】识别为多仓配置")
                self.process_storehouse(name, data)
            else:
                print(f"【{name}】识别为单仓配置")
                self.down(data, f'{name}.json')
                
        except json.JSONDecodeError as e:
            print(f"【{name}】JSON解析失败，内容前100字符: {content[:100]}...")
            print(f"JSON错误: {e}")
        except Exception as e:
            print(f"【{name}】处理失败: {e}")

    def process_storehouse(self, name, data):
        """处理多仓配置"""
        storehouse = data.get('storeHouse', [])
        if not storehouse:
            print(f"【{name}】多仓配置为空")
            return
            
        items = []
        count = 0
        
        for source in storehouse[:self.num]:  # 限制数量
            s_name = source.get('sourceName', '').strip()
            s_url = source.get('sourceUrl', '').strip()
            
            if not s_name or not s_url:
                continue
                
            s_name = self.remove_emojis(s_name)
            filename = f'{s_name}.json'
            
            print(f"【多仓子源】{s_name}: {s_url}")
            
            # 这里简化处理，直接保存子源URL
            items.append({
                'sourceName': s_name,
                'sourceUrl': s_url  # 保持原始URL，不替换
            })
            count += 1
        
        if items:
            result = {'storeHouse': items}
            with open(f'{self.repo}{self.sep}{name}.json', 'w+', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"【{name}】多仓配置保存成功，包含 {count} 个子源")

    def batch_download_urls(self):
        """批量下载配置源"""
        print('=' * 50)
        print('开始处理在线接口')
        print('=' * 50)
        
        urls = self.read_urls_from_file()
        if not urls:
            print("未找到有效的配置源")
            return
            
        for url_info in urls:
            self.process_single_source(url_info['name'], url_info['url'])

    def mirror_init(self):
        """初始化镜像配置"""
        mirrors = {
            1: 'https://gh.927223.xyz/https://raw.githubusercontent.com',
            2: 'https://gitdl.cn/https://raw.githubusercontent.com',
            3: 'https://ghproxy.net/https://raw.githubusercontent.com',
            4: 'https://github.moeyy.xyz/https://raw.githubusercontent.com',
            5: 'https://gh-proxy.com/https://raw.githubusercontent.com',
            6: 'https://ghproxy.cc/https://raw.githubusercontent.com',
            7: 'https://raw.yzuu.cf',
            8: 'https://raw.nuaa.cf',
            9: 'https://raw.kkgithub.com',
        }
        
        self.mirror_proxy = mirrors.get(self.mirror, mirrors[1])
        # 修复：在slot中包含repo目录路径
        self.slot = f'{self.mirror_proxy}/{self.username}/{self.repo_name}/{self.main_branch}/{self.repo}'
        print(f"使用镜像: {self.mirror_proxy}")

    def run(self):
        """主运行函数"""
        start_time = time.time()
        
        self.mirror_init()
        
        # 创建必要的目录
        os.makedirs(self.repo, exist_ok=True)
        os.makedirs(f'{self.repo}/jar', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        # 执行下载和处理
        self.batch_download_urls()
        self.all()
        
        end_time = time.time()
        print(f'\n处理完成，耗时: {end_time - start_time:.2f} 秒')
        print('\n' + '=' * 50)
        print('影视仓APP配置接口:')
        print(f'{self.slot}/all.json')
        print(f'{self.slot}/tvbox.json')
        print('=' * 50)


if __name__ == '__main__':
    # 从环境变量获取参数，确保类型正确
    repo = os.getenv('repo', 'tvbox')
    target = os.getenv('target')
    num = int(os.getenv('num', '10'))
    timeout = float(os.getenv('timeout', '10.0'))  # 默认超时改为10秒
    mirror = int(os.getenv('mirror', '1'))
    jar_suffix = os.getenv('jar_suffix', 'jar')
    
    print(f"启动参数: repo={repo}, num={num}, timeout={timeout}, mirror={mirror}")
    
    GetSrc(
        repo=repo, 
        num=num, 
        target=target, 
        timeout=timeout, 
        mirror=mirror, 
        jar_suffix=jar_suffix
    ).run()