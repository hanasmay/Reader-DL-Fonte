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
st.set_page_config(page_title="Deep Cleaner OCR", layout="wide")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 深度数据清洗引擎 ---
def extreme_clean(ocr_list):
    # 需要彻底从行内抠除的干扰词（包含误读变形）
    junk_patterns = [
        r'DRIVER\s?LICENSE', r'Licenseio', r'PERSONAL', r'Director',
        r'STATE\s?OF', r'CLASS', r'EXPIRANONDAIE', r'EXPIRATION', r'DATE',
        r'HASUE\s?DATE', r'ISSUE', r'HUR', r'NO\s?\.', r'NO\s', r'NONE',
        r'RESTRICTIONS?', r'ENDORSEMENTS?', r'SEX', r'HGT', r'WGT', r'EYES',
        r'OFFICE', r'AUDIT', r'PARISH', r'DONOR', r'LIMITS', r'APPLY',
        r'USA', r'IDENTIFICATION', r'COMMONWEALTH'
    ]
    
    # 50 州名称正则
    states_pattern = r'ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW\s?HAMPSHIRE|NEW\s?JERSEY|NEW\s?MEXICO|NEW\s?YORK|NORTH\s?CAROLINA|NORTH\s?DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s?ISLAND|SOUTH\s?CAROLINA|SOUTH\s?DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s?VIRGINIA|WISCONSIN|WYOMING'

    final_lines = []
    
    # 展开 OCR 段落
    for text in ocr_list:
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # --- 步骤 1: 逐个抠除干扰词 ---
            for p in junk_patterns:
                line = re.sub(p, '', line, flags=re.IGNORECASE)
            # 抠除州名
            line = re.sub(states_pattern, '', line, flags=re.IGNORECASE)
            
            # --- 步骤 2: 清理残余符号（冒号、引号、多余空格） ---
            line = re.sub(r'[:"\'\$#_]', '', line)
            line = re.sub(r'\s+', ' ', line).strip()
            
            # --- 步骤 3: 逻辑过滤 ---
            # 过滤掉清理后只剩 1-2 个字符的无意义碎渣
            if len(line) < 3 and not line.isdigit():
                continue
            # 过滤掉纯英文的“DONOR”等残留（如果没被匹配到）
            if line.upper() in ["DONOR", "PARISH", "SEX", "EYES"]:
                continue
                
            final_lines.append(line)
            
    return final_lines

# --- 3. UI 界面 ---
st.title("🪪 核心数据提取器 (极致清洗版)")
st.markdown("已自动剥离所有证件标题、州名及法律标签。")

src = st.radio("图片来源", ["📷 拍照", "📁 上传"], horizontal=True)
img_source = st.camera_input("拍照") if src == "📷 拍照" else st.file_uploader("上传文件", type=['jpg','png','jpeg'])

if img_source:
    raw_img = ImageOps.exif_transpose(Image.open(img_source))
    col_l, col_r = st.columns([1.2, 1])
    
    with col_l:
        # 允许自由比例裁剪
        cropped_img = st_cropper(raw_img, realtime_update=True, box_color='#00FF00', aspect_ratio=None)
        st.image(cropped_img, caption="扫描区", use_container_width=True)

    with col_r:
        if st.button("🚀 提取核心数据", type="primary", use_container_width=True):
            with st.spinner("深度清洗中..."):
                roi_np = np.array(cropped_img)
                # 图像增强加速识别
                gray = cv2.cvtColor(roi_np, cv2.COLOR_RGB2GRAY)
                
                reader = load_reader()
                # 识别参数微调：加强对比度处理
                results = reader.readtext(gray, detail=0, paragraph=True, adjust_contrast=0.8)
                
                # 执行极致清洗
                clean_data = extreme_clean(results)
                
                if clean_data:
                    st.subheader("📋 纯净数据字段")
                    for i, val in enumerate(clean_data):
                        st.text_input(f"字段 {i+1}", val, key=f"data_{i}")
                    
                    st.divider()
                    st.subheader("📄 汇总 (可复制)")
                    st.text_area("Final Output", "\n".join(clean_data), height=250)
                else:
                    st.warning("未检测到数据，请尝试调整红框。")
                
                del roi_np, gray
                gc.collect()
