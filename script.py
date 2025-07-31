import os
import re
import base64
import requests
from urllib.parse import unquote
from github import Github

# --- 1. 从环境变量获取配置 (新增和修改部分) ---

# GitHub 相关配置
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
FILE_PATH = os.getenv("FILE_PATH")

# 订阅链接配置 (从单个 URL 变为多个)
# 请在 GitHub Secrets 中设置 WEBPAGE_URLS, 多个 URL 用换行符分隔
WEBPAGE_URLS = os.getenv("WEBPAGE_URLS", "").strip().splitlines()

# 筛选和排序配置 (核心自定义功能)
# 国家/地区代码排序, 请用逗号分隔。脚本将按此顺序排列输出。
# 例如: HK,SG,JP,TW,KR,US
COUNTRY_ORDER_STR = os.getenv("COUNTRY_ORDER", "HK,SG,JP,TW,KR,US,CA,AU,GB,FR,IT,NL,DE,RU,PL")
COUNTRY_ORDER = [code.strip() for code in COUNTRY_ORDER_STR.split(',')]

# 每个国家/地区保留的链接数量
LINKS_PER_COUNTRY = int(os.getenv("LINKS_PER_COUNTRY", "20"))


# --- 2. 检查环境变量 ---
if not GITHUB_TOKEN or not REPO_NAME or not FILE_PATH:
    print("错误: 缺少必要的 GitHub 环境变量 (MY_GITHUB_TOKEN, REPO_NAME, FILE_PATH)")
    exit(1)
if not WEBPAGE_URLS:
    print("错误: 环境变量 WEBPAGE_URLS 未设置或为空。")
    exit(1)

# --- 3. 国家/地区名称到代码的映射 (参考自 _worker.js) ---
COUNTRY_MAPPING = {
    "香港": "HK", "澳门": "MO", "台湾": "TW", "韩国": "KR", "日本": "JP",
    "新加坡": "SG", "美国": "US", "英国": "GB", "法国": "FR", "德国": "DE",
    "加拿大": "CA", "澳大利亚": "AU", "意大利": "IT", "荷兰": "NL", "挪威": "NO",
    "芬兰": "FI", "瑞典": "SE", "丹麦": "DK", "立陶宛": "LT", "俄罗斯": "RU",
    "印度": "IN", "土耳其": "TR", "捷克": "CZ", "爱沙尼亚": "EE", "拉脱维亚": "LV",
    "都柏林": "IE", "西班牙": "ES", "奥地利": "AT", "罗马尼亚": "RO", "波兰": "PL"
}

# --- 4. 核心处理函数 (逻辑来自 _worker.js) ---

def extract_links_from_content(decoded_content):
    """从解码后的文本中提取、转换并格式化链接"""
    # 正则表达式匹配 vless 链接
    regex = re.compile(r'vless://[a-zA-Z0-9\-]+@([^:]+):(\d+)\?[^#]+#([^\n\r]+)')
    
    links = []
    
    for match in regex.finditer(decoded_content):
        ip = match.group(1)
        port = match.group(2)
        country_name_raw = unquote(match.group(3).strip()) # URL解码#后面的内容
        
        country_code = "UNKNOWN"
        # 映射国家名称到代码
        for name, code in COUNTRY_MAPPING.items():
            if name in country_name_raw:
                country_code = code
                break
        else: # 如果上面的 for 循环没有 break
            # 如果没有在 MAPPING 中找到，尝试直接从原始文本提取两个大写字母作为代码
            code_match = re.search(r'([A-Z]{2})', country_name_raw)
            if code_match:
                country_code = code_match.group(1)

        if country_code != "UNKNOWN":
            formatted_link = f"{ip}:{port}#{country_code}"
            links.append({"link": formatted_link, "country_code": country_code})
            
    return links

def process_subscription_url(url):
    """获取单个订阅链接内容并处理"""
    print(f"正在处理 URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 1. Base64 解码
        try:
            # 移除内容中的空白字符再解码
            base64_content = "".join(response.text.split())
            decoded_bytes = base64.b64decode(base64_content)
        except Exception as e:
            print(f"  > Base64 解码失败: {e}")
            return []
            
        # 2. 文本解码 (尝试多种编码)
        try:
            decoded_text = decoded_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                decoded_text = decoded_bytes.decode('gbk')
            except Exception as e:
                print(f"  > 文本解码失败: {e}")
                return []
        
        # 3. 提取链接
        return extract_links_from_content(decoded_text)

    except requests.RequestException as e:
        print(f"  > 获取 URL 内容失败: {e}")
        return None

def filter_and_sort_links(all_links, country_order, limit):
    """根据国家顺序对链接进行分组、排序和筛选"""
    grouped_links = {}
    for link_info in all_links:
        code = link_info['country_code']
        if code not in grouped_links:
            grouped_links[code] = []
        grouped_links[code].append(link_info['link'])
        
    sorted_and_filtered_links = []
    # 按照预设的国家顺序进行迭代
    for country_code in country_order:
        if country_code in grouped_links:
            # 去重并截取指定数量的链接
            unique_links = list(dict.fromkeys(grouped_links[country_code]))
            sorted_and_filtered_links.extend(unique_links[:limit])
            
    return sorted_and_filtered_links

# --- 5. GitHub 写入函数 (保持不变) ---
def write_to_github(content):
    """将最终内容写入到 GitHub 文件"""
    if not content:
        print("没有生成任何内容，已跳过写入 GitHub。")
        return
        
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            # 尝试获取文件，如果文件存在则更新
            file = repo.get_contents(FILE_PATH, ref="main")
            repo.update_file(
                path=FILE_PATH,
                message="Update subscription links",
                content=content,
                sha=file.sha,
                branch="main"
            )
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功更新。")
        except Exception:
            # 如果文件不存在，则创建文件
            repo.create_file(
                path=FILE_PATH,
                message="Create subscription links file",
                content=content,
                branch="main"
            )
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功创建。")
            
    except Exception as e:
        print(f"写入 GitHub 时发生错误: {e}")

# --- 6. 主执行函数 ---
def main():
    print("开始执行订阅链接处理任务...")
    
    all_extracted_links = []
    for url in WEBPAGE_URLS:
        if url: # 确保 URL 不为空
            links = process_subscription_url(url)
            if links:
                all_extracted_links.extend(links)
    
    print(f"\n从所有源共提取了 {len(all_extracted_links)} 个有效链接。")

    if not all_extracted_links:
        print("未能从任何源提取到链接，任务终止。")
        return

    # 进行排序和筛选
    final_links = filter_and_sort_links(all_extracted_links, COUNTRY_ORDER, LINKS_PER_COUNTRY)
    print(f"经过排序和筛选后，最终保留 {len(final_links)} 个链接。")
    
    # 将链接列表合并为单一的文本内容
    final_content = "\n".join(final_links)
    
    # 写入 GitHub
    write_to_github(final_content)

if __name__ == "__main__":
    main()
