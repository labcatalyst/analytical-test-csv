import io
import gc
import re
import zipfile
import pandas as pd
import streamlit as st

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(page_title="CSV Sample Splitter", page_icon="🧪", layout="centered")
st.title("🧪 CSV Sample Splitter")
st.caption(
    "Upload a raw .csv file, I'll:\n"
    "1) Keep only rows with Sample Type = 'Sample'\n"
    "2) Drop rows where Concentration is null/blank\n"
    "3) Split into separate CSVs by Sample Name"
)

# ----------------------------
# Sidebar options (privacy-safe)
# ----------------------------
with st.sidebar:
    st.header("Options")
    encoding = st.selectbox("CSV encoding", ["utf-8-sig", "utf-8", "latin-1"], index=0)
    max_mb = st.number_input("Max upload size (MB)", min_value=1, max_value=200, value=25, step=1)
    st.write("No files are written to disk. Nothing is cached.")

# ----------------------------
# File uploader (in-memory)
# ----------------------------
uploaded = st.file_uploader("Step 1 — Upload your raw .csv file", type=["csv"])

# ----------------------------
# Core transform
# ----------------------------
SAMPLE_TYPE_COL = "Sample Type"
CONCENTRATION_COL = "Concentration"
SAMPLE_NAME_COL = "Sample Name"


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    1) Filter on Sample Type == 'Sample'
    2) Filter on Concentration ≠ null/blank
    Returns the filtered DataFrame.
    """
    # Ensure required columns exist
    missing = [c for c in [SAMPLE_TYPE_COL, CONCENTRATION_COL, SAMPLE_NAME_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    # 1. Keep only rows where Sample Type == 'Sample'
    st.write(f"Unique values in '{SAMPLE_TYPE_COL}' before filtering:", df[SAMPLE_TYPE_COL].unique())
    mask_sample_type = (
        df[SAMPLE_TYPE_COL]
        .astype(str)
        .str.strip()
        .eq("Sample")
    )
    df = df[mask_sample_type]

    # 2. Keep only rows where Concentration is not null/blank
    conc_series = df[CONCENTRATION_COL]
    mask_conc = conc_series.notna() & conc_series.astype(str).str.strip().ne("")
    df = df[mask_conc]

    return df.reset_index(drop=True)


def slugify(value: str) -> str:
    """Create a safe filename slug from the Sample Name."""
    value = str(value)
    value = value.strip()
    value = value.replace(" ", "_")
    value = re.sub(r"[^0-9A-Za-z_\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "sample"


# ----------------------------
# Process & Download (no disk writes)
# ----------------------------
if uploaded is not None:
    try:
        # Read raw bytes (IN MEMORY)
        raw_bytes = uploaded.getvalue()

        # Size guard (in memory)
        size_mb = len(raw_bytes) / (1024 * 1024)
        if size_mb > max_mb:
            st.error(f"File is {size_mb:.2f} MB, exceeds the {max_mb} MB limit.")
            st.stop()

        # Parse CSV from memory (no temp files)
        mem_buf = io.BytesIO(raw_bytes)
        df = pd.read_csv(mem_buf, dtype=str, encoding=encoding, engine="python")

        st.write(f"Input rows: {len(df)}")

        # Apply filtering steps 1 & 2
        out_df = transform(df)

        if out_df.empty:
            st.warning("After filtering, no rows remain (no 'Sample' rows with non-blank Concentration).")
            st.stop()

        st.success(f"Filtered — output rows: {len(out_df)}")
        st.write("Preview of filtered data (first 100 rows):")
        st.dataframe(out_df.head(100), use_container_width=True)

        # ----------------------------
        # Step 3 — Split by Sample Name
        # ----------------------------
        grouped = list(out_df.groupby(SAMPLE_NAME_COL, dropna=False))
        st.write(f"Found {len(grouped)} unique Sample Name value(s).")

        # Optional: combined filtered CSV download
        combined_buf = io.StringIO()
        out_df.to_csv(combined_buf, index=False)
        st.download_button(
            label="⬇ Download single combined filtered CSV",
            data=combined_buf.getvalue(),
            file_name="filtered_all_samples.csv",
            mime="text/csv",
        )

        # Build a ZIP with one CSV per Sample Name (in memory)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for idx, (sample_name, sub_df) in enumerate(grouped, start=1):
                sample_slug = slugify(sample_name)
                filename = f"{sample_slug}.csv"
                csv_buf = io.StringIO()
                sub_df.to_csv(csv_buf, index=False)
                zf.writestr(filename, csv_buf.getvalue())

        st.download_button(
            label="⬇ Download all Sample Name CSVs as ZIP",
            data=zip_buf.getvalue(),
            file_name="samples_split_by_sample_name.zip",
            mime="application/zip",
        )

        # Also provide individual download buttons (if you want that UX)
        with st.expander("Individual Sample Name downloads"):
            for idx, (sample_name, sub_df) in enumerate(grouped, start=1):
                sample_slug = slugify(sample_name)
                csv_buf = io.StringIO()
                sub_df.to_csv(csv_buf, index=False)
                st.download_button(
                    label=f"⬇ Download CSV for Sample Name = {sample_name}",
                    data=csv_buf.getvalue(),
                    file_name=f"{sample_slug}.csv",
                    mime="text/csv",
                    key=f"dl_{idx}_{sample_slug}",
                )

        # Explicit cleanup (defensive)
        del raw_bytes, mem_buf, df, out_df, combined_buf, zip_buf
        gc.collect()

    except Exception as e:
        st.error(f"Error: {e}")

# ----------------------------
# Help / Notes
# ----------------------------
with st.expander("Privacy & Behavior"):
    st.markdown(
        """
- **In-memory only:** Uploaded files are read directly into memory (`getvalue()`) and never written to disk.
- **No caching:** The app does not use `st.cache_data` or `st.cache_resource`.
- **Ephemeral session:** When the page refreshes or the session ends, data in memory is gone.
        """
    )
