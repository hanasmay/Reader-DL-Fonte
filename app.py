# -*- coding: utf-8 -*-
import streamlit as st
import re

def extract_fields_v2(text_list):
    raw_text = " ".join(text_list).upper()
    # 移除干扰符号，保留斜杠用于日期
    clean_text = re.sub(r'[^A-Z0-9\s/]', '', raw_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    # 初始化结果字典
    results = {
        "DLN (DAQ)": "未检测",
        "姓氏 (1)": "未检测",
        "名字 (2)": "未检测",
        "地址 (8)": "未检测",
        "生日 (DOB)": "未检测",
        "过期日 (EXP)": "未检测",
        "签发日 (ISS)": "未检测",
        "档案号 (DD)": "未检测"
    }

    # 1. 驾照号 (DLN/DAQ) - 匹配 8-10 位数字
    dln_match = re.search(r'(?:DLN|DAQ|NO)\s*([0-9]{8,10})', clean_text)
    if dln_match: results["DLN (DAQ)"] = dln_match.group(1)

    # 2. 姓名处理 (1-姓, 2-名)
    # 宾州格式常见为: 1 LASTNAME 2 FIRSTNAME
    name_match = re.search(r'1\s+([A-Z]+)\s+2\s+([A-Z\s]+)', clean_text)
    if name_match:
        results["姓氏 (1)"] = name_match.group(1)
        results["名字 (2)"] = name_match.group(2).strip()

    # 3. 地址处理 (8) - 匹配 8 之后的街道地址
    addr_match = re.search(r'8\s+(\d{1,5}\s[A-Z0-9\s,]{10,})', clean_text)
    if addr_match: results["地址 (8)"] = addr_match.group(1).strip()

    # 4. 日期组 (DOB, EXP, ISS)
    # 匹配 MM/DD/YYYY 格式
    dob_match = re.search(r'(?:DOB|3)\s*(\d{2}/\d{2}/\d{4})', clean_text)
    if dob_match: results["生日 (DOB)"] = dob_match.group(1)

    exp_match = re.search(r'(?:EXP|4B)\s*(\d{2}/\d{2}/\d{4})', clean_text)
    if exp_match: results["过期日 (EXP)"] = exp_match.group(1)

    iss_match = re.search(r'(?:ISS|4A)\s*(\d{2}/\d{2}/\d{4})', clean_text)
    if iss_match: results["签发日 (ISS)"] = iss_match.group(1)

    # 5. 档案号 (DD) - 通常在底部或特定位置的长数字
    dd_match = re.search(r'(?:DD)\s*([0-9]{10,20})', clean_text)
    if dd_match: results["档案号 (DD)"] = dd_match.group(1)

    return results

# --- 数据映射展示 ---
st.subheader("📋 映射分析结果")
# 假设 text_list 为 OCR 识别出的内容
# results = extract_fields_v2(ocr_text_list)
# st.table(results)
