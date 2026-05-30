#!/usr/bin/env python3
"""
批量JSON格式转换脚本
将 xl 目录下的所有 txt 文件（JSON格式）转换为与 tt.json 相同的格式
从每个文件中读取数据，并从hmd.txt读取黑名单过滤站点
【修改】不限制站点数量，添加新的直播源配置（排在第一位），保留原有直播源
【增强】支持更多JSON变体格式（##注释、格式错误的字段、嵌套空数组等）
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
        self.site_key_for_error = ""  # 用于错误处理的站点key
        # 站点名称黑名单 - 从文件读取
        self.name_blacklist = []
        self.filtered_count = 0  # 记录被过滤的站点数量
        self.blacklist_file = "data/hmd.txt"  # 黑名单文件路径
        
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
                print("  将使用默认空黑名单")
                return
                
            with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                # 读取所有行，去除空白行和空格
                lines = [line.strip() for line in f.readlines() if line.strip()]
                self.name_blacklist = lines
                
            print(f"✅ 成功加载 {len(self.name_blacklist)} 个黑名单关键词")
            if self.name_blacklist:
                print(f"  关键词: {', '.join(self.name_blacklist[:10])}{'...' if len(self.name_blacklist) > 10 else ''}")
                
        except Exception as e:
            print(f"❌ 加载黑名单文件失败: {e}")
            print("  将使用默认空黑名单")
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
        
        # 移除各种类型的注释
        cleaned_content = self._remove_all_comments(content)
        
        # 修复常见的JSON格式问题
        cleaned_content = self._fix_json_format(cleaned_content)
        
        try:
            self.source_data = json.loads(cleaned_content)
            if self.source_url:
                sites_count = len(self.source_data.get('sites', [])) if self.source_data else 0
                print(f"✅ 成功获取数据，包含 {sites_count} 个站点")
            else:
                sites_count = len(self.source_data.get('sites', [])) if self.source_data else 0
                print(f"✅ 成功解析文件，包含 {sites_count} 个站点")
            return True
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON解析失败: {e}")
            print("🔄 尝试激进的JSON修复...")
            
            # 尝试多种修复策略
            repaired_content = self._aggressive_json_fix(cleaned_content)
            try:
                self.source_data = json.loads(repaired_content)
                print(f"✅ JSON修复成功")
                sites_count = len(self.source_data.get('sites', [])) if self.source_data else 0
                print(f"   包含 {sites_count} 个站点")
                return True
            except json.JSONDecodeError as e2:
                print(f"❌ JSON修复仍然失败: {e2}")
                
                # 尝试提取sites数组
                print("🔄 尝试提取sites数组...")
                extracted_data = self._extract_sites_array(content)
                if extracted_data and extracted_data.get('sites'):
                    self.source_data = extracted_data
                    print(f"✅ 成功提取sites数组，包含 {len(self.source_data.get('sites', []))} 个站点")
                    return True
                    
                return False
    
    def _remove_all_comments(self, json_str):
        """移除所有类型的注释：//、/* */、##、#"""
        if not json_str:
            return json_str
        
        # 移除 ## 注释（某些文件使用）
        lines = json_str.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 处理行内的 ## 注释
            line = self._remove_inline_comment(line, '##')
            # 处理行内的 # 注释
            line = self._remove_inline_comment(line, '#')
            # 处理行内的 // 注释
            line = self._remove_inline_comment(line, '//')
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # 移除 /* */ 块注释
        result = re.sub(r'/\*.*?\*/', '', result, flags=re.DOTALL)
        
        return result
    
    def _remove_inline_comment(self, line, comment_marker):
        """移除行内注释，但保留字符串内的"""
        if not line:
            return line
        
        in_string = False
        string_char = None
        i = 0
        line_len = len(line)
        comment_pos = -1
        
        while i < line_len:
            char = line[i]
            
            # 处理转义字符
            if char == '\\' and i + 1 < line_len:
                i += 2
                continue
            
            # 字符串开始/结束
            if char in ['"', "'"]:
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
            
            # 查找不在字符串中的注释标记
            elif not in_string and line.startswith(comment_marker, i):
                comment_pos = i
                break
            
            i += 1
        
        if comment_pos != -1:
            line = line[:comment_pos]
        
        return line.rstrip()
    
    def _fix_json_format(self, content):
        """修复常见的JSON格式问题"""
        # 修复缺失引号的键（简单键名）
        content = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        
        # 修复尾随逗号
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        
        # 修复空数组问题
        content = re.sub(r'\[\s*\]', '[]', content)
        
        # 修复嵌套空数组 lives: [[]] -> lives: []
        content = re.sub(r'"lives"\s*:\s*\[\s*\[\s*\]\s*\]', '"lives": []', content)
        
        # 修复换行符导致的字段问题（如 "key": "\nconfig"）
        content = re.sub(r'"key":\s*"\\n\s*([^"]+)"', r'"key": "\1"', content)
        
        # 移除BOM
        content = content.lstrip('\ufeff')
        
        return content
    
    def _aggressive_json_fix(self, content):
        """激进的JSON修复，处理各种格式问题"""
        # 先移除所有注释
        content = self._remove_all_comments(content)
        
        # 修复缺失的引号
        content = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        
        # 修复单引号为双引号
        content = re.sub(r"'([^']*)'", r'"\1"', content)
        
        # 修复尾随逗号
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        content = re.sub(r',\s*,', ',', content)
        
        # 修复空数组
        content = re.sub(r'\[\s*\]', '[]', content)
        
        # 修复 lives: [[]] 问题
        content = re.sub(r'"lives"\s*:\s*\[\s*\[\s*\]\s*\]', '"lives": []', content)
        
        # 修复换行导致的字段问题
        content = re.sub(r'"key":\s*"\\n\s*([^"]+)"', r'"key": "\1"', content)
        content = re.sub(r'"key":\s*"([^"]*\\n[^"]*)"', r'"key": "\1"', content)
        
        # 移除未闭合的字符串中的换行符
        def fix_multiline_strings(match):
            s = match.group(0)
            s = s.replace('\n', '\\n').replace('\r', '\\r')
            return s
        
        # 查找并修复多行字符串（简单处理）
        content = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', fix_multiline_strings, content)
        
        return content
    
    def _extract_sites_array(self, content):
        """从混乱的JSON中提取sites数组"""
        try:
            # 查找sites数组
            sites_match = re.search(r'"sites"\s*:\s*\[(.*?)(?=\]\s*[,}])', content, re.DOTALL)
            if not sites_match:
                return None
            
            sites_content = sites_match.group(1)
            
            # 修复sites内容中的换行和特殊字符
            # 分割成独立的site对象
            sites = []
            brace_count = 0
            current_site = ""
            in_string = False
            
            for char in sites_content:
                if char == '"' and not in_string:
                    in_string = True
                elif char == '"' and in_string:
                    in_string = False
                
                if not in_string:
                    if char == '{':
                        if brace_count == 0:
                            current_site = ""
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            current_site += char
                            # 尝试解析这个site对象
                            try:
                                # 修复site对象中的问题
                                fixed_site = self._fix_json_format(current_site)
                                site_obj = json.loads(fixed_site)
                                sites.append(site_obj)
                            except:
                                # 如果解析失败，尝试更激进的修复
                                try:
                                    # 替换换行符
                                    fixed_site = current_site.replace('\n', '\\n')
                                    fixed_site = self._fix_json_format(fixed_site)
                                    site_obj = json.loads(fixed_site)
                                    sites.append(site_obj)
                                except:
                                    pass
                            current_site = ""
                            continue
                
                if brace_count > 0:
                    current_site += char
            
            if sites:
                # 构建完整的数据结构
                result = {"sites": sites}
                
                # 尝试提取其他字段
                for field in ['lives', 'parses', 'rules', 'flags', 'ijk', 'ads', 'spider', 'wallpaper', 'doh']:
                    field_match = re.search(r'"' + field + r'"\s*:\s*(\[[^\]]*\]|\{[^\}]*\}|"[^"]*")', content, re.DOTALL)
                    if field_match:
                        try:
                            field_content = field_match.group(1)
                            # 修复 lives: [[]] 问题
                            if field == 'lives' and field_content.strip() == '[[]]':
                                result[field] = []
                            else:
                                field_content = self._fix_json_format(field_content)
                                result[field] = json.loads(field_content)
                        except:
                            if field == 'lives':
                                result[field] = []
                            else:
                                result[field] = []
                
                return result
                
        except Exception as e:
            print(f"  提取sites数组失败: {e}")
        
        return None
    
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
        
        # 创建基础结构（与 tt.json 相同）
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
        
        # 1. 处理所有站点
        self._process_sites()
        
        # 2. 处理版本信息
        self._process_version()
        
        # 3. 处理直播源
        self._process_lives()
        
        # 4. 处理解析线路
        self._process_parses()
        
        # 5. 处理规则
        self._process_rules()
        
        # 6. 处理 flags
        self._process_flags()
        
        # 7. 处理 ijk 配置
        self._process_ijk()
        
        # 8. 处理其他字段
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
        """处理直播源配置：保留原有配置，并在第一位添加新的直播源"""
        lives_list = []
        
        # 首先添加新的直播源（排在第一位）
        lives_list.append(self.additional_live)
        print(f"  ➕ 已添加新直播源: {self.additional_live['name']}")
        
        # 然后保留原有的直播源配置
        if "lives" in self.source_data and self.source_data["lives"]:
            original_lives = self.source_data["lives"]
            
            if isinstance(original_lives, list):
                for live in original_lives:
                    if not live:
                        continue
                    # 跳过空数组
                    if isinstance(live, list) and not live:
                        continue
                    # 如果是有效的直播源配置
                    if isinstance(live, dict) and "name" in live:
                        lives_list.append(live)
                        print(f"  ✓ 保留原直播源: {live.get('name', 'unknown')[:30]}")
            else:
                print(f"  ℹ️ 原有lives格式不是列表，跳过")
        else:
            print(f"  ℹ️ 源数据中没有lives配置")
        
        self.converted_data["lives"] = lives_list
    
    def _process_sites(self):
        """处理站点，不限制数量，只过滤黑名单"""
        if "sites" not in self.source_data:
            print("⚠️ 源数据中没有sites字段")
            return
            
        site_count = 0
        filtered_sites = []
        error_sites = []
        total_sites = len(self.source_data["sites"])
        
        print(f"\n🔍 开始过滤站点（共{total_sites}个，黑名单关键词{len(self.name_blacklist)}个）...")
        print(f"ℹ️ 站点数量不限制，将保留所有非黑名单站点")
        
        for idx, site in enumerate(self.source_data["sites"]):
            if not site:
                continue
                
            if not isinstance(site, dict):
                error_sites.append(f"索引{idx}")
                continue
            
            site_key = site.get("key", "")
            site_name = site.get("name", "")
            
            # 跳过无效的站点
            if not site_key and not site_name:
                error_sites.append(f"索引{idx}: 缺少key和name")
                continue
            
            if self._is_blacklisted(site_name, site_key):
                self.filtered_count += 1
                filtered_sites.append(f"{site_name} [{site_key}]")
                continue
                
            cleaned_site = self._clean_site_config(site)
            if cleaned_site:
                self.converted_data["sites"].append(cleaned_site)
                site_count += 1
                if site_count % 20 == 0:
                    print(f"  ✓ 已处理 {site_count} 个站点...")
        
        if self.converted_data["sites"]:
            print(f"\n  ✅ 成功添加 {site_count} 个站点")
            if site_count > 0:
                print(f"  最后添加的站点示例:")
                last_sites = self.converted_data["sites"][-5:]
                for i, site in enumerate(last_sites, 1):
                    name = site.get('name', site.get('key', 'unknown'))
                    print(f"    {i}. {name}")
        
        if filtered_sites:
            print(f"\n  🚫 已过滤黑名单站点 ({len(filtered_sites)}个):")
            for i, site in enumerate(filtered_sites[:10], 1):
                print(f"     {i}. {site}")
            if len(filtered_sites) > 10:
                print(f"     ... 等共 {len(filtered_sites)} 个")
        
        if error_sites and len(error_sites) <= 10:
            print(f"\n  ⚠️ 跳过错误站点 ({len(error_sites)}个)")
                
        print(f"✅ 站点处理完成: 添加{site_count}个，过滤{self.filtered_count}个，跳过{len(error_sites)}个")
    
    def _clean_site_config(self, site):
        """清理站点配置"""
        if "key" not in site:
            return None
            
        site_name = site.get("name")
        if not site_name or not isinstance(site_name, str):
            site_name = site["key"]
            
        cleaned = {
            "key": site["key"],
            "name": self._clean_site_name(site_name, site["key"]),
            "type": site.get("type", 3)
        }
        
        # 保留核心字段
        core_fields = ["api", "jar", "searchable", "quickSearch", 
                      "changeable", "filterable", "timeout", "playerType",
                      "genre", "gridview", "indexs", "style"]
        
        for field in core_fields:
            if field in site and site[field] is not None:
                cleaned[field] = site[field]
        
        # 处理 ext 字段
        if "ext" in site and site["ext"]:
            cleaned_ext = self._clean_ext_config(site["ext"])
            if cleaned_ext:
                cleaned["ext"] = cleaned_ext
        
        if "playurl" in site:
            cleaned["playurl"] = site["playurl"]
            
        return cleaned
    
    def _clean_site_name(self, name, site_key):
        """清理站点名称，移除表情符号和装饰字符"""
        if not isinstance(name, str):
            return site_key
            
        # 扩展的表情符号移除模式
        patterns = [
            r'[🐮🐷🐸🐙🐨🐒🐑🐘🐪🦒🦘🦙🦚🦜🦢🦩🦔🐿️🦫🦡]',
            r'[🐡🐠🐟🐬🐳🐋🦈🦭🐊🐅🐆🦓🦍🦧🦣🐘🦛🦏🐫]',
            r'[🌈🔥⭐✨🌟💫💥💢💤💦💧💨💩]',
            r'[🎨🎯🎲🎳🎴🎵🎶🎷🎸🎹🎺🎻]',
            r'[📱📲📺📻📷📸📹🎥]',
            r'[🔫🔪💣🧨🪓]',
            r'[🚗🚕🚙🚌🚎🏎️🚓🚑🚒🚐🚚🚛🚜]',
            r'[🏍️🛵🛺🚲✈️🚀🛸🚁🛶⛵🚤🛥️🛳️⚓🔱]',
            r'[💝💖💗💓💞💕💟❣️💔💯💢💬👁️‍🗨️🗣️💤]',
            r'[🐲❤🛸🥷🧸💥🎇🎎🅱️🦸🧸🐼🐧🎃🍋🦌🚀☀⚽🎬🎭📺🍋🦌]',
            r'┃',
            r'【.*?】',
            r'\|.*?\|',
            r'\-.*?\-',
            r'公众号.*?',
            r'限自用测试勿传播贩卖',
            r'公众号【.*?】',
            r'🚀┃|🐼┃|🐷┃|🍄┃|🐧┃|👽┃|🌉┃|🐶┃',
            r'┃$',
            r'^国内-|^海外-',
            r'[⬇️🆙🔝💪👈👉👆👇]',
        ]
        
        for pattern in patterns:
            name = re.sub(pattern, '', name)
            
        name = re.sub(r'\s+', ' ', name).strip()
        
        if not name:
            if site_key.startswith('csp_'):
                name = site_key[4:]
            elif site_key.endswith('zy'):
                name = site_key[:-2] + '资源'
            else:
                name = site_key
            
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
                            "siteKey", "listKey", "parsesKey"]
            
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
            if not parse or not isinstance(parse, dict):
                continue
            if "name" not in parse:
                continue
                
            cleaned_parse = {
                "name": parse["name"],
                "type": parse.get("type", 0),
                "url": parse.get("url", "")
            }
            
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
            
        for rule in self.source_data["rules"]:
            if not rule or not isinstance(rule, dict):
                continue
                
            if "hosts" in rule and "regex" in rule:
                for host in rule.get("hosts", []):
                    if host:
                        cleaned_rule = {
                            "host": host,
                            "rule": rule.get("regex", [])
                        }
                        self.converted_data["rules"].append(cleaned_rule)
            elif "host" in rule and "rule" in rule:
                self.converted_data["rules"].append(rule)
            elif "name" in rule and "hosts" in rule and "script" in rule:
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
        if "ads" in self.source_data:
            if isinstance(self.source_data["ads"], list):
                self.converted_data["ads"] = self.source_data["ads"]
            elif isinstance(self.source_data["ads"], str):
                self.converted_data["ads"] = [self.source_data["ads"]]
        
        if "wallpaper" in self.source_data:
            self.converted_data["wallpaper"] = self.source_data["wallpaper"]
        
        if "warningText" in self.source_data:
            self.converted_data["warningText"] = self.source_data["warningText"]
        
        if "spider" in self.source_data:
            self.converted_data["spider"] = self.source_data["spider"]
    
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
                print(f"❌ 缺少必需字段: {field}")
                return False
        
        if not self.converted_data["lives"]:
            print(f"⚠️ 警告: lives配置为空")
        else:
            print(f"✅ 直播源配置验证通过: 共{len(self.converted_data['lives'])}个直播源")
                
        print(f"✅ 格式验证通过，包含 {len(self.converted_data['sites'])} 个站点")
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
    
    if not converter.validate_conversion():
        print(f"⚠️ 转换验证有问题，但继续保存...")
    
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
    print("🎬 批量JSON格式转换工具 (增强版)")
    print("=" * 60)
    print(f"📁 输入目录: {input_dir}/")
    print(f"📁 输出目录: {output_dir}/")
    print("📺 直播源配置: 添加新源（排在第一位），保留原直播源")
    print("   新增源URL: https://zb.hao123.qzz.io/lv/migutv.txt")
    print("ℹ️  支持格式: JSON、带注释JSON、##注释、格式错误的JSON")
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
    total_filtered = 0
    
    for i, input_file in enumerate(txt_files, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(txt_files)}] 处理文件")
        
        temp_converter = BbtvConverter(source_file_path=input_file)
        temp_converter.load_blacklist()
        
        if process_single_file(input_file, output_dir):
            success_count += 1
            output_file = os.path.join(output_dir, os.path.basename(input_file))
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_sites += len(data.get('sites', []))
            except:
                pass
            if temp_converter.filtered_count:
                total_filtered += temp_converter.filtered_count
        else:
            fail_count += 1
            failed_files.append(os.path.basename(input_file))
    
    print("\n" + "=" * 60)
    print("📊 批量转换完成!")
    print("=" * 60)
    print(f"✅ 成功: {success_count} 个文件")
    print(f"❌ 失败: {fail_count} 个文件")
    print(f"📈 总计保留站点: {total_sites} 个")
    print(f"🚫 总计过滤站点: {total_filtered} 个")
    
    if failed_files:
        print("\n失败的文件列表:")
        for f in failed_files:
            print(f"   - {f}")

def main():
    """主函数"""
    batch_convert()

if __name__ == "__main__":
    main()