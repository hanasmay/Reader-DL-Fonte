# -*- coding: utf-8 -*-
import streamlit as st
import numpy as np
from PIL import Image, ImageOps
import re
import gc
import io

# --- 1. 初始化配置 ---
st.set_page_config(page_title="DL Data Extractor Pro", layout="wide")

# 延迟导入，极大提高启动稳定性
def get_cropper():
    from streamlit_cropper import st_cropper
    return st_cropper

@st.cache_resource
def load_reader():
    import easyocr
    # 强制单线程/CPU，减少模型寻址时间
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 核心清洗逻辑 ---
def ultimate_clean(ocr_list):
    junk_patterns = [
        r'\b[1-9][ab]?\.\s?(?:EXP|ISS|DOB|ID|DL)?',
        r'\b(?:EXP|ISS|DOB|CLASS|REST|END|HGT|WGT|EYES|SEX|DIRECTOR|LICENSE|SIGNATURE)\b',
        r'DRIVER\s?LICENSE', r'STATE\s?OF', r'FEDERAL\s?LIMITS', r'USA', r'ORGAN\s?DONOR',
        r'\bDL\b', r'\b[0-9]{1,2}\.\s'
    ]
    states_pattern = r'ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW\s?HAMPSHIRE|NEW\s?JERSEY|NEW\s?MEXICO|NEW\s?YORK|NORTH\s?CAROLINA|NORTH\s?DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s?ISLAND|SOUTH\s?CAROLINA|SOUTH\s?DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s?VIRGINIA|WISCONSIN|WYOMING'

    raw_text = " ".join(ocr_list).upper()
    raw_text = re.sub(r'[:"\'\$#_!;]', '', raw_text)
    
    processed = raw_text
    for p in junk_patterns:
        processed = re.sub(p, '', processed, flags=re.IGNORECASE)
    processed = re.sub(states_pattern, '', processed, flags=re.IGNORECASE)
    
    # 智能分行
    processed = re.sub(r'(\d{2}/\d{2}/\d{4})', r'\n\1', processed)
    processed = re.sub(r'(\s\d{2,5}\s[A-Z])', r'\n\1', processed)
    
    final_lines = []
    for line in processed.split('\n'):
        line = line.strip()
        if len(line) > 3:
            final_lines.append(line)
    return final_lines

# --- 3. 粘贴功能增强 ---
def get_pasted_image():
    from streamlit_paste_button import paste_image_button
    # 这个按钮点击后会直接读取剪贴板图片
    pasted_image = paste_image_button(
        label="📋 点击此处粘贴截图 (Ctrl+V)",
        background_color="#f0f2f6",
        hover_color="#e0e4ea",
        errors="ignore"
    )
    if pasted_image.image_data is not None:
        return pasted_image.image_data
    return None

# --- 4. 界面布局 ---
st.title("🪪 驾照正面数据清洗提取器")
st.info("提示：截图后点击下方的粘贴按钮，或直接拖拽文件。识别慢是正常现象（CPU限制）。")

# 三种导入方式并存
img_source = None
c1, c2 = st.columns(2)
with c1:
    pasted_data = get_pasted_image()
with c2:
    uploaded_file = st.file_uploader("或上传文件", type=['jpg','png','jpeg'])

# 确定数据源
final_source = pasted_data if pasted_data else uploaded_file

if final_source:
    # 统一转为 Image 对象
    if isinstance(final_source, Image.Image):
        raw_img = final_source
    else:
        raw_img = Image.open(final_source)
        
    raw_img = ImageOps.exif_transpose(raw_img)
    
    # 强制缩放：这是提速的关键，防止内存溢出同时也减少了像素处理点
    MAX_DIM = 1000 
    if max(raw_img.size) > MAX_DIM:
        raw_img.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)

    col_l, col_r = st.columns([1, 1])
    
    with col_l:
        st.subheader("✂️ 框选识别区域")
        st_cropper = get_cropper()
        # 实时更新关闭，点击下方识别按钮再触发
        cropped_img = st_cropper(raw_img, box_color='#1a73e8', aspect_ratio=None, realtime_update=False)
        st.image(cropped_img, caption="选区预览", use_container_width=True)

    with col_r:
        if st.button("🚀 提取并深度清洗", type="primary", use_container_width=True):
            with st.spinner("正在分析（CPU 模式约需 5-10 秒）..."):
                try:
                    # 转为灰度图可略微提高文字对比度和识别速度
                    process_img = ImageOps.grayscale(cropped_img)
                    reader = load_reader()
                    
                    results = reader.readtext(np.array(process_img), detail=0, paragraph=True)
                    clean_lines = ultimate_clean(results)
                    
                    if clean_lines:
                        st.subheader("💎 提取结果")
                        for i, val in enumerate(clean_lines):
                            st.text_input(f"字段 {i+1}", val, key=f"field_{i}")
                        
                        st.text_area("汇总文本", "\n".join(clean_lines), height=150)
                    else:
                        st.warning("未检测到字符，请重新选区。")
                except Exception as e:
                    st.error(f"解析出错: {e}")
                finally:
                    gc.collect()
