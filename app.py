import io
import pandas as pd
import streamlit as st

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(page_title="CSV Analyte Pivot", page_icon="🧪", layout="centered")
st.title("🧪 CSV Analyte Pivot")
st.caption(
    "Upload a raw CSV export. I’ll pivot analyte columns → rows, keep your sample attributes as columns, "
    "drop empty results, and sort by Data File → Analyte."
)

# ----------------------------
# Sidebar options (kept simple)
# ----------------------------
with st.sidebar:
    st.header("Options")
    encoding = st.selectbox("CSV encoding", ["utf-8-sig", "utf-8", "latin-1"], index=0)
    require_brackets = st.checkbox("Detect analytes only if header contains [ ]", value=True)
    st.write("Tip: Leave this ON for ICP/MS-style headers like `27  Al  [ He ]`.")

# ----------------------------
# File uploader
# ----------------------------
uploaded = st.file_uploader("Step 1 — Upload your raw .csv file", type=["csv"])

# ----------------------------
# Core transform
# ----------------------------
def transform(df: pd.DataFrame, brackets_required: bool = True) -> pd.DataFrame:
    """
    - Identify analyte columns
    - Melt to long format as (Analyte, Result)
    - Drop empty results
    - Sort by Data File, Analyte (if present)
    """
    if brackets_required:
        # Typical ICP/MS exports include [ He ] / [ H2 ] etc. in analyte headers
        analyte_cols = [c for c in df.columns if ("[" in str(c) and "]" in str(c))]
    else:
        # Fallback: any header containing at least one digit (e.g., masses like 27, 208)
        analyte_cols = [c for c in df.columns if any(ch.isdigit() for ch in str(c))]

    if not analyte_cols:
        raise ValueError("No analyte columns detected with the current rule.")

    id_vars = [c for c in df.columns if c not in analyte_cols]

    long_df = df.melt(
        id_vars=id_vars,
        value_vars=analyte_cols,
        var_name="Analyte",
        value_name="Result",
    )

    # Clean up
    long_df["Analyte"] = long_df["Analyte"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    long_df["Result"] = long_df["Result"].astype(str).str.strip()

    # Drop empty/blank results
    long_df = long_df[long_df["Result"].ne("").fillna(False)]

    # Sort by Data File then Analyte if available
    sort_cols = [c for c in ["Data File", "Analyte"] if c in long_df.columns]
    if sort_cols:
        long_df = long_df.sort_values(by=sort_cols, ascending=[True] * len(sort_cols))

    # Reset index for a clean CSV
    long_df = long_df.reset_index(drop=True)
    return long_df

# ----------------------------
# Run transform & show output
# ----------------------------
if uploaded is not None:
    try:
        # Read CSV as text (let pandas infer separator; engine='python' is forgiving)
        df = pd.read_csv(uploaded, dtype=str, encoding=encoding, engine="python")

        out_df = transform(df, brackets_required=require_brackets)

        # Success + preview
        st.success(f"Processed successfully — input rows: {len(df)}, output rows: {len(out_df)}")
        st.write("Preview of processed data (first 100 rows):")
        st.dataframe(out_df.head(100), use_container_width=True)

        # Download button
        buf = io.StringIO()
        out_df.to_csv(buf, index=False)
        st.download_button(
            label="⬇ Step 2 — Download processed CSV",
            data=buf.getvalue(),
            file_name="processed.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Error: {e}")

# ----------------------------
# Footer help
# ----------------------------
with st.expander("Help / Notes"):
    st.markdown(
        """
- **What counts as an analyte column?**  
  By default, any header that *contains* square brackets (e.g., `27  Al  [ He ]`, `201  [Hg]  [ He ]`).  
  Disable the option in the sidebar if your analyte headers lack brackets but include digits (e.g., `27 Al`).

- **Sorting:**  
  The output is sorted by **Data File** and then **Analyte** when those columns exist.

- **Encoding issues:**  
  If you see decoding errors or garbled characters, try switching the encoding to `latin-1` in the sidebar.

- **Large files:**  
  Streamlit Cloud’s free tier supports moderate file sizes. For very large CSVs, consider chunking or a paid tier.
        """
    )
