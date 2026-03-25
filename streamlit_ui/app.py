import streamlit as st
import requests
import time
import json
import base64

API_URL = "http://localhost:8000"
API_KEY = "GoldenEY1479"

# ---------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Contract Intelligence Platform",
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------
# EY BRANDING + GLOBAL CSS
# ---------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Playfair+Display:wght@600;700&display=swap');

/* Global font */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Headings */
h1, h2, h3 { font-family: 'Playfair Display', serif !important; }

/* EY Header */
.ey-header {
    background: #111;
    padding: 1.4rem 2rem;
    border-bottom: 3px solid #FFE600;
    color: white;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.ey-title {
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.3px;
}

/* EY Footer */
.ey-footer {
    margin-top: 4rem;
    padding: 1.4rem;
    text-align: center;
    color: #aaa;
    border-top: 1px solid #333;
    font-size: 13px;
}

/* Dashboard job cards */
.job-card {
    padding: 1rem;
    border-radius: 10px;
    background: rgba(255,230,0,0.12);
    border-left: 5px solid #FFE600;
    margin-bottom: 0.8rem;
    color: white !important;
}

/* Buttons */
button[kind="primary"] {
    background-color: #FFE600 !important;
    color: #111 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}

/* Error box fix */
div.stAlert {
    background-color: rgba(255,0,0,0.15) !important;
    border-left: 4px solid #ff4d4d !important;
    color: #ffcccc !important;
}

/* Code block fix */
.stCodeBlock {
    background-color: #0f0f0f !important;
    color: #fff !important;
    border-radius: 10px !important;
}

/* PDF preview container */
.pdf-box {
    border: 1px solid #333;
    border-radius: 10px;
    background: #1a1a1a;
    padding: 0.8rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# EY HEADER
# ---------------------------------------------------------------
st.markdown("""
<div class="ey-header">
    <span class="ey-title">EY Contract Intelligence Platform</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# SIDEBAR NAV
# ---------------------------------------------------------------
st.sidebar.title("📁 Navigation")
page = st.sidebar.radio("Go to:", ["Upload", "Job Status", "Dashboard", "Canonical Viewer"])


# =================================================================
# ✅ 1. UPLOAD PAGE
# =================================================================
if page == "Upload":
    st.title("📤 Upload Contract")
    st.write("Upload PDFs, Word docs, emails, or audio — AI converts them into **EY-standardized NDA/SOW packages**.")

    col1, col2 = st.columns([1.6, 1])

    with col1:

        uploaded_file = st.file_uploader(
            "Choose file",
            type=["pdf", "docx", "doc", "eml", "mp3", "wav", "m4a"]
        )

        contract_type = st.selectbox("Contract Type", ["auto", "nda", "sow"])

        if st.button("Start Analysis", use_container_width=True):
            if not uploaded_file:
                st.error("Please upload a file.")
            else:
                with st.spinner("Uploading & analyzing…"):
                    files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                    data = {"contract_type": contract_type}

                    try:
                        r = requests.post(
                            f"{API_URL}/analyze",
                            headers={"X-API-Key": API_KEY},
                            files=files,
                            data=data
                        )
                        if r.status_code == 200:
                            job_id = r.json()["job_id"]
                            st.session_state["job_id"] = job_id
                            st.success("✅ Job created successfully!")
                            st.info("Go to **Job Status** to track progress.")
                        else:
                            st.error("❌ Backend error.")
                    except:
                        st.error("❌ Cannot connect to backend.")

    with col2:
        st.subheader("⚡ Supported Formats")
        st.write("- PDF\n- Word\n- Email (.eml)\n- Audio (MP3, WAV, M4A)")
        st.write("AI automatically picks the correct pipeline.")


# =================================================================
# ✅ 2. JOB STATUS
# =================================================================
if page == "Job Status":
    st.title("⏳ Job Status")

    if "job_id" not in st.session_state:
        st.warning("Upload a file first.")
        st.stop()

    job_id = st.session_state["job_id"]
    st.write(f"Tracking Job: `{job_id}`")

    status_box = st.empty()
    progress_bar = st.empty()
    download_area = st.empty()

    progress = 0

    while True:
        try:
            resp = requests.get(f"{API_URL}/jobs/{job_id}", headers={"X-API-Key": API_KEY})
            job = resp.json()
        except:
            status_box.error("❌ Backend unreachable.")
            break

        status = job["status"]

        if status == "queued":
            progress = 10
            progress_bar.progress(progress)
            status_box.warning("🟡 Job Queued…")
            time.sleep(2)

        elif status == "processing":
            progress = min(progress + 10, 90)
            progress_bar.progress(progress)
            status_box.info("🔄 Processing…")
            time.sleep(3)

        elif status == "failed":
            status_box.error(f"❌ Failed: {job.get('error')}")
            break

        elif status == "complete":
            progress_bar.progress(100)
            status_box.success("✅ Completed!")

            urls = job["download_urls"]

            nda_bytes = requests.get(f"{API_URL}{urls['nda_pdf']}", headers={"X-API-Key": API_KEY}).content
            sow_bytes = requests.get(f"{API_URL}{urls['sow_pdf']}", headers={"X-API-Key": API_KEY}).content

            with download_area:
                st.download_button("⬇ Download NDA PDF", nda_bytes, "NDA.pdf")
                st.download_button("⬇ Download SOW PDF", sow_bytes, "SOW.pdf")

            break


# =================================================================
# ✅ 3. DASHBOARD
# =================================================================
if page == "Dashboard":
    st.title("📊 Dashboard")

    try:
        r = requests.get(f"{API_URL}/jobs", headers={"X-API-Key": API_KEY})
        jobs = r.json().get("jobs", [])
    except:
        st.error("Cannot load job history.")
        st.stop()

    st.subheader("Recent Jobs")

    for job in jobs[::-1]:
        st.markdown(f"""
        <div class="job-card">
            <strong>{job['job_id']}</strong><br>
            Status: {job['status']}<br>
            <small>{job['created_at']}</small>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Analytics (Coming Soon)")
    st.info("Charts will show NDA/SOW volume, audio usage, processing duration, etc.")


# =================================================================
# ✅ 4. CANONICAL VIEWER (With PDF Preview)
# =================================================================
if page == "Canonical Viewer":
    st.title("🧩 Canonical Viewer")

    if "job_id" not in st.session_state:
        st.warning("Upload a file first.")
        st.stop()

    job_id = st.session_state["job_id"]

    job = requests.get(f"{API_URL}/jobs/{job_id}", headers={"X-API-Key": API_KEY}).json()

    # ---- Fetch canonical JSON ----
    canonical_url = f"{API_URL}/download/{job_id}/canonical"
    canonical_json = requests.get(canonical_url, headers={"X-API-Key": API_KEY}).json()

    # ---------------------------------
    # ✅ SUMMARY CARD
    # ---------------------------------
    st.subheader("📄 Summary")

    st.markdown(f"""
        <div style="
            background: rgba(255,230,0,0.07);
            padding:1rem;
            border-left:5px solid #FFE600;
            border-radius:10px;
            margin-bottom:1rem;">
            <b>Job ID:</b> {job_id}<br>
            <b>Status:</b> {job['status']}
        </div>
    """, unsafe_allow_html=True)

    # ---------------------------------
    # ✅ PDF PREVIEW (EMBEDDED)
    # ---------------------------------
    st.subheader("📑 Document Preview")

    # Ensure the job actually completed
    if "download_urls" not in job:
        st.error("❌ Documents are not ready yet. Go to Job Status and wait for completion.")
        st.stop()

    urls = job["download_urls"]

    nda_url = f"{API_URL}{urls['nda_pdf']}"
    sow_url = f"{API_URL}{urls['sow_pdf']}"
    
    col_pdf1, col_pdf2 = st.columns(2)

    def preview_pdf(binary_data):
        b64 = base64.b64encode(binary_data).decode()
        pdf_embed = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="500px"></iframe>'
        st.markdown(pdf_embed, unsafe_allow_html=True)

    with col_pdf1:
        st.write("### NDA Preview")
        nda_bytes = requests.get(nda_url, headers={"X-API-Key": API_KEY}).content
        preview_pdf(nda_bytes)

    with col_pdf2:
        st.write("### SOW Preview")
        sow_bytes = requests.get(sow_url, headers={"X-API-Key": API_KEY}).content     
        preview_pdf(sow_bytes)

    # ---------------------------------
    # ✅ Canonical JSON
    # ---------------------------------
    st.markdown("---")
    st.subheader("🧱 Canonical JSON")
    st.code(json.dumps(canonical_json, indent=2), language="json")

    # ---------------------------------
    # ✅ Missing Fields
    # ---------------------------------
    if canonical_json.get("missingFields"):
        st.subheader("⚠ Missing Fields")
        st.warning(", ".join(canonical_json["missingFields"]))

    # ---------------------------------
    # ✅ Conflicts Viewer
    # ---------------------------------
    if canonical_json.get("conflicts"):
        st.subheader("⚡ Conflicts")
        with st.expander("View Conflicts"):
            for c in canonical_json["conflicts"]:
                st.write(f"- **{c['field']}** → chosen: `{c['chosen']}`, alternatives: `{c['alternatives']}`")

# ---------------------------------------------------------------
# EY FOOTER
# ---------------------------------------------------------------
st.markdown("""
<div class="ey-footer">
    © 2026 EY Contract Intelligence — Internal Demo Platform
</div>
""", unsafe_allow_html=True)