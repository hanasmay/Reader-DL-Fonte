# -*- coding: utf-8 -*-
import streamlit as st
import easyocr
import numpy as np
from PIL import Image
import re
import cv2

# --- 1. 页面配置 ---
st.set_page_config(page_title="极速 DL 正面扫描器", layout="wide")

# --- 2. 性能优化模型加载 ---
@st.cache_resource
def load_ocr_model():
    # 强制不使用 GPU（在云端服务器更稳定），仅加载英文模型
    return easyocr.Reader(['en'], gpu=False)

# --- 3. 图像预处理（提速核心） ---
def fast_preprocess(img_np):
    """通过压缩和降噪大幅减少 OCR 计算量"""
    # 1. 尺寸压缩：固定宽度为 1000px，高度按比例缩放
    h, w = img_np.shape[:2]
    target_w = 1000
    if w > target_w:
        target_h = int(h * (target_w / w))
        img_np = cv2.resize(img_np, (target_w, target_h), interpolation=cv2.INTER_AREA)
    
    # 2. 转换为灰度图（减少 2/3 的颜色通道计算）
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # 3. 自适应对比度增强 (CLAHE) - 帮助识别浅色文字
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    return enhanced

# --- 4. 字段提取算法 ---
def extract_fields(text_list):
    raw_text = " ".join(text_list).upper()
    clean_text = re.sub(r'\s+', ' ', raw_text)
    
    fields = {
        "DAQ": "未检测", "DCS": "未检测", "DAC": "未检测",
        "DCA": "未检测", "DCB": "未检测", "DCD": "未检测",
        "DBB": "未检测", "DBA": "未检测", "DBD": "未检测",
        "DAG": "未检测", "DCJ": "未检测", "DDB": "未检测"
    }

    # 证件号
    id_m = re.search(r'(?:DAQ|4D|DL|NO)\s*[:#]?\s*([A-Z0-9\s-]{8,15})', clean_text)
    if id_m: fields["DAQ"] = id_m.group(1).strip()

    # 日期类 (匹配 MM/DD/YYYY)
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', clean_text)
    if len(dates) >= 1: fields["DBA"] = dates[0]
    if len(dates) >= 2: fields["DBD"] = dates[1]
    if len(dates) >= 3: fields["DBB"] = dates[2]

    # 等级、限制、背书
    class_m = re.search(r'CLASS\s*[:]?\s*([A-Z0-9])', clean_text)
    if class_m: fields["DCA"] = class_m.group(1)
    
    rest_m = re.search(r'REST\s*[:]?\s*([A-Z0-9\s,]{1,3})', clean_text)
    if rest_m: fields["DCB"] = rest_m.group(1).strip()
    
    end_m = re.search(r'END\s*[:]?\s*([A-Z0-9\s,]{1,3})', clean_text)
    if end_m: fields["DCD"] = end_m.group(1).strip()

    # 审计码 (10-15位数字)
    audit_m = re.search(r'(?:DD|AUDIT|FILE)\s*[:#]?\s*([0-9\s-]{10,20})', clean_text)
    if audit_m: fields["DCJ"] = audit_m.group(1).strip()

    # 地址
    addr_m = re.search(r'(\d{1,5}\s[A-Z0-9\s,]{10,})', clean_text)
    if addr_m: fields["DAG"] = addr_m.group(1).strip()

    return fields

# --- 5. UI 界面 ---
st.title("🪪 驾驶证正面极速读取器")
st.markdown("---")

col_img, col_form = st.columns([1, 1.2])

with col_img:
    st.subheader("📷 影像输入")
    img_file = st.file_uploader("上传证件正面", type=['jpg', 'jpeg', 'png'])
    if not img_file:
        img_file = st.camera_input("使用摄像头拍摄")

if img_file:
    img_pil = Image.open(img_file)
    img_np = np.array(img_pil)
    
    with col_img:
        st.image(img_pil, caption="输入影像", use_container_width=True)

    with col_form:
        st.subheader("📝 自动提取结果")
        with st.spinner("⚡ 正在执行极速 OCR 分析..."):
            # 预处理
            processed_img = fast_preprocess(img_np)
            reader = load_ocr_model()
            
            # 使用性能优化参数
            ocr_results = reader.readtext(
                processed_img, 
                detail=0, 
                paragraph=True,      # 提速：将行合并
                batch_size=4,        # 批处理
                adjust_contrast=0.5  # 减少对比度计算
            )
            data = extract_fields(ocr_results)

        # 录入表单
        with st.form("dl_verify_form"):
            c1, c2 = st.columns(2)
            with c1:
                daq = st.text_input("证件号 (DAQ)", data["DAQ"])
                ln = st.text_input("姓氏 (DCS)", "")
                fn = st.text_input("名字 (DAC)", "")
                dca = st.text_input("等级 (DCA)", data["DCA"])
            with c2:
                dbb = st.text_input("生日 (DBB)", data["DBB"])
                dba = st.text_input("过期日 (DBA)", data["DBA"])
                dbd = st.text_input("签发日 (DBD)", data["DBD"])
                dcj = st.text_input("档案号 (DCJ)", data["DCJ"])
            
            c3, c4 = st.columns(2)
            with c3:
                dcb = st.text_input("限制 (DCB)", data["DCB"])
            with c4:
                dcd = st.text_input("背书 (DCD)", data["DCD"])
                
            dag = st.text_area("居住地址 (DAG)", data["DAG"])
            
            submit = st.form_submit_button("✅ 锁定数据")
            if submit:
                st.success("数据校对完成！")
                st.json({"DAQ": daq, "Name": f"{fn} {ln}", "EXP": dba, "Audit": dcj})

        with st.expander("查看原始识别文本"):
            st.write(ocr_results)
else:
    with col_form:
        st.info("💡 请在左侧提供影像。系统会自动压缩图片以提升识别效率。")
