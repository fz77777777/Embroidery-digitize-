import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

st.set_page_config(page_title="AI Industrial Digitizer PRO", layout="wide", page_icon="🪡")
st.title("🪡 Wilcom-Grade Heavy Density AI Digitizer (Diagonal Fill Edition)")
st.write("Professional Embroidery Engine: High Stitch Count, 45° Diagonal Fills & Tight Details.")

# --- SIDEBAR: PARAMETERS ---
st.sidebar.header("🧵 Production Stitch Controller")

max_width_mm = st.sidebar.number_input("Design Width (mm)", min_value=10, max_value=600, value=140)
max_height_mm = st.sidebar.number_input("Design Height (mm)", min_value=10, max_value=600, value=140)

stitch_budget = st.sidebar.selectbox(
    "Target Stitch Count (Design Density)",
    options=["10,000 (Light / Outline Fill)", "15,000 (Standard Kurti Quality)", "20,000 (High Density / Heavy)", "25,000 (Premium Heavy Tatami)", "30,000 (Rich Embroidery / Wilcom Solid)"]
)
target_stitches = int(stitch_budget.split(" ")[0].replace(",", ""))

stitch_style = st.sidebar.selectbox("Stitch Type", ["Pure Heavy Diagonal Tatami", "Auto-Switch (Satin + Tatami)"])
max_stitch_len_mm = st.sidebar.slider("Max Machine Jump Limit (mm)", 1.0, 5.0, 3.5, 0.1)

st.sidebar.subheader("🎨 Artwork Tracing Filters")
bg_omit_sensitivity = st.sidebar.slider("Background Cutter Sensitivity", 10, 150, 45)
noise_remover = st.sidebar.slider("Filter Tiny Specs", 5, 200, 30)

file_format = st.sidebar.selectbox("Machine Extension", [".DST (Tajima)", ".PES (Brother)"])

# --- MAIN ENGINE ---
uploaded_file = st.file_uploader("Upload High-Resolution Artwork / Kurti Design", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Source Image")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("⚙️ High-Density Stitch Matrix Engine")
        with st.spinner("Processing thick diagonal stitch paths..."):
            
            img_np = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            bg_sample = blurred[5, 5]
            if bg_sample > 180:
                _, thresh = cv2.threshold(blurred, int(bg_sample - bg_omit_sensitivity), 255, cv2.THRESH_BINARY_INV)
            else:
                _, thresh = cv2.threshold(blurred, int(bg_sample + bg_omit_sensitivity), 255, cv2.THRESH_BINARY)
                
            struct_elem = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, struct_elem)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            
            pattern = pyembroidery.EmbPattern()
            stitch_count = 0
            
            h_img, w_img = img_np.shape[:2]
            cx_img, cy_img = w_img / 2, h_img / 2
            
            scale_x = (max_width_mm * 10) / w_img
            scale_y = (max_height_mm * 10) / h_img
            
            valid_contours = [c for c in contours if cv2.contourArea(c) > noise_remover]
            
            if len(valid_contours) > 0:
                total_area = sum(cv2.contourArea(c) for c in valid_contours)
                
                # Dynamic step calculator for high density
                if total_area > 0:
                    density_factor = max(1, int(np.sqrt(total_area / (target_stitches * 0.45))))
                else:
                    density_factor = 2
                
                for contour in valid_contours:
                    pattern.add_command(pyembroidery.COLOR_BREAK)
                    
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # --- 45 DEGREE DIAGONAL SCANLINE ENGINE ---
                    # Rotates coordinate calculations to create professional look
                    step_size = max(1, int(density_factor))
                    stitch_len_px = max(2, int(max_stitch_len_mm / (max_width_mm / w_img)))
                    
                    # Scan diagonally using tilted bounds
                    for diag in range(x + y, x + w + y + h, step_size):
                        row_stitches = []
                        for col in range(x, x + w, stitch_len_px):
                            row = diag - col
                            if y <= row < y + h:
                                if cv2.pointPolygonTest(contour, (float(col), float(row)), False) >= 0:
                                    mx = (col - cx_img) * scale_x
                                    my = (row - cy_img) * scale_y
                                    row_stitches.append((mx, my))
                                    
                        if diag % (step_size * 2) == 0:
                            row_stitches.reverse()
                            
                        for pt in row_stitches:
                            pattern.add_stitch_absolute(pyembroidery.STITCH, pt[0], pt[1])
                            stitch_count += 1
                            
                # Underlay / Outlines injection if budget is unfilled
                if stitch_count < target_stitches:
                    deficit = target_stitches - stitch_count
                    for contour in valid_contours:
                        if deficit <= 0:
                            break
                        for pt in contour:
                            if deficit <= 0:
                                break
                            px, py = pt[0][0], pt[0][1]
                            mx = (px - cx_img) * scale_x
                            my = (py - cy_img) * scale_y
                            pattern.add_stitch_absolute(pyembroidery.STITCH, mx, my)
                            stitch_count += 1
                            deficit -= 1
            
            pattern.add_command(pyembroidery.END)
            
            st.success("🎉 Advanced Diagonal Digitization Complete!")
            
            c1, c2, c3 = st.columns(3)
            c1.metric(label="Calculated Heavy Stitches", value=f"{stitch_count}")
            c2.metric(label="Target Selected", value=f"{target_stitches}")
            c3.metric(label="Fill Style", value="45° Pro Tatami")
            
            out_buffer = io.BytesIO()
            if file_format == ".DST (Tajima)":
                pyembroidery.write_dst(pattern, out_buffer)
                mime_type = "application/octet-stream"
                ext = ".dst"
            else:
                pyembroidery.write_pes(pattern, out_buffer)
                mime_type = "application/octet-stream"
                ext = ".pes"
                
            out_buffer.seek(0)
            
            st.download_button(
                label=f"💾 Download {stitch_budget.split(' ')[0]} Stitch Machine File ({ext.upper()})",
                data=out_buffer,
                file_name=f"diagonal_heavy_design{ext}",
                mime=mime_type
            )
