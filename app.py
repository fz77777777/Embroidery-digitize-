import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

st.set_page_config(page_title="Pro AI Embroidery Digitizer", layout="wide", page_icon="🪡")
st.title("🪡 Wilcom-Inspired AI Embroidery Digitizer (Solid Fill Engine)")
st.write("Generates filled embroidery structures from clean artwork sketches or vector previews.")

# --- SIDEBAR PARAMETERS ---
st.sidebar.header("⚙️ Embroidery Controls")
max_width_mm = st.sidebar.number_input("Max Width (mm)", min_value=10, max_value=500, value=120)
max_height_mm = st.sidebar.number_input("Max Height (mm)", min_value=10, max_value=500, value=120)

stitch_type = st.sidebar.selectbox(
    "Stitch Generation Method",
    options=["Tatami Solid Fill (Bade Areas Ke Liye)", "Satin Zig-Zag (Borders & Leaf Shapes)", "Run Outline (Sui ki single line)"]
)

stitch_density = st.sidebar.slider("Stitch Density / Spacing (mm)", min_value=0.2, max_value=1.2, value=0.4, step=0.05)
stitch_length = st.sidebar.slider("Max Stitch Length (mm)", min_value=1.0, max_value=6.0, value=3.5, step=0.1)

st.sidebar.subheader("🎛️ Advanced Tracing")
noise_filter = st.sidebar.slider("Remove Small Noise Dots", min_value=20, max_value=500, value=100)
file_format = st.sidebar.selectbox("Machine Export Format", options=[".DST (Tajima)", ".PES (Brother)"])

# --- MAIN ENGINE ---
uploaded_file = st.file_uploader("Upload Design Image", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Input Vector Design")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("🧵 Generated Stitch Preview")
        with st.spinner("Executing dense fill stitching matrices..."):
            
            img_np = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            
            # Contrast boost to lock design shapes
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            _, thresh = cv2.threshold(blurred, 240, 255, cv2.THRESH_BINARY_INV)
            
            # Morphological close to bridge gaps in lines
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            pattern = pyembroidery.EmbPattern()
            stitch_count = 0
            
            h_img, w_img = img_np.shape[:2]
            cx_img, cy_img = w_img / 2, h_img / 2
            
            # Scaling Factor: Pixel to 0.1mm unit
            scale_x = (max_width_mm * 10) / w_img
            scale_y = (max_height_mm * 10) / h_img
            
            for idx, contour in enumerate(contours):
                if cv2.contourArea(contour) < noise_filter:
                    continue
                
                pattern.add_command(pyembroidery.COLOR_BREAK)
                
                # --- TATAMI FILL ENGINE (SOLID SCANNING) ---
                if "Tatami" in stitch_type:
                    x, y, w, h = cv2.boundingRect(contour)
                    # Step size matches stitch density translated to pixels
                    pixel_density = max(1, int(stitch_density / (max_height_mm / h_img)))
                    pixel_length = max(1, int(stitch_length / (max_width_mm / w_img)))
                    
                    for row in range(y, y + h, pixel_density):
                        row_stitches = []
                        for col in range(x, x + w, pixel_length):
                            # Test if pixel sits inside the design boundary
                            if cv2.pointPolygonTest(contour, (float(col), float(row)), False) >= 0:
                                mx = (col - cx_img) * scale_x
                                my = (row - cy_img) * scale_y
                                row_stitches.append((mx, my))
                        
                        # Alternate rows to mimic a continuous continuous run without jumps
                        if row % (pixel_density * 2) == 0:
                            row_stitches.reverse()
                            
                        for pt in row_stitches:
                            pattern.add_stitch_absolute(pyembroidery.STITCH, pt[0], pt[1])
                            stitch_count += 1
                            
                # --- SATIN ZIG-ZAG ENGINE ---
                elif "Satin" in stitch_type:
                    # Simplify contour for cleaner pairs
                    epsilon = 0.01 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    
                    half = len(approx) // 2
                    for i in range(half):
                        p1 = approx[i][0]
                        p2 = approx[len(approx) - 1 - i][0]
                        
                        mx1 = (p1[0] - cx_img) * scale_x
                        my1 = (p1[1] - cy_img) * scale_y
                        mx2 = (p2[0] - cx_img) * scale_x
                        my2 = (p2[1] - cy_img) * scale_y
                        
                        pattern.add_stitch_absolute(pyembroidery.STITCH, mx1, my1)
                        pattern.add_stitch_absolute(pyembroidery.STITCH, mx2, my2)
                        stitch_count += 2
                        
                # --- RUN STITCH OUTLINE ---
                else:
                    for pt in contour:
                        px, py = pt[0][0], pt[0][1]
                        mx = (px - cx_img) * scale_x
                        my = (py - cy_img) * scale_y
                        pattern.add_stitch_absolute(pyembroidery.STITCH, mx, my)
                        stitch_count += 1
                        
            pattern.add_command(pyembroidery.END)
            
            st.success("🎉 Solid Stitches Generated Successfully!")
            
            c1, c2 = st.columns(2)
            c1.metric(label="Total Dense Stitches", value=f"{stitch_count}")
            c2.metric(label="Pattern Status", value="Filled Blocks")
            
            # Universal Export Stream
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
                label=f"💾 Download Machine Ready {ext.upper()} File",
                data=out_buffer,
                file_name=f"solid_embroidery_design{ext}",
                mime=mime_type
            )
            st.info("💡 Tip: Download karne se pehle sidebar me 'Tatami Solid Fill' select karein aur density ko 0.4 standard rakhein, isse viewer me moti aur bhari hui design show hogi.")
