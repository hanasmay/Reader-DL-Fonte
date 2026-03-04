# -*- coding: utf-8 -*-
import streamlit as st
import numpy as np
from PIL import Image, ImageOps
import re
import gc

# --- 1. 初始化配置 ---
st.set_page_config(page_title="DL Data Extractor Pro", layout="wide")

# 延迟导入组件，减少启动内存占用
def get_cropper():
    from streamlit_cropper import st_cropper
    return st_cropper

@st.cache_resource
def load_reader():
    # 仅在需要时导入并加载模型
    import easyocr
    # gpu=False 是云端稳定运行的关键
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 核心清洗逻辑 ---
def ultimate_clean(ocr_list):
    # 定义 AAMVA 标签及冗余字符正则模式
    junk_patterns = [
        r'\b[1-9][ab]?\.\s?(?:EXP|ISS|DOB|ID|DL)?', # 匹配 4a.Iss, 4b.Exp, 8. 等标签
        r'\b(?:EXP|ISS|DOB|CLASS|REST|END|HGT|WGT|EYES|SEX|DIRECTOR|LICENSE|SIGNATURE)\b',
        r'DRIVER\s?LICENSE', r'STATE\s?OF', r'FEDERAL\s?LIMITS', r'USA', r'ORGAN\s?DONOR',
        r'\bDL\b', r'\b[0-9]{1,2}\.\s'
    ]
    
    # 50 州名正则
    states_pattern = r'ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW\s?HAMPSHIRE|NEW\s?JERSEY|NEW\s?MEXICO|NEW\s?YORK|NORTH\s?CAROLINA|NORTH\s?DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s?ISLAND|SOUTH\s?CAROLINA|SOUTH\s?DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s?VIRGINIA|WISCONSIN|WYOMING'

    raw_text = " ".join(ocr_list).upper()
    # 移除特殊干扰符
    raw_text = re.sub(r'[:"\'\$#_!;]', '', raw_text)
    
    processed = raw_text
    # 剔除黑名单模式
    for p in junk_patterns:
        processed = re.sub(p, '', processed, flags=re.IGNORECASE)
    # 剔除州名
    processed = re.sub(states_pattern, '', processed, flags=re.IGNORECASE)
    
    # 智能换行：在日期前换行，在可能的地址开头换行
    processed = re.sub(r'(\d{2}/\d{2}/\d{4})', r'\n\1', processed)
    processed = re.sub(r'(\s\d{2,5}\s[A-Z])', r'\n\1', processed)
    
    # 最终精简处理
    final_lines = []
    for line in processed.split('\n'):
        line = line.strip()
        # 移除过短的碎片文字
        if len(line) > 3:
            final_lines.append(line)
            
    return final_lines

# --- 3. 界面布局 ---
st.title("🪪 驾照正面数据清洗提取器")
st.markdown("---")

img_source = st.file_uploader("上传证件正面试图", type=['jpg','png','jpeg']) or st.camera_input("拍照")

if img_source:
    # 加载并修正图片方向
    raw_img = ImageOps.exif_transpose(Image.open(img_source))
    
    # 内存优化：如果图片过大，先进行等比例缩放
    MAX_DIM = 1200
    if max(raw_img.size) > MAX_DIM:
        raw_img.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)

    col_l, col_r = st.columns([1, 1])
    
    with col_l:
        st.subheader("✂️ 框选识别区域")
        st_cropper = get_cropper()
        # 实时更新设为 False 减少云端 Rerun 压力
        cropped_img = st_cropper(raw_img, box_color='#1a73e8', aspect_ratio=None, realtime_update=False)
        st.image(cropped_img, caption="选区预览", use_container_width=True)

    with col_r:
        if st.button("🚀 提取并深度清洗", type="primary", use_container_width=True):
            with st.spinner("OCR 引擎启动中 (仅限 CPU 模式)..."):
                try:
                    reader = load_reader()
                    # 启用 paragraph 模式有助于合并邻近文本块
                    results = reader.readtext(np.array(cropped_img), detail=0, paragraph=True)
                    clean_lines = ultimate_clean(results)
                    
                    if clean_lines:
                        st.subheader("💎 提取结果")
                        for i, val in enumerate(clean_lines):
                            st.text_input(f"字段 {i+1}", val, key=f"field_{i}")
                        
                        st.subheader("📄 原始文本流")
                        st.text_area("Cleaned Data", "\n".join(clean_lines), height=200)
                    else:
                        st.warning("未检测到有效字符，请扩大框选范围。")
                except Exception as e:
                    st.error(f"处理失败: {str(e)}")
                finally:
                    gc.collect() # 强制垃圾回收释放内存
