
# stock_matcher.py - 股票名称四层匹配工具
# 使用: from stock_matcher import match_a_stock, batch_lookup
# 依赖: urllib, json, concurrent.futures

STOCK_SUFFIXES = ['-U', '-W', '-WD', '-V']
STOCK_PREFIXES = ['XD', 'XR', 'DR', 'N', 'C', 'ST', '*ST']

def strip_suffix(name):
    for s in STOCK_SUFFIXES:
        if name.endswith(s): return name[:-len(s)]
    return name

def strip_prefix(name):
    for p in STOCK_PREFIXES:
        if name.startswith(p): return name[len(p):].strip()
    return name

def normalize_em_name(sname):
    return strip_prefix(strip_suffix(sname))

def match_a_stock(alpha_name, api_items):
    """四层匹配"""
    for item in api_items:
        sname = str(item.get("ShortName", ""))
        code = str(item.get("OuterCode", ""))
        if not code.isdigit():
            continue
        if sname == alpha_name: return _to_secid(code)
        if normalize_em_name(sname) == alpha_name: return _to_secid(code)
        if strip_prefix(sname) == alpha_name: return _to_secid(code)
        if len(alpha_name) >= 4 and (alpha_name in sname or sname in alpha_name):
            return _to_secid(code)
    return None

def _to_secid(code):
    return ("1" if code.startswith(('6','5','9','68')) else "0") + "." + code.zfill(6)

def search_suggest(name, timeout=8):
    import urllib.request, urllib.parse, json
    url = ("https://searchadapter.eastmoney.com/api/suggest/get?input="
           + urllib.parse.quote(name)
           + "&type=1,2,3,4,5,6,7,8&token=D43BF722C8E33BDC906FB84D85E326E8&count=5")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    return (data.get("GubaCodeTable") or {}).get("Data") or []

def parse_stocks(text):
    """
    解析关注段：用栈式括号匹配处理嵌套括号
    例如 天岳先进/基本半导体（碳化硅（SiC）是800V架构关键材料...）
    中的（SiC）不会被误判为推荐理由结束
    
    返回: [(name, reason), ...]
    """
    import re
    results = []
    i = 0
    while i < len(text):
        open_idx = text.find('（', i)
        if open_idx == -1:
            remaining = text[i:].strip()
            if remaining:
                for name in re.split(r'[，,、/]+', remaining):
                    name = name.strip()
                    if name:
                        results.append((name, ''))
            break
        name_part = text[i:open_idx].strip().strip('，,、/ ')
        if not name_part:
            i = open_idx + 1
            continue
        # 栈式括号匹配（支持嵌套（（）））
        depth = 1
        j = open_idx + 1
        while j < len(text) and depth > 0:
            if text[j] == '（':
                depth += 1
            elif text[j] == '）':
                depth -= 1
            j += 1
        if depth != 0:
            break  # 括号不闭合，终止
        reason = text[open_idx+1:j-1].strip()
        names = [n.strip() for n in name_part.split('/') if n.strip()]
        for name in names:
            results.append((name, reason))
        i = j
    return results
