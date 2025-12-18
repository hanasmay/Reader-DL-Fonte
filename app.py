# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_cropper import st_cropper
import easyocr
import numpy as np
from PIL import Image
import cv2
import re
import pandas as pd

# --- 1. 配置 ---
st.set_page_config(page_title="高级透视裁剪扫描器", layout="wide")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 字段解析逻辑 ---
def extract_logic(text_list):
    full = " ".join(text_list).upper()
    res = {
        "DAQ (证件号)": "未检测",
        "DCS (姓氏-1)": "未检测",
        "DAC (名字-2)": "未检测",
        "DBB (生日-DOB)": "未检测",
        "DBA (过期-EXP)": "未检测",
        "DAG (地址-8)": "未检测"
    }
    # 简化的正则匹配
    id_m = re.search(r'(?:DAQ|DL|4D|NO)\s*([A-Z0-9 -]{8,15})', full)
    if id_m: res["DAQ (证件号)"] = id_m.group(1).strip()
    
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', full)
    if len(dates) >= 1: res["DBA (过期-EXP)"] = dates[0]
    if len(dates) >= 2: res["DBB (生日-DOB)"] = dates[1]
    
    name_m = re.search(r'1\s+([A-Z]+)\s+2\s+([A-Z]+)', full)
    if name_m:
        res["DCS (姓氏-1)"] = name_m.group(1)
        res["DAC (名字-2)"] = name_m.group(2)
        
    return res

# --- 3. UI 界面 ---
st.title("✂️ 手动裁剪与透视识别专家")
st.markdown("上传图片后，在左侧拖动裁剪框覆盖证件文字区域。")

up_file = st.file_uploader("上传证件照片", type=['jpg', 'jpeg', 'png'])

if up_file:
    img = Image.open(up_file)
    
    col_crop, col_res = st.columns([1, 1])
    
    with col_crop:
        st.subheader("1. 手动裁剪区域")
        # 交互式裁剪组件
        # box_color: 裁剪框颜色
        # aspect_ratio: 驾照比例通常接近 1.58 (85.6/53.98)
        cropped_img = st_cropper(img, realtime_update=True, box_color='#FF0000', aspect_ratio=(1.58, 1))
        
        st.write("预览裁剪后的图像：")
        st.image(cropped_img, use_container_width=True)

    with col_res:
        st.subheader("2. 识别结果")
        if st.button("🚀 识别当前裁剪区域", type="primary", use_container_width=True):
            with st.spinner("正在提取文字..."):
                # 将 PIL 转为 OpenCV 格式进行最后的预处理
                roi_np = np.array(cropped_img)
                
                # 图像增强：转灰度并做自适应对比度
                gray = cv2.cvtColor(roi_np, cv2.COLOR_RGB2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                final_roi = clahe.apply(gray)
                
                # OCR 识别
                reader = load_reader()
                # 针对裁剪后的图，adjust_contrast 设为 0 极速运行
                results = reader.readtext(final_roi, detail=0, paragraph=True, adjust_contrast=0)
                data = extract_logic(results)
                
                st.table(pd.DataFrame(list(data.items()), columns=["字段", "内容"]))
                
                with st.expander("查看原始 OCR 文本"):
                    st.write(results)

            st.success("识别完成！手动裁剪大幅提升了 OCR 的准确率和速度。")

else:
    st.info("请先上传一张驾驶证正面照片。")
