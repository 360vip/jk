#!/usr/bin/env python3
"""
批量JSON格式转换脚本
将 xl 目录下的所有 txt 文件（JSON格式）转换为与 tt.json 相同的格式
从每个文件中读取数据，并从hmd.txt读取黑名单过滤站点
【修改】不限制站点数量，添加新的直播源配置（排在第一位），保留原有直播源
【增强】支持多种JSON变体格式，正确提取所有站点
"""

import json
import requests
import re
from datetime import datetime
import sys
import time
import os
import glob

class BbtvConverter:
    def __init__(self, source_url=None, source_file_path=None):
        self.source_url = source_url
        self.source_file_path = source_file_path
        self.source_data = None
        self.converted_data = None
        self.site_key_for_error = ""
        # 站点名称黑名单 - 从文件读取
        self.name_blacklist = []
        self.filtered_count = 0
        self.blacklist_file = "data/hmd.txt"
        
        # 要添加的直播源配置（将排在第一位）
        self.additional_live = {
            "name": "live",
            "type": 0,
            "url": "https://zb.hao123.qzz.io/lv/migutv.txt",
            "playerType": 1,
            "ua": "okhttp/3.15",
            "epg": "http://diyp.112114.xyz/?ch={name}&date={date}",
            "logo": "https://epg.112114.xyz/logo/{name}.png"
        }
        
    def load_blacklist(self):
        """从文件加载黑名单关键词"""
        print(f"📋 正在从 {self.blacklist_file} 加载黑名单关键词...")
        try:
            if not os.path.exists(self.blacklist_file):
                print(f"⚠️ 黑名单文件不存在: {self.blacklist_file}")
                return
                
            with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                self.name_blacklist = lines
                
            print(f"✅ 成功加载 {len(self.name_blacklist)} 个黑名单关键词")
        except Exception as e:
            print(f"❌ 加载黑名单文件失败: {e}")
            self.name_blacklist = []
        
    def fetch_bbtv_data(self):
        """从 URL 或本地文件获取 JSON 数据，支持带注释的JSON"""
        if self.source_url:
            print(f"📥 正在从 {self.source_url} 获取数据...")
            try:
                response = requests.get(self.source_url, timeout=30)
                response.raise_for_status()
                content = response.text
            except requests.exceptions.RequestException as e:
                print(f"❌ 获取数据失败: {e}")
                return False
        elif self.source_file_path:
            print(f"📁 正在从本地文件 {self.source_file_path} 读取数据...")
            try:
                with open(self.source_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                print(f"❌ 读取文件失败: {e}")
                return False
        else:
            print(f"❌ 没有指定数据源")
            return False
        
        # 移除各种注释
        cleaned_content = self._remove_all_comments(content)
        
        # 修复常见的JSON格式问题
        cleaned_content = self._fix_json_format(cleaned_content)
        
        try:
            self.source_data = json.loads(cleaned_content)
            sites_count = len(self.source_data.get('sites', [])) if self.source_data else 0
            print(f"✅ 成功解析文件，包含 {sites_count} 个站点")
            return True
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON解析失败: {e}")
            print("🔄 尝试激进的JSON修复...")
            
            # 尝试修复
            repaired_content = self._aggressive_json_fix(cleaned_content)
            try:
                self.source_data = json.loads(repaired_content)
                sites_count = len(self.source_data.get('sites', [])) if self.source_data else 0
                print(f"✅ JSON修复成功，包含 {sites_count} 个站点")
                return True
            except json.JSONDecodeError as e2:
                print(f"❌ JSON修复失败: {e2}")
                print("🔄 尝试提取sites数组...")
                
                # 尝试提取sites数组（增强版）
                extracted_data = self._extract_sites_array_enhanced(content)
                if extracted_data and extracted_data.get('sites'):
                    self.source_data = extracted_data
                    print(f"✅ 成功提取sites数组，包含 {len(self.source_data.get('sites', []))} 个站点")
                    return True
                    
                return False
    
    def _remove_all_comments(self, content):
        """移除所有类型的注释：//、##、#、/* */"""
        if not content:
            return content
        
        result = []
        in_string = False
        escape = False
        i = 0
        n = len(content)
        
        while i < n:
            ch = content[i]
            
            if escape:
                result.append(ch)
                escape = False
                i += 1
                continue
            
            if ch == '\\':
                result.append(ch)
                escape = True
                i += 1
                continue
            
            if ch == '"' and not escape:
                in_string = not in_string
                result.append(ch)
                i += 1
                continue
            
            if not in_string:
                # 检查 // 注释
                if ch == '/' and i + 1 < n and content[i + 1] == '/':
                    while i < n and content[i] not in '\n\r':
                        i += 1
                    continue
                
                # 检查 ## 注释
                if ch == '#' and i + 1 < n and content[i + 1] == '#':
                    while i < n and content[i] not in '\n\r':
                        i += 1
                    continue
                
                # 检查 # 注释（单独#）
                if ch == '#' and (i == 0 or content[i-1] in '\n\r'):
                    while i < n and content[i] not in '\n\r':
                        i += 1
                    continue
                
                # 检查 /* */ 注释
                if ch == '/' and i + 1 < n and content[i + 1] == '*':
                    i += 2
                    while i + 1 < n:
                        if content[i] == '*' and content[i + 1] == '/':
                            i += 2
                            break
                        i += 1
                    continue
            
            result.append(ch)
            i += 1
        
        return ''.join(result)
    
    def _fix_json_format(self, content):
        """修复常见的JSON格式问题"""
        # 移除BOM
        content = content.lstrip('\ufeff')
        
        # 修复换行导致的字段问题
        content = re.sub(r'"key":\s*"\\n\s*([^"]+)"', r'"key": "\1"', content)
        content = re.sub(r'"key":\s*"([^"]*\\n[^"]*)"', r'"key": "\1"', content)
        content = re.sub(r'\\n', '', content)
        
        # 修复缺失引号的键
        content = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        
        # 修复尾随逗号
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        content = re.sub(r',\s*,', ',', content)
        
        # 修复空数组
        content = re.sub(r'\[\s*\]', '[]', content)
        
        # 修复 lives: [[]] 问题
        content = re.sub(r'"lives"\s*:\s*\[\s*\[\s*\]\s*\]', '"lives": []', content)
        
        return content
    
    def _aggressive_json_fix(self, content):
        """激进的JSON修复"""
        content = self._fix_json_format(content)
        
        # 修复未闭合的字符串
        def fix_multiline_strings(match):
            s = match.group(0)
            s = s.replace('\n', '\\n').replace('\r', '\\r')
            return s
        
        content = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', fix_multiline_strings, content)
        
        return content
    
    def _extract_sites_array_enhanced(self, content):
        """增强版：从混乱的JSON中提取完整的sites数组"""
        try:
            # 首先尝试直接匹配sites数组
            sites_match = re.search(r'"sites"\s*:\s*\[', content, re.DOTALL)
            if not sites_match:
                return None
            
            start_pos = sites_match.end()
            brace_count = 1
            i = start_pos
            n = len(content)
            in_string = False
            escape = False
            
            # 找到匹配的结束括号
            while i < n and brace_count > 0:
                ch = content[i]
                
                if escape:
                    escape = False
                    i += 1
                    continue
                
                if ch == '\\':
                    escape = True
                    i += 1
                    continue
                
                if ch == '"' and not escape:
                    in_string = not in_string
                
                if not in_string:
                    if ch == '[':
                        brace_count += 1
                    elif ch == ']':
                        brace_count -= 1
                
                i += 1
            
            if brace_count != 0:
                return None
            
            sites_content = content[start_pos:i-1]
            
            # 解析sites数组中的每个对象
            sites = []
            obj_start = -1
            brace_count = 0
            in_string = False
            escape = False
            j = 0
            len_sites = len(sites_content)
            
            while j < len_sites:
                ch = sites_content[j]
                
                if escape:
                    escape = False
                    j += 1
                    continue
                
                if ch == '\\':
                    escape = True
                    j += 1
                    continue
                
                if ch == '"' and not escape:
                    in_string = not in_string
                
                if not in_string:
                    if ch == '{':
                        if brace_count == 0:
                            obj_start = j
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0 and obj_start != -1:
                            obj_str = sites_content[obj_start:j+1]
                            # 修复对象字符串
                            obj_str = self._fix_json_format(obj_str)
                            try:
                                site_obj = json.loads(obj_str)
                                if site_obj:
                                    sites.append(site_obj)
                            except:
                                # 尝试更激进的修复
                                try:
                                    obj_str_fixed = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', obj_str)
                                    site_obj = json.loads(obj_str_fixed)
                                    if site_obj:
                                        sites.append(site_obj)
                                except:
                                    pass
                            obj_start = -1
                
                j += 1
            
            if not sites:
                return None
            
            print(f"  📍 成功提取到 {len(sites)} 个站点对象")
            
            # 构建完整的数据结构
            result = {"sites": sites}
            
            # 提取其他字段
            other_fields = ['lives', 'parses', 'rules', 'flags', 'ijk', 'ads', 
                           'spider', 'wallpaper', 'doh', 'proxy', 'danmaku', 'logo',
                           'headers', 'notice', 'version']
            
            for field in other_fields:
                pattern = r'"' + re.escape(field) + r'"\s*:\s*'
                field_match = re.search(pattern, content, re.DOTALL)
                if field_match:
                    field_start = field_match.end()
                    
                    if content[field_start] == '"':
                        end_pos = field_start + 1
                        while end_pos < len(content):
                            if content[end_pos] == '"' and content[end_pos-1] != '\\':
                                break
                            end_pos += 1
                        field_value = content[field_start:end_pos+1]
                        try:
                            if field_value.startswith('"'):
                                field_value = field_value[1:-1]
                            result[field] = field_value
                        except:
                            pass
                    elif content[field_start] in ['[', '{']:
                        bracket_count = 1
                        end_pos = field_start + 1
                        bracket_char = content[field_start]
                        close_char = ']' if bracket_char == '[' else '}'
                        
                        while end_pos < len(content) and bracket_count > 0:
                            if content[end_pos] == bracket_char:
                                bracket_count += 1
                            elif content[end_pos] == close_char:
                                bracket_count -= 1
                            end_pos += 1
                        
                        field_content = content[field_start:end_pos]
                        field_content = self._fix_json_format(field_content)
                        try:
                            if field == 'lives' and field_content.strip() == '[[]]':
                                result[field] = []
                            else:
                                result[field] = json.loads(field_content)
                        except:
                            result[field] = []
            
            return result
            
        except Exception as e:
            print(f"  ❌ 提取sites数组失败: {e}")
            return None
    
    def _normalize_value(self, value):
        """标准化字段值 - 修复版本，安全处理各种类型"""
        if value is None:
            return None
            
        # 已经是数字类型，直接返回
        if isinstance(value, (int, float, bool)):
            return value
        
        # 字符串类型，尝试转换
        if isinstance(value, str):
            # 空字符串
            if not value:
                return None
            
            # 尝试转换为整数
            if value.isdigit():
                return int(value)
            
            # 尝试转换为浮点数（必须是有效的数字格式）
            try:
                # 检查是否是有效的浮点数格式（只包含数字、小数点、负号）
                # 排除像 '0-0-4.1' 这样的格式
                cleaned = value.strip()
                # 浮点数应该只包含数字、一个小数点、一个可选的负号
                if cleaned.count('.') <= 1:
                    # 移除负号后检查是否全是数字和小数点
                    test_str = cleaned.lstrip('-')
                    if test_str.replace('.', '').isdigit():
                        return float(cleaned)
            except (ValueError, TypeError):
                pass
            
            # 处理 "0" 和 "1" 作为数字（已经处理过了，但保留）
            if value in ['0', '1']:
                return int(value)
            
            # 无法转换，返回原字符串
            return value
        
        # 其他类型，直接返回
        return value
    
    def _is_blacklisted(self, site_name, site_key):
        """检查站点是否在黑名单中"""
        if not site_name and not site_key:
            return False
            
        site_name_lower = site_name.lower() if site_name else ""
        site_key_lower = site_key.lower() if site_key else ""
        
        for keyword in self.name_blacklist:
            if not keyword:
                continue
            keyword_lower = keyword.lower()
            if keyword_lower in site_name_lower:
                return True
            if keyword_lower in site_key_lower:
                return True
                
        return False
            
    def convert_to_tt_format(self):
        """转换为 tt.json 格式"""
        if not self.source_data:
            print("❌ 没有源数据，请先获取数据")
            return False
            
        print("🔄 正在转换为 tt.json 格式...")
        
        # 创建基础结构
        self.converted_data = {
            "sites": [],
            "version": [
                {
                    "number": "1.0.0",
                    "url": "",
                    "type": 0,
                    "text": f"自动更新于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ],
            "lives": [],
            "parses": [
                {
                    "name": "解析聚合",
                    "type": 3,
                    "url": "Demo"
                },
                {
                    "name": "Web聚合",
                    "type": 3,
                    "url": "Web"
                },
                {
                    "name": "Json轮询",
                    "type": 2,
                    "url": "Sequence"
                },
                {
                    "name": "Json并发",
                    "type": 2,
                    "url": "Parallel"
                }
            ],
            "rules": [],
            "flags": [],
            "ijk": [],
            "ads": [],
            "wallpaper": "",
            "warningText": "",
            "spider": ""
        }
        
        # 处理各个部分
        self._process_sites()
        self._process_version()
        self._process_lives()
        self._process_parses()
        self._process_rules()
        self._process_flags()
        self._process_ijk()
        self._process_other_fields()
        
        print(f"✅ 格式转换完成，总计 {len(self.converted_data['sites'])} 个站点（过滤掉 {self.filtered_count} 个黑名单站点）")
        print(f"✅ 直播源配置: {len(self.converted_data['lives'])} 个（新增1个到第一位）")
        return True
    
    def _process_version(self):
        """处理版本信息"""
        if "version" in self.source_data and self.source_data["version"]:
            version_data = self.source_data["version"]
            if isinstance(version_data, list) and version_data:
                version_data = version_data[0]
            elif isinstance(version_data, dict):
                pass
            else:
                version_data = {}
            
            self.converted_data["version"] = [{
                "number": version_data.get("number", "1.0.0"),
                "url": version_data.get("url", ""),
                "type": version_data.get("type", 0),
                "text": version_data.get("text", f"自动更新于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            }]
    
    def _process_lives(self):
        """处理直播源配置"""
        lives_list = []
        
        # 添加新的直播源
        lives_list.append(self.additional_live)
        print(f"  ➕ 已添加新直播源: {self.additional_live['name']}")
        
        # 保留原有的直播源
        if "lives" in self.source_data and self.source_data["lives"]:
            original_lives = self.source_data["lives"]
            if isinstance(original_lives, list):
                for live in original_lives:
                    if not live:
                        continue
                    if isinstance(live, list) and not live:
                        continue
                    if isinstance(live, dict):
                        if "name" not in live:
                            live["name"] = "直播源"
                        lives_list.append(live)
                        print(f"  ✓ 保留原直播源: {live.get('name', 'unknown')[:30]}")
            else:
                print(f"  ℹ️ 原有lives格式不是列表，跳过")
        else:
            print(f"  ℹ️ 源数据中没有lives配置")
        
        self.converted_data["lives"] = lives_list
    
    def _process_sites(self):
        """处理站点"""
        if "sites" not in self.source_data:
            print("⚠️ 源数据中没有sites字段")
            return
            
        site_count = 0
        filtered_sites = []
        error_count = 0
        total_sites = len(self.source_data["sites"])
        
        print(f"\n🔍 开始处理站点（共{total_sites}个，黑名单关键词{len(self.name_blacklist)}个）...")
        print(f"ℹ️ 站点数量不限制，将保留所有非黑名单站点")
        
        for idx, site in enumerate(self.source_data["sites"]):
            if not site:
                continue
            
            if not isinstance(site, dict):
                if hasattr(site, '__dict__'):
                    site = site.__dict__
                else:
                    error_count += 1
                    continue
            
            site_key = site.get("key", "")
            site_name = site.get("name", "")
            
            # 清理特殊字符
            if isinstance(site_key, str):
                site_key = site_key.replace('\n', '').replace('\r', '').strip()
            if isinstance(site_name, str):
                site_name = site_name.replace('\n', '').replace('\r', '').strip()
            
            if not site_key and not site_name:
                error_count += 1
                continue
            
            # 黑名单过滤
            if self._is_blacklisted(site_name, site_key):
                self.filtered_count += 1
                if len(filtered_sites) < 10:
                    filtered_sites.append(f"{site_name} [{site_key}]")
                continue
            
            cleaned_site = self._clean_site_config(site)
            if cleaned_site:
                self.converted_data["sites"].append(cleaned_site)
                site_count += 1
                
                if site_count % 50 == 0:
                    print(f"  ✓ 已处理 {site_count} 个站点...")
        
        # 显示结果
        if self.converted_data["sites"]:
            print(f"\n  ✅ 成功添加 {site_count} 个站点")
            if site_count > 0:
                print(f"  示例站点:")
                show_count = min(5, site_count)
                for i, site in enumerate(self.converted_data["sites"][:show_count], 1):
                    name = site.get('name', site.get('key', 'unknown'))
                    print(f"    {i}. {name}")
                if site_count > show_count:
                    print(f"    ... 等共 {site_count} 个")
        
        if filtered_sites:
            print(f"\n  🚫 已过滤黑名单站点 ({self.filtered_count}个)")
            for i, site in enumerate(filtered_sites[:10], 1):
                print(f"     {i}. {site[:60]}")
            if self.filtered_count > 10:
                print(f"     ... 等共 {self.filtered_count} 个")
        
        if error_count > 0:
            print(f"\n  ⚠️ 跳过 {error_count} 个无效站点")
                
        print(f"✅ 站点处理完成: 添加{site_count}个，过滤{self.filtered_count}个")
    
    def _clean_site_config(self, site):
        """清理站点配置 - 修复版本，安全处理字段值"""
        if "key" not in site:
            return None
        
        site_key = str(site["key"]).replace('\n', '').replace('\r', '').strip()
        site_name = site.get("name", site_key)
        if isinstance(site_name, str):
            site_name = site_name.replace('\n', '').replace('\r', '').strip()
        
        # 基础字段
        cleaned = {
            "key": site_key,
            "name": self._clean_site_name(site_name, site_key),
            "type": self._normalize_value(site.get("type", 3))
        }
        
        # 数字字段 - 安全处理
        numeric_fields = ["searchable", "quickSearch", "changeable", "filterable", 
                         "timeout", "playerType", "indexs", "gridview"]
        
        for field in numeric_fields:
            if field in site and site[field] is not None:
                normalized = self._normalize_value(site[field])
                if normalized is not None:
                    cleaned[field] = normalized
        
        # 字符串字段
        string_fields = ["api", "jar", "genre", "playurl"]
        for field in string_fields:
            if field in site and site[field] is not None:
                val = site[field]
                if isinstance(val, str):
                    val = val.replace('\n', '').replace('\r', '').strip()
                cleaned[field] = val
        
        # 处理 ext 字段
        if "ext" in site and site["ext"] is not None:
            cleaned_ext = self._clean_ext_config(site["ext"])
            if cleaned_ext:
                cleaned["ext"] = cleaned_ext
        
        # 处理 style 字段
        if "style" in site and site["style"]:
            cleaned["style"] = site["style"]
        
        # 处理 cookies/header
        if "cookies" in site and site["cookies"]:
            cleaned["cookies"] = site["cookies"]
        if "header" in site and site["header"]:
            cleaned["header"] = site["header"]
        
        # 处理 boot/core
        if "boot" in site:
            cleaned["boot"] = site["boot"]
        if "core" in site:
            cleaned["core"] = site["core"]
        
        # 处理 categories
        if "categories" in site and site["categories"]:
            cleaned["categories"] = site["categories"]
        
        # 处理 switchable
        if "switchable" in site:
            cleaned["switchable"] = self._normalize_value(site["switchable"])
        
        # 处理 gridview（可能是字符串如 "0-0-4.1"）
        if "gridview" in site and site["gridview"]:
            cleaned["gridview"] = site["gridview"]
        
        return cleaned
    
    def _clean_site_name(self, name, site_key):
        """清理站点名称 - 保留原始名称中的所有内容，只移除换行符和多余空格"""
        if not isinstance(name, str):
            return site_key
        
        # 只移除换行符、回车符和多余空格，完全保留原始内容
        # 包括表情符号、装饰字符、分隔符等全部保留
        name = name.replace('\n', ' ').replace('\r', ' ').strip()
        
        # 合并多个空格为一个空格（但保留其他所有字符）
        name = re.sub(r'\s+', ' ', name)
        
        # 如果清理后为空，使用站点key作为备选
        if not name or len(name.strip()) == 0:
            if site_key.startswith('csp_'):
                name = site_key[4:]
            elif site_key.endswith('zy'):
                name = site_key[:-2]
            else:
                name = site_key
        
        # 限制长度（增加到200以保留完整名称）
        name = name.strip()[:200]
        
        # 确保非空
        if not name:
            name = site_key[:50]
        
        return name
    
    def _clean_ext_config(self, ext):
        """清理 ext 配置"""
        if not ext:
            return None
        
        if isinstance(ext, str):
            return ext
        
        if isinstance(ext, dict):
            cleaned_ext = {}
            
            allowed_fields = ["danmu", "sp", "url", "host", "site", "filters", 
                            "sites", "catesSet", "tabsSet", "classes", "ver",
                            "site_urls", "url_key", "threadinfo", "appName",
                            "publicKey", "dataKey", "dataIv", "pkg", "version",
                            "decrypt", "cookie", "json", "appkey", "LoginPath",
                            "versionName", "package", "buildNumber", "buildSignature",
                            "siteKey", "listKey", "parsesKey", "keys", "abid", "pub"]
            
            for field in allowed_fields:
                if field in ext and ext[field] is not None:
                    cleaned_ext[field] = ext[field]
            
            return cleaned_ext if cleaned_ext else None
        
        return None
    
    def _process_parses(self):
        """处理解析线路"""
        if "parses" not in self.source_data:
            return
        
        for parse in self.source_data["parses"]:
            if not parse:
                continue
            if not isinstance(parse, dict):
                continue
            if "name" not in parse:
                continue
            
            cleaned_parse = {
                "name": parse["name"],
                "type": self._normalize_value(parse.get("type", 0)),
                "url": parse.get("url", "")
            }
            
            # 处理ext配置
            if "ext" in parse and parse["ext"]:
                ext_config = {}
                if isinstance(parse["ext"], dict):
                    if "header" in parse["ext"]:
                        ext_config["header"] = parse["ext"]["header"]
                    if "flag" in parse["ext"]:
                        ext_config["flag"] = parse["ext"]["flag"]
                if ext_config:
                    cleaned_parse["ext"] = ext_config
            
            self.converted_data["parses"].append(cleaned_parse)
    
    def _process_rules(self):
        """处理规则"""
        if "rules" not in self.source_data:
            return
        
        # 广告规则过滤关键词
        exclude_regex = ["更多", "请访问", "example", "社 區", "x u u", "直 播", "更 新",
                        "社 区", "有趣", "有 趣", "英皇体育", "全中文AV在线", "澳门皇冠赌场",
                        "哥哥快来", "美女荷官", "裸聊", "新片首发", "UUE29", "最 新"]
        
        for rule in self.source_data["rules"]:
            if not rule or not isinstance(rule, dict):
                continue
            
            # 检查是否是广告规则
            if "regex" in rule:
                skip = False
                for regex in rule.get("regex", []):
                    if regex in exclude_regex:
                        skip = True
                        break
                if skip:
                    continue
            
            # 转换规则格式
            if "hosts" in rule and "regex" in rule:
                for host in rule.get("hosts", []):
                    if host and host != "magnet":
                        cleaned_rule = {
                            "host": host,
                            "rule": rule.get("regex", [])
                        }
                        self.converted_data["rules"].append(cleaned_rule)
            elif "host" in rule and "rule" in rule:
                self.converted_data["rules"].append(rule)
            elif "hosts" in rule and "script" in rule:
                for host in rule.get("hosts", []):
                    if host:
                        cleaned_rule = {
                            "host": host,
                            "rule": rule.get("script", [])
                        }
                        self.converted_data["rules"].append(cleaned_rule)
    
    def _process_flags(self):
        """处理 flags"""
        if "flags" in self.source_data and self.source_data["flags"]:
            if isinstance(self.source_data["flags"], list):
                self.converted_data["flags"] = self.source_data["flags"]
    
    def _process_ijk(self):
        """处理 ijk 配置"""
        if "ijk" in self.source_data and self.source_data["ijk"]:
            if isinstance(self.source_data["ijk"], list):
                self.converted_data["ijk"] = self.source_data["ijk"]
                return
        
        # 默认配置
        self.converted_data["ijk"] = [
            {
                "group": "软解码",
                "options": [
                    {"category": 4, "name": "opensles", "value": "0"},
                    {"category": 4, "name": "overlay-format", "value": "842225234"},
                    {"category": 4, "name": "framedrop", "value": "1"},
                    {"category": 4, "name": "soundtouch", "value": "1"},
                    {"category": 4, "name": "start-on-prepared", "value": "1"},
                    {"category": 1, "name": "http-detect-range-support", "value": "0"},
                    {"category": 1, "name": "fflags", "value": "fastseek"},
                    {"category": 2, "name": "skip_loop_filter", "value": "48"},
                    {"category": 4, "name": "reconnect", "value": "1"},
                    {"category": 4, "name": "max-buffer-size", "value": "5242880"},
                    {"category": 4, "name": "enable-accurate-seek", "value": "0"},
                    {"category": 4, "name": "mediacodec", "value": "0"},
                    {"category": 4, "name": "mediacodec-auto-rotate", "value": "0"},
                    {"category": 4, "name": "mediacodec-handle-resolution-change", "value": "0"},
                    {"category": 4, "name": "mediacodec-hevc", "value": "0"},
                    {"category": 1, "name": "dns_cache_timeout", "value": "600000000"}
                ]
            },
            {
                "group": "硬解码",
                "options": [
                    {"category": 4, "name": "opensles", "value": "0"},
                    {"category": 4, "name": "overlay-format", "value": "842225234"},
                    {"category": 4, "name": "framedrop", "value": "1"},
                    {"category": 4, "name": "soundtouch", "value": "1"},
                    {"category": 4, "name": "start-on-prepared", "value": "1"},
                    {"category": 1, "name": "http-detect-range-support", "value": "0"},
                    {"category": 1, "name": "fflags", "value": "fastseek"},
                    {"category": 2, "name": "skip_loop_filter", "value": "48"},
                    {"category": 4, "name": "reconnect", "value": "1"},
                    {"category": 4, "name": "max-buffer-size", "value": "5242880"},
                    {"category": 4, "name": "enable-accurate-seek", "value": "0"},
                    {"category": 4, "name": "mediacodec", "value": "1"},
                    {"category": 4, "name": "mediacodec-auto-rotate", "value": "1"},
                    {"category": 4, "name": "mediacodec-handle-resolution-change", "value": "1"},
                    {"category": 4, "name": "mediacodec-hevc", "value": "1"},
                    {"category": 1, "name": "dns_cache_timeout", "value": "600000000"}
                ]
            }
        ]
    
    def _process_other_fields(self):
        """处理其他字段"""
        # ads
        if "ads" in self.source_data:
            if isinstance(self.source_data["ads"], list):
                self.converted_data["ads"] = self.source_data["ads"]
            elif isinstance(self.source_data["ads"], str):
                self.converted_data["ads"] = [self.source_data["ads"]]
        
        # wallpaper
        if "wallpaper" in self.source_data:
            self.converted_data["wallpaper"] = self.source_data["wallpaper"]
        
        # warningText
        if "warningText" in self.source_data:
            self.converted_data["warningText"] = self.source_data["warningText"]
        
        # spider
        if "spider" in self.source_data:
            self.converted_data["spider"] = self.source_data["spider"]
        
        # proxy 保留为规则
        if "proxy" in self.source_data and self.source_data["proxy"]:
            if isinstance(self.source_data["proxy"], list):
                proxy_rule = {
                    "host": "proxy",
                    "rule": self.source_data["proxy"]
                }
                existing = any(r.get("host") == "proxy" for r in self.converted_data["rules"])
                if not existing:
                    self.converted_data["rules"].append(proxy_rule)
    
    def save_converted_data(self, output_file):
        """保存转换后的数据"""
        if not self.converted_data:
            print("❌ 没有转换后的数据可保存")
            return False
            
        try:
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.converted_data, f, ensure_ascii=False, indent=2)
            print(f"✅ 转换后的数据已保存到 {output_file}")
            return True
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
            return False
    
    def validate_conversion(self):
        """验证转换结果"""
        if not self.converted_data:
            return False
        
        required_fields = ["sites", "version", "lives", "parses", "rules", "flags", "ijk"]
        for field in required_fields:
            if field not in self.converted_data:
                print(f"⚠️ 缺少字段: {field}")
        
        print(f"✅ 验证通过，包含 {len(self.converted_data['sites'])} 个站点，{len(self.converted_data['lives'])} 个直播源")
        return True

def process_single_file(input_file, output_dir):
    """处理单个文件"""
    print("\n" + "=" * 60)
    print(f"📄 处理文件: {input_file}")
    print("=" * 60)
    
    base_name = os.path.basename(input_file)
    
    converter = BbtvConverter(source_file_path=input_file)
    converter.load_blacklist()
    
    if not converter.fetch_bbtv_data():
        print(f"❌ 无法解析文件: {input_file}")
        return False
    
    if not converter.convert_to_tt_format():
        print(f"❌ 格式转换失败: {input_file}")
        return False
    
    converter.validate_conversion()
    
    output_file = os.path.join(output_dir, base_name)
    
    if not converter.save_converted_data(output_file):
        return False
    
    print(f"\n📊 文件统计:")
    print(f"   站点数量: {len(converter.converted_data['sites'])}")
    print(f"   过滤黑名单: {converter.filtered_count} 个站点")
    print(f"   直播源数量: {len(converter.converted_data['lives'])}")
    print(f"   解析线路: {len(converter.converted_data['parses'])}")
    print(f"   规则数量: {len(converter.converted_data['rules'])}")
    
    return True

def batch_convert():
    """批量转换 xl 目录下的所有 txt 文件"""
    input_dir = "xl"
    output_dir = "mybox"
    
    print("=" * 60)
    print("🎬 批量JSON格式转换工具")
    print("=" * 60)
    print(f"📁 输入目录: {input_dir}/")
    print(f"📁 输出目录: {output_dir}/")
    print("📺 直播源配置: 添加新源（排在第一位），保留原直播源")
    print("   新增源URL: https://zb.hao123.qzz.io/lv/migutv.txt")
    print("=" * 60)
    
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录不存在: {input_dir}/")
        sys.exit(1)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"✅ 创建输出目录: {output_dir}/")
    
    pattern = os.path.join(input_dir, "*.txt")
    txt_files = glob.glob(pattern)
    
    if not txt_files:
        print(f"❌ 在 {input_dir}/ 目录下未找到任何 .txt 文件")
        sys.exit(1)
    
    print(f"\n📋 找到 {len(txt_files)} 个 txt 文件:")
    for f in txt_files:
        print(f"   - {os.path.basename(f)}")
    print()
    
    success_count = 0
    fail_count = 0
    failed_files = []
    total_sites = 0
    
    for i, input_file in enumerate(txt_files, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(txt_files)}] 处理文件")
        
        if process_single_file(input_file, output_dir):
            success_count += 1
            output_file = os.path.join(output_dir, os.path.basename(input_file))
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_sites += len(data.get('sites', []))
            except:
                pass
        else:
            fail_count += 1
            failed_files.append(os.path.basename(input_file))
    
    print("\n" + "=" * 60)
    print("📊 批量转换完成!")
    print("=" * 60)
    print(f"✅ 成功: {success_count} 个文件")
    print(f"❌ 失败: {fail_count} 个文件")
    print(f"📈 总计保留站点: {total_sites} 个")
    
    if failed_files:
        print("\n失败的文件列表:")
        for f in failed_files:
            print(f"   - {f}")

def main():
    """主函数"""
    batch_convert()

if __name__ == "__main__":
    main()