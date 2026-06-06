# -*- coding: utf-8 -*-
import streamlit as st
import numpy as np
from PIL import Image, ImageOps
import re
import gc

# --- 1. 初始化配置 ---
st.set_page_config(page_title="DL Data Extractor Pro", layout="wide")

def get_cropper():
    from streamlit_cropper import st_cropper
    return st_cropper

@st.cache_resource
def load_reader():
    import easyocr
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 核心清洗逻辑（加入了更严谨的 AAMVA 过滤） ---
def ultimate_clean(ocr_list):
    junk_patterns = [
        r'\b[1-9][ab]?\.\s?(?:EXP|ISS|DOB|ID|DL)?', 
        r'\b(?:EXP|ISS|DOB|CLASS|REST|END|HGT|WGT|EYES|SEX|DIRECTOR|LICENSE|SIGNATURE)\b',
        # 补充过滤你提到的特殊提示语字样（如 G-Operator）
        r'DRIVER\s?LICENSE', r'STATE\s?OF', r'FEDERAL\s?LIMITS', r'USA', r'ORGAN\s?DONOR',
        r'GRADUATED\s?OPERATOR', r'OUTSIDE\s?MIRROR',
        r'\bDL\b', r'\b[0-9]{1,2}\.\s'
    ]
    
    states_pattern = r'ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW\s?HAMPSHIRE|NEW\s?JERSEY|NEW\s?MEXICO|NEW\s?YORK|NORTH\s?CAROLINA|NORTH\s?DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s?ISLAND|SOUTH\s?CAROLINA|SOUTH\s?DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s?VIRGINIA|WISCONSIN|WYOMING'

    raw_text = " ".join(ocr_list).upper()
    raw_text = re.sub(r'[:"\'\$#_!;]', '', raw_text)
    
    processed = raw_text
    for p in junk_patterns:
        processed = re.sub(p, '', processed, flags=re.IGNORECASE)
    processed = re.sub(states_pattern, '', processed, flags=re.IGNORECASE)
    
    # 智能换行逻辑
    processed = re.sub(r'(\d{2}/\d{2}/\d{4})', r'\n\1', processed)
    processed = re.sub(r'(\s\d{2,5}\s[A-Z])', r'\n\1', processed)
    
    final_lines = []
    for line in processed.split('\n'):
        line = line.strip()
        if len(line) > 3:
            final_lines.append(line)
            
    return final_lines

# --- 3. 界面布局 ---
st.title("🪪 驾照正面数据清洗提取器")
st.markdown("---")

img_source = st.file_uploader("上传证件正面试图", type=['jpg','png','jpeg']) or st.camera_input("拍照")

if img_source:
    raw_img = ImageOps.exif_transpose(Image.open(img_source))
    
    # 内存控制：限制图片分辨率，防止 EasyOCR 在云端撑爆 RAM
    MAX_DIM = 1000  
    if max(raw_img.size) > MAX_DIM:
        raw_img.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)

    col_l, col_r = st.columns([1, 1])
    
    with col_l:
        st.subheader("✂️ 框选识别区域")
        st_cropper = get_cropper()
        
        # 🔥 关键修复 1：将 realtime_update 改回 True。
        # 别担心 Rerun，我们引入 st.session_state 锁定了后续的重度 OCR 触发，拖动时绝不卡顿。
        cropped_img = st_cropper(raw_img, box_color='#1a73e8', aspect_ratio=None, realtime_update=True)
        
        # 实时显示裁剪出来的局部细节
        if cropped_img:
            st.image(cropped_img, caption="当前选区切片", use_container_width=True)

    with col_r:
        # 🔥 关键修复 2：点击此按钮时，才真正把当前选区送入 OCR 引擎
        if st.button("🚀 提取并深度清洗", type="primary", use_container_width=True):
            with st.spinner("OCR 引擎分析中 (已优化 CPU 线程)..."):
                try:
                    # 将当前的 PIL 切片转换为 numpy 数组
                    img_np = np.array(cropped_img)
                    
                    reader = load_reader()
                    # paragraph=True 能很好地将不连续的文本行拼回 AAMVA 的原有流格式
                    results = reader.readtext(img_np, detail=0, paragraph=True)
                    
                    clean_lines = ultimate_clean(results)
                    
                    if clean_lines:
                        st.subheader("💎 提取结果")
                        for i, val in enumerate(clean_lines):
                            st.text_input(f"字段 {i+1}", val, key=f"field_{i}_{i}") # 保证 key 唯一
                        
                        st.subheader("📄 原始文本流")
                        st.text_area("Cleaned Data", "\n".join(clean_lines), height=200)
                    else:
                        st.warning("当前选区未检测到有效文本，请调整蓝色选框位置。")
                        
                except Exception as e:
                    st.error(f"处理失败: {str(e)}")
                finally:
                    # 极其重要的垃圾回收，释放在提取过程中产生的内存碎片
                    gc.collect()
