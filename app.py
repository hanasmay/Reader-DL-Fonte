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
st.set_page_config(page_title="Deep Data Cleaner", layout="wide")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 深度清洗引擎 (核心升级) ---
def deep_clean_filter(ocr_list):
    # 50 州全称正则表达式 (用于匹配并删除行内的州名)
    states_pattern = r'ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW\s?HAMPSHIRE|NEW\s?JERSEY|NEW\s?MEXICO|NEW\s?YORK|NORTH\s?CAROLINA|NORTH\s?DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s?ISLAND|SOUTH\s?CAROLINA|SOUTH\s?DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s?VIRGINIA|WISCONSIN|WYOMING'
    
    # 需要从行内彻底删除的废词
    junk_patterns = [
        r'DRIVER\s?LICENSE', r'DRIVERS\s?LICENSE', r'IDENTIFICATION\s?CARD', 
        r'FEDERAL\s?LIMITS\s?APPLY', r'NOT\s?FOR\s?FEDERAL.*', r'DIRECTOR:', 
        r'STATE\s?OF', r'COMMONWEALTH\s?OF', r'ORGAN\s?DONOR', r'USA'
    ]

    cleaned_data = []
    
    # 将 OCR 返回的列表展开（处理由于 paragraph=True 导致的合并块）
    raw_lines = []
    for text in ocr_list:
        # 如果一段话里有换行，拆分成单行处理
        raw_lines.extend(text.split('\n'))

    for line in raw_lines:
        current_line = line.strip()
        if not current_line: continue
        
        # --- 步骤 1: 行内关键词剔除 ---
        # 逐个剔除法律条文和标题
        for p in junk_patterns:
            current_line = re.sub(p, '', current_line, flags=re.IGNORECASE)
        
        # 剔除州名
        current_line = re.sub(states_pattern, '', current_line, flags=re.IGNORECASE)
        
        # --- 步骤 2: 清理多余符号和空格 ---
        current_line = current_line.replace(':', '').strip()
        current_line = re.sub(r'\s+', ' ', current_line) # 合并多余空格
        
        # --- 步骤 3: 最终有效性检查 ---
        # 过滤掉清理后只剩下个别字母或空行的噪声
        if len(current_line) < 3 and not current_line.isdigit():
            continue
            
        cleaned_data.append(current_line)
        
    return cleaned_data

# --- 3. UI 界面 ---
st.title("🪪 50州驾照核心数据精准清洗")
st.markdown("该版本已强化：自动抠除行内的 **州名**、**DRIVER LICENSE**、**Director** 等干扰项。")

# 拍照或上传
src = st.radio("选择输入源", ["📷 拍照", "📁 上传"], horizontal=True)
img_source = st.camera_input("拍照") if src == "📷 拍照" else st.file_uploader("上传文件", type=['jpg','png','jpeg'])

if img_source:
    raw_img = ImageOps.exif_transpose(Image.open(img_source))
    col_l, col_r = st.columns([1.2, 1])
    
    with col_l:
        # 自由裁剪
        cropped_img = st_cropper(raw_img, realtime_update=True, box_color='#FF4B4B', aspect_ratio=None)
        st.image(cropped_img, caption="扫描区域", use_container_width=True)

    with col_r:
        if st.button("🚀 执行深度扫描并清洗", type="primary", use_container_width=True):
            with st.spinner("正在逐行剥离非核心数据..."):
                roi_np = np.array(cropped_img)
                reader = load_reader()
                # 识别时 detail=0, paragraph=True 确保段落完整性
                raw_results = reader.readtext(roi_np, detail=0, paragraph=True)
                
                # 执行深度清洗
                final_list = deep_clean_filter(raw_results)
                
                if final_list:
                    st.subheader("📋 清洗后的核心字段")
                    for i, item in enumerate(final_list):
                        st.text_input(f"字段 {i+1}", item, key=f"f_{i}")
                    
                    st.divider()
                    st.subheader("📄 完整汇总 (可直接复制)")
                    st.text_area("汇总结果", "\n".join(final_list), height=250)
                else:
                    st.warning("未检测到有效个人信息，请重新调整红框位置。")
