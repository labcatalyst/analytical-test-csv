import io
import pandas as pd
import gradio as gr

TITLE = "🧪 CSV Analyte Pivot"
DESC = "Drop a CSV. I’ll pivot analyte columns → rows, keep your sample attributes, and sort by Data File → Analyte."

def process(file, encoding="utf-8-sig", require_brackets=True):
    if file is None:
        return None, "Please upload a CSV."
    try:
        # Read
        df = pd.read_csv(file.name, dtype=str, encoding=encoding, engine="python")

        # Detect analyte columns
        if require_brackets:
            analyte_cols = [c for c in df.columns if ("[" in str(c) and "]" in str(c))]
        else:
            analyte_cols = [c for c in df.columns if any(ch.isdigit() for ch in str(c))]
        if not analyte_cols:
            return None, "No analyte columns detected with current rule."

        # Pivot to long format
        id_vars = [c for c in df.columns if c not in analyte_cols]
        out = df.melt(id_vars=id_vars, value_vars=analyte_cols,
                      var_name="Analyte", value_name="Result")
        out["Analyte"] = out["Analyte"].astype(str).str.replace(r"\s+"," ",regex=True).str.strip()
        out["Result"] = out["Result"].astype(str).str.strip()
        out = out[out["Result"].ne("").fillna(False)]

        # Sort
        sort_cols = [c for c in ["Data File","Analyte"] if c in out.columns]
        if sort_cols:
            out = out.sort_values(by=sort_cols, ascending=[True]*len(sort_cols))

        # Return as downloadable CSV
        buf = io.BytesIO()
        out.to_csv(buf, index=False)
        buf.seek(0)
        return (buf, "processed.csv"), f"OK — {len(out)} rows."
    except Exception as e:
        return None, f"Error: {e}"

with gr.Blocks(title=TITLE) as demo:
    gr.Markdown(f"## {TITLE}\n{DESC}")
    with gr.Row():
        file_in = gr.File(file_types=[".csv"], label="Upload CSV")
        encoding = gr.Textbox(value="utf-8-sig", label="Encoding")
        brackets = gr.Checkbox(value=True, label="Headers must contain [ ]")
    btn = gr.Button("Process")
    file_out = gr.File(label="Download processed CSV")
    status = gr.Markdown()
    btn.click(process, inputs=[file_in, encoding, brackets], outputs=[file_out, status])

if __name__ == "__main__":
    demo.launch()
