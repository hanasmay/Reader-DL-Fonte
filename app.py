# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_cropper import st_cropper
import easyocr
import numpy as np
from PIL import Image, ImageOps
import cv2
import re
import pandas as pd

# --- 1. 基础配置 ---
st.set_page_config(page_title="Core Data Extractor", layout="wide")

@st.cache_resource
def load_reader():
    # 加载 EasyOCR 模型
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 智能黑名单过滤引擎 ---
def intelligent_filter(ocr_list):
    # A. 50 州名称及缩写黑名单
    states_list = {
        "ALABAMA", "AL", "ALASKA", "AK", "ARIZONA", "AZ", "ARKANSAS", "AR", "CALIFORNIA", "CA", 
        "COLORADO", "CO", "CONNECTICUT", "CT", "DELAWARE", "DE", "FLORIDA", "FL", "GEORGIA", "GA", 
        "HAWAII", "HI", "IDAHO", "ID", "ILLINOIS", "IL", "INDIANA", "IN", "IOWA", "IA", "KANSAS", "KS", 
        "KENTUCKY", "KY", "LOUISIANA", "LA", "MAINE", "ME", "MARYLAND", "MD", "MASSACHUSETTS", "MA", 
        "MICHIGAN", "MI", "MINNESOTA", "MN", "MISSISSIPPI", "MS", "MISSOURI", "MO", "MONTANA", "MT", 
        "NEBRASKA", "NE", "NEVADA", "NV", "NEW HAMPSHIRE", "NH", "NEW JERSEY", "NJ", "NEW MEXICO", "NM", 
        "NEW YORK", "NY", "NORTH CAROLINA", "NC", "NORTH DAKOTA", "ND", "OHIO", "OH", "OKLAHOMA", "OK", 
        "OREGON", "OR", "PENNSYLVANIA", "PA", "RHODE ISLAND", "RI", "SOUTH CAROLINA", "SC", "SOUTH DAKOTA", "SD", 
        "TENNESSEE", "TN", "TEXAS", "TX", "UTAH", "UT", "VERMONT", "VT", "VIRGINIA", "VA", "WASHINGTON", "WA", 
        "WEST VIRGINIA", "WV", "WISCONSIN", "WI", "WYOMING", "WY", "DISTRICT OF COLUMBIA", "DC", "USA"
    }
    
    # B. 联邦限制及法律免责词库
    junk_phrases = [
        "FEDERAL LIMITS APPLY", "NOT FOR FEDERAL IDENTIFICATION", "NOT FOR REAL ID",
        "DRIVER LICENSE", "DRIVERS LICENSE", "IDENTIFICATION CARD", "USA", "ORGAN DONOR"
    ]

    filtered_data = []
    
    for text in ocr_list:
        clean_text = text.strip().upper()
        
        # --- 保护规则：如果是驾照号（通常含多位数字），直接保留 ---
        if re.search(r'\d{7,}', clean_text):
            filtered_data.append(text)
            continue
            
        # --- 过滤规则 1：检查是否为州名或缩写 ---
        if clean_text in states_list:
            continue
            
        # --- 过滤规则 2：检查是否包含联邦限制关键词 ---
        is_junk = False
        for junk in junk_phrases:
            if junk in clean_text:
                is_junk = True
                break
        if is_junk:
            continue
            
        # --- 过滤规则 3：过滤极短的无意义字符（如单个逗号或噪点） ---
        if len(clean_text) < 2 and not clean_text.isdigit():
            continue
            
        filtered_data.append(text)
        
    return filtered_data

# --- 3. UI 交互界面 ---
st.title("🪪 50州核心数据提取器 (智能过滤版)")
st.markdown("该工具会自动跳过**州名**与**联邦限制说明**，仅保留个人信息与驾照号。")

src = st.radio("选择照片来源", ["📷 实时拍照", "📁 上传文件"], horizontal=True)
img_source = st.camera_input("拍照") if src == "📷 实时拍照" else st.file_uploader("选择照片", type=['jpg','jpeg','png'])

if img_source:
    raw_img = Image.open(img_source)
    raw_img = ImageOps.exif_transpose(raw_img) # 自动纠正旋转
    
    col_l, col_r = st.columns([1.2, 1])
    
    with col_l:
        st.subheader("✂️ 框选文字区域")
        # 自由比例裁剪
        cropped_img = st_cropper(raw_img, realtime_update=True, box_color='#FF4B4B', aspect_ratio=None)
        st.image(cropped_img, caption="当前识别区域", use_container_width=True)

    with col_r:
        st.subheader("📊 过滤后的核心数据")
        if st.button("🚀 开始精准提取", type="primary", use_container_width=True):
            with st.spinner("正在解析并过滤冗余信息..."):
                # 图像预处理
                roi_np = np.array(cropped_img)
                gray = cv2.cvtColor(roi_np, cv2.COLOR_RGB2GRAY)
                
                # 执行 OCR (段落合并模式)
                reader = load_reader()
                raw_results = reader.readtext(gray, detail=0, paragraph=True)
                
                # 执行智能过滤
                final_results = intelligent_filter(raw_results)
                
                if final_results:
                    for i, item in enumerate(final_results):
                        st.info(f"数据段 {i+1}: **{item}**")
                    
                    # 生成可复制的文本块
                    st.text_area("一键复制结果", "\n".join(final_results), height=150)
                else:
                    st.warning("未检测到有效核心数据，请调整裁剪框。")

        st.markdown("""
        **过滤逻辑说明：**
        * **保留**：姓名、地址、日期、驾照号、分类(Class)等。
        * **跳过**：50州名称(如 CALIFORNIA)、联邦限制语(如 REAL ID 字样)、证件标题。
        """)
