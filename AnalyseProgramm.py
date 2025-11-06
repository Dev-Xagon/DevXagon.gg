from __future__ import annotations

import argparse
import html
import webbrowser
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype
import plotly.graph_objects as go
import plotly.io as pio

# GUI / drag & drop
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


def _coerce_numeric(series: pd.Series) -> pd.Series:
    # If already numeric, keep values (just ensure float)
    if is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    # Remove thousands separator '.', switch decimal ',' -> '.' and coerce
    cleaned = (
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _clean_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    replacements = {
        "\u202f": " ",  # narrow no-break space
        "\xa0": " ",    # no-break space
        "\t": " ",
    }
    for col in df.select_dtypes(include="object"):
        series = df[col]
        mask = series.isna()
        cleaned = series.astype(str)
        for src, tgt in replacements.items():
            cleaned = cleaned.str.replace(src, tgt, regex=False)
        cleaned = (
            cleaned.str.replace('"', "", regex=False)
            .str.strip()
        )
        cleaned = cleaned.mask(mask, pd.NA)
        cleaned = cleaned.replace({"": pd.NA})
        df[col] = cleaned
    return df


def load_csv(csv_path: Path, header_row: int = 2) -> pd.DataFrame:
    last_err = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            df = pd.read_csv(
                csv_path,
                sep=None,
                engine="python",
                decimal=",",
                encoding=enc,
                header=max(0, header_row - 1),
            )
            break
        except Exception as exc:
            last_err = exc
            df = None
    if df is None:
        raise RuntimeError(f"Konnte CSV nicht lesen: {last_err}")

    df.columns = [str(c).strip() for c in df.columns]
    df = _clean_object_columns(df)

    # Remove informational rows such as the leading "Definition:" line
    definition_mask = df.apply(
        lambda col: col.astype(str).str.contains("Definition:", na=False)
    )
    if definition_mask.any().any():
        df = df[~definition_mask.any(axis=1)].copy()

    if "Datum" not in df.columns:
        raise RuntimeError('Spalte "Datum" fehlt in der CSV.')

    df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Datum"])

    numeric_cols: list[str] = []
    for col in df.columns:
        if col == "Datum":
            continue
        coerced = _coerce_numeric(df[col])
        if (coerced > 0).any():
            df[col] = coerced
            numeric_cols.append(col)

    if not numeric_cols:
        raise RuntimeError("Keine Spalten mit Werten > 0,00 gefunden.")

    return df[["Datum", *numeric_cols]].copy()


def infer_units(column_name: str) -> str:
    start = column_name.find("(")
    end = column_name.find(")")
    if start != -1 and end != -1 and end > start:
        return column_name[start + 1 : end]
    return ""


def build_figures(df: pd.DataFrame) -> list[go.Figure]:
    figures: list[go.Figure] = []
    time_axis = df["Datum"]
    value_cols = [c for c in df.columns if c != "Datum"]

    for col in value_cols:
        units = infer_units(col)
        y_label = units or "Wert"
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=time_axis,
                y=df[col],
                mode="lines+markers",
                name=col,
                line=dict(width=2),
                marker=dict(size=6),
            )
        )
        fig.update_layout(
            title=col,
            xaxis_title="Datum",
            yaxis_title=y_label,
            template="plotly_white",
            hovermode="x unified",
        )
        figures.append(fig)

    return figures


def write_dashboard(figures: list[go.Figure], title: str, out_path: Path) -> Path:
    cards: list[str] = []
    for idx, fig in enumerate(figures):
        html_fragment = pio.to_html(
            fig,
            include_plotlyjs="inline" if idx == 0 else False,
            full_html=False,
            config={"displayModeBar": True, "responsive": True},
        )
        cards.append(f"<section class='card'>{html_fragment}</section>")

    css = """
:root { --bg:#F9FAFB; --card:#fff; --text:#111827; --border:#E5E7EB; }
*{box-sizing:border-box}
body{margin:0;padding:24px;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;background:var(--bg);color:var(--text)}
h1{margin:0 0 14px 0;font-size:22px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
"""

    html_doc = f"""<!DOCTYPE html>
<html lang='de'>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>{html.escape(title)}</title>
  <style>{css}</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class='grid'>
    {''.join(cards)}
  </div>
</body>
</html>"""

    out_path.write_text(html_doc, encoding="utf-8")
    return out_path


def generate_dashboard(
    csv_path: Path,
    output_path: Path | None,
    title: str,
    header_row: int,
    open_report: bool = True,
) -> Path:
    df = load_csv(csv_path, header_row=header_row)
    figures = build_figures(df)
    out_path = output_path if output_path else csv_path.with_suffix(".dashboard.html")
    write_dashboard(figures, title, out_path)
    if open_report:
        try:
            webbrowser.open(out_path.as_uri(), new=2)
        except Exception:
            webbrowser.open(str(out_path))
    return out_path


def parse_dnd_list(widget: tk.Widget, data: str) -> list[Path]:
    try:
        raw_paths = widget.tk.splitlist(data)
    except Exception:
        raw_paths = data.split()
    cleaned: list[Path] = []
    for entry in raw_paths:
        entry = entry.strip().strip('{}"')
        if entry:
            cleaned.append(Path(entry))
    return cleaned


class DashboardApp:
    def __init__(self, default_title: str, default_header: int, output_override: Path | None):
        if DND_AVAILABLE and TkinterDnD is not None:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()
        self.root.title("CSV -> Energie-Dashboard")
        self.root.geometry("600x420")
        self.output_override = output_override

        self.title_var = tk.StringVar(value=default_title)
        self.header_var = tk.StringVar(value=str(default_header))
        self.status_var = tk.StringVar(value="CSV-Datei ziehen oder auswählen")

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Seitentitel").pack(anchor="w")
        ttk.Entry(container, textvariable=self.title_var).pack(fill="x")

        options_frame = ttk.Frame(container)
        options_frame.pack(fill="x", pady=(8, 12))
        ttk.Label(options_frame, text="Header-Zeile (1-basiert):").pack(side="left")
        ttk.Entry(options_frame, width=5, textvariable=self.header_var).pack(side="left", padx=(4, 0))

        drop_text = (
            "CSV hierher ziehen und ablegen"
            if DND_AVAILABLE
            else "Drag & Drop optional (tkinterdnd2 installieren)"
        )
        self.drop_label = ttk.Label(
            container,
            text=drop_text,
            relief="solid",
            padding=24,
            anchor="center",
        )
        self.drop_label.pack(fill="x")

        if DND_AVAILABLE and DND_FILES is not None:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self.on_drop)
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self.on_drop)

        ttk.Button(container, text="Datei auswählen …", command=self.choose_file).pack(pady=10)

        ttk.Label(container, textvariable=self.status_var, wraplength=520).pack(fill="x", pady=(8, 0))

        ttk.Label(
            container,
            text=(
                "Hinweis: Erste Zeile wird ignoriert; zweite Zeile enthält die Spaltennamen."
            ),
            foreground="#6B7280",
        ).pack(anchor="w", pady=(8, 0))

    def on_drop(self, event):
        widget = event.widget if hasattr(event, "widget") else self.root
        paths = parse_dnd_list(widget, event.data)
        for path in paths:
            if path.suffix.lower() == ".csv":
                self.process(path)
                break

    def choose_file(self):
        file_path = filedialog.askopenfilename(
            title="CSV auswählen",
            filetypes=[("CSV", "*.csv"), ("Alle Dateien", "*.*")],
        )
        if file_path:
            self.process(Path(file_path))

    def process(self, path: Path):
        try:
            header_row = int(self.header_var.get())
        except ValueError:
            messagebox.showerror("Fehler", "Bitte gültige Header-Zeile angeben (Zahl).")
            return

        title = self.title_var.get().strip() or "Energie-Dashboard"
        self.status_var.set(f"Verarbeite: {path}")
        self.root.update_idletasks()
        try:
            out = generate_dashboard(
                path,
                self.output_override,
                title,
                header_row,
                open_report=True,
            )
            self.status_var.set(f"Fertig: {out}")
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            self.status_var.set(f"Fehler: {exc}")

    def run(self):
        self.root.mainloop()


def launch_gui(default_title: str, default_header: int, output_override: Path | None) -> None:
    app = DashboardApp(default_title, default_header, output_override)
    app.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CSV -> interaktives HTML-Dashboard mit Zeitreihen pro Spalte"
    )
    parser.add_argument(
        "csv",
        nargs="?",
        help=(
            "Pfad zur CSV-Datei (erste Zeile ignoriert, zweite Zeile Header). "
            "Wenn weggelassen: Es öffnet sich ein GUI-Fenster mit Drag & Drop."
        ),
    )
    parser.add_argument("-o", "--output", default=None, help="Pfad zur HTML-Ausgabe")
    parser.add_argument("--title", default="Energie-Dashboard", help="Seitentitel")
    parser.add_argument(
        "--header-row",
        type=int,
        default=2,
        help="1-basierte Zeilennummer der Kopfzeile (Standard: 2)",
    )
    args = parser.parse_args()

    output_override = Path(args.output) if args.output else None

    if args.csv:
        csv_path = Path(args.csv.strip().strip('"'))
        if not csv_path.exists():
            raise SystemExit(f"Datei nicht gefunden: {csv_path}")
        out_path = generate_dashboard(
            csv_path,
            output_override,
            args.title,
            args.header_row,
            open_report=True,
        )
        print(f"OK: {out_path}")
    else:
        launch_gui(args.title, args.header_row, output_override)


if __name__ == "__main__":
    main()
