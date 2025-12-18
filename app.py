# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re
import cv2
import pandas as pd
import gc  # 内存回收

# --- 1. 页面配置 ---
st.set_page_config(page_title="PA Scanner Pro", layout="centered")

# --- 2. 内存优化模型加载 ---
@st.cache_resource
def load_ocr_model():
    # 仅加载英文，关闭显卡加速（防止云端驱动冲突）
    return easyocr.Reader(['en'], gpu=False, download_enabled=True)

# --- 3. 极速提取逻辑 (针对 1, 2, 8 编号) ---
def extract_pa_fields(text_list):
    raw_text = " ".join(text_list).upper()
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

    # 正则提取规则
    id_m = re.search(r'(?:DLN|DAQ|4D)\s*([0-9]{8,10})', clean_text)
    if id_m: results["DAQ (驾照号)"] = id_m.group(1)

    # 姓名：容错匹配 1 和 2
    ln_m = re.search(r'(?:1|I|L)\s+([A-Z]+)', clean_text)
    if ln_m: results["DCS (1 姓氏)"] = ln_m.group(1)
    
    fn_m = re.search(r'(?:2|Z)\s+([A-Z]+)', clean_text)
    if fn_m: results["DAC (2 名字)"] = fn_m.group(1)

    # 日期类
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean_text)
    if len(dates) >= 1: results["DBA (EXP 过期)"] = dates[0]
    if len(dates) >= 2: results["DBB (DOB 生日)"] = dates[1]
    if len(dates) >= 3: results["DBD (ISS 签发)"] = dates[2]

    # 地址与档案号
    addr_m = re.search(r'8\s+([A-Z0-9\s]{10,})', clean_text)
    if addr_m: results["DAG (8 地址)"] = addr_m.group(1).strip()[:35]
    
    dd_m = re.search(r'(?:DD|DUPE)\s*([0-9]{2,})', clean_text)
    if dd_m: results["DCJ (DD 档案号)"] = dd_m.group(1)

    return results

# --- 4. 主程序 ---
st.title("🪪 PA 驾驶证极速识别")
st.write("上传后点击识别按钮，若白屏请刷新重试。")

img_file = st.file_uploader("上传证件正面", type=['jpg', 'jpeg', 'png'])

if img_file:
    # 1. 压缩显示
    image = Image.open(img_file)
    st.image(image, width=400)
    
    # 2. 识别触发（不放在 form 里，减少交互层级）
    if st.button("🚀 开始极速识别", type="primary"):
        try:
            with st.spinner("正在处理..."):
                # 图像预压缩提速
                img_np = np.array(image)
                h, w = img_np.shape[:2]
                img_small = cv2.resize(img_np, (800, int(h*(800/w))))
                img_gray = cv2.cvtColor(img_small, cv2.COLOR_RGB2GRAY)
                
                # OCR 过程
                reader = load_ocr_model()
                ocr_results = reader.readtext(img_gray, detail=0, paragraph=True)
                
                # 数据提取
                data = extract_pa_fields(ocr_results)
                
                # 显示结果
                st.success("识别完成！")
                st.table(pd.DataFrame(list(data.items()), columns=["字段标签", "内容"]))
                
                # 清理内存
                del img_np, img_small, img_gray
                gc.collect() 
        except Exception as e:
            st.error(f"识别出错: {e}")
            st.info("建议检查图片是否清晰且无大面积反光。")
