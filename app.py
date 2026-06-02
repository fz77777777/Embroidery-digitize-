import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pyembroidery
import io

# Page Configuration (Willcom Theme Vibes)
st.set_page_config(page_title="AI Embroidery Digitizer", layout="wide", page_icon="🪡")

st.title("🪡 AI Embroidery Digitizer Pro")
st.write("Convert your images/designs into machine-ready embroidery files (Inspired by Willcom)")

# --- SIDEBAR: Parameters (Willcom Style) ---
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

# 3. Technical Parameters (Willcom based)
stitch_length = st.sidebar.slider("Stitch Length (mm)", min_value=1.0, max_value=7.0, value=4.0, step=0.1)
stitch_density = st.sidebar.slider("Stitch Density / Spacing (mm)", min_value=0.2, max_value=1.5, value=0.4, step=0.05)

if stitch_type == "Tatami Fill (For Large Areas)":
    tatami_angle = st.sidebar.slider("Tatami Fill Angle (Degrees)", min_value=0, max_value=180, value=45)
else:
    tatami_angle = 0

# 4. Export Format
file_format = st.sidebar.selectbox("Export Machine Format", options=[".DST (Tajima)", ".PES (Brother)", ".EXP (Melco)"])

# --- MAIN SECTION: File Upload & Processing ---
uploaded_file = st.file_uploader("Upload your Embroidery Design / Image (PNG, JPG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # Image display
    image = Image.open(uploaded_file)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🖼️ Original Design")
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("⚙️ Processing Status")
        with st.spinner("Analyzing image contours and generating stitch paths..."):
            
            # Convert PIL Image to OpenCV format
            img_np = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            
            # Image preprocessing (Thresholding to find shapes)
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            
            # Initialize a new embroidery pattern
            pattern = pyembroidery.EmbPattern()
            
            stitch_count = 0
            
            # Simple Digitizing Logic based on contours
            for contour in contours:
                # Rescale contour points based on user defined mm size
                # 10 pixels roughly = 1mm scale for simplicity here
                pattern.add_command(pyembroidery.COLOR_BREAK)
                
                if "Satin" in stitch_type:
                    # Satin simulation: Zig-zag along the contour points
                    for i in range(0, len(contour)-1, int(stitch_density * 10)):
                        pt1 = contour[i][0]
                        pt2 = contour[(i + len(contour)//2) % len(contour)][0]
                        
                        # Scale to match mm bounds
                        x1 = (pt1[0] / img_np.shape[1]) * max_width_mm * 10 # pyembroidery uses 0.1mm units
                        y1 = (pt1[1] / img_np.shape[0]) * max_height_mm * 10
                        x2 = (pt2[0] / img_np.shape[1]) * max_width_mm * 10
                        y2 = (pt2[1] / img_np.shape[0]) * max_height_mm * 10
                        
                        pattern.add_stitch_absolute(pyembroidery.STITCH, x1, y1)
                        pattern.add_stitch_absolute(pyembroidery.STITCH, x2, y2)
                        stitch_count += 2
                        
                elif "Tatami" in stitch_type:
                    # Tatami simulation: Fill horizontal lines inside bounding box of contour
                    x, y, w, h = cv2.boundingRect(contour)
                    # Adjust lines based on density
                    step_size = max(1, int(stitch_density * 10))
                    for row in range(y, y + h, step_size):
                        # Simple back and forth fill lines
                        for col in range(x, x + w, int(stitch_length * 10)):
                            # Check if point is inside contour
                            if cv2.pointPolygonTest(contour, (col, row), False) >= 0:
                                cx = (col / img_np.shape[1]) * max_width_mm * 10
                                cy = (row / img_np.shape[0]) * max_height_mm * 10
                                pattern.add_stitch_absolute(pyembroidery.STITCH, cx, cy)
                                stitch_count += 1
                                
                else: # Run Stitch / Outline
                    for i in range(0, len(contour), max(1, int(stitch_length))):
                        pt = contour[i][0]
                        cx = (pt[0] / img_np.shape[1]) * max_width_mm * 10
                        cy = (pt[1] / img_np.shape[0]) * max_height_mm * 10
                        pattern.add_stitch_absolute(pyembroidery.STITCH, cx, cy)
                        stitch_count += 1
            
            pattern.add_command(pyembroidery.END)
            
            st.success("🎉 Digitizing Completed successfully!")
            st.metric(label="Estimated Stitch Count", value=f"{stitch_count} Stitches")
            
            # --- File Export / Download Logic ---
            # Create an in-memory file bytes buffer
            out_buffer = io.BytesIO()
            
            if file_format == ".DST (Tajima)":
                pyembroidery.write_dst(pattern, out_buffer)
                mime_type = "application/x-dst"
                ext = ".dst"
            elif file_format == ".PES (Brother)":
                pyembroidery.write_pes(pattern, out_buffer)
                mime_type = "application/x-pes"
                ext = ".pes"
            else:
                pyembroidery.write_exp(pattern, out_buffer)
                mime_type = "application/x-exp"
                ext = ".exp"
                
            out_buffer.seek(0)
            
            # Download Button
            st.download_button(
                label= f"💾 Download Embroidery File ({ext.upper()})",
                data=out_buffer,
                file_name=f"digitized_design{ext}",
                mime=mime_type
            )
            
            st.info("💡 Tip: Is file ko aap direct apni Tajima/Brother machine me daal kar check kar sakte hain.")
            
---

### 🧠 Willcom Research & Smart Logic Jo Maine Isme Add Kiya Hai:
1. **Stitch Unit Conversion:** Willcom me hum hamesha `mm` (millimeters) me baat karte hain. Lekin embroidery machines internal units `0.1mm` use karti hain. Maine code me automatic scaling add kar di hai jo pixel coordinates ko machine dimensions me convert kar degi.
2. **Satin vs Tatami Logic:**
   * **Satin:** Borders aur chhote text ke liye hota hai. Code automatically image ke edges ke beech me zig-zag patterns generate karega.
   * **Tatami:** Bade shapes ko fill karne ke liye use hota hai. Isme code horizontal grid lines create karega (density ke according) taaki filling tight ho.
3. **Multi-Format Export:** India me sabse jyada **Tajima (.DST)** use hota hai commercial levels par, aur gharon me **Brother (.PES)**. Maine dono ka support de diya hai.

### 🚀 GitHub Par Kaise Dalein?
1. GitHub par ek new repository banayein.
2. Vahan do files create karein: `requirements.txt` aur `app.py` (Upar se copy-paste karein).
3. [share.streamlit.io](https://share.streamlit.io/) par jayein, apne GitHub se login karein aur is repo ko select karke **Deploy** par click kar dein. 5 minute me aapki custom embroidery app live ho jayegi!
