# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_cropper import st_cropper
import easyocr
import numpy as np
from PIL import Image, ImageOps
import cv2
import re
import pandas as pd

# --- 1. 配置 ---
st.set_page_config(page_title="自由裁剪扫描终端", layout="wide")

@st.cache_resource
def load_reader():
    # 使用 CPU 模式
    return easyocr.Reader(['en'], gpu=False)

# --- 2. 字段解析算法 ---
def universal_parse(text_list):
    full = " ".join(text_list).upper()
    # 清理特殊符号
    clean = re.sub(r'[^A-Z0-9\s/]', '', full)
    
    res = {
        "DAQ (证件号)": "未匹配",
        "DCS (姓氏-1)": "未匹配",
        "DAC (名字-2)": "未匹配",
        "DBB (生日-DOB)": "未匹配",
        "DBA (过期-EXP)": "未匹配",
        "DAG (地址-8)": "未匹配"
    }
    
    # 提取证件号 (8-10位数字)
    id_m = re.search(r'([0-9]{8,10})', clean)
    if id_m: res["DAQ (证件号)"] = id_m.group(1)
    
    # 提取所有日期
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean)
    if len(dates) >= 1: res["DBA (过期-EXP)"] = dates[0]
    if len(dates) >= 2: res["DBB (生日-DOB)"] = dates[1]
    
    # 提取姓名 (基于 1 和 2 标签)
    ln_m = re.search(r'(?:1|LN)\s+([A-Z]+)', clean)
    if ln_m: res["DCS (姓氏-1)"] = ln_m.group(1)
    fn_m = re.search(r'(?:2|FN)\s+([A-Z]+)', clean)
    if fn_m: res["DAC (名字-2)"] = fn_m.group(1)
    
    # 提取地址
    addr_m = re.search(r'8\s+([0-9]{1,5}\s[A-Z0-9\s]{10,})', clean)
    if addr_m: res["DAG (地址-8)"] = addr_m.group(1).strip()[:35]
        
    return res

# --- 3. UI 界面 ---
st.title("✂️ 自由裁剪识别终端 (支持横屏/摄像头)")

# 输入源切换
src_mode = st.radio("选择输入方式", ["📷 摄像头拍照", "📁 上传图片"], horizontal=True)

img_source = None
if src_mode == "📷 摄像头拍照":
    img_source = st.camera_input("请对准证件拍摄")
else:
    img_source = st.file_uploader("选择照片文件", type=['jpg', 'jpeg', 'png'])

if img_source:
    # 加载图片并校正旋转方向 (针对手机拍照)
    raw_img = Image.open(img_source)
    raw_img = ImageOps.exif_transpose(raw_img)
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("调整选取框")
        st.info("拖动红框边缘：自由调整大小 (已解除比例锁定)")
        
        # 核心组件：手动裁剪
        # aspect_ratio=None 允许自由调整比例
        cropped_img = st_cropper(
            raw_img, 
            realtime_update=True, 
            box_color='#FF0000', 
            aspect_ratio=None,
            key="cropper"
        )
        
        st.write("当前选取预览：")
        st.image(cropped_img, use_container_width=True)

    with col_right:
        st.subheader("识别解析结果")
        if st.button("🚀 识别当前选取区域", type="primary", use_container_width=True):
            with st.spinner("正在精准解析..."):
                # 转换格式
                roi_np = np.array(cropped_img)
                
                # 预处理：灰度化 + 锐化
                gray = cv2.cvtColor(roi_np, cv2.COLOR_RGB2GRAY)
                # 使用自适应直方图均衡化增加对比度
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                final_roi = clahe.apply(gray)
                
                # OCR 识别
                reader = load_reader()
                # 因为图片已手动裁剪，关闭自动对比度微调以极速运行
                results = reader.readtext(final_roi, detail=0, paragraph=True, adjust_contrast=0)
                data = universal_parse(results)
                
                # 展示表格
                st.table(pd.DataFrame(list(data.items()), columns=["字段标签", "解析内容"]))
                
                with st.expander("查看底层文字流"):
                    st.write(results)
            
            st.success("识别耗时极短，因为只处理了裁剪区域！")

else:
    st.info("💡 请先拍照或上传图片，然后在红框内选择文字密集的区域进行识别。")
