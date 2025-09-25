import io
import gc
import pandas as pd
import streamlit as st

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(page_title="CSV Analyte Pivot", page_icon="🧪", layout="centered")
st.title("🧪 CSV Analyte Pivot")
st.caption(
    "Files are processed entirely in memory (no server-side writes). "
    "I’ll pivot analyte columns → rows, keep sample attributes as columns, "
    "drop empty results, and sort by Data File → Analyte."
)

# ----------------------------
# Sidebar options (privacy-safe)
# ----------------------------
with st.sidebar:
    st.header("Options")
    encoding = st.selectbox("CSV encoding", ["utf-8-sig", "utf-8", "latin-1"], index=0)
    require_brackets = st.checkbox("Detect analytes only if header contains [ ]", value=True)
    max_mb = st.number_input("Max upload size (MB)", min_value=1, max_value=200, value=25, step=1)
    st.write("No files are written to disk. Nothing is cached.")

# ----------------------------
# File uploader (in-memory)
# ----------------------------
uploaded = st.file_uploader("Step 1 — Upload your raw .csv file", type=["csv"])

# ----------------------------
# Core transform
# ----------------------------
def transform(df: pd.DataFrame, brackets_required: bool = True) -> pd.DataFrame:
    """
    Identify analyte columns, melt to (Analyte, Result), drop blanks,
    and sort by Data File then Analyte if present.
    """
    if brackets_required:
        analyte_cols = [c for c in df.columns if ("[" in str(c) and "]" in str(c))]
    else:
        analyte_cols = [c for c in df.columns if any(ch.isdigit() for ch in str(c))]

    if not analyte_cols:
        raise ValueError("No analyte columns detected with the current rule.")

    id_vars = [c for c in df.columns if c not in analyte_cols]

    out = df.melt(
        id_vars=id_vars,
        value_vars=analyte_cols,
        var_name="Analyte",
        value_name="Result",
    )

    # Clean up
    out["Analyte"] = out["Analyte"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    out["Result"] = out["Result"].astype(str).str.strip()

    # Drop empty/blank results
    out = out[out["Result"].ne("").fillna(False)]

    # Sort by Data File then Analyte if available
    sort_cols = [c for c in ["Data File", "Analyte"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(by=sort_cols, ascending=[True] * len(sort_cols))

    return out.reset_index(drop=True)

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

        out_df = transform(df, brackets_required=require_brackets)

        # Show preview
        st.success(f"Processed — input rows: {len(df)}, output rows: {len(out_df)}")
        st.write("Preview of processed data (first 100 rows):")
        st.dataframe(out_df.head(100), use_container_width=True)

        # Build downloadable CSV (in memory)
        download_buf = io.StringIO()
        out_df.to_csv(download_buf, index=False)
        st.download_button(
            label="⬇ Step 2 — Download processed CSV",
            data=download_buf.getvalue(),
            file_name="processed.csv",
            mime="text/csv",
        )

        # Explicit cleanup (defensive)
        del raw_bytes, mem_buf, df, out_df, download_buf
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
- **Public app:** On a free public Streamlit instance, avoid uploading sensitive or regulated data.
        """
    )
