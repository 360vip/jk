#!/usr/bin/env python3
"""
批量JSON格式转换脚本
将 xl 目录下的所有 txt 文件（JSON格式）转换为与 tt.json 相同的格式
从每个文件中读取数据，并从hmd.txt读取黑名单过滤站点
【修改】不限制站点数量，添加新的直播源配置（排在第一位），保留原有直播源
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
                with open(self.source_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"❌ 读取文件失败: {e}")
                return False
        else:
            print(f"❌ 没有指定数据源")
            return False
        
        # 移除JavaScript风格的注释（// 和 /* */）
        cleaned_content = self._remove_json_comments(content)
        
        try:
            self.source_data = json.loads(cleaned_content)
            if self.source_url:
                print(f"✅ 成功获取数据，包含 {len(self.source_data.get('sites', []))} 个站点")
            else:
                print(f"✅ 成功解析文件，包含 {len(self.source_data.get('sites', []))} 个站点")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            # 尝试更激进的清理
            print("🔄 尝试激进的JSON修复...")
            repaired_content = self._repair_json(cleaned_content)
            try:
                self.source_data = json.loads(repaired_content)
                print(f"✅ JSON修复成功，包含 {len(self.source_data.get('sites', []))} 个站点")
                return True
            except json.JSONDecodeError as e2:
                print(f"❌ JSON修复仍然失败: {e2}")
                return False
    
    def _remove_json_comments(self, json_str):
        """移除JSON中的JavaScript风格注释"""
        if not json_str:
            return json_str
            
        lines = json_str.split('\n')
        cleaned_lines = []
        in_block_comment = False
        
        for line in lines:
            # 处理块注释 /* */
            if not in_block_comment:
                # 查找块注释开始
                block_start = line.find('/*')
                if block_start != -1:
                    in_block_comment = True
                    line = line[:block_start]
                    
            if in_block_comment:
                # 查找块注释结束
                block_end = line.find('*/')
                if block_end != -1:
                    in_block_comment = False
                    line = line[block_end + 2:]
                else:
                    line = ''
            
            # 移除行注释 //，但要注意URL中的//
            if not in_block_comment:
                # 处理行注释，但保留URL中的//
                in_string = False
                string_char = None
                pos = 0
                comment_pos = -1
                
                while pos < len(line):
                    char = line[pos]
                    
                    # 字符串开始/结束
                    if char in ['"', "'"] and (pos == 0 or line[pos-1] != '\\'):
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                            string_char = None
                    
                    # 查找不在字符串中的 //
                    elif char == '/' and pos + 1 < len(line) and line[pos + 1] == '/' and not in_string:
                        comment_pos = pos
                        break
                    
                    pos += 1
                
                if comment_pos != -1:
                    line = line[:comment_pos]
            
            # 移除行首尾空白
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _repair_json(self, json_str):
        """激进的JSON修复"""
        # 移除所有注释
        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 修复最后一个对象后面的逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*\]', ']', json_str)
        
        # 修复数组中的逗号问题
        lines = json_str.split('\n')
        repaired_lines = []
        
        for i, line in enumerate(lines):
            # 如果这一行是注释，跳过
            if line.strip().startswith('//'):
                continue
                
            # 修复逗号问题
            if i > 0 and lines[i-1].strip().endswith(','):
                if line.strip().startswith('//'):
                    lines[i-1] = lines[i-1].rstrip(',')
                    
            repaired_lines.append(line)
        
        return '\n'.join(repaired_lines)
    
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
            # 检查站点名称
            if keyword_lower in site_name_lower:
                return True
            # 也检查站点key
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
            "lives": [],  # 稍后会处理，添加原有lives并插入新的到第一位
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
        
        # 1. 处理所有站点（不限制数量，但过滤黑名单）
        self._process_sites()
        
        # 2. 处理版本信息
        self._process_version()
        
        # 3. 处理直播源（保留原有，并添加新的到第一位）
        self._process_lives()
        
        # 4. 解析线路（保留原有处理逻辑）
        self._process_parses()
        
        # 5. 处理规则（统一格式）
        self._process_rules()
        
        # 6. 处理 flags
        self._process_flags()
        
        # 7. 处理 ijk 配置
        self._process_ijk()
        
        # 8. 处理其他字段
        self._process_other_fields()
        
        print(f"✅ 格式转换完成，总计 {len(self.converted_data['sites'])} 个站点（过滤掉 {self.filtered_count} 个黑名单站点）")
        print(f"✅ 直播源配置: 原有 {len(self.converted_data['lives']) - 1} 个 + 新增1个（排在第一位）")
        return True
    
    def _process_version(self):
        """处理版本信息"""
        if "version" in self.source_data and self.source_data["version"]:
            version_data = self.source_data["version"][0] if isinstance(self.source_data["version"], list) else self.source_data["version"]
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
                    if isinstance(live, dict) and "name" in live:
                        lives_list.append(live)
                        print(f"  ✓ 保留原直播源: {live.get('name', 'unknown')}")
            else:
                print(f"  ⚠️ 原有lives格式不是列表，跳过")
        else:
            print(f"  ℹ️ 源数据中没有lives配置")
        
        self.converted_data["lives"] = lives_list
    
    def _process_sites(self):
        """处理站点，不限制数量，只过滤黑名单"""
        if "sites" not in self.source_data:
            return
            
        site_count = 0
        filtered_sites = []  # 记录被过滤的站点
        total_sites = len(self.source_data["sites"])
        
        print(f"\n🔍 开始过滤站点（共{total_sites}个，黑名单关键词{len(self.name_blacklist)}个）...")
        print(f"ℹ️ 站点数量不限制，将保留所有非黑名单站点")
        
        # 遍历所有站点
        for site in self.source_data["sites"]:
            if not isinstance(site, dict):
                continue
                
            self.site_key_for_error = site.get("key", "unknown")
            
            # 检查站点是否在黑名单中
            site_name = site.get("name", "")
            site_key = site.get("key", "")
            
            if self._is_blacklisted(site_name, site_key):
                self.filtered_count += 1
                filtered_sites.append(f"{site_name} [{site_key}]")
                continue
                
            cleaned_site = self._clean_site_config(site)
            if cleaned_site:
                self.converted_data["sites"].append(cleaned_site)
                site_count += 1
                # 只在每10个站点显示一次进度，避免输出过多
                if site_count % 10 == 0:
                    print(f"  ✓ 已处理 {site_count} 个站点...")
        
        # 显示最后添加的站点（显示最后5个）
        if self.converted_data["sites"]:
            print(f"\n  ✅ 成功添加 {site_count} 个站点")
            print(f"  最后添加的站点示例:")
            last_sites = self.converted_data["sites"][-5:]
            for i, site in enumerate(last_sites, 1):
                print(f"    {i}. {site.get('name', site['key'])}")
        
        # 显示被过滤的站点
        if filtered_sites:
            print(f"\n  🚫 已过滤黑名单站点 ({len(filtered_sites)}个):")
            # 显示所有被过滤的站点，但限制显示数量
            display_count = min(len(filtered_sites), 20)
            for i, site in enumerate(filtered_sites[:display_count], 1):
                print(f"     {i}. {site}")
            if len(filtered_sites) > display_count:
                print(f"     ... 等共 {len(filtered_sites)} 个")
                
        print(f"✅ 站点处理完成: 添加{site_count}个，过滤{self.filtered_count}个")
    
    def _clean_site_config(self, site):
        """清理站点配置，移除与 tt.json 格式不同的字段"""
        # 必须有 key 字段
        if "key" not in site:
            return None
            
        # 获取站点名称，提供默认值
        site_name = site.get("name")
        if not site_name or not isinstance(site_name, str):
            site_name = site["key"]
            
        cleaned = {
            "key": site["key"],
            "name": self._clean_site_name(site_name, site["key"]),
            "type": site.get("type", 3)
        }
        
        # 保留核心字段（tt.json 中存在的字段）
        core_fields = ["api", "jar", "searchable", "quickSearch", 
                      "changeable", "filterable", "timeout", "playerType"]
        
        for field in core_fields:
            if field in site and site[field] is not None:
                cleaned[field] = site[field]
        
        # 处理 ext 字段（精简配置）
        if "ext" in site and site["ext"]:
            cleaned_ext = self._clean_ext_config(site["ext"])
            if cleaned_ext:
                cleaned["ext"] = cleaned_ext
        
        # 对于 type=1 的站点，保留 categories
        if cleaned["type"] == 1 and "categories" in site:
            cleaned["categories"] = site["categories"]
        
        # 保留 playurl 字段
        if "playurl" in site:
            cleaned["playurl"] = site["playurl"]
            
        return cleaned
    
    def _clean_site_name(self, name, site_key):
        """清理站点名称，移除表情符号和装饰字符"""
        if not isinstance(name, str):
            return site_key
            
        # 移除常见表情符号和装饰字符
        patterns = [
            # 移除常见装饰字符
            r'[☀⚽🎬🎭📺🍋🦌🚀🐧🐼🎃📚🅱📖🎤🦸‍♂️💿🔹💿📺🎬⚽📚🎤🦸‍♂️☀🐧🐼🎃🍋🦌🚀]',
            r'┃',  # 移除分隔线
            r'【.*?】',  # 移除【】及其内容
            r'\|.*?\|',  # 移除|内容|
            r'\-.*?\-',   # 移除-内容-
            r'公众号.*?',  # 移除公众号相关
            r'限自用测试勿传播贩卖',  # 移除特定文本
            r'公众号【.*?】',  # 移除公众号
            r'🚀┃',  # 移除特定前缀
            r'🐼┃',
            r'🐷┃',
            r'🍄┃',
            r'🐧┃',
            r'👽┃',
            r'🌉┃',
            r'🐶┃',
            r'┃$',  # 移除末尾的┃
            r'^国内-',  # 移除前缀
            r'^海外-',  # 移除前缀
        ]
        
        for pattern in patterns:
            name = re.sub(pattern, '', name)
            
        # 移除多余空白
        name = re.sub(r'\s+', ' ', name).strip()
        
        # 如果清理后为空，使用站点key作为名称
        if not name:
            # 从key中提取可读名称
            if site_key.startswith('csp_'):
                name = site_key[4:]
            elif site_key.endswith('zy'):
                name = site_key[:-2] + '资源'
            else:
                name = site_key
            
        return name
    
    def _clean_ext_config(self, ext):
        """清理 ext 配置，只保留必要的字段"""
        if not isinstance(ext, dict):
            return None
            
        cleaned_ext = {}
        
        # 只保留这些核心字段
        allowed_fields = ["danmu", "sp", "url", "host", "site", "filters", 
                         "sites", "catesSet", "tabsSet", "classes", "ver"]
        
        for field in allowed_fields:
            if field in ext and ext[field] is not None:
                cleaned_ext[field] = ext[field]
                
        return cleaned_ext if cleaned_ext else None
    
    def _process_parses(self):
        """处理解析线路"""
        if "parses" not in self.source_data:
            return
            
        # 添加源数据中的解析线路（精简配置）
        for parse in self.source_data["parses"]:
            if not isinstance(parse, dict) or "name" not in parse:
                continue
                
            cleaned_parse = {
                "name": parse["name"],
                "type": parse.get("type", 0),
                "url": parse.get("url", "")
            }
            
            # 添加必要的扩展配置
            if "ext" in parse and parse["ext"]:
                ext_config = {}
                if "header" in parse["ext"]:
                    ext_config["header"] = parse["ext"]["header"]
                if "flag" in parse["ext"]:
                    ext_config["flag"] = parse["ext"]["flag"]
                if ext_config:
                    cleaned_parse["ext"] = ext_config
            
            self.converted_data["parses"].append(cleaned_parse)
    
    def _process_rules(self):
        """处理规则，统一格式"""
        if "rules" not in self.source_data:
            return
            
        for rule in self.source_data["rules"]:
            if not isinstance(rule, dict):
                continue
                
            # 转换格式：从原格式转换为 tt.json 格式
            if "hosts" in rule and "regex" in rule:
                for host in rule.get("hosts", []):
                    cleaned_rule = {
                        "host": host,
                        "rule": rule.get("regex", [])
                    }
                    self.converted_data["rules"].append(cleaned_rule)
            elif "host" in rule and "rule" in rule:
                # 已经是 tt.json 格式
                self.converted_data["rules"].append(rule)
            elif "name" in rule and "hosts" in rule and "script" in rule:
                # 处理原bbtv格式的script规则
                for host in rule.get("hosts", []):
                    cleaned_rule = {
                        "host": host,
                        "rule": rule.get("script", [])
                    }
                    self.converted_data["rules"].append(cleaned_rule)
    
    def _process_flags(self):
        """处理 flags"""
        if "flags" in self.source_data:
            self.converted_data["flags"] = self.source_data["flags"]
    
    def _process_ijk(self):
        """处理 ijk 配置"""
        if "ijk" in self.source_data:
            # 直接使用源数据中的ijk配置
            self.converted_data["ijk"] = self.source_data["ijk"]
        else:
            # 如果没有ijk配置，提供默认值
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
            self.converted_data["ads"] = self.source_data["ads"]
        
        # wallpaper
        if "wallpaper" in self.source_data:
            self.converted_data["wallpaper"] = self.source_data["wallpaper"]
        
        # warningText
        if "warningText" in self.source_data:
            self.converted_data["warningText"] = self.source_data["warningText"]
        
        # spider
        if "spider" in self.source_data:
            self.converted_data["spider"] = self.source_data["spider"]
    
    def save_converted_data(self, output_file):
        """保存转换后的数据"""
        if not self.converted_data:
            print("❌ 没有转换后的数据可保存")
            return False
            
        try:
            # 确保输出目录存在
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
            
        # 检查必需字段
        required_fields = ["sites", "version", "lives", "parses", "rules", "flags", "ijk"]
        for field in required_fields:
            if field not in self.converted_data:
                print(f"❌ 缺少必需字段: {field}")
                return False
        
        # 检查直播源配置是否已添加新源
        if not self.converted_data["lives"]:
            print(f"⚠️ 警告: lives配置为空")
        elif self.converted_data["lives"][0] != self.additional_live:
            print(f"⚠️ 警告: 新直播源未正确放置在第一位")
        else:
            print(f"✅ 直播源配置验证通过: 新增源在第一位，共{len(self.converted_data['lives'])}个")
                
        print(f"✅ 格式验证通过，包含 {len(self.converted_data['sites'])} 个站点")
        return True

def process_single_file(input_file, output_dir):
    """处理单个文件"""
    print("\n" + "=" * 60)
    print(f"📄 处理文件: {input_file}")
    print("=" * 60)
    
    # 获取文件名（不含扩展名）
    base_name = os.path.basename(input_file)
    name_without_ext = os.path.splitext(base_name)[0]
    
    # 创建转换器（使用本地文件）
    converter = BbtvConverter(source_file_path=input_file)
    
    # 加载黑名单
    converter.load_blacklist()
    
    # 获取数据
    if not converter.fetch_bbtv_data():
        print(f"❌ 无法解析文件: {input_file}")
        return False
    
    # 转换格式
    if not converter.convert_to_tt_format():
        print(f"❌ 格式转换失败: {input_file}")
        return False
    
    # 验证转换
    if not converter.validate_conversion():
        print(f"⚠️ 转换验证有问题，但继续保存...")
    
    # 生成输出文件名（保持原文件名）
    output_file = os.path.join(output_dir, base_name)
    
    # 保存结果
    if not converter.save_converted_data(output_file):
        return False
    
    # 输出文件统计信息
    print(f"\n📊 文件统计:")
    print(f"   站点数量: {len(converter.converted_data['sites'])}")
    print(f"   过滤黑名单: {converter.filtered_count} 个站点")
    print(f"   直播源数量: {len(converter.converted_data['lives'])} (新增1个到第一位)")
    print(f"   解析线路: {len(converter.converted_data['parses'])}")
    print(f"   规则数量: {len(converter.converted_data['rules'])}")
    
    return True

def batch_convert():
    """批量转换 xl 目录下的所有 txt 文件"""
    # 配置
    input_dir = "xl"
    output_dir = "mybox"
    
    print("=" * 60)
    print("🎬 批量JSON格式转换工具 (站点不限制 + 黑名单过滤 + 添加直播源)")
    print("=" * 60)
    print(f"📁 输入目录: {input_dir}/")
    print(f"📁 输出目录: {output_dir}/")
    print("📺 直播源配置: 添加新源（排在第一位），保留原直播源")
    print("   新增源URL: https://zb.hao123.qzz.io/lv/migutv.txt")
    print("   新增源EPG: http://diyp.112114.xyz/?ch={name}&date={date}")
    print("   新增源LOGO: https://epg.112114.xyz/logo/{name}.png")
    print("ℹ️  站点数量: 不限制，保留所有非黑名单站点")
    print("=" * 60)
    
    # 检查输入目录是否存在
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录不存在: {input_dir}/")
        print("请确保 xl 目录存在并包含需要转换的 txt 文件")
        sys.exit(1)
    
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"✅ 创建输出目录: {output_dir}/")
    
    # 获取所有 txt 文件
    pattern = os.path.join(input_dir, "*.txt")
    txt_files = glob.glob(pattern)
    
    if not txt_files:
        print(f"❌ 在 {input_dir}/ 目录下未找到任何 .txt 文件")
        sys.exit(1)
    
    print(f"\n📋 找到 {len(txt_files)} 个 txt 文件:")
    for f in txt_files:
        print(f"   - {os.path.basename(f)}")
    print()
    
    # 统计信息
    success_count = 0
    fail_count = 0
    failed_files = []
    total_sites = 0
    total_filtered = 0
    
    # 逐个处理文件
    for i, input_file in enumerate(txt_files, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(txt_files)}] 处理文件")
        
        # 创建临时转换器用于获取统计信息
        temp_converter = BbtvConverter(source_file_path=input_file)
        temp_converter.load_blacklist()
        
        if process_single_file(input_file, output_dir):
            success_count += 1
            # 读取输出文件获取统计信息
            output_file = os.path.join(output_dir, os.path.basename(input_file))
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_sites += len(data.get('sites', []))
            except:
                pass
            # 获取过滤数量
            if temp_converter.filtered_count:
                total_filtered += temp_converter.filtered_count
        else:
            fail_count += 1
            failed_files.append(os.path.basename(input_file))
    
    # 输出总结
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
    
    # 生成总体报告
    generate_batch_report(success_count, fail_count, failed_files, input_dir, output_dir, total_sites, total_filtered)

def generate_batch_report(success_count, fail_count, failed_files, input_dir, output_dir, total_sites, total_filtered):
    """生成批量转换报告"""
    report = {
        "conversion_time": datetime.now().isoformat(),
        "description": "批量转换 xl 目录下的所有 JSON/txt 文件到 mybox 目录（站点不限制）",
        "input_directory": input_dir,
        "output_directory": output_dir,
        "statistics": {
            "total_files": success_count + fail_count,
            "success_count": success_count,
            "fail_count": fail_count,
            "failed_files": failed_files,
            "total_sites_retained": total_sites,
            "total_sites_filtered": total_filtered
        },
        "config": {
            "sites_limit": "无限制",
            "blacklist_file": "data/hmd.txt",
            "lives_mode": "添加新源到第一位，保留原有源",
            "additional_live_url": "https://zb.hao123.qzz.io/lv/migutv.txt"
        }
    }
    
    try:
        with open("batch_conversion_report.json", 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("\n📋 批量转换报告已保存到 batch_conversion_report.json")
    except Exception as e:
        print(f"⚠️ 保存批量转换报告失败: {e}")

def main():
    """主函数"""
    batch_convert()

if __name__ == "__main__":
    main()