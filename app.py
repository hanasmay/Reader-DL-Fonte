# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re
import cv2
import pandas as pd
import gc

# --- 1. 页面设置 ---
st.set_page_config(page_title="PA 智能扫描终端", layout="centered")

# --- 2. 模型缓存 (内存优化) ---
@st.cache_resource
def load_ocr_model():
    return easyocr.Reader(['en'], gpu=False)

# --- 3. 强化版 PA 提取算法 ---
def extract_pa_fields_pro(text_list):
    raw_text = " ".join(text_list).upper()
    # 清理非必要字符，保留斜杠用于日期
    clean_text = re.sub(r'[^A-Z0-9\s/]', '', raw_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    results = {
        "DAQ (驾照号)": "未匹配",
        "DCS (1 姓氏)": "未匹配",
        "DAC (2 名字)": "未匹配",
        "DAG (8 地址)": "未匹配",
        "DBB (DOB 生日)": "未匹配",
        "DBA (EXP 过期)": "未匹配",
        "DBD (ISS 签发)": "未匹配",
        "DCJ (DD 档案号)": "未匹配"
    }

    # 1. 驾照号 (DAQ/DLN): 匹配 8-9 位连续数字
    daq_m = re.search(r'(?:DAQ|DLN|4D|NO)\s*(\d{8,10})|(\d{8,10})', clean_text)
    if daq_m:
        results["DAQ (驾照号)"] = daq_m.group(1) or daq_m.group(2)

    # 2. 姓氏 (标签 1): 模糊匹配 1, I, L
    ln_m = re.search(r'(?:1|I|L)\s+([A-Z]{2,})', clean_text)
    if ln_m: results["DCS (1 姓氏)"] = ln_m.group(1)
    
    # 3. 名字 (标签 2): 模糊匹配 2, Z, S
    fn_m = re.search(r'(?:2|Z|S)\s+([A-Z]{2,})', clean_text)
    if fn_m: results["DAC (2 名字)"] = fn_m.group(1)

    # 4. 日期组 (DOB, EXP, ISS)
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean_text)
    # PA 常见逻辑：第一个日期通常是 EXP，第二个是 DOB
    if len(dates) >= 1: results["DBA (EXP 过期)"] = dates[0]
    if len(dates) >= 2: results["DBB (DOB 生日)"] = dates[1]
    if len(dates) >= 3: results["DBD (ISS 签发)"] = dates[2]

    # 5. 地址 (标签 8)
    addr_m = re.search(r'(?:8|B)\s+(\d{1,5}\s[A-Z0-9\s]{5,})', clean_text)
    if addr_m:
        results["DAG (8 地址)"] = addr_m.group(1).strip()[:35]

    # 6. 档案号 (DD/DUPE)
    dd_m = re.search(r'(?:DD|DUPE)\s*(\d{2,})', clean_text)
    if dd_m: results["DCJ (DD 档案号)"] = dd_m.group(1)

    return results

# --- 4. 主程序界面 ---
st.title("🪪 PA 驾照智能识别终端")

# 输入源选择
src_mode = st.radio("选择输入源", ["📷 实时摄像头", "📁 上传图片文件"], horizontal=True)

img_buffer = None
if src_mode == "📷 实时摄像头":
    img_buffer = st.camera_input("请对准证件正面并点击拍照")
else:
    img_buffer = st.file_uploader("选择照片文件", type=['jpg', 'jpeg', 'png'])

if img_buffer:
    image = Image.open(img_buffer)
    st.image(image, caption="已捕获影像", width=450)
    
    if st.button("🚀 极速解析数据", type="primary"):
        with st.spinner("正在进行智能 OCR 解析..."):
            # 1. 预处理
            img_np = np.array(image)
            h, w = img_np.shape[:2]
            # 极限压缩提速至 750px 宽度
            img_small = cv2.resize(img_np, (750, int(h*(750/w))))
            img_gray = cv2.cvtColor(img_small, cv2.COLOR_RGB2GRAY)
            
            # 2. OCR 识别
            reader = load_ocr_model()
            # 关键参数：paragraph=True 能大幅提高“标签+内容”的合并成功率
            ocr_results = reader.readtext(img_gray, detail=0, paragraph=True)
            
            # 3. 解析
            final_data = extract_pa_fields_pro(ocr_results)
            
            # 4. 展示表格
            st.success("解析完成！")
            df = pd.DataFrame(list(final_data.items()), columns=["字段标签", "内容"])
            st.table(df)
            
            # 5. 内存释放
            del img_np, img_small, img_gray
            gc.collect()

    with st.expander("🛠️ 查看底层文字流"):
        if 'ocr_results' in locals():
            st.write(ocr_results)
