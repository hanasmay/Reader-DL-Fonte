# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_cropper import st_cropper
import easyocr
import numpy as np
from PIL import Image, ImageOps
import cv2
import re
import gc

# --- 1. 基础配置 ---
st.set_page_config(page_title="Core Data Extractor", layout="wide", page_icon="🪪")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 智能过滤引擎 ---
def intelligent_filter(ocr_list):
    # 50 州全称黑名单
    full_states = {
        "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT", 
        "DELAWARE", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO", "ILLINOIS", "INDIANA", "IOWA", 
        "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN", 
        "MINNESOTA", "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA", "NEW HAMPSHIRE", 
        "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA", "NORTH DAKOTA", "OHIO", 
        "OKLAHOMA", "OREGON", "PENNSYLVANIA", "PA", "RHODE ISLAND", "RI", "SOUTH CAROLINA", "SC", 
        "SOUTH DAKOTA", "SD", "TENNESSEE", "TEXAS", "UTAH", "VERMONT", "VIRGINIA", "WASHINGTON", 
        "WEST VIRGINIA", "WV", "WISCONSIN", "WI", "WYOMING", "DISTRICT OF COLUMBIA"
    }
    
    hidden_phrases = [
        "DRIVER LICENSE", "DRIVERS LICENSE", "DL", "IDENTIFICATION CARD", "ID",
        "FEDERAL LIMITS APPLY", "NOT FOR FEDERAL IDENTIFICATION", "NOT FOR REAL ID",
        "USA", "ORGAN DONOR", "COMMERCIAL", "CDL", "TEMPORARY", "STATE OF", "COMMONWEALTH OF"
    ]

    filtered_data = []
    for text in ocr_list:
        clean_text = text.strip().upper()
        
        # 保护规则：含长数字（驾照号）必保留
        if re.search(r'\d{7,}', clean_text):
            filtered_data.append(text)
            continue
            
        # 过滤州全称
        is_state = False
        for state in full_states:
            if state == clean_text or f"STATE OF {state}" in clean_text or f"COMMONWEALTH OF {state}" in clean_text:
                is_state = True
                break
        if is_state: continue
            
        # 过滤干扰词（使用正则边界匹配避免误伤）
        is_hidden = False
        for phrase in hidden_phrases:
            if re.search(rf'\b{re.escape(phrase)}\b', clean_text):
                is_hidden = True
                break
        if is_hidden: continue
            
        # 过滤过短字符
        if len(clean_text) < 2 and not clean_text.isdigit():
            continue
            
        filtered_data.append(text)
        
    return filtered_data

# --- 3. UI 交互界面 ---
st.title("🪪 50州驾照核心数据扫描终端")
st.markdown("该版本将**逐个字段输出**清洗后的数据，并附带**完整汇总**。")

# 输入源
src = st.radio("选择图片来源", ["📷 拍照识别", "📁 上传图片"], horizontal=True)
img_source = st.camera_input("拍照") if src == "📷 拍照识别" else st.file_uploader("上传文件", type=['jpg','jpeg','png'])

if img_source:
    raw_img = Image.open(img_source)
    raw_img = ImageOps.exif_transpose(raw_img)
    
    col_l, col_r = st.columns([1.2, 1])
    
    with col_l:
        st.subheader("✂️ 裁剪核心文字区")
        cropped_img = st_cropper(raw_img, realtime_update=True, box_color='#FF4B4B', aspect_ratio=None)
        st.image(cropped_img, caption="当前扫描区域", use_container_width=True)

    with col_r:
        st.subheader("📑 字段解析结果")
        if st.button("🚀 开始精准提取", type="primary", use_container_width=True):
            with st.spinner("正在逐个字段清洗数据..."):
                # 图像处理
                roi_np = np.array(cropped_img)
                gray = cv2.cvtColor(roi_np, cv2.COLOR_RGB2GRAY)
                
                # 执行 OCR
                reader = load_reader()
                raw_results = reader.readtext(gray, detail=0, paragraph=True)
                
                # 执行智能过滤
                final_results = intelligent_filter(raw_results)
                
                if final_results:
                    # --- 逐个字段输出 ---
                    for i, item in enumerate(final_results):
                        # 使用 columns 让输出更有条理
                        c_idx, c_val = st.columns([1, 4])
                        c_idx.markdown(f"**字段 {i+1}**")
                        c_val.info(item)
                    
                    st.divider()
                    
                    # --- 完整数据汇总输出 ---
                    st.subheader("📋 完整数据汇总")
                    full_text = "\n".join(final_results)
                    st.text_area("点击下方框内内容可直接全选复制", full_text, height=200)
                    
                    st.success(f"共提取到 {len(final_results)} 条核心数据段。")
                else:
                    st.warning("未检测到有效数据，请确保红框覆盖了姓名、地址或驾照号区域。")
                
                del roi_np, gray
                gc.collect()

        st.info("💡 建议：如果某个字段被错误隐藏，请尝试在裁剪时多包含一点周边文字。")
