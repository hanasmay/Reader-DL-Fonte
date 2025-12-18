# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re
import cv2
import pandas as pd

# --- 1. 页面配置 ---
st.set_page_config(page_title="PA 驾照正面识别器", layout="wide")

# --- 2. 模型加载 ---
@st.cache_resource
def load_ocr_model():
    return easyocr.Reader(['en'], gpu=False)

# --- 3. 极速预处理 ---
def fast_preprocess(img_np):
    h, w = img_np.shape[:2]
    target_w = 1000
    if w > target_w:
        target_h = int(h * (target_w / w))
        img_np = cv2.resize(img_np, (target_w, target_h), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    return gray

# --- 4. 针对性提取算法 (宾州编号逻辑) ---
def extract_pa_fields(text_list):
    raw_text = " ".join(text_list).upper()
    # 保持斜杠处理日期，保持 # 处理档案号
    clean_text = re.sub(r'[^A-Z0-9\s/#]', '', raw_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    fields = {
        "DAQ (驾照号)": "未检测",
        "DCS (1 姓氏)": "未检测",
        "DAC (2 名字)": "未检测",
        "DAG (8 地址)": "未检测",
        "DBB (DOB 生日)": "未检测",
        "DBA (EXP 过期)": "未检测",
        "DBD (ISS 签发)": "未检测",
        "DCJ (DD 档案号)": "未检测"
    }

    # 1. 驾照号 (DLN/DAQ)
    id_m = re.search(r'(?:DLN|DAQ|NO|NUMBER)\s*([0-9]{8,10})', clean_text)
    if id_m: fields["DAQ (驾照号)"] = id_m.group(1)

    # 2. 姓名 (1 姓 / 2 名)
    # 匹配 1 后面跟着的单词作为姓，2 后面跟着的单词作为名
    ln_m = re.search(r'1\s+([A-Z]+)', clean_text)
    if ln_m: fields["DCS (1 姓氏)"] = ln_m.group(1)
    
    fn_m = re.search(r'2\s+([A-Z]+)', clean_text)
    if fn_m: fields["DAC (2 名字)"] = fn_m.group(1)

    # 3. 日期 (DOB, EXP, ISS)
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean_text)
    # 逻辑分配：根据标签位置精准匹配
    dob_m = re.search(r'DOB\s*(\d{2}/\d{2}/\d{4})', clean_text)
    if dob_m: fields["DBB (DOB 生日)"] = dob_m.group(1)
    
    exp_m = re.search(r'EXP\s*(\d{2}/\d{2}/\d{4})', clean_text)
    if exp_m: fields["DBA (EXP 过期)"] = exp_m.group(1)
    
    iss_m = re.search(r'ISS\s*(\d{2}/\d{2}/\d{4})', clean_text)
    if iss_m: fields["DBD (ISS 签发)"] = iss_m.group(1)

    # 4. 地址 (8)
    # 匹配数字 8 之后开始的街道格式
    addr_m = re.search(r'8\s+(\d{1,5}\s[A-Z0-9\s]{5,})', clean_text)
    if addr_m: fields["DAG (8 地址)"] = addr_m.group(1).strip()

    # 5. 档案号 (DD)
    dd_m = re.search(r'DD\s*([0-9]{2,})', clean_text)
    if dd_m: fields["DCJ (DD 档案号)"] = dd_m.group(1)

    return fields

# --- 5. UI 界面 ---
st.title("🪪 PA 驾驶证正面识别器")
st.markdown("---")

col_left, col_right = st.columns([1, 1.2])

with col_left:
    st.subheader("📸 影像输入")
    img_file = st.file_uploader("上传证件正面", type=['jpg', 'jpeg', 'png'])
    if not img_file:
        img_file = st.camera_input("使用摄像头拍摄")

if img_file:
    img_pil = Image.open(img_file)
    img_np = np.array(img_pil)
    st.image(img_pil, caption="输入影像", use_container_width=True)

    with col_right:
        st.subheader("📋 映射分析结果")
        with st.spinner("⚡ 正在执行深度扫描..."):
            processed = fast_preprocess(img_np)
            reader = load_ocr_model()
            # 识别
            ocr_res = reader.readtext(processed, detail=0, paragraph=True)
            # 提取
            data = extract_pa_fields(ocr_res)
            
            # 将结果转换为 DataFrame 展示表格
            df = pd.DataFrame(list(data.items()), columns=["字段标签", "提取内容"])
            st.table(df)

        # 可编辑表单，用于最后的校对
        st.subheader("📝 修正与确认")
        with st.form("verify_form"):
            c1, c2 = st.columns(2)
            f_daq = c1.text_input("证件号 (DAQ)", data["DAQ (驾照号)"])
            f_ln = c1.text_input("姓氏 (DCS)", data["DCS (1 姓氏)"])
            f_fn = c1.text_input("名字 (DAC)", data["DAC (2 名字)"])
            f_dob = c2.text_input("生日 (DBB)", data["DBB (DOB 生日)"])
            f_exp = c2.text_input("过期日 (DBA)", data["DBA (EXP 过期)"])
            f_iss = c2.text_input("签发日 (DBD)", data["DBD (ISS 签发)"])
            
            f_audit = st.text_input("档案号 (DCJ/DD)", data["DCJ (DD 档案号)"])
            f_addr = st.text_area("地址 (DAG)", data["DAG (8 地址)"])
            
            if st.form_submit_button("✅ 确认数据"):
                st.success("数据校对完成！")
                st.json({"final": "ready"})

        with st.expander("查看原始扫描文本"):
            st.write(ocr_res)
else:
    with col_right:
        st.info("请在左侧上传驾照正面图片。系统将自动映射 AAMVA 1, 2, 8, DOB, EXP 等字段。")
