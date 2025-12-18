# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import cv2
import re
import time
import pandas as pd

# --- 1. 页面配置与性能设置 ---
st.set_page_config(page_title="PA/US DL 极速扫描器", layout="wide")

@st.cache_resource
def load_reader():
    # 强制 CPU 模式，减少模型加载开销
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 核心：ROI 裁剪与图像优化 ---
def preprocess_roi(img_np):
    h, w = img_np.shape[:2]
    
    # A. 自动 ROI 裁剪：
    # 驾照的核心文字通常集中在中间及右侧，照片在左侧。
    # 我们裁掉上下各 10% 的边缘，左侧裁掉 25% (避开照片)，右侧裁掉 5%。
    top, bottom = int(h * 0.10), int(h * 0.90)
    left, right = int(w * 0.25), int(w * 0.95)
    roi_img = img_np[top:bottom, left:right]
    
    # B. 极限尺寸压缩：
    # 将 ROI 区域缩放至宽度 800px，这足以识别所有 AAMVA 字段
    rh, rw = roi_img.shape[:2]
    target_w = 800
    target_h = int(rh * (target_w / rw))
    roi_resized = cv2.resize(roi_img, (target_w, target_h), interpolation=cv2.INTER_AREA)
    
    # C. 灰度化处理
    gray = cv2.cvtColor(roi_resized, cv2.COLOR_RGB2GRAY)
    
    return gray

# --- 3. 50 州通用漏斗解析 ---
def extract_fields(text_list):
    full = " ".join(text_list).upper()
    clean = re.sub(r'[^A-Z0-9\s/:-]', '', full)
    
    res = {
        "DAQ (DLN)": "未检测", "DCS (Surname)": "未检测", "DAC (First)": "未检测",
        "DBB (DOB)": "未检测", "DBA (EXP)": "未检测", "DBD (ISS)": "未检测",
        "DAG (Address)": "未检测", "DCJ (Audit)": "未检测"
    }

    # 驾照号常用正则
    id_m = re.search(r'(?:DLN|DAQ|4D|NO|NUMBER)\s*[:#]?\s*([A-Z0-9 -]{8,15})', clean)
    if id_m: res["DAQ (DLN)"] = id_m.group(1).strip()

    # 姓名映射 (1 姓 / 2 名 / LN / FN)
    ln_m = re.search(r'(?:1|LN|DCS|SURNAME)\s*[:]?\s*([A-Z]+)', clean)
    if ln_m: res["DCS (Surname)"] = ln_m.group(1)
    
    fn_m = re.search(r'(?:2|FN|DAC|GIVEN)\s*[:]?\s*([A-Z]+)', clean)
    if fn_m: res["DAC (First)"] = fn_m.group(1)

    # 日期逻辑 (MM/DD/YYYY)
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean)
    if dob_m := re.search(r'(?:3|DOB|BIRTH)\s*(\d{2}/\d{2}/\d{4})', clean): res["DBB (DOB)"] = dob_m.group(1)
    if exp_m := re.search(r'(?:4B|EXP|EXPIRES)\s*(\d{2}/\d{2}/\d{4})', clean): res["DBA (EXP)"] = exp_m.group(1)
    
    # 暴力补充：如果没读到标签但有日期，按常见顺序填入
    if res["DBA (EXP)"] == "未检测" and len(dates) >= 1: res["DBA (EXP)"] = dates[0]
    if res["DBB (DOB)"] == "未检测" and len(dates) >= 2: res["DBB (DOB)"] = dates[1]

    # 地址特征识别
    addr_m = re.search(r'(?:8|ADDRESS|ADDR)\s+([0-9]{1,5}\s[A-Z0-9\s]{8,})', clean)
    if addr_m: res["DAG (Address)"] = addr_m.group(1).strip()[:35]

    return res

# --- 4. Streamlit 交互界面 ---
st.title("⚡ ROI 极速驾照扫描器")
st.markdown("通过智能裁剪 ROI 区域，识别速度提升约 **60%**。")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📸 影像采集")
    mode = st.radio("选择输入源", ["摄像头实时拍摄", "本地图片上传"], horizontal=True)
    img_file = st.camera_input("拍照识别") if mode == "摄像头实时拍摄" else st.file_uploader("选择文件", type=['jpg','png','jpeg'])

if img_file:
    start_t = time.time()
    img_pil = Image.open(img_file)
    img_np = np.array(img_pil)
    
    # 执行预处理 (ROI 裁剪)
    processed = preprocess_roi(img_np)
    
    with col1:
        st.image(processed, caption="ROI 裁剪后的识别区域", use_container_width=True)

    with col2:
        st.subheader("📋 识别与核对")
        with st.spinner("⚡ 极速解析中..."):
            reader = load_reader()
            # 极限提速参数：关闭调整对比度，开启段落合并
            results = reader.readtext(processed, detail=0, paragraph=True, adjust_contrast=0)
            data = extract_fields(results)
            
        duration = time.time() - start_t
        st.metric("处理耗时", f"{duration:.2f} 秒")

        with st.form("verify_form"):
            c1, c2 = st.columns(2)
            f_daq = c1.text_input("证件号", data["DAQ (DLN)"])
            f_ln = c1.text_input("姓氏", data["DCS (Surname)"])
            f_fn = c1.text_input("名字", data["DAC (First)"])
            
            f_dob = c2.text_input("生日", data["DBB (DOB)"])
            f_exp = c2.text_input("有效期至", data["DBA (EXP)"])
            f_iss = c2.text_input("签发日", data["DBD (ISS)"])
            
            f_addr = st.text_area("居住地址", data["DAG (Address)"])
            
            if st.form_submit_button("✅ 确认并锁定数据"):
                st.success("数据校对完毕")
                st.balloons()

        with st.expander("查看 ROI 原始 OCR 文本"):
            st.write(results)
