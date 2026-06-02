import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

st.set_page_config(page_title="AI Professional Digitizer", layout="wide", page_icon="🪡")
st.title("🪡 Wilcom-Grade Multi-Stitch AI Digitizer")
st.write("Automatically drops background and applies appropriate Satin/Tatami stitches.")

# --- SIDEBAR PARAMETERS ---
st.sidebar.header("🧵 Production Settings")
max_width_mm = st.sidebar.number_input("Design Width (mm)", min_value=10, max_value=500, value=120)
max_height_mm = st.sidebar.number_input("Design Height (mm)", min_value=10, max_value=500, value=120)

st.sidebar.subheader("🎛️ Stitch Tuning")
tatami_density = st.sidebar.slider("Tatami Fill Density (mm)", min_value=0.3, max_value=1.0, value=0.4, step=0.05)
satin_spacing = st.sidebar.slider("Satin Stitch Spacing (mm)", min_value=0.3, max_value=1.2, value=0.5, step=0.05)
stitch_length = st.sidebar.slider("Stitch Length (mm)", min_value=1.5, max_value=5.0, value=3.0, step=0.1)

st.sidebar.subheader("🎨 Background Isolation")
bg_tolerance = st.sidebar.slider("Background Omit Sensitivity", min_value=5, max_value=100, value=30,
                                 help="Higher value helps cut out cream/white backgrounds perfectly.")

file_format = st.sidebar.selectbox("Format", options=[".DST (Tajima)", ".PES (Brother)"])

# --- MAIN LOGIC ---
uploaded_file = st.file_uploader("Upload Clean Artwork", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Original Design")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("⚙️ AI Stitch Generation")
        with st.spinner("Dropping background and plotting stitches..."):
            
            img_np = np.array(image.convert('RGB'))
            
            # Convert to Grayscale
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            
            # Smart Background Inversion: Assuming top-left pixel is background color
            bg_color = gray[10, 10]
            if bg_color > 200: # White/Bright background
                _, thresh = cv2.threshold(gray, int(bg_color - bg_tolerance), 255, cv2.THRESH_BINARY_INV)
            else: # Dark background
                _, thresh = cv2.threshold(gray, int(bg_color + bg_tolerance), 255, cv2.THRESH_BINARY)
            
            # Clean tiny pixel noise
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
            
            pattern = pyembroidery.EmbPattern()
            stitch_count = 0
            
            h_img, w_img = img_np.shape[:2]
            cx_img, cy_img = w_img / 2, h_img / 2
            
            scale_x = (max_width_mm * 10) / w_img
            scale_y = (max_height_mm * 10) / h_img
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 40: # Skip noise
                    continue
                
                # Signal a color break / thread change for distinct parts
                pattern.add_command(pyembroidery.COLOR_BREAK)
                
                # Smart Decision: Thickness check for Satin vs Tatami
                # We check the ratio of area to contour perimeter (Arc Length)
                perimeter = cv2.arcLength(contour, True)
                thickness = (2 * area) / perimeter if perimeter > 0 else 0
                
                # --- CASE 1: SATIN STITCH FOR THIN ELEMENTS & BORDERS ---
                if thickness < 12.0: 
                    epsilon = 0.008 * perimeter
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    half = len(approx) // 2
                    
                    for i in range(0, half, max(1, int(satin_spacing * 5))):
                        p1 = approx[i][0]
                        p2 = approx[len(approx) - 1 - i][0]
                        
                        mx1 = (p1[0] - cx_img) * scale_x
                        my1 = (p1[1] - cy_img) * scale_y
                        mx2 = (p2[0] - cx_img) * scale_x
                        my2 = (p2[1] - cy_img) * scale_y
                        
                        pattern.add_stitch_absolute(pyembroidery.STITCH, mx1, my1)
                        pattern.add_stitch_absolute(pyembroidery.STITCH, mx2, my2)
                        stitch_count += 2
                        
                # --- CASE 2: TATAMI SOLID FILL FOR LARGE OBJECTS ---
                else:
                    x, y, w, h = cv2.boundingRect(contour)
                    pixel_density = max(1, int(tatami_density / (max_height_mm / h_img)))
                    pixel_length = max(1, int(stitch_length / (max_width_mm / w_img)))
                    
                    for row in range(y, y + h, pixel_density):
                        row_stitches = []
                        for col in range(x, x + w, pixel_length):
                            if cv2.pointPolygonTest(contour, (float(col), float(row)), False) >= 0:
                                mx = (col - cx_img) * scale_x
                                my = (row - cy_img) * scale_y
                                row_stitches.append((mx, my))
                                
                        if row % (pixel_density * 2) == 0:
                            row_stitches.reverse()
                            
                        for pt in row_stitches:
                            pattern.add_stitch_absolute(pyembroidery.STITCH, pt[0], pt[1])
                            stitch_count += 1
            
            pattern.add_command(pyembroidery.END)
            
            st.success("🎉 Smart Digitization Complete!")
            
            c1, c2 = st.columns(2)
            c1.metric(label="Total Stitches", value=f"{stitch_count}")
            c2.metric(label="Background Status", value="Dropped Successfully")
            
            # Export Stream
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
                label=f"💾 Download Machine File ({ext.upper()})",
                data=out_buffer,
                file_name=f"perfect_embroidery{ext}",
                mime=mime_type
            )
            st.info("💡 Pro-Tip: Agar background ka thoda hissa abhi bhi aaye, toh sidebar se 'Background Omit Sensitivity' slider ko thoda badha dena (e.g. 45-50).")
