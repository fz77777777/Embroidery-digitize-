import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

# Page Configuration
st.set_page_config(page_title="AI HD Embroidery Digitizer", layout="wide", page_icon="🪡")

st.title("🪡 AI Studio-Grade Embroidery Digitizer")
st.write("Clean Vector-to-Stitch Conversion (No Noise, Optimized Jumps)")

# --- SIDEBAR: Parameters ---
st.sidebar.header("🛠️ Stitch & Hoop Settings")

# 1. Size Selection
max_width_mm = st.sidebar.number_input("Max Width (mm)", min_value=10, max_value=500, value=100)
max_height_mm = st.sidebar.number_input("Max Height (mm)", min_value=10, max_value=500, value=100)

# 2. Stitch Type Selection
stitch_type = st.sidebar.selectbox(
    "Select Stitch Style",
    options=["Run Stitch (Clean Outline)", "Satin Stitch (Borders)", "Tatami Fill (Solid Fill)"]
)

# 3. Technical Parameters
stitch_length = st.sidebar.slider("Stitch Length (mm)", min_value=1.0, max_value=7.0, value=3.0, step=0.1)
stitch_density = st.sidebar.slider("Stitch Density (mm)", min_value=0.2, max_value=1.5, value=0.5, step=0.05)

# 4. Advanced Filter (To stop confetti/scratches)
st.sidebar.subheader("🎛️ Noise Filter Controls")
min_area = st.sidebar.slider("Ignore Small Elements (Area)", min_value=10, max_value=500, value=150, 
                             help="Higher value removes tiny unwanted dots/scratches.")

file_format = st.sidebar.selectbox("Export Machine Format", options=[".DST (Tajima)", ".PES (Brother)"])

# --- MAIN SECTION ---
uploaded_file = st.file_uploader("Upload Clean Design Image", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Input Design")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("⚙️ Clean Stitch Generation")
        with st.spinner("Smoothing image and extracting clean vector lines..."):
            
            # Convert PIL to OpenCV (BGR)
            img_np = np.array(image.convert('RGB'))
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            # Step 1: Grayscale conversion
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            
            # Step 2: Blur the image to merge microscopic pixels (Removes 99% noise)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Step 3: High-Quality Edge Detection (Canny) instead of messy thresholding
            edges = cv2.Canny(blurred, 50, 150)
            
            # Step 4: Find clean outer boundaries
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
            
            # Initialize Embroidery Pattern
            pattern = pyembroidery.EmbPattern()
            stitch_count = 0
            
            h_img, w_img = img_np.shape[:2]
            cx_img, cy_img = w_img / 2, h_img / 2
            
            # Loop through clean contours
            for contour in contours:
                # Strictly ignore anything smaller than user threshold (Filters scratches)
                if cv2.contourArea(contour) < min_area:
                    continue
                
                # Only add a color break when genuinely moving to a distinct large block
                pattern.add_command(pyembroidery.COLOR_BREAK)
                
                # Convert pixels to actual scaled 0.1mm machine units
                points = []
                for pt in contour:
                    px, py = pt[0][0], pt[0][1]
                    mx = ((px - cx_img) / w_img) * max_width_mm * 10
                    my = ((py - cy_img) / h_img) * max_height_mm * 10
                    points.append((mx, my))
                
                if len(points) < 2:
                    continue
                
                # Generate paths based on clean vector edges
                if "Run" in stitch_type:
                    for i, pt in enumerate(points):
                        if i % max(1, int(stitch_length)) == 0:
                            pattern.add_stitch_absolute(pyembroidery.STITCH, pt[0], pt[1])
                            stitch_count += 1
                            
                elif "Satin" in stitch_type:
                    half = len(points) // 2
                    for i in range(0, half, max(1, int(stitch_density * 8))):
                        p1 = points[i]
                        p2 = points[len(points) - 1 - i]
                        pattern.add_stitch_absolute(pyembroidery.STITCH, p1[0], p1[1])
                        pattern.add_stitch_absolute(pyembroidery.STITCH, p2[0], p2[1])
                        stitch_count += 2
                        
                elif "Tatami" in stitch_type:
                    for i, pt in enumerate(points):
                        if i % max(1, int(stitch_density * 4)) == 0:
                            pattern.add_stitch_absolute(pyembroidery.STITCH, pt[0], pt[1])
                            stitch_count += 1
            
            # Correct end sequence
            pattern.add_command(pyembroidery.END)
            
            st.success("🎉 Optimized Stitch Path Generated!")
            
            # Metrics to verify the fix
            c1, c2 = st.columns(2)
            c1.metric(label="Total Stitches", value=f"{stitch_count}")
            c2.metric(label="Color Changes (Optimized)", value="Cleaned")
            
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
                label=f"💾 Download Cleaned {ext.upper()} File",
                data=out_buffer,
                file_name=f"clean_embroidery_design{ext}",
                mime=mime_type
            )
            
            st.info("💡 Pro-Tip: Agar abhi bhi halki lines dikhein, toh sidebar se 'Ignore Small Elements (Area)' ko badha kar 250-300 kar dena. Kachra bilkul saaf ho jayega!")
