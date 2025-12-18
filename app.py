# -*- coding: utf-8 -*-
import re

def extract_pa_fields(text_list):
    # 将列表转换为带索引的结构，方便定位标签后的内容
    raw_full = " ".join(text_list).upper()
    # 彻底清理干扰字符，仅保留字母、数字和日期斜杠
    clean_text = re.sub(r'[^A-Z0-9\s/]', '', raw_full)
    
    results = {
        "DAQ (驾照号)": "未检测",
        "DCS (1 姓氏)": "未检测",
        "DAC (2 名字)": "未检测",
        "DAG (8 地址)": "未检测",
        "DBB (DOB 生日)": "未检测",
        "DBA (EXP 过期)": "未检测",
        "DBD (ISS 签发)": "未检测",
        "DCJ (DD 档案号)": "未检测"
    }

    # 1. 驾照号：查找 DLN/DAQ 标签或 8-10 位纯数字块
    daq_m = re.search(r'(?:DLN|DAQ|4D)\s*(\d{8,10})|(\d{8,10})', clean_text)
    if daq_m:
        results["DAQ (驾照号)"] = daq_m.group(1) or daq_m.group(2)

    # 2. 姓名处理：通过模糊匹配标签 '1' 和 '2'
    # 容错处理：有时 OCR 会把 '1' 识别为 'I' 或 'L'
    ln_m = re.search(r'(?:1|I|L)\s+([A-Z]{3,})', clean_text)
    if ln_m: results["DCS (1 姓氏)"] = ln_m.group(1)
    
    fn_m = re.search(r'(?:2|Z)\s+([A-Z]{3,})', clean_text)
    if fn_m: results["DAC (2 名字)"] = fn_m.group(1)

    # 3. 日期类处理：提取所有符合 MM/DD/YYYY 的内容
    dates = re.findall(r'\d{2}/\d{2}/\d{4}', clean_text)
    # 根据 PA 布局习惯分配：
    # 第一个是 DOB (3), 第二个是 ISS (4a), 第三个是 EXP (4b)
    # 或者通过关键词重新定位
    for d in dates:
        if re.search(r'DOB\s*' + d, clean_text) or "3" in clean_text:
            results["DBB (DOB 生日)"] = d
        if re.search(r'EXP\s*' + d, clean_text) or "4B" in clean_text:
            results["DBA (EXP 过期)"] = d
        if re.search(r'ISS\s*' + d, clean_text) or "4A" in clean_text:
            results["DBD (ISS 签发)"] = d
    
    # 如果关键词没匹配上，按日期出现的物理顺序兜底
    if results["DBA (EXP 过期)"] == "未检测" and len(dates) >= 1:
        results["DBA (EXP 过期)"] = dates[0]
    if results["DBB (DOB 生日)"] == "未检测" and len(dates) >= 2:
        results["DBB (DOB 生日)"] = dates[1]

    # 4. 地址处理：匹配标签 '8'
    addr_m = re.search(r'8\s+([A-Z0-9\s]{10,})', clean_text)
    if addr_m:
        # 截断可能的后续干扰，只取前 40 个字符
        results["DAG (8 地址)"] = addr_m.group(1).strip()[:40]

    # 5. 档案号 (DD/DCJ)
    dd_m = re.search(r'DD\s*(\d{2,})|DUPE\s*(\d{2,})', clean_text)
    if dd_m:
        results["DCJ (DD 档案号)"] = dd_m.group(1) or dd_m.group(2)

    return results
