import os
import re
import base64
import requests
from urllib.parse import unquote
from github import Github

# --- 配置和环境变量部分 (无任何改动) ---
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
FILE_PATH = os.getenv("FILE_PATH")
WEBPAGE_URLS = os.getenv("WEBPAGE_URLS", "").strip().splitlines()
COUNTRY_ORDER_STR = os.getenv("COUNTRY_ORDER") or "HK,SG,JP,TW,KR,US,CA,AU,GB,FR,IT,NL,DE,RU,PL"
COUNTRY_ORDER = [code.strip() for code in COUNTRY_ORDER_STR.split(',')]
LINKS_PER_COUNTRY = int(os.getenv("LINKS_PER_COUNTRY") or "20")
LINK_PREFIX = os.getenv("LINK_PREFIX", "")
LINK_SUFFIX = os.getenv("LINK_SUFFIX", "")

if not GITHUB_TOKEN or not REPO_NAME or not FILE_PATH:
    print("错误: 缺少必要的 GitHub 环境变量 (MY_GITHUB_TOKEN, REPO_NAME, FILE_PATH)")
    exit(1)
if not WEBPAGE_URLS:
    print("错误: 环境变量 WEBPAGE_URLS 未设置或为空。")
    exit(1)

COUNTRY_MAPPING = {
    "香港": "HK", "澳门": "MO", "台湾": "TW", "韩国": "KR", "日本": "JP",
    "新加坡": "SG", "美国": "US", "英国": "GB", "法国": "FR", "德国": "DE",
    "加拿大": "CA", "澳大利亚": "AU", "意大利": "IT", "荷兰": "NL", "挪威": "NO",
    "芬兰": "FI", "瑞典": "SE", "丹麦": "DK", "立тов": "LT", "俄罗斯": "RU",
    "印度": "IN", "土耳其": "TR", "捷克": "CZ", "爱沙尼亚": "EE", "拉脱维亚": "LV",
    "都柏林": "IE", "西班牙": "ES", "奥地利": "AT", "罗马尼亚": "RO", "波兰": "PL"
}

# --- 核心处理函数 ---

def extract_vless_links(decoded_content):
    regex = re.compile(r'vless://[a-zA-Z0-9\-]+@([^:]+):(\d+)\?[^#]+#([^\n\r]+)')
    links = []
    for match in regex.finditer(decoded_content):
        ip = match.group(1)
        port = match.group(2)
        country_name_raw = unquote(match.group(3).strip())
        country_code = "UNKNOWN"
        for name, code in COUNTRY_MAPPING.items():
            if name in country_name_raw:
                country_code = code
                break
        else:
            code_match = re.search(r'([A-Z]{2})', country_name_raw)
            if code_match:
                country_code = code_match.group(1)

        if country_code != "UNKNOWN":
            formatted_link = f"{ip}:{port}#{LINK_PREFIX}{country_code}{LINK_SUFFIX}"
            links.append({"link": formatted_link, "country_code": country_code})
    return links

# <<< 修改点 START >>>
def extract_plain_text_links(plain_content):
    """
    从纯文本内容 (IP:端口#代码) 中提取链接。
    此版本经过优化，可以处理多余的空行和空白。
    """
    links = []
    # 按行分割，有效处理各种换行符，并去除空行
    for line in plain_content.strip().splitlines():
        # 清理每行前后的空白字符
        clean_line = line.strip()
        if not clean_line:
            continue # 如果是空行，则跳过

        # 在清理过的单行上进行匹配
        match = re.search(r'([^:]+:\d+)#([A-Z]{2})', clean_line)
        if match:
            link_part = match.group(1)
            country_code = match.group(2)
            
            formatted_link = f"{link_part}#{LINK_PREFIX}{country_code}{LINK_SUFFIX}"
            links.append({"link": formatted_link, "country_code": country_code})
    return links
# <<< 修改点 END >>>

def process_subscription_url(url):
    print(f"正在处理 URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_content = response.text
        try:
            base64_content = "".join(raw_content.split())
            decoded_bytes = base64.b64decode(base64_content)
            try:
                decoded_text = decoded_bytes.decode('utf-8')
            except UnicodeDecodeError:
                decoded_text = decoded_bytes.decode('gbk', 'ignore')
            print("  > 检测到 Base64 格式，使用 vless 解析器。")
            return extract_vless_links(decoded_text)
        except Exception:
            print("  > 检测到纯文本格式，使用纯文本解析器。")
            return extract_plain_text_links(raw_content)
    except requests.RequestException as e:
        print(f"  > 获取 URL 内容失败: {e}")
        return []
    except Exception as e:
        print(f"  > 处理发生未知错误: {e}")
        return []

# --- 其余函数 (无任何改动) ---

def filter_and_sort_links(all_links, country_order, limit):
    grouped_links = {}
    for link_info in all_links:
        code = link_info['country_code']
        if code not in grouped_links:
            grouped_links[code] = []
        grouped_links[code].append(link_info['link'])
    
    sorted_and_filtered_links = []
    for country_code in country_order:
        if country_code in grouped_links:
            unique_links = list(dict.fromkeys(grouped_links[country_code]))
            sorted_and_filtered_links.extend(unique_links[:limit])
            
    return sorted_and_filtered_links

def write_to_github(content):
    if not content:
        print("没有生成任何内容，已跳过写入 GitHub。")
        return
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH, ref="main")
            repo.update_file(path=FILE_PATH, message="Update subscription links", content=content, sha=file.sha, branch="main")
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功更新。")
        except Exception:
            repo.create_file(path=FILE_PATH, message="Create subscription links file", content=content, branch="main")
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功创建。")
    except Exception as e:
        print(f"写入 GitHub 时发生错误: {e}")

def main():
    print("开始执行订阅链接处理任务...")
    all_extracted_links = []
    for url in WEBPAGE_URLS:
        if url:
            links = process_subscription_url(url)
            if links:
                all_extracted_links.extend(links)
    
    print(f"\n从所有源共提取了 {len(all_extracted_links)} 个有效链接。")

    if not all_extracted_links:
        print("未能从任何源提取到链接，任务终止。")
        return

    final_links = filter_and_sort_links(all_extracted_links, COUNTRY_ORDER, LINKS_PER_COUNTRY)
    print(f"经过排序和筛选后，最终保留 {len(final_links)} 个链接。")
    
    final_content = "\n".join(final_links)
    write_to_github(final_content)

if __name__ == "__main__":
    main()
