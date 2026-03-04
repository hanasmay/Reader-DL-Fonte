# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_cropper import st_cropper
import numpy as np
from PIL import Image, ImageOps
import cv2
import re
import gc

# --- 1. 配置 ---
st.set_page_config(page_title="Clean Data Extractor", layout="wide")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 核心：终极清洗函数 ---
def ultimate_clean(ocr_list):
    # 需要删除的 AAMVA 标签及证件固定标题
    # 增加对 4b.Exp, 4a.Iss, 8., 1., 2. 等标签的模糊匹配
    junk_patterns = [
        r'\b[1-9][ab]?\.\s?(?:EXP|ISS|DOB|ID|DL)?', # 匹配 4a.Iss, 4b.Exp, 8. 等
        r'\b(?:EXP|ISS|DOB|CLASS|REST|END|HGT|WGT|EYES|SEX|DIRECTOR)\b',
        r'DRIVER\s?LICENSE', r'Licenseio', r'STATE\s?OF', r'FEDERAL\s?LIMITS',
        r'NOT\s?FOR\s?FEDERAL', r'USA', r'ORGAN\s?DONOR', r'AUDIT', r'DL\b',
        r'\b[0-9]{1,2}\.\s', # 匹配类似 12. 16. 18. 的孤立编号
    ]
    
    # 50 州全称正则
    states_pattern = r'ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW\s?HAMPSHIRE|NEW\s?JERSEY|NEW\s?MEXICO|NEW\s?YORK|NORTH\s?CAROLINA|NORTH\s?DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s?ISLAND|SOUTH\s?CAROLINA|SOUTH\s?DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s?VIRGINIA|WISCONSIN|WYOMING'

    raw_text = " ".join(ocr_list)
    # 预先处理一些顽固字符
    raw_text = re.sub(r'[:"\'\$#_!;]', '', raw_text)
    
    # 将文本打散成段落
    lines = raw_text.split(' ')
    processed_stream = " ".join(lines)
    
    # 1. 批量剔除黑名单模式
    for p in junk_patterns:
        processed_stream = re.sub(p, '', processed_stream, flags=re.IGNORECASE)
    # 2. 剔除州名
    processed_stream = re.sub(states_pattern, '', processed_stream, flags=re.IGNORECASE)
    
    # 3. 智能分行逻辑 (核心优化)
    # 只要检测到日期、全大写长单词(名字)、或者是连续长数字(DLN)，就强制换行
    # 日期前换行
    processed_stream = re.sub(r'(\d{2}/\d{2}/\d{4})', r'\n\1', processed_stream)
    # 可能是地址的开头 (数字+空格+字母) 前换行
    processed_stream = re.sub(r'(\s\d{2,5}\s[A-Z])', r'\n\1', processed_stream)
    
    # 4. 最后清理多余空格和零碎单字符
    final_lines = []
    for line in processed_stream.split('\n'):
        line = line.strip()
        # 移除行首的干扰字符如 'g 78'
        line = re.sub(r'^[a-z]\s[0-9]{1,2}\s', '', line)
        if len(line) > 3: # 过滤掉极短的碎片
            final_lines.append(line)
            
    return final_lines

# --- 3. 界面 ---
st.title("🪪 极致纯净数据提取器")

img_source = st.file_uploader("上传证件照片", type=['jpg','png','jpeg']) or st.camera_input("实时拍照")

if img_source:
    raw_img = ImageOps.exif_transpose(Image.open(img_source))
    col_l, col_r = st.columns([1, 1])
    
    with col_l:
        st.subheader("✂️ 选取数据区域")
        cropped_img = st_cropper(raw_img, box_color='#00FF00', aspect_ratio=None)
        st.image(cropped_img, use_container_width=True)

    with col_r:
        if st.button("🚀 提取并清洗数据", type="primary", use_container_width=True):
            with st.spinner("正在剥离标签与干扰项..."):
                reader = load_reader()
                results = reader.readtext(np.array(cropped_img), detail=0, paragraph=True)
                clean_lines = ultimate_clean(results)
                
                if clean_lines:
                    st.subheader("💎 纯净数据字段")
                    for i, val in enumerate(clean_lines):
                        st.text_input(f"字段 {i+1}", val, key=f"d_{i}")
                    
                    st.subheader("📄 汇总 (已自动分行)")
                    st.text_area("Final Output", "\n".join(clean_lines), height=300)
                else:
                    st.warning("未能解析到足够数据，请调整裁剪范围。")
                gc.collect()
