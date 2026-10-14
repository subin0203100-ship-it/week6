import csv
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure



def read_load_data(file_path: Path) -> tuple[list[dict[str, float]], int]:
    data: list[dict[str, float]] = []
    invalid_count = 0

    with file_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        required_fields = ("time_s", "force_N")
        missing_fields = [
            field_name for field_name in required_fields if field_name not in fieldnames
        ]
        if missing_fields:
            missing_text = ", ".join(missing_fields)
            raise ValueError(
                f"필수 열이 없습니다: {missing_text}. "
                "필요한 열 이름: time_s, force_N"
            )

        for row in reader:
            try:
                time_s = float(row["time_s"] or "")
                force_n = float(row["force_N"] or "")
            except (TypeError, ValueError):
                invalid_count += 1
                continue

            if not math.isfinite(time_s) or not math.isfinite(force_n):
                invalid_count += 1
                continue

            data.append({"time_s": time_s, "force_N": force_n})

    if not data:
        raise ValueError("유효한 데이터가 없습니다.")

    return data, invalid_count


class LoadAnalyzerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Load Analyzer")
        self.root.geometry("900x650")
        self.root.minsize(700, 500)

        self.file_path = tk.StringVar()
        self.valid_count = tk.StringVar(value="유효 데이터 수: -")
        self.section_type = tk.StringVar(value="사각형")
        self.area_text = tk.StringVar(value="단면적 A: - mm²")
        self.max_stress_text = tk.StringVar(value="최대 응력: - | 해당 시간: -")
        self.data: list[dict[str, float]] = []
        self.dimension_vars: dict[str, tk.StringVar] = {}
        self.dimension_frame: ttk.Frame | None = None
        self.analysis_is_current = False

        self._build_widgets()

    def _build_widgets(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        top_panel = ttk.Frame(self.root, padding=10)
        top_panel.grid(row=0, column=0, sticky="ew")
        top_panel.columnconfigure(1, weight=1)

        browse_button = ttk.Button(
            top_panel,
            text="CSV 찾아보기",
            command=self._select_csv,
        )
        browse_button.grid(row=0, column=0, padx=(0, 8))

        path_entry = ttk.Entry(
            top_panel,
            textvariable=self.file_path,
            state="readonly",
        )
        path_entry.grid(row=0, column=1, sticky="ew")

        count_label = ttk.Label(top_panel, textvariable=self.valid_count)
        count_label.grid(row=0, column=2, padx=(12, 0))

        section_label = ttk.Label(top_panel, text="단면 종류")
        section_label.grid(row=1, column=0, pady=(10, 0), sticky="w")

        section_menu = ttk.Combobox(
            top_panel,
            textvariable=self.section_type,
            values=("사각형", "원형봉", "원형관", "사각형관", "H형강"),
            state="readonly",
            width=10,
        )
        section_menu.grid(row=1, column=1, pady=(10, 0), sticky="w")
        section_menu.bind("<<ComboboxSelected>>", self._on_section_changed)

        self.dimension_frame = ttk.Frame(top_panel)
        self.dimension_frame.grid(
            row=2,
            column=0,
            columnspan=6,
            pady=(8, 0),
            sticky="w",
        )

        area_label = ttk.Label(top_panel, textvariable=self.area_text)
        area_label.grid(row=3, column=0, padx=(0, 16), pady=(8, 0), sticky="w")

        analyze_button = ttk.Button(
            top_panel,
            text="분석",
            command=self._analyze,
        )
        analyze_button.grid(row=3, column=1, padx=(16, 0), pady=(8, 0), sticky="w")

        result_label = ttk.Label(top_panel, textvariable=self.max_stress_text)
        result_label.grid(row=4, column=0, columnspan=6, pady=(10, 0), sticky="w")

        self._on_section_changed()

        graph_panel = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        graph_panel.grid(row=2, column=0, sticky="nsew")
        graph_panel.rowconfigure(0, weight=1)
        graph_panel.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(7, 4), dpi=100)
        self.axis = self.figure.add_subplot(111)
        self.axis.set_xlabel("Time (s)")
        self.axis.set_ylabel("Stress (MPa)")
        self.axis.grid(True, alpha=0.3)
        self.figure.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_panel)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.canvas.draw()

    def _select_csv(self) -> None:
        selected_file = filedialog.askopenfilename(
            title="CSV 파일 선택",
            filetypes=(
                ("CSV files", "*.csv"),
                ("All files", "*.*"),
            ),
        )
        if not selected_file:
            return

        self.file_path.set(selected_file)
        try:
            data, invalid_count = read_load_data(Path(selected_file))
        except (OSError, ValueError) as error:
            self.data = []
            self.valid_count.set("유효 데이터 수: -")
            self.max_stress_text.set("최대 응력: - | 해당 시간: -")
            self._clear_graph()
            messagebox.showerror("CSV 읽기 오류", str(error))
            return

        self.data = data
        self.valid_count.set(
            f"유효 데이터 수: {len(data)}개 | 제외 데이터 수: {invalid_count}개"
        )
        self.analysis_is_current = False
        self.max_stress_text.set("최대 응력: - | 해당 시간: -")
        self._clear_graph()

    def _on_section_changed(self, _event: tk.Event | None = None) -> None:
        if self.dimension_frame is None:
            return

        if _event is not None:
            self._invalidate_analysis()

        for child in self.dimension_frame.winfo_children():
            child.destroy()

        dimension_labels = {
            "사각형": (("b", "폭 b (mm)"), ("h", "높이 h (mm)")),
            "원형봉": (("d", "지름 d (mm)"),),
            "원형관": (("D", "외경 D (mm)"), ("t", "두께 t (mm)")),
            "사각형관": (
                ("B", "외측 폭 B (mm)"),
                ("H", "외측 높이 H (mm)"),
                ("t", "두께 t (mm)"),
            ),
            "H형강": (
                ("H", "전체 높이 H (mm)"),
                ("B", "플랜지 폭 B (mm)"),
                ("tw", "웹 두께 tw (mm)"),
                ("tf", "플랜지 두께 tf (mm)"),
            ),
        }
        self.dimension_vars = {}
        for row_index, (name, label_text) in enumerate(
            dimension_labels[self.section_type.get()]
        ):
            variable = tk.StringVar()
            self.dimension_vars[name] = variable
            ttk.Label(self.dimension_frame, text=label_text).grid(
                row=row_index,
                column=0,
                padx=(0, 8),
                pady=2,
                sticky="w",
            )
            entry = ttk.Entry(self.dimension_frame, textvariable=variable, width=12)
            entry.grid(row=row_index, column=1, pady=2, sticky="w")
            entry.bind("<KeyRelease>", self._update_area_display)

        self.area_text.set("단면적 A: - mm²")
        self._update_area_display()

    def _calculate_area(self) -> float:
        dimension_names = {
            "b": "폭 b",
            "h": "높이 h",
            "d": "지름 d",
            "D": "외경 D",
            "B": "외측 폭 B 또는 플랜지 폭 B",
            "H": "외측 높이 H 또는 전체 높이 H",
            "t": "두께 t",
            "tw": "웹 두께 tw",
            "tf": "플랜지 두께 tf",
        }
        dimensions: dict[str, float] = {}
        for name, variable in self.dimension_vars.items():
            value_text = variable.get().strip()
            if not value_text:
                raise ValueError(f"{dimension_names[name]} 값을 입력하세요.")
            try:
                value = float(value_text)
            except ValueError as error:
                raise ValueError(
                    f"{dimension_names[name]}에는 숫자를 입력하세요."
                ) from error
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{dimension_names[name]}은 0보다 커야 합니다.")
            dimensions[name] = value

        if self.section_type.get() == "사각형":
            area = dimensions["b"] * dimensions["h"]
        elif self.section_type.get() == "원형봉":
            area = math.pi * dimensions["d"] ** 2 / 4
        elif self.section_type.get() == "원형관":
            if dimensions["D"] <= 2 * dimensions["t"]:
                raise ValueError("원형관은 2t < D이어야 하며 내부 공간이 필요합니다.")
            area = math.pi * (
                dimensions["D"] ** 2
                - (dimensions["D"] - 2 * dimensions["t"]) ** 2
            ) / 4
        elif self.section_type.get() == "사각형관":
            if dimensions["B"] <= 2 * dimensions["t"] or dimensions["H"] <= 2 * dimensions["t"]:
                raise ValueError("사각형관은 2t < B, 2t < H이어야 합니다.")
            area = dimensions["B"] * dimensions["H"] - (
                dimensions["B"] - 2 * dimensions["t"]
            ) * (dimensions["H"] - 2 * dimensions["t"])
        else:
            if dimensions["H"] <= 2 * dimensions["tf"] or dimensions["tw"] >= dimensions["B"]:
                raise ValueError("H형강은 2tf < H, tw < B이어야 합니다.")
            area = (
                2 * dimensions["B"] * dimensions["tf"]
                + (dimensions["H"] - 2 * dimensions["tf"]) * dimensions["tw"]
            )

        if not math.isfinite(area) or area <= 0:
            raise ValueError
        return area

    def _update_area_display(self, _event: tk.Event | None = None) -> None:
        if _event is not None:
            self._invalidate_analysis()

        try:
            area = self._calculate_area()
        except (KeyError, ValueError):
            self.area_text.set("단면적 A: - mm²")
            return

        if self.analysis_is_current:
            self.area_text.set(f"단면적 A: {area:.2f} mm²")
        else:
            self.area_text.set(
                f"단면적 A: {area:.2f} mm² (조건변경됨: 다시분석필요)"
            )

    def _invalidate_analysis(self) -> None:
        self.analysis_is_current = False
        self.max_stress_text.set("조건변경됨: 다시분석필요")
        self._clear_graph()

    def _analyze(self) -> None:
        if not self.data:
            messagebox.showwarning("분석할 데이터 없음", "먼저 CSV 파일을 선택하세요.")
            return

        try:
            area = self._calculate_area()
        except (KeyError, ValueError) as error:
            self._invalidate_analysis()
            self.area_text.set("단면적 A: - mm²")
            messagebox.showerror("단면 치수 오류", str(error))
            return

        stress_data = [
            {
                "time_s": row["time_s"],
                "stress_MPa": row["force_N"] / area,
            }
            for row in self.data
        ]
        maximum = max(stress_data, key=lambda row: row["stress_MPa"])
        self.analysis_is_current = True
        self.area_text.set(f"단면적 A: {area:.2f} mm²")
        self.max_stress_text.set(
            f"최대 응력: {maximum['stress_MPa']:.3f} MPa | "
            f"해당 시간: {maximum['time_s']:g} s"
        )
        self._draw_stress_graph(stress_data)

    def _clear_graph(self) -> None:
        self.axis.clear()
        self.axis.set_xlabel("Time (s)")
        self.axis.set_ylabel("Stress (MPa)")
        self.axis.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()

    def _draw_stress_graph(self, data: list[dict[str, float]]) -> None:
        time_s = [row["time_s"] for row in data]
        stress_mpa = [row["stress_MPa"] for row in data]

        self.axis.clear()
        self.axis.plot(time_s, stress_mpa, marker="o")
        self.axis.set_xlabel("Time (s)")
        self.axis.set_ylabel("Stress (MPa)")
        self.axis.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()


def main() -> None:
    root = tk.Tk()
    LoadAnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
