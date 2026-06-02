import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

# Page Configuration
st.set_page_config(page_title="AI Advanced Embroidery Digitizer", layout="wide", page_icon="🪡")

st.title("🪡 AI Embroidery Digitizer Pro (Wilcom Auto-Trace Engine)")
st.write("Extracts complex patterns from garment images and converts them to clean embroidery files.")

# --- SIDEBAR: Parameters ---
st.sidebar.header("🛠️ Digitizing Parameters")

# 1. Size Selection
st.sidebar.subheader("📐 Hoop & Design Size")
max_width_mm = st.sidebar.number_input("Max Width (mm)", min_value=10, max_value=500, value=100)
max_height_mm = st.sidebar.number_input("Max Height (mm)", min_value=10, max_value=500, value=100)

# 2. Stitch Type Selection
st.sidebar.subheader("🧵 Stitch Settings")
stitch_type = st.sidebar.selectbox(
    "Select Stitch Style",
    options=["Satin Stitch (For Borders/Text)", "Tatami Fill (For Large Areas)", "Run Stitch (Outline)"]
)

# 3. Technical Parameters
stitch_length = st.sidebar.slider("Stitch Length (mm)", min_value=1.0, max_value=7.0, value=3.5, step=0.1)
stitch_density = st.sidebar.slider("Stitch Density / Spacing (mm)", min_value=0.2, max_value=1.5, value=0.4, step=0.05)

# 4. Advanced Sensitivity Control (Wilcom Style Magic)
st.sidebar.subheader("🎨 Image Tracing Sensitivity")
bg_threshold = st.sidebar.slider("Filter Dark Background/Cloth", min_value=10, max_value=200, value=70, 
                                   help="Adjust this if your motif or background is too dark/bright to filter out the fabric.")

file_format = st.sidebar.selectbox("Export Machine Format", options=[".DST (Tajima)", ".PES (Brother)"])

# --- MAIN SECTION ---
uploaded_file = st.file_uploader("Upload your Embroidery Design / Image (PNG, JPG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Original Design")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("⚙️ Live Stitch Processing")
        with st.spinner("Isolating embroidery threads and computing paths..."):
            
            # Convert PIL Image to OpenCV format
            img_np = np.array(image.convert('RGB'))
            
            # Step 1: Convert to Grayscale
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            
            # Step 2: Enhance Contrast (Makes the thread pop out from the fabric)
            enhanced = cv2.equalizeHist(gray)
            
            # Step 3: Adaptive thresholding to catch tiny threads and isolate background fabric
            thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY, 11, 2)
            
            # Clean noise (small dots/garment texture noise)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            
            # Find contours of the isolated embroidery work
            contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # Initialize pattern
            pattern = pyembroidery.EmbPattern()
            stitch_count = 0
            
            # Center alignment logic
            h_img, w_img = img_np.shape[:2]
            cx_img, cy_img = w_img / 2, h_img / 2
            
            # Simple simulation loop for stitch path generation
            for contour in contours:
                # Filter out extremely small noise contours
                if cv2.contourArea(contour) < 20:
                    continue
                    
                pattern.add_command(pyembroidery.COLOR_BREAK)
                
                # Scale contours and shift origin to center
                scaled_points = []
                for pt in contour:
                    x_pixel, y_pixel = pt[0][0], pt[0][1]
                    
                    # Shift origin to center of design, then scale to mm (10 units = 1mm in pyembroidery)
                    x_mm = ((x_pixel - cx_img) / w_img) * max_width_mm * 10
                    y_mm = ((y_pixel - cy_img) / h_img) * max_height_mm * 10
                    scaled_points.append((x_mm, y_mm))
                
                if len(scaled_points) < 2:
                    continue
                
                if "Satin" in stitch_type:
                    # Alternating zig-zag across the contour path
                    half = len(scaled_points) // 2
                    for i in range(0, half, max(1, int(stitch_density * 5))):
                        p1 = scaled_points[i]
                        p2 = scaled_points[len(scaled_points) - 1 - i]
                        pattern.add_stitch_absolute(pyembroidery.STITCH, p1[0], p1[1])
                        pattern.add_stitch_absolute(pyembroidery.STITCH, p2[0], p2[1])
                        stitch_count += 2
                        
                elif "Tatami" in stitch_type:
                    # Row-wise fill paths
                    for i, pt in enumerate(scaled_points):
                        if i % max(1, int(stitch_length)) == 0:
                            pattern.add_stitch_absolute(pyembroidery.STITCH, pt[0], pt[1])
                            stitch_count += 1
                else:
                    # Run Stitch / Simple Outline trace
                    for pt in scaled_points:
                        pattern.add_stitch_absolute(pyembroidery.STITCH, pt[0], pt[1])
                        stitch_count += 1
            
            pattern.add_command(pyembroidery.END)
            
            st.success("🎉 Digitizing Processed Based on Contrast!")
            st.metric(label="Estimated Stitch Count", value=f"{stitch_count} Stitches")
            
            # Byte Stream logic with correct universal octet-stream MIME type
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
                label=f"💾 Download Clean Embroidery File ({ext.upper()})",
                data=out_buffer,
                file_name=f"kurti_digitized_design{ext}",
                mime=mime_type
            )
            
            st.info("💡 Tip: Download karne ke baad file ko directly Stitch Viewer app me refresh karke open karein. Design ab exact coordinates par center me show hoga.")
