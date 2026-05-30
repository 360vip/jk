#!/usr/bin/env python3
import requests
import os
import time
import concurrent.futures
import re
import json
from pathlib import Path
from urllib.parse import urlparse

def read_urls_from_file(file_path):
    """从文件中读取包含https://的网址"""
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if 'https://' in line:
                    # 提取https://开头的完整URL
                    start_index = line.find('https://')
                    if start_index != -1:
                        url = line[start_index:].split()[0]  # 取第一个空格前的部分
                        # 确保URL以https://开头且包含域名
                        if url.startswith('https://') and len(url) > 10:
                            # 如果URL以/结尾，去掉结尾的/
                            if url.endswith('/'):
                                url = url[:-1]
                            urls.append(url)
        print(f"从文件中读取到 {len(urls)} 个URL")
        return urls
    except FileNotFoundError:
        print(f"错误: 文件 {file_path} 不存在")
        return []
    except Exception as e:
        print(f"读取文件时出错: {e}")
        return []

def test_url_speed(base_url, timeout=5):
    """
    测试URL访问速度和有效性
    通过访问GitHub raw文件来验证代理是否有效
    """
    # 使用稳定的测试文件
    github_path = "https://raw.githubusercontent.com/vipxb/EPG-Server/main/README.md"
    test_url = f"{base_url}/{github_path}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        print(f"测试代理: {base_url}")
        print(f"测试URL: {test_url}")
        
        start_time = time.time()
        
        # 允许重定向，设置超时
        response = requests.get(
            test_url, 
            headers=headers, 
            timeout=timeout,
            allow_redirects=True,
            verify=True
        )
        response_time = time.time() - start_time
        
        print(f"HTTP状态码: {response.status_code}")
        print(f"响应时间: {response_time:.2f}秒")
        
        # 检查状态码（2xx或3xx都算成功）
        if 200 <= response.status_code < 400:
            content_length = len(response.content)
            print(f"内容大小: {content_length} 字节")
            
            # 检查内容是否有效
            if content_length > 0:
                # 检查是否是有效的README内容（应该包含特定关键词）
                content_text = response.text.lower()
                
                # 检查是否是错误页面
                error_keywords = [
                    'error', 'not found', '404', '502', '503', 
                    'access denied', 'forbidden', 'bad gateway',
                    'timeout', 'service unavailable', 'internal server error'
                ]
                
                is_error_page = any(keyword in content_text for keyword in error_keywords)
                
                # 检查是否是有效的README（应该包含epg、server等相关内容）
                valid_keywords = ['epg', 'server', 'readme', '#', 'github']
                has_valid_content = any(keyword in content_text for keyword in valid_keywords)
                
                if not is_error_page and has_valid_content and content_length > 100:
                    print(f"✓ 代理有效: {base_url}")
                    print(f"  - 响应时间: {response_time:.2f}秒")
                    print(f"  - 内容大小: {content_length}字节")
                    return True, response_time
                elif not is_error_page and content_length > 500:
                    # 即使没有特定关键词，如果内容足够大也可能是有效的
                    print(f"✓ 代理有效（内容较大）: {base_url}")
                    print(f"  - 响应时间: {response_time:.2f}秒")
                    print(f"  - 内容大小: {content_length}字节")
                    return True, response_time
                else:
                    print(f"✗ 代理返回错误页面: {base_url}")
                    print(f"  - 原因: {'错误关键词' if is_error_page else '内容无效'}")
                    return False, response_time
            else:
                print(f"✗ 代理返回空内容: {base_url}")
                return False, response_time
        else:
            print(f"✗ 代理返回错误状态码: {response.status_code}")
            return False, response_time
            
    except requests.exceptions.Timeout:
        print(f"✗ 代理超时 (>{timeout}秒): {base_url}")
        return False, timeout
    except requests.exceptions.ConnectionError as e:
        print(f"✗ 连接错误: {base_url} - {str(e)[:50]}")
        return False, timeout
    except requests.exceptions.SSLError as e:
        print(f"✗ SSL错误: {base_url} - {str(e)[:50]}")
        return False, timeout
    except requests.exceptions.TooManyRedirects:
        print(f"✗ 重定向过多: {base_url}")
        return False, timeout
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求失败: {base_url} - {str(e)[:50]}")
        return False, timeout
    except Exception as e:
        print(f"✗ 测试异常: {base_url} - {str(e)[:50]}")
        return False, timeout

def test_single_proxy_multiple(base_url, timeout=5, retries=2):
    """
    对单个代理进行多次测试，取平均响应时间
    提高测试准确性
    """
    print(f"\n开始测试代理: {base_url}")
    print("-" * 50)
    
    success_times = []
    failed_count = 0
    
    for attempt in range(1, retries + 1):
        print(f"第 {attempt}/{retries} 次测试...")
        is_valid, response_time = test_url_speed(base_url, timeout)
        
        if is_valid:
            success_times.append(response_time)
            print(f"✓ 第{attempt}次成功: {response_time:.2f}秒")
        else:
            failed_count += 1
            print(f"✗ 第{attempt}次失败")
        
        # 测试间隔，避免请求过于频繁
        if attempt < retries:
            time.sleep(1)
    
    # 判断代理是否有效（至少成功1次）
    if success_times:
        avg_time = sum(success_times) / len(success_times)
        success_rate = (len(success_times) / retries) * 100
        
        print(f"\n代理测试总结:")
        print(f"  - 成功次数: {len(success_times)}/{retries}")
        print(f"  - 成功率: {success_rate:.1f}%")
        print(f"  - 平均响应时间: {avg_time:.2f}秒")
        print(f"  - 最快响应: {min(success_times):.2f}秒")
        print(f"  - 最慢响应: {max(success_times):.2f}秒")
        
        # 成功率 >= 50% 认为有效
        return True, avg_time, success_rate
    else:
        print(f"\n代理测试失败: 全部 {retries} 次测试均失败")
        return False, timeout, 0

def test_urls_parallel(urls, max_workers=5, timeout=5, retries=2):
    """并行测试URL，返回有效的URL及其详细信息"""
    valid_urls_info = []
    
    print(f"\n开始并行测试 {len(urls)} 个代理...")
    print(f"超时设置: {timeout}秒")
    print(f"每个代理测试次数: {retries}")
    print(f"并行线程数: {max_workers}")
    print("=" * 60)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 为每个URL创建测试任务
        future_to_url = {
            executor.submit(test_single_proxy_multiple, url, timeout, retries): url 
            for url in urls
        }
        
        # 收集结果
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                is_valid, avg_time, success_rate = future.result()
                if is_valid:
                    valid_urls_info.append((url, avg_time, success_rate))
                    print(f"\n✅ 代理有效: {url}")
                    print(f"   平均速度: {avg_time:.2f}秒, 成功率: {success_rate:.1f}%")
                else:
                    print(f"\n❌ 代理无效: {url}")
            except Exception as e:
                print(f"\n❌ 测试代理 {url} 时发生异常: {e}")
    
    return valid_urls_info

def test_urls_sequential(urls, timeout=5, retries=2):
    """顺序测试URL，返回有效的URL及其详细信息"""
    valid_urls_info = []
    
    print(f"\n开始顺序测试 {len(urls)} 个代理...")
    print(f"超时设置: {timeout}秒")
    print(f"每个代理测试次数: {retries}")
    print("=" * 60)
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] 测试代理")
        print("=" * 40)
        
        is_valid, avg_time, success_rate = test_single_proxy_multiple(url, timeout, retries)
        
        if is_valid:
            valid_urls_info.append((url, avg_time, success_rate))
            print(f"\n✅ 代理有效: {url}")
            print(f"   平均速度: {avg_time:.2f}秒, 成功率: {success_rate:.1f}%")
        else:
            print(f"\n❌ 代理无效: {url}")
        
        # 添加延迟避免请求过于频繁
        if i < len(urls):
            time.sleep(0.5)
    
    return valid_urls_info

def sort_urls_by_speed(valid_urls_info):
    """根据响应时间对URL进行排序（从快到慢）"""
    # 按平均响应时间排序
    return sorted(valid_urls_info, key=lambda x: x[1])

def save_valid_urls(valid_urls_info, output_file):
    """保存有效的URL到文件，按速度排序"""
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 保存简化列表（仅URL）
        with open(output_file, 'w', encoding='utf-8') as file:
            for url, avg_time, success_rate in valid_urls_info:
                file.write(f"{url}\n")
        
        # 保存详细报告
        report_file = output_file.replace('.txt', '_detail.json')
        detailed_results = [
            {
                'url': url,
                'avg_time': avg_time,
                'success_rate': success_rate,
                'rank': i+1
            }
            for i, (url, avg_time, success_rate) in enumerate(valid_urls_info)
        ]
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 成功保存 {len(valid_urls_info)} 个有效代理到 {output_file}")
        print(f"✅ 详细报告保存到 {report_file}")
        
        # 显示速度排名
        print("\n" + "=" * 70)
        print("代理速度排名 (从快到慢)")
        print("=" * 70)
        print(f"{'排名':<6} {'平均速度':<12} {'成功率':<10} {'代理URL'}")
        print("-" * 70)
        
        for i, (url, avg_time, success_rate) in enumerate(valid_urls_info, 1):
            print(f"{i:<6} {avg_time:<11.2f}秒 {success_rate:<9.1f}% {url}")
        
        # 显示最佳代理
        if valid_urls_info:
            best_url, best_time, best_rate = valid_urls_info[0]
            print("\n" + "=" * 70)
            print("🏆 最佳代理推荐")
            print("=" * 70)
            print(f"代理地址: {best_url}")
            print(f"平均响应时间: {best_time:.2f}秒")
            print(f"成功率: {best_rate:.1f}%")
            
    except Exception as e:
        print(f"保存文件时出错: {e}")

def replace_github_urls_with_proxy(content, proxy_url):
    """替换内容中的所有GitHub RAW链接，添加代理前缀"""
    
    def replace_url(match):
        url = match.group(0)
        # 如果URL已经包含代理前缀，先提取原始URL
        proxy_pattern = r'https?://[^/]+/https://raw\.githubusercontent\.com/'
        if re.match(proxy_pattern, url):
            # 提取原始GitHub URL
            original_url = 'https://raw.githubusercontent.com/' + url.split('https://raw.githubusercontent.com/')[-1]
            return f"{proxy_url}/{original_url}"
        # 如果是直接的GitHub URL
        elif 'https://raw.githubusercontent.com/' in url:
            return f"{proxy_url}/{url}"
        return url
    
    # 匹配所有https://开头的URL（包括可能带代理的）
    url_pattern = r'https://[^\s"\'<>]+'
    modified_content = re.sub(url_pattern, replace_url, content)
    
    return modified_content

def process_tvbox_files(fastest_proxy_url):
    """处理tvbox目录下所有包含GitHub RAW链接的文件"""
    print("\n" + "=" * 60)
    print("开始处理tvbox目录下的所有文件...")
    print("=" * 60)
    
    if not fastest_proxy_url:
        print("✗ 没有可用的最快代理URL")
        return False
    
    print(f"使用代理: {fastest_proxy_url}")
    
    # 查找所有文件
    source_dir = Path('tvbox')
    target_dir = Path('xl')
    
    if not source_dir.exists():
        print(f"✗ 源目录 {source_dir} 不存在")
        return False
    
    # 创建目标目录
    target_dir.mkdir(exist_ok=True)
    print(f"目标目录: {target_dir}")
    
    # 查找所有txt和json文件
    all_files = list(source_dir.glob('*.txt')) + list(source_dir.glob('*.json'))
    
    if not all_files:
        print("✗ tvbox目录下没有找到txt或json文件")
        return False
    
    processed_count = 0
    modified_count = 0
    
    for source_file in all_files:
        print(f"\n处理文件: {source_file.name}")
        
        try:
            # 读取源文件内容
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否包含GitHub RAW链接
            if 'https://raw.githubusercontent.com/' in content:
                print(f"  ✓ 发现GitHub RAW链接，正在替换...")
                
                # 替换所有GitHub链接
                modified_content = replace_github_urls_with_proxy(content, fastest_proxy_url)
                
                # 保存到xl目录
                target_file = target_dir / source_file.name
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                # 统计替换数量
                original_count = len(re.findall(r'https://raw\.githubusercontent\.com/', content))
                print(f"  ✓ 已替换 {original_count} 个GitHub RAW链接")
                print(f"  ✓ 已保存到: {target_file}")
                modified_count += 1
            else:
                # 没有GitHub链接，直接复制文件
                print(f"  - 未发现GitHub RAW链接，直接复制")
                target_file = target_dir / source_file.name
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            processed_count += 1
            
        except json.JSONDecodeError as e:
            # JSON文件格式错误，但仍然作为文本处理
            print(f"  ⚠ JSON解析错误: {e}，仍作为文本处理")
            try:
                if 'https://raw.githubusercontent.com/' in content:
                    modified_content = replace_github_urls_with_proxy(content, fastest_proxy_url)
                    target_file = target_dir / source_file.name
                    with open(target_file, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    processed_count += 1
            except Exception as e2:
                print(f"  ✗ 处理失败: {e2}")
                
        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
    
    print(f"\n" + "=" * 60)
    print(f"处理完成！共处理 {processed_count} 个文件，其中 {modified_count} 个文件被修改")
    print(f"所有文件已保存到 {target_dir} 目录")
    print("=" * 60)
    
    return True

def main():
    # 配置参数
    proxy_list_file = 'proxy/url.txt'  # 代理列表文件
    output_file = 'proxy/okdl.txt'     # 有效代理输出文件
    timeout = 5                         # 超时时间（秒），增加到5秒
    use_parallel = True                 # 是否使用并行测试
    max_workers = 5                     # 并行测试的最大线程数（减少到5避免被限制）
    retries = 2                         # 每个代理测试次数
    
    print("=" * 70)
    print("GitHub代理URL测试工具 - 优化版")
    print("=" * 70)
    print(f"测试文件: https://raw.githubusercontent.com/vipxb/EPG-Server/main/README.md")
    print(f"超时设置: {timeout}秒")
    print(f"测试模式: {'并行' if use_parallel else '顺序'}")
    print(f"每个代理测试次数: {retries}")
    print(f"并行线程数: {max_workers}")
    print("=" * 70)
    
    # 读取代理URL
    urls = read_urls_from_file(proxy_list_file)
    if not urls:
        print("没有找到有效的代理URL，程序退出")
        return
    
    print(f"\n待测试代理数量: {len(urls)}")
    
    # 测试URL
    if use_parallel and len(urls) > 1:
        valid_urls_info = test_urls_parallel(urls, max_workers, timeout, retries)
    else:
        valid_urls_info = test_urls_sequential(urls, timeout, retries)
    
    # 按速度排序
    sorted_urls = sort_urls_by_speed(valid_urls_info)
    
    # 保存有效的代理列表
    if sorted_urls:
        save_valid_urls(sorted_urls, output_file)
        
        # 使用最快的代理处理tvbox目录下的所有文件
        fastest_url = sorted_urls[0][0]
        fastest_time = sorted_urls[0][1]
        
        print(f"\n验证完成!")
        print(f"找到 {len(sorted_urls)} 个有效GitHub代理URL")
        print(f"最快代理: {fastest_url}")
        print(f"最快响应时间: {fastest_time:.2f}秒")
        
        if len(sorted_urls) > 1:
            print(f"最慢代理: {sorted_urls[-1][0]}")
            print(f"最慢响应时间: {sorted_urls[-1][1]:.2f}秒")
            
            # 计算平均响应时间
            avg_time = sum([t for _, t, _ in sorted_urls]) / len(sorted_urls)
            print(f"平均响应时间: {avg_time:.2f}秒")
        
        # 处理文件
        process_tvbox_files(fastest_url)
        
    else:
        print("\n验证完成! 没有找到有效的GitHub代理URL")
        
        # 如果没有任何有效URL，创建空文件
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write('# No valid proxy found\n')
            print("已创建空的输出文件")
        except Exception as e:
            print(f"创建空文件时出错: {e}")

if __name__ == "__main__":
    main()