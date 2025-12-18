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
    # 初始化 EasyOCR 引擎
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 智能过滤与黑名单引擎 ---
def intelligent_filter(ocr_list):
    # A. 50 州全称黑名单 (包含常见的 "STATE OF..." 前缀)
    full_states = [
        "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT", 
        "DELAWARE", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO", "ILLINOIS", "INDIANA", "IOWA", 
        "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN", 
        "MINNESOTA", "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA", "NEW HAMPSHIRE", 
        "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA", "NORTH DAKOTA", "OHIO", 
        "OKLAHOMA", "OREGON", "PENNSYLVANIA", "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA", 
        "TENNESSEE", "TEXAS", "UTAH", "VERMONT", "VIRGINIA", "WASHINGTON", "WEST VIRGINIA", 
        "WISCONSIN", "WYOMING", "DISTRICT OF COLUMBIA"
    ]
    
    # B. 其他需要隐藏的干扰词
    hidden_phrases = [
        "DRIVER LICENSE", "DRIVERS LICENSE", "DL", "IDENTIFICATION CARD", "ID",
        "FEDERAL LIMITS APPLY", "NOT FOR FEDERAL IDENTIFICATION", "NOT FOR REAL ID",
        "USA", "ORGAN DONOR", "COMMERCIAL", "CDL", "TEMPORARY", "STATE OF", "COMMONWEALTH OF"
    ]

    filtered_data = []
    
    for text in ocr_list:
        clean_text = text.strip().upper()
        
        # --- 核心保护规则：如果是驾照号（含7位以上数字），强制通过 ---
        if re.search(r'\d{7,}', clean_text):
            filtered_data.append(text)
            continue
            
        # --- 过滤规则 1：隐藏州全称 ---
        # 检查段落是否完全匹配州名，或者包含 "STATE OF [州名]"
        is_state_name = False
        for state in full_states:
            if state == clean_text or f"STATE OF {state}" in clean_text or f"COMMONWEALTH OF {state}" in clean_text:
                is_state_name = True
                break
        if is_state_name:
            continue
            
        # --- 过滤规则 2：隐藏 Driver License / DL 等干扰词 ---
        is_hidden_phrase = False
        for phrase in hidden_phrases:
            # 使用边界匹配，防止误删单词内的字母（如 Midland）
            if re.search(rf'\b{re.escape(phrase)}\b', clean_text):
                is_hidden_phrase = True
                break
        if is_hidden_phrase:
            continue
            
        # --- 过滤规则 3：过滤极短的干扰符 ---
        if len(clean_text) < 2 and not clean_text.isdigit():
            continue
            
        filtered_data.append(text)
        
    return filtered_data

# --- 3. UI 交互界面 ---
st.title("🪪 50州驾照核心数据扫描器")
st.markdown("已自动过滤：**各州全称**、**STATE OF...**、**DRIVER LICENSE** 及 **DL** 字样。")

# 输入源
src = st.radio("选择图片来源", ["📷 实时拍照识别", "📁 上传图片识别"], horizontal=True)
img_source = st.camera_input("拍照") if src == "📷 实时拍照识别" else st.file_uploader("选择文件", type=['jpg','jpeg','png'])

if img_source:
    raw_img = Image.open(img_source)
    raw_img = ImageOps.exif_transpose(raw_img) # 自动纠正手机拍摄倾斜
    
    col_l, col_r = st.columns([1.2, 1])
    
    with col_l:
        st.subheader("✂️ 自由选取识别区")
        st.info("建议：框选姓名、地址、日期所在区域，避开顶部的州标题。")
        # 自由比例裁剪
        cropped_img = st_cropper(raw_img, realtime_update=True, box_color='#FF4B4B', aspect_ratio=None)
        st.image(cropped_img, caption="待处理区域", use_container_width=True)

    with col_r:
        st.subheader("📑 提取的核心数据")
        if st.button("🚀 执行过滤识别", type="primary", use_container_width=True):
            with st.spinner("神经网络正在扫描并清洗数据..."):
                # 图像处理加速
                roi_np = np.array(cropped_img)
                gray = cv2.cvtColor(roi_np, cv2.COLOR_RGB2GRAY)
                
                # 执行 OCR (段落模式)
                reader = load_reader()
                raw_results = reader.readtext(gray, detail=0, paragraph=True)
                
                # 过滤冗余信息
                final_results = intelligent_filter(raw_results)
                
                if final_results:
                    # 结果展示
                    for item in final_results:
                        st.code(item, language=None)
                    
                    st.text_area("批量结果（可复制）", "\n".join(final_results), height=200)
                else:
                    st.warning("未检测到有效个人数据，请确保裁剪框内包含文字。")
                
                # 显式内存清理
                del roi_np, gray
                gc.collect()

        st.markdown("""
        **当前过滤策略：**
        1. **自动跳过**：如 PENNSYLVANIA, NEW YORK, STATE OF CALIFORNIA 等。
        2. **自动隐藏**：如 DL, DRIVER LICENSE, USA, ORGAN DONOR。
        3. **强制保留**：任何包含 7 位以上连续数字的行（视为驾照号或档案号）。
        """)
