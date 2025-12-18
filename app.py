# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re
import cv2
import pandas as pd

# --- 1. 核心配置 ---
st.set_page_config(page_title="50州驾照全能读取器", layout="wide")

@st.cache_resource
def get_reader():
    # 加载模型，针对 50 州建议保持 paragraph=True 逻辑
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 图像极速预处理 ---
def preprocess_for_all_states(img_np):
    # 灰度化 + 提升对比度（应对不同州复杂的底纹）
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    # 使用自适应阈值增强文字边缘
    enhanced = cv2.detailEnhance(gray, sigma_s=10, sigma_r=0.15)
    # 限制宽度加速
    h, w = enhanced.shape[:2]
    target_w = 1200
    if w > target_w:
        enhanced = cv2.resize(enhanced, (target_w, int(h*(target_w/w))))
    return enhanced

# --- 3. 50 州全字段“漏斗提取”算法 ---
def extract_universal_data(text_list):
    full_text = " ".join(text_list).upper()
    # 深度清理：只保留字母数字和必要的符号
    clean = re.sub(r'[^A-Z0-9\s/:-]', '', full_text)
    clean = re.sub(r'\s+', ' ', clean)
    
    # 结果容器
    res = {
        "DAQ (DL Number)": "未检测",
        "DCS (Last Name)": "未检测",
        "DAC (First Name)": "未检测",
        "DBB (Date of Birth)": "未检测",
        "DBA (Expiration)": "未检测",
        "DBD (Issue Date)": "未检测",
        "DAG (Address)": "未检测",
        "DAJ (State)": "未检测",
        "DCA (Class)": "未检测",
        "DCB (Restrictions)": "未检测",
        "DCD (Endorsements)": "未检测",
        "DCJ (Audit/DD)": "未检测"
    }

    # --- 策略 A: 捕捉所有日期 (MM/DD/YYYY) ---
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean)
    
    # --- 策略 B: 标签库匹配 ---
    # 驾照号常用标签
    id_m = re.search(r'(?:DAQ|DL|4D|DLN|NO|NUMBER|LIC)\s*[:#]?\s*([A-Z0-9 -]{8,15})', clean)
    if id_m: res["DAQ (DL Number)"] = id_m.group(1).strip()

    # 姓名 (数字标签 1, 2 或 缩写 LN, FN)
    ln_m = re.search(r'(?:1|LN|DCS|SURNAME)\s*[:]?\s*([A-Z]+)', clean)
    if ln_m: res["DCS (Last Name)"] = ln_m.group(1)
    
    fn_m = re.search(r'(?:2|FN|DAC|GIVEN)\s*[:]?\s*([A-Z]+)', clean)
    if fn_m: res["DAC (First Name)"] = fn_m.group(1)

    # 日期逻辑 (通过标签定位日期)
    dob_m = re.search(r'(?:3|DOB|BIRTH)\s*(\d{2}/\d{2}/\d{4})', clean)
    if dob_m: res["DBB (Date of Birth)"] = dob_m.group(1)
    
    exp_m = re.search(r'(?:4B|EXP|EXPIRES)\s*(\d{2}/\d{2}/\d{4})', clean)
    if exp_m: res["DBA (Expiration)"] = exp_m.group(1)
    
    iss_m = re.search(r'(?:4A|ISS|ISSUED)\s*(\d{2}/\d{2}/\d{4})', clean)
    if iss_m: res["DBD (Issue Date)"] = iss_m.group(1)

    # --- 策略 C: 暴力搜索兜底 ---
    # 如果通过标签没找全日期，将找到的日期按逻辑排序填入
    if res["DBB (Date of Birth)"] == "未检测" and len(dates) >= 1:
        # 生日通常不是最大的也不是最小的日期，这里简单取值
        res["DBB (Date of Birth)"] = dates[-1] 
    
    # 地址提取 (8 标签或常见街道后缀)
    addr_m = re.search(r'(?:8|ADDRESS|ADDR)\s+([0-9]{1,5}\s[A-Z0-9\s]{10,})', clean)
    if addr_m: res["DAG (Address)"] = addr_m.group(1).strip()[:40]

    # 州代码 (搜索两个连续大写字母，通常在地址末尾)
    state_m = re.findall(r'\s([A-Z]{2})\s\d{5}', clean)
    if state_m: res["DAJ (State)"] = state_m[-1]

    return res

# --- 4. Streamlit UI ---
st.title("🪪 美国 50 州驾照全能扫描终端")
st.warning("注：各州版式不同，若自动提取不准，请参考下方 OCR 原始流手动微调。")

input_file = st.file_uploader("上传任意州驾照正面", type=['jpg', 'jpeg', 'png'])

if input_file:
    image = Image.open(input_file)
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.image(image, caption="待识别影像", use_container_width=True)
    
    with col2:
        if st.button("🚀 执行深度扫描", type="primary", use_container_width=True):
            with st.spinner("正在分析 50 州版式特征..."):
                reader = get_reader()
                processed = preprocess_for_all_states(np.array(image))
                # 识别并使用 paragraph 模式，这对地址读取至关重要
                results = reader.readtext(processed, detail=0, paragraph=True)
                data = extract_universal_data(results)
                
                st.subheader("📋 综合提取结果")
                st.table(pd.DataFrame(list(data.items()), columns=["字段 (AAMVA 标签)", "内容"]))

        with st.expander("🛠️ 查看 OCR 全文文本流 (用于分类错误时参考)"):
            if 'results' in locals():
                st.write(results)
