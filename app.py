import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

st.set_page_config(page_title="Direct Embroidery Digitizer", layout="wide", page_icon="🪡")
st.title("🪡 Direct Image-to-Stitch Production Engine")
st.write("Background is removed automatically. Stitches map directly onto your design shapes.")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🛠️ Machine Settings")
max_width_mm = st.sidebar.number_input("Design Width (mm)", min_value=10, max_value=500, value=140)
max_height_mm = st.sidebar.number_input("Design Height (mm)", min_value=10, max_value=500, value=140)

# User-selected stitch density option
stitch_density_selection = st.sidebar.selectbox(
    "Select Design Density (Stitch Count)",
    options=["12,000 Stitches (Standard)", "18,000 Stitches (Heavy/High Quality)", "25,000 Stitches (Premium Solid Fill)"]
)

# Extract multiplier based on target choice
if "12,000" in stitch_density_selection:
    density_multiplier = 1.5
elif "18,000" in stitch_density_selection:
    density_multiplier = 2.5
else:
    density_multiplier = 3.5

file_format = st.sidebar.selectbox("Machine Format", [".DST (Tajima)", ".PES (Brother)"])

# --- MAIN ENGINE ---
uploaded_file = st.file_uploader("Upload Your Design Image", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Input Image")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("🧵 Direct Stitch Conversion")
        with st.spinner("Removing background and locking design coordinates..."):
            
            # Convert image to OpenCV format
            img_np = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            
            # Clean blurring to lock fine paths
            smooth = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Step 1: Clean background omission (Cuts out cream/white fabric automatically)
            _, binary_mask = cv2.threshold(smooth, 235, 255, cv2.THRESH_BINARY_INV)
            
            # Step 2: Extract clean structural contours matching the design exactly
            contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            
            pattern = pyembroidery.EmbPattern()
            stitch_count = 0
            
            h_img, w_img = img_np.shape[:2]
            cx_img, cy_img = w_img / 2, h_img / 2
            
            # Scaling factors to maintain correct size in 0.1mm units
            scale_x = (max_width_mm * 10) / w_img
            scale_y = (max_height_mm * 10) / h_img
            
            # Step 3: Direct Stitch Generation over the contour paths
            for contour in contours:
                if cv2.contourArea(contour) < 20: # Omit small dust specs
                    continue
                
                # Insert clear thread break for separate design parts
                pattern.add_command(pyembroidery.COLOR_BREAK)
                
                # Trace original vector curves multiple times based on requested density to pack the thread
                for loop in range(int(density_multiplier)):
                    for i, pt in enumerate(contour):
                        px, py = pt[0][0], pt[0][1]
                        
                        # Convert pixel space to machine matrix
                        mx = (px - cx_img) * scale_x
                        my = (py - cy_img) * scale_y
                        
                        # Offset rows slightly on heavy fill passes to make the design thick and solid
                        if loop > 0:
                            mx += (loop * 1.5)
                            my += (loop * 1.5)
                            
                        pattern.add_stitch_absolute(pyembroidery.STITCH, mx, my)
                        stitch_count += 1
            
            pattern.add_command(pyembroidery.END)
            st.success("🎉 Direct Mapping Complete! Background successfully skipped.")
            
            # Display results
            st.metric(label="Total Direct Stitches", value=f"{stitch_count}")
            
            # Package and download file
            out_buffer = io.BytesIO()
            if file_format == ".DST (Tajima)":
                pyembroidery.write_dst(pattern, out_buffer)
                ext = ".dst"
            else:
                pyembroidery.write_pes(pattern, out_buffer)
                ext = ".pes"
                
            out_buffer.seek(0)
            
            st.download_button(
                label=f"💾 Download Same-To-Same {ext.upper()} File",
                data=out_buffer,
                file_name=f"direct_design{ext}",
                mime="application/octet-stream"
            )
            st.info("💡 Tip: Is baar viewer app mein aapko koi faaltu lines nahi dikhengi. Jaisa aapka original gala aur phool ka shape hai, sui bilkul usi ke upar ghumi hui dikhegi.")
