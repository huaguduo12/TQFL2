import os
import re
import base64
import requests
import csv
import random 
from io import StringIO
from urllib.parse import unquote
from github import Github

# --- 1. 配置读取 ---
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
FILE_PATH = os.getenv("FILE_PATH")
WEBPAGE_URLS = os.getenv("WEBPAGE_URLS", "").strip().splitlines()

COUNTRY_ORDER_STR = os.getenv("COUNTRY_ORDER") or ""
COUNTRY_ORDER = [code.strip() for code in COUNTRY_ORDER_STR.split(',')] if COUNTRY_ORDER_STR else []

LINKS_PER_COUNTRY = int(os.getenv("LINKS_PER_COUNTRY") or "20")
LINK_PREFIX = os.getenv("LINK_PREFIX") or ""
LINK_SUFFIX = os.getenv("LINK_SUFFIX") or ""

OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT") or "full"
SELECTION_MODE = os.getenv("SELECTION_MODE") or "sequential" # <--- 新增：提取模式控制器

if not GITHUB_TOKEN or not REPO_NAME or not FILE_PATH: exit(1)
if not WEBPAGE_URLS: exit(1)

# --- 2. 全球国家/地区、机场代码与名称、国旗的映射 (已是最新最全版本) ---
COUNTRY_MAPPING = {
    "香港": "HK", "澳门": "MO", "台湾": "TW", "中国": "CN", "大陆": "CN", "高雄": "TW",
    "日本": "JP", "韩国": "KR", "新加坡": "SG", "马来西亚": "MY", "泰国": "TH", "缅甸": "MM",
    "越南": "VN", "菲律宾": "PH", "印度尼西亚": "ID", "印度": "IN", "土耳其": "TR", "阿联酋": "AE", "沙特": "SA", "亚美尼亚": "AM",
    "伊朗": "IR", "柬埔寨": "KH", "吉尔吉斯斯坦": "KG", "哈萨克斯坦": "KZ", "以色列": "IL",
    "英国": "GB", "法国": "FR", "德国": "DE", "荷兰": "NL", "瑞士": "CH", "俄罗斯": "RU", "白俄罗斯": "BY",
    "乌克兰": "UA", "意大利": "IT", "西班牙": "ES", "葡萄牙": "PT", "瑞典": "SE", "挪威": "NO", "罗马尼亚": "RO",
    "丹麦": "DK", "芬兰": "FI", "爱尔兰": "IE", "比利时": "BE", "奥地利": "AT", "波兰": "PL", "捷克": "CZ", "立陶宛": "LT",
    "匈牙利": "HU", "希腊": "GR", "保加利亚": "BG", "爱沙尼亚": "EE", "拉脱维亚": "LV", "阿尔巴尼亚": "AL", "塞浦路斯": "CY",
    "格鲁吉亚": "GE", "克罗地亚": "HR", "冰岛": "IS", "列支敦士登": "LI", "摩尔多瓦": "MD", "黑山": "ME", "北马其顿": "MK", "塞尔维亚": "RS", "斯洛文尼亚": "SI", "斯洛伐克": "SK",
    "美国": "US", "加拿大": "CA", "墨西哥": "MX", "巴西": "BR", "阿根廷": "AR", "智利": "CL", "哥伦比亚": "CO",
    "澳大利亚": "AU", "新西兰": "NZ", "南非": "ZA", "肯尼亚": "KE", "毛里求斯": "MU", "塞舌尔": "SC", "乌兹别克斯坦": "UZ"
}

CODE_TO_NAME = {v: k for k, v in COUNTRY_MAPPING.items() if k not in ["大陆", "高雄"]}

CODE_TO_FLAG = {
    "HK": "🇭🇰", "MO": "🇲🇴", "TW": "🇹🇼", "CN": "🇨🇳", "JP": "🇯🇵", "KR": "🇰🇷", "SG": "🇸🇬", "MY": "🇲🇾", "TH": "🇹🇭", "MM": "🇲🇲",
    "VN": "🇻🇳", "PH": "🇵🇭", "ID": "🇮🇩", "IN": "🇮🇳", "TR": "🇹🇷", "AE": "🇦🇪", "SA": "🇸🇦", "AM": "🇦🇲", "IR": "🇮🇷",
    "KH": "🇰🇭", "KG": "🇰🇬", "KZ": "🇰🇿", "IL": "🇮🇱", "GB": "🇬🇧", "FR": "🇫🇷", "DE": "🇩🇪", "NL": "🇳🇱", "CH": "🇨🇭", "RU": "🇷🇺", "BY": "🇧🇾",
    "UA": "🇺🇦", "IT": "🇮🇹", "ES": "🇪🇸", "PT": "🇵🇹", "SE": "🇸🇪", "NO": "🇳🇴", "RO": "🇷🇴", "DK": "🇩🇰", "FI": "🇫🇮",
    "IE": "🇮🇪", "BE": "🇧🇪", "AT": "🇦🇹", "PL": "🇵🇱", "CZ": "🇨🇿", "LT": "🇱🇹", "HU": "🇭🇺", "GR": "🇬🇷", "BG": "🇧🇬",
    "EE": "🇪🇪", "LV": "🇱🇻", "AL": "🇦🇱", "CY": "🇨🇾", "GE": "🇬🇪", "HR": "🇭🇷", "IS": "🇮🇸", "LI": "🇱🇮", "MD": "🇲🇩", "ME": "🇲🇪",
    "MK": "🇲🇰", "RS": "🇷🇸", "SI": "🇸🇮", "SK": "🇸🇰", "US": "🇺🇸", "CA": "🇨🇦", "MX": "🇲🇽", "BR": "🇧🇷", "AR": "🇦🇷",
    "CL": "🇨🇱", "CO": "🇨🇴", "AU": "🇦🇺", "NZ": "🇳🇿", "ZA": "🇿🇦", "KE": "🇰🇪", "MU": "🇲🇺", "SC": "🇸🇨", "UZ": "🇺🇿",
    "UNKNOWN": "❓"
}

LOCATION_TO_CODE = {
    'hkg': 'HK', 'hong kong': 'HK', 'mfm': 'MO', 'macau': 'MO', 'tpe': 'TW', 'taipei': 'TW', 'khh': 'TW', 'kaohsiung': 'TW', 'kaohsiung city': 'TW',
    'pek': 'CN', 'beijing': 'CN', 'pvg': 'CN', 'shanghai': 'CN', 'szx': 'CN', 'shenzhen': 'CN', 'can': 'CN', 'guangzhou': 'CN',
    'nrt': 'JP', 'hnd': 'JP', 'tokyo': 'JP', 'kix': 'JP', 'osaka': 'JP', 'fuk': 'JP', 'fukuoka': 'JP',
    'icn': 'KR', 'seoul': 'KR', 'sin': 'SG', 'singapore': 'SG', 'kul': 'MY', 'kuala lumpur': 'MY',
    'bkk': 'TH', 'bangkok': 'TH', 'han': 'VN', 'hanoi': 'VN', 'sgn': 'VN', 'ho chi minh city': 'VN',
    'mnl': 'PH', 'manila': 'PH', 'cgk': 'ID', 'jakarta': 'ID', 'bom': 'IN', 'mumbai': 'IN', 'del': 'IN', 'delhi': 'IN',
    'ist': 'TR', 'istanbul': 'TR', 'dxb': 'AE', 'dubai': 'AE', 'ruh': 'SA', 'riyadh': 'SA', 'evn': 'AM', 'yerevan': 'AM',
    'lhr': 'GB', 'london': 'GB', 'man': 'GB', 'manchester': 'GB', 'cdg': 'FR', 'paris': 'FR', 'mrs': 'FR', 'marseille': 'FR',
    'fra': 'DE', 'frankfurt': 'DE', 'muc': 'DE', 'munich': 'DE', 'ber': 'DE', 'berlin': 'DE', 'dus': 'DE', 'düsseldorf': 'DE', 'ham': 'DE', 'hamburg': 'DE', 'txl': 'DE',
    'ams': 'NL', 'amsterdam': 'NL', 'zrh': 'CH', 'zurich': 'CH', 'svo': 'RU', 'moscow': 'RU', 'dme': 'RU', 'led': 'RU', 'saint petersburg': 'RU',
    'kbp': 'UA', 'kyiv': 'UA', 'fco': 'IT', 'rome': 'IT', 'mxp': 'IT', 'milan': 'IT',
    'mad': 'ES', 'madrid': 'ES', 'bcn': 'ES', 'barcelona': 'ES', 'lis': 'PT', 'lisbon': 'PT',
    'arn': 'SE', 'stockholm': 'SE', 'osl': 'NO', 'oslo': 'NO', 'otp': 'RO', 'bucharest': 'RO',
    'cph': 'DK', 'copenhagen': 'DK', 'hel': 'FI', 'helsinki': 'FI', 'dub': 'IE', 'dublin': 'IE',
    'bru': 'BE', 'brussels': 'BE', 'vie': 'AT', 'vienna': 'AT', 'waw': 'PL', 'warsaw': 'PL',
    'prg': 'CZ', 'prague': 'CZ', 'vno': 'LT', 'vilnius': 'LT', 'bud': 'HU', 'budapest': 'HU',
    'ath': 'GR', 'athens': 'GR', 'sof': 'BG', 'sofia': 'BG', 'tll': 'EE', 'tallinn': 'EE', 'rix': 'LV', 'riga': 'LV',
    'sjc': 'US', 'san jose': 'US', 'lax': 'US', 'los angeles': 'US', 'sfo': 'US', 'san francisco': 'US',
    'sea': 'US', 'seattle': 'US', 'pdx': 'US', 'portland': 'US', 'phx': 'US', 'phoenix': 'US',
    'den': 'US', 'denver': 'US', 'ord': 'US', 'chicago': 'US', 'dfw': 'US', 'dallas': 'US',
    'jfk': 'US', 'new york': 'US', 'ewr': 'US', 'newark': 'US', 'iad': 'US', 'ashburn': 'US', 'washington': 'US',
    'atl': 'US', 'atlanta': 'US', 'mia': 'US', 'miami': 'US', 'buf': 'US', 'buffalo': 'US',
    'yyz': 'CA', 'toronto': 'CA', 'yvr': 'CA', 'vancouver': 'CA', 'yul': 'CA', 'montreal': 'CA',
    'mex': 'MX', 'mexico city': 'MX', 'gru': 'BR', 'sao paulo': 'BR', 'eze': 'AR', 'buenos aires': 'AR', 'scl': 'CL', 'santiago': 'CL',
    'syd': 'AU', 'sydney': 'AU', 'mel': 'AU', 'melbourne': 'AU', 'akl': 'NZ', 'auckland': 'NZ',
    'jnb': 'ZA', 'johannesburg': 'ZA', 'cai': 'EG', 'cairo': 'EG'
}

# --- 3. 辅助函数与链接提取函数 (已重构) ---
def get_code_from_fragment(fragment):
    fragment_upper = fragment.upper()
    dc_match = re.search(r'([A-Z]{3})', fragment_upper)
    if dc_match:
        code = LOCATION_TO_CODE.get(dc_match.group(1).lower())
        if code: return code
    code_match = re.search(r'([A-Z]{2})', fragment_upper)
    if code_match and code_match.group(1) in CODE_TO_NAME:
        return code_match.group(1)
    for name, code in COUNTRY_MAPPING.items():
        if name in fragment: return code
    return "UNKNOWN"

def extract_protocol_links(decoded_content):
    regex = re.compile(r'(vless|vmess|trojan)://[^@]+@([^?#]+)\?[^#]*#(.+)')
    links = []
    for match in regex.finditer(decoded_content):
        link_part, fragment = match.group(2).strip(), unquote(match.group(3).strip())
        country_code = get_code_from_fragment(fragment)
        if country_code != "UNKNOWN":
            links.append({"link_part": link_part, "code": country_code})
    return links

def extract_csv_links(csv_content):
    links = []
    try:
        f = StringIO(csv_content)
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 6:
                ip, port, data_center, city = row[0].strip(), row[1].strip(), row[3].strip(), row[5].strip()
                if ip and port:
                    link_part = f"{ip}:{port}"
                    code = LOCATION_TO_CODE.get(data_center.lower()) or LOCATION_TO_CODE.get(city.lower()) or "UNKNOWN"
                    if code != "UNKNOWN":
                        links.append({"link_part": link_part, "code": code})
    except Exception as e:
        print(f"  > CSV 解析时出错: {e}")
    return links

def extract_line_based_links(plain_content):
    links = []
    for line in plain_content.strip().splitlines():
        clean_line = line.strip()
        if not clean_line: continue
        ip_port_match = re.search(r'([^#]+:\d+)#(.+)', clean_line)
        if ip_port_match:
            link_part, fragment = ip_port_match.group(1), ip_port_match.group(2).strip()
            code = get_code_from_fragment(fragment)
            if code != "UNKNOWN":
                links.append({"link_part": link_part, "code": code})
    return links

# --- 4. 核心处理逻辑 ---
def process_subscription_url(url):
    print(f"正在处理 URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_content = response.text
        try:
            base64_content = "".join(raw_content.split())
            missing_padding = len(base64_content) % 4
            if missing_padding: base64_content += '=' * (4 - missing_padding)
            decoded_text = base64.b64decode(base64_content).decode('utf-8')
            print("  > 检测到 Base64 格式，使用协议解析器。")
            return extract_protocol_links(decoded_text)
        except Exception: pass
        first_line = raw_content.strip().splitlines()[0] if raw_content.strip() else ""
        if ',' in first_line and ("IP地址" in first_line or "地址" in first_line):
            print("  > 检测到 CSV 格式，使用 CSV 解析器。")
            return extract_csv_links(raw_content)
        print("  > 未知格式，使用通用的行解析器。")
        return extract_protocol_links(raw_content) + extract_line_based_links(raw_content)
    except requests.RequestException as e:
        print(f"  > 获取 URL 内容失败: {e}")
        return []

def format_link(link_part, code, index=None):
    if OUTPUT_FORMAT == 'full':
        flag = CODE_TO_FLAG.get(code, CODE_TO_FLAG["UNKNOWN"])
        name = CODE_TO_NAME.get(code, code)
        name_suffix = str(index) if index is not None else ""
        return f"{link_part}#{LINK_PREFIX}{flag}{name}{name_suffix}{LINK_SUFFIX}"
    else:
        return f"{link_part}#{LINK_PREFIX}{code}{LINK_SUFFIX}"

def filter_and_sort_links(all_links, order, limit):
    grouped_links = {}
    for link_info in all_links:
        code = link_info['code']
        if code not in grouped_links: grouped_links[code] = []
        grouped_links[code].append(link_info['link_part'])
    
    order_to_use = order if order else sorted(list(grouped_links.keys()))
    
    final_links = []
    for code in order_to_use:
        if code in grouped_links:
            unique_links = list(dict.fromkeys(grouped_links[code]))
            
            # --- <--- 核心修改点 ---> ---
            selected_links = []
            if SELECTION_MODE == 'random':
                num_to_sample = min(limit, len(unique_links))
                selected_links = random.sample(unique_links, num_to_sample)
                print(f"  > {code}: 随机模式, 已从 {len(unique_links)} 个链接中选择 {num_to_sample} 个。")
            else: # 默认 sequential
                selected_links = unique_links[:limit]
                print(f"  > {code}: 顺序模式, 已从 {len(unique_links)} 个链接中选择前 {len(selected_links)} 个。")
            # --- <--- 修改结束 ---> ---

            for i, link_part in enumerate(selected_links, 1):
                final_links.append(format_link(link_part, code, i))
                
    return final_links

def write_to_github(content):
    if not content:
        print("没有生成任何内容，已跳过写入 GitHub。")
        return
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file_content = repo.get_contents(FILE_PATH, ref="main")
            repo.update_file(FILE_PATH, "Update subscription links", content, file_content.sha, branch="main")
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功更新。")
        except Exception:
            repo.create_file(FILE_PATH, "Create subscription links file", content, branch="main")
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功创建。")
    except Exception as e:
        print(f"写入 GitHub 时发生错误: {e}")

# --- 5. 主函数 ---
def main():
    print("开始执行订阅链接处理任务...")
    all_extracted_links = []
    for url in WEBPAGE_URLS:
        if url:
            links = process_subscription_url(url)
            if links:
                all_extracted_links.extend(links)
    
    seen_link_parts = set()
    unique_links_info = []
    for link_info in all_extracted_links:
        if link_info['link_part'] not in seen_link_parts:
            unique_links_info.append(link_info)
            seen_link_parts.add(link_info['link_part'])

    print(f"\n从所有源共提取了 {len(all_extracted_links)} 个链接，去重后剩余 {len(unique_links_info)} 个。")

    if not unique_links_info:
        print("未能从任何源提取到链接，任务终止。")
        return

    final_links = []
    if COUNTRY_ORDER:
        print("\n检测到 COUNTRY_ORDER, 进入排序分组模式...")
        final_links = filter_and_sort_links(unique_links_info, COUNTRY_ORDER, LINKS_PER_COUNTRY)
    else:
        print("\n未检测到 COUNTRY_ORDER, 进入原始顺序模式...")
        country_counters = {}
        for link_info in unique_links_info:
            code = link_info['code']
            link_part = link_info['link_part']
            current_count = country_counters.get(code, 0) + 1
            country_counters[code] = current_count
            final_links.append(format_link(link_part, code, current_count))

    print(f"\n经过处理后，最终保留 {len(final_links)} 个链接。")
    final_content = "\n".join(final_links)
    write_to_github(final_content)

if __name__ == "__main__":
    main()
