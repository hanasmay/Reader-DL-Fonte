# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re

# --- 1. 初始化模型 ---
@st.cache_resource
def load_ocr_model():
    # 首次运行会自动下载约150MB的模型文件
    return easyocr.Reader(['en'])

# --- 2. 核心识别函数 ---
def extract_fields(text_list):
    raw_text = " ".join(text_list).upper()
    # 清理多余空格
    clean_text = re.sub(r'\s+', ' ', raw_text)
    
    # 预设结果模板
    fields = {
        "证件号/ID": "未匹配", "姓氏": "未匹配", "名字": "未匹配",
        "等级 (Class)": "未匹配", "限制 (REST)": "未匹配", "背书 (END)": "未匹配",
        "生日 (DOB)": "未匹配", "过期日 (EXP)": "未匹配", "签发日 (ISS)": "未匹配",
        "地址": "未匹配", "档案号/审计码": "未匹配"
    }

    # 简单的正则匹配示例 (根据实际扫描结果可优化)
    # 匹配证件号 (查找 4d 或字母开头)
    id_match = re.search(r'(?:DAQ|4D|DL|NO)\s*[:#]?\s*([A-Z0-9\s-]{8,15})', clean_text)
    if id_match: fields["证件号/ID"] = id_match.group(1).strip()

    # 匹配日期 (识别 MM/DD/YYYY)
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean_text)
    if len(dates) >= 1: fields["过期日 (EXP)"] = dates[0]
    if len(dates) >= 2: fields["签发日 (ISS)"] = dates[1]
    if len(dates) >= 3: fields["生日 (DOB)"] = dates[2]

    return fields

# --- 3. Streamlit 界面 ---
st.set_page_config(page_title="DL 正面扫描器", layout="wide")
st.title("🪪 驾驶证正面智能识别")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📷 图像输入")
    mode = st.radio("选择上传方式", ["本地文件", "即时拍摄"], horizontal=True)
    img_file = st.file_uploader("上传图片", type=['jpg', 'png', 'jpeg']) if mode == "本地文件" else st.camera_input("拍照")

if img_file:
    img = Image.open(img_file)
    with col1:
        st.image(img, caption="待处理证件", use_container_width=True)

    with col2:
        st.subheader("📝 识别与校对")
        with st.spinner("正在进行智能扫描..."):
            reader = load_ocr_model()
            # 执行识别
            results = reader.readtext(np.array(img), detail=0)
            data = extract_fields(results)

            # 生成可编辑的表单
            with st.form("edit_form"):
                c1, c2 = st.columns(2)
                with c1:
                    dl_id = st.text_input("证件号", data["证件号/ID"])
                    ln = st.text_input("姓氏 (Last Name)", "")
                    fn = st.text_input("名字 (First Name)", "")
                    dca = st.text_input("等级 (Class)", data["等级 (Class)"])
                with c2:
                    dob = st.text_input("生日", data["生日 (DOB)"])
                    exp = st.text_input("过期日期", data["过期日 (EXP)"])
                    iss = st.text_input("签发日期", data["签发日 (ISS)"])
                    audit = st.text_input("档案号/审计码", data["档案号/审计码"])
                
                addr = st.text_area("居住地址", data["地址"])
                
                if st.form_submit_state("💾 确认并导出"):
                    st.success("数据已校对完毕！")

        with st.expander("查看原始识别出的文字"):
            st.write(results)
