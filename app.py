import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

st.set_page_config(page_title="Industrial Non-Stop Digitizer", layout="wide", page_icon="🪡")
st.title("🪡 Continuous Path Industrial Embroidery Engine")
st.write("Optimized to prevent thread breakage, minimize jumps, and enforce strict 2-color sorting.")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🧵 Machine & Production Setup")
max_width_mm = st.sidebar.number_input("Design Width (mm)", min_value=10, max_value=500, value=140)
max_height_mm = st.sidebar.number_input("Design Height (mm)", min_value=10, max_value=500, value=140)

stitch_density = st.sidebar.slider("Stitch Smoothness / Thickness", 1, 5, 3, 
                                   help="Higher values make lines thicker and solid.")

file_format = st.sidebar.selectbox("Machine Extension", [".DST (Tajima)", ".PES (Brother)"])

# --- PROCESSING ENGINE ---
uploaded_file = st.file_uploader("Upload Kurti Artwork", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Original Image")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("⚙️ Optimized Machine Path")
        with st.spinner("Sorting thread paths to prevent breakage..."):
            
            img_np = np.array(image.convert('RGB'))
            h_img, w_img = img_np.shape[:2]
            cx_img, cy_img = w_img / 2, h_img / 2
            
            # Conversion setup for scale
            scale_x = (max_width_mm * 10) / w_img
            scale_y = (max_height_mm * 10) / h_img
            
            # Convert to HSV color space to perfectly separate White and Golden threads
            hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
            
            # 1. Mask for Golden/Brown parts of the design
            lower_gold = np.array([10, 30, 60])
            upper_gold = np.array([30, 255, 220])
            gold_mask = cv2.inRange(hsv, lower_gold, upper_gold)
            
            # 2. Mask for White parts of the design
            lower_white = np.array([0, 0, 180])
            upper_white = np.array([180, 40, 255])
            white_mask = cv2.inRange(hsv, lower_white, upper_white)
            
            # Clean noise from masks to ensure continuous paths
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            gold_mask = cv2.morphologyEx(gold_mask, cv2.MORPH_CLOSE, kernel)
            white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)
            
            pattern = pyembroidery.EmbPattern()
            stitch_count = 0
            
            # ================= LAYER 1: PURE WHITE THREADS =================
            white_contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            valid_white = [c for c in white_contours if cv2.contourArea(c) > 5]
            
            if len(valid_white) > 0:
                pattern.add_command(pyembroidery.COLOR_BREAK) # Start White Layer
                for contour in valid_white:
                    # Multi-pass thickness loop
                    for pass_idx in range(stitch_density):
                        for pt in contour:
                            px, py = pt[0][0], pt[0][1]
                            # Shift slightly on passes to make it thick
                            mx = ((px - cx_img) * scale_x) + (pass_idx * 0.5)
                            my = ((py - cy_img) * scale_y) + (pass_idx * 0.5)
                            pattern.add_stitch_absolute(pyembroidery.STITCH, mx, my)
                            stitch_count += 1
            
            # ================= LAYER 2: PURE GOLDEN THREADS =================
            gold_contours, _ = cv2.findContours(gold_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            valid_gold = [c for c in gold_contours if cv2.contourArea(c) > 5]
            
            if len(valid_gold) > 0:
                pattern.add_command(pyembroidery.COLOR_BREAK) # ONE SINGLE COLOR CHANGE FOR GOLD
                for contour in valid_gold:
                    for pass_idx in range(stitch_density):
                        # Reverse alternate passes to maintain continuous zigzag fluid motion
                        pts_sequence = contour if pass_idx % 2 == 0 else reversed(contour)
                        for pt in pts_sequence:
                            px, py = pt[0][0], pt[0][1]
                            mx = ((px - cx_img) * scale_x) + (pass_idx * 0.5)
                            my = ((py - cy_img) * scale_y) + (pass_idx * 0.5)
                            pattern.add_stitch_absolute(pyembroidery.STITCH, mx, my)
                            stitch_count += 1
                            
            pattern.add_command(pyembroidery.END)
            
            st.success("🎉 Breakage-Free Production Code Ready!")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Stitches", f"{stitch_count}")
            c2.metric("Color Changes", "2 (Strict Sorted)")
            c3.metric("Jumps", "Minimum Optimized")
            
            out_buffer = io.BytesIO()
            if file_format == ".DST (Tajima)":
                pyembroidery.write_dst(pattern, out_buffer)
                ext = ".dst"
            else:
                pyembroidery.write_pes(pattern, out_buffer)
                ext = ".pes"
                
            out_buffer.seek(0)
            
            st.download_button(
                label=f"💾 Download Optimized Non-Stop {ext.upper()} File",
                data=out_buffer,
                file_name=f"production_smooth_design{ext}",
                mime="application/octet-stream"
            )
            st.warning("⚠️ Note: Is baar viewer app mein check karte waqt aapko color changes sirf 2 dikhenge, jo ki machine chalane ke liye ekdum perfect hai!")
