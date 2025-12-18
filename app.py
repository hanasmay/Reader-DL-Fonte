# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re
import cv2
import pandas as pd
import gc

# --- 1. 配置 ---
st.set_page_config(page_title="US DL Scanner", layout="wide", page_icon="🪪")

@st.cache_resource
def get_reader():
    # 强制 CPU 模式，减少云端崩溃概率
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 修复后的预处理（解决 cv2.error） ---
def safe_preprocess(img_np):
    # 1. 颜色空间转换
    if img_np.shape[-1] == 4:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
    
    # 2. 转灰度
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # 3. 增强对比度 (CLAHE) - 比 detailEnhance 更稳健，不报错
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # 4. 智能缩放 (限制宽度为 900px 以兼顾精度与速度)
    h, w = enhanced.shape[:2]
    target_w = 900
    if w > target_w:
        enhanced = cv2.resize(enhanced, (target_w, int(h*(target_w/w))), interpolation=cv2.INTER_AREA)
    
    return enhanced

# --- 3. 50 州通用提取逻辑 ---
def extract_universal(text_list):
    full_text = " ".join(text_list).upper()
    clean = re.sub(r'[^A-Z0-9\s/:-]', '', full_text)
    
    res = {
        "DAQ (DLN)": "未检测", "DCS (Surname)": "未检测", "DAC (First)": "未检测",
        "DBB (DOB)": "未检测", "DBA (EXP)": "未检测", "DBD (ISS)": "未检测",
        "DAG (Address)": "未检测", "DCJ (Audit)": "未检测"
    }

    # 驾照号
    id_m = re.search(r'(?:DLN|DAQ|4D|NO|NUMBER)\s*[:#]?\s*([A-Z0-9 -]{8,15})', clean)
    if id_m: res["DAQ (DLN)"] = id_m.group(1).strip()

    # 姓名 (支持 1, 2, LN, FN)
    ln_m = re.search(r'(?:1|LN|DCS|SURNAME)\s*[:]?\s*([A-Z]+)', clean)
    if ln_m: res["DCS (Surname)"] = ln_m.group(1)
    
    fn_m = re.search(r'(?:2|FN|DAC|GIVEN)\s*[:]?\s*([A-Z]+)', clean)
    if fn_m: res["DAC (First)"] = fn_m.group(1)

    # 日期 (MM/DD/YYYY)
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean)
    if dob_m := re.search(r'(?:3|DOB|BIRTH)\s*(\d{2}/\d{2}/\d{4})', clean): res["DBB (DOB)"] = dob_m.group(1)
    if exp_m := re.search(r'(?:4B|EXP|EXPIRES)\s*(\d{2}/\d{2}/\d{4})', clean): res["DBA (EXP)"] = exp_m.group(1)
    
    # 地址
    addr_m = re.search(r'(?:8|ADDRESS|ADDR)\s+([0-9]{1,5}\s[A-Z0-9\s]{8,})', clean)
    if addr_m: res["DAG (Address)"] = addr_m.group(1).strip()[:40]

    return res

# --- 4. 界面逻辑 ---
st.title("🪪 美国 50 州驾照摄像头扫描器")
st.markdown("---")

# 选项卡：切换摄像头与文件上传
tab_cam, tab_file = st.tabs(["📷 摄像头扫描", "📁 文件上传"])

img_buffer = None

with tab_cam:
    st.info("💡 请确保使用 HTTPS 访问，并授予摄像头权限。")
    img_buffer = st.camera_input("请对准证件正面并保持稳定")

with tab_file:
    up_file = st.file_uploader("或直接上传照片", type=['jpg', 'jpeg', 'png'])
    if up_file:
        img_buffer = up_file

if img_buffer:
    image = Image.open(img_buffer)
    col_left, col_right = st.columns([1, 1.2])
    
    with col_left:
        st.image(image, caption="捕获的原始影像", use_container_width=True)
    
    with col_right:
        if st.button("🚀 执行全字段识别", type="primary", use_container_width=True):
            with st.spinner("深度分析中..."):
                # 预处理
                processed = safe_preprocess(np.array(image))
                
                # 识别
                reader = get_reader()
                ocr_results = reader.readtext(processed, detail=0, paragraph=True)
                data = extract_universal(ocr_results)
                
                # 存入 Session 供表单使用
                st.session_state['ocr_data'] = data
                st.session_state['ocr_raw'] = ocr_results

        # 结果校验表单
        if 'ocr_data' in st.session_state:
            d = st.session_state['ocr_data']
            with st.form("verify_data"):
                st.subheader("📋 识别结果核对")
                c1, c2 = st.columns(2)
                f_daq = c1.text_input("证件号 (DAQ)", d["DAQ (DLN)"])
                f_ln = c1.text_input("姓氏 (DCS)", d["DCS (Surname)"])
                f_fn = c1.text_input("名字 (DAC)", d["DAC (First)"])
                
                f_dob = c2.text_input("生日 (DBB)", d["DBB (DOB)"])
                f_exp = c2.text_input("过期日 (DBA)", d["DBA (EXP)"])
                f_iss = c2.text_input("签发日 (DBD)", d["DBD (ISS)"])
                
                f_addr = st.text_area("居住地址 (DAG)", d["DAG (Address)"])
                
                if st.form_submit_button("✅ 确认并导出结果"):
                    st.success("数据校对已完成")
                    st.json({"status": "verified", "data": f_daq})

            with st.expander("🛠️ 查看 OCR 原始流"):
                st.write(st.session_state['ocr_raw'])
