"""Graph Lab: редактор и визуализатор графов (один файл, только стандартная библиотека).

Запуск: python graph_lab.py
"""
from __future__ import annotations

import csv
import io
import json
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ======================================================================
# МОДЕЛЬ (логика графа, без GUI)
# ======================================================================
MAX_VERTICES = 50
HISTORY_LIMIT = 100


class GraphError(ValueError):
    """Operation is not allowed; the message is shown to the user as is."""


def _key(directed: bool, u: int, v: int) -> tuple[int, int]:
    """Identity of an edge for duplicate detection."""
    return (u, v) if directed else (min(u, v), max(u, v))


class Graph:
    def __init__(self, directed: bool = False, allow_multi: bool = False) -> None:
        self.directed = directed
        self.allow_multi = allow_multi          # loops and multiple edges
        self.positions: dict[int, tuple[float, float]] = {}
        self.edges: list[tuple[int, int]] = []  # column k of incidence matrix == edge k
        self._next_id = 1
        self._history: list[dict] = []

    # ---------- undo ----------
    def _snapshot(self) -> dict:
        return {"directed": self.directed, "allow_multi": self.allow_multi,
                "positions": dict(self.positions), "edges": list(self.edges),
                "next_id": self._next_id}

    def checkpoint(self) -> None:
        """Save current state so that undo() can return to it."""
        self._history.append(self._snapshot())
        del self._history[:-HISTORY_LIMIT]

    def undo(self) -> bool:
        if not self._history:
            return False
        s = self._history.pop()
        self.directed = s["directed"]
        self.allow_multi = s["allow_multi"]
        self.positions = s["positions"]
        self.edges = s["edges"]
        self._next_id = s["next_id"]
        return True

    # ---------- editing ----------
    @property
    def vertices(self) -> list[int]:
        return sorted(self.positions)

    def add_vertex(self, x: float, y: float) -> int:
        if len(self.positions) >= MAX_VERTICES:
            raise GraphError(f"Достигнут предел: максимум {MAX_VERTICES} вершин.")
        self.checkpoint()
        v = self._next_id
        self._next_id += 1
        self.positions[v] = (x, y)
        return v

    def remove_vertex(self, v: int) -> None:
        if v not in self.positions:
            raise GraphError("Такой вершины нет.")
        self.checkpoint()
        del self.positions[v]
        self.edges = [e for e in self.edges if v not in e]

    def has_edge(self, u: int, v: int) -> bool:
        k = _key(self.directed, u, v)
        return any(_key(self.directed, a, b) == k for a, b in self.edges)

    def add_edge(self, u: int, v: int) -> int:
        """Add edge/arc u->v. Returns its index."""
        if u not in self.positions or v not in self.positions:
            raise GraphError("Вершина не найдена.")
        if not self.allow_multi:
            if u == v:
                raise GraphError("Петли отключены. Включите «Петли и кратные рёбра».")
            if self.has_edge(u, v):
                raise GraphError("Такое ребро уже есть. Для кратных рёбер "
                                 "включите «Петли и кратные рёбра».")
        self.checkpoint()
        self.edges.append((u, v))
        return len(self.edges) - 1

    def remove_edge(self, index: int) -> None:
        if not 0 <= index < len(self.edges):
            raise GraphError("Такого ребра нет.")
        self.checkpoint()
        del self.edges[index]

    def clear(self) -> None:
        self.checkpoint()
        self.positions = {}
        self.edges = []
        self._next_id = 1

    def move_vertex(self, v: int, x: float, y: float) -> None:
        """No checkpoint: the caller makes one at the start of a drag."""
        self.positions[v] = (x, y)

    def circular_layout(self, cx: float, cy: float, radius: float) -> None:
        self.checkpoint()
        n = len(self.positions)
        for i, v in enumerate(self.vertices):
            a = -math.pi / 2 + 2 * math.pi * i / max(n, 1)
            self.positions[v] = (cx + radius * math.cos(a), cy + radius * math.sin(a))

    # ---------- graph type ----------
    def _simple_edges(self) -> list[tuple[int, int]]:
        seen, kept = set(), []
        for u, v in self.edges:
            k = _key(self.directed, u, v)
            if u == v or k in seen:
                continue
            seen.add(k)
            kept.append((u, v))
        return kept

    def nonsimple_count(self) -> int:
        """How many edges would be dropped if the graph had to be simple."""
        return len(self.edges) - len(self._simple_edges())

    def set_directed(self, flag: bool) -> int:
        """Switch type, keeping vertices/edges. Returns number of dropped edges
        (only possible in simple mode, when (1,2) and (2,1) merge into one)."""
        if flag == self.directed:
            return 0
        self.checkpoint()
        self.directed = flag
        return self._enforce_simple()

    def set_allow_multi(self, flag: bool) -> int:
        if flag == self.allow_multi:
            return 0
        self.checkpoint()
        self.allow_multi = flag
        return self._enforce_simple()

    def _enforce_simple(self) -> int:
        if self.allow_multi:
            return 0
        kept = self._simple_edges()
        removed = len(self.edges) - len(kept)
        self.edges = kept
        return removed

    # ---------- degrees and handshake lemma ----------
    def degrees(self) -> dict[int, int]:
        """deg(v); a loop gives 2. For a digraph: in + out."""
        d = {v: 0 for v in self.positions}
        for u, v in self.edges:
            d[u] += 1
            d[v] += 1
        return d

    def out_degrees(self) -> dict[int, int]:
        d = {v: 0 for v in self.positions}
        for u, _ in self.edges:
            d[u] += 1
        return d

    def in_degrees(self) -> dict[int, int]:
        d = {v: 0 for v in self.positions}
        for _, v in self.edges:
            d[v] += 1
        return d

    def degree_sum(self) -> int:
        return sum(self.degrees().values())

    def lemma_holds(self) -> bool:
        m = len(self.edges)
        if self.directed:
            return sum(self.out_degrees().values()) == m == sum(self.in_degrees().values())
        return self.degree_sum() == 2 * m

    def odd_vertices(self) -> list[int]:
        return [v for v, d in sorted(self.degrees().items()) if d % 2]

    # ---------- matrices ----------
    def adjacency_matrix(self) -> list[list[int]]:
        """Undirected: symmetric, loop gives 2 on the diagonal (row sum = deg).
        Directed: a[i][j] = number of arcs i->j."""
        idx = {v: i for i, v in enumerate(self.vertices)}
        n = len(idx)
        m = [[0] * n for _ in range(n)]
        for u, v in self.edges:
            i, j = idx[u], idx[v]
            if self.directed:
                m[i][j] += 1
            elif i == j:
                m[i][i] += 2
            else:
                m[i][j] += 1
                m[j][i] += 1
        return m

    def incidence_matrix(self) -> list[list[int]]:
        """|V| x |E|. Undirected: 1 for both ends (a loop gives 2).
        Directed: +1 at the tail, -1 at the head (a loop gives 0)."""
        idx = {v: i for i, v in enumerate(self.vertices)}
        m = [[0] * len(self.edges) for _ in idx]
        for k, (u, v) in enumerate(self.edges):
            i, j = idx[u], idx[v]
            if self.directed:
                if i != j:
                    m[i][k] = 1
                    m[j][k] = -1
            elif i == j:
                m[i][k] = 2
            else:
                m[i][k] = m[j][k] = 1
        return m

    def edges_between(self, a: int, b: int) -> list[int]:
        """Indexes of edges a-b (or arcs a->b for a digraph); loops if a == b."""
        out = []
        for k, (u, v) in enumerate(self.edges):
            if (u, v) == (a, b) or (not self.directed and (u, v) == (b, a)):
                out.append(k)
        return out

    # ---------- JSON ----------
    def to_dict(self) -> dict:
        return {"directed": self.directed, "allow_multi": self.allow_multi,
                "vertices": [{"id": v, "x": x, "y": y}
                             for v, (x, y) in sorted(self.positions.items())],
                "edges": [list(e) for e in self.edges]}

    def load_dict(self, data: dict) -> None:
        try:
            directed = bool(data["directed"])
            allow_multi = bool(data.get("allow_multi", False))
            positions = {int(v["id"]): (float(v["x"]), float(v["y"]))
                         for v in data["vertices"]}
            edges = [(int(a), int(b)) for a, b in data["edges"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise GraphError("Некорректный файл графа.") from exc
        if len(positions) > MAX_VERTICES:
            raise GraphError(f"В графе больше {MAX_VERTICES} вершин.")
        seen = set()
        for u, v in edges:
            if u not in positions or v not in positions:
                raise GraphError("Ребро ссылается на несуществующую вершину.")
            k = _key(directed, u, v)
            if not allow_multi and (u == v or k in seen):
                raise GraphError("Файл содержит петли/кратные рёбра, но они отключены.")
            seen.add(k)
        self.directed, self.allow_multi = directed, allow_multi
        self.positions, self.edges = positions, edges
        self._next_id = max(positions, default=0) + 1
        self._history = []

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def load_json(self, text: str) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GraphError("Файл не является корректным JSON.") from exc
        if not isinstance(data, dict):
            raise GraphError("Некорректный файл графа.")
        self.load_dict(data)


def matrix_to_csv(matrix: list[list[int]], row_labels, col_labels) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([""] + [str(c) for c in col_labels])
    for label, row in zip(row_labels, matrix):
        w.writerow([str(label)] + row)
    return buf.getvalue()


# ======================================================================
# ИНТЕРФЕЙС (Tkinter)
# ======================================================================
R = 20                      # vertex radius
MIN_DIST = 2 * R + 5        # minimal distance between vertex centres

MODE_HINTS = {
    "vertex": "Клик по пустому месту — добавить вершину.",
    "edge": "Выберите две вершины. У орграфа первая — начало дуги.",
    "delete": "Клик по вершине или ребру — удалить.",
    "move": "Перетаскивайте вершины. Клик выделяет вершину/ребро, Del удаляет.",
}


def dist_to_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class MatrixView(ttk.Frame):
    """Scrollable matrix drawn on a canvas; clicking a cell calls on_cell(row, col)."""
    CW, CH, HW = 34, 24, 42

    def __init__(self, master, on_cell):
        super().__init__(master)
        self.on_cell = on_cell
        self.matrix, self.rows, self.cols, self.selected = [], [], [], None
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        vs = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self._click)

    def set_data(self, matrix, row_labels, col_labels):
        self.matrix, self.rows, self.cols, self.selected = matrix, row_labels, col_labels, None
        self._draw()

    def _draw(self):
        c, CW, CH, HW = self.canvas, self.CW, self.CH, self.HW
        c.delete("all")
        n, m = len(self.rows), len(self.cols)
        width, height = HW + m * CW, CH * (n + 1)
        for j, lab in enumerate(self.cols):
            c.create_text(HW + j * CW + CW / 2, CH / 2, text=lab, font=("TkDefaultFont", 9, "bold"))
        for i, lab in enumerate(self.rows):
            c.create_text(HW / 2, CH * (i + 1) + CH / 2, text=lab, font=("TkDefaultFont", 9, "bold"))
        for i, row in enumerate(self.matrix):
            for j, val in enumerate(row):
                c.create_text(HW + j * CW + CW / 2, CH * (i + 1) + CH / 2, text=str(val),
                              fill="#aaaaaa" if val == 0 else "black")
        for i in range(n + 2):
            c.create_line(0, i * CH, width, i * CH, fill="#dddddd")
        for j in range(m + 1):
            c.create_line(HW + j * CW, 0, HW + j * CW, height, fill="#dddddd")
        c.create_line(HW, 0, HW, height, fill="#888888")
        c.create_line(0, CH, width, CH, fill="#888888")
        if self.selected:
            i, j = self.selected
            c.create_rectangle(HW + j * CW, CH * (i + 1), HW + (j + 1) * CW, CH * (i + 2),
                               outline="red", width=2)
        c.configure(scrollregion=(0, 0, width, height))

    def _click(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        j, i = int((x - self.HW) // self.CW), int((y - self.CH) // self.CH)
        if 0 <= i < len(self.rows) and 0 <= j < len(self.cols):
            self.selected = (i, j)
            self._draw()
            self.on_cell(i, j)

    def to_csv(self) -> str:
        return matrix_to_csv(self.matrix, self.rows, self.cols)


class GraphApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Graph Lab")
        root.geometry("1250x720")
        self.g = Graph()
        self.mode = "vertex"
        self.pending = None          # first vertex of an edge being created
        self.sel_vertex = None
        self.sel_edge = None
        self.hl_edges: set[int] = set()
        self.hl_vertices: set[int] = set()
        self.drag = None
        self.edge_pts: dict[int, list[tuple[float, float]]] = {}
        self._build_ui()
        self.changed()

    # ------------------------------------------------------------ UI layout
    def _build_ui(self):
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left, right = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=2)

        bar = ttk.Frame(left)
        bar.pack(fill="x", padx=4, pady=2)
        self.mode_var = tk.StringVar(value="vertex")
        for text, val in [("Вершина", "vertex"), ("Ребро", "edge"),
                          ("Удалить", "delete"), ("Переместить", "move")]:
            ttk.Radiobutton(bar, text=text, value=val, variable=self.mode_var,
                            style="Toolbutton", command=self.on_mode).pack(side="left", padx=2)

        bar2 = ttk.Frame(left)
        bar2.pack(fill="x", padx=4, pady=2)
        self.directed_var = tk.BooleanVar(value=False)
        self.multi_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(bar2, text="Неориентированный", value=False, variable=self.directed_var,
                        command=self.on_directed).pack(side="left")
        ttk.Radiobutton(bar2, text="Ориентированный", value=True, variable=self.directed_var,
                        command=self.on_directed).pack(side="left", padx=(6, 12))
        ttk.Checkbutton(bar2, text="Петли и кратные рёбра", variable=self.multi_var,
                        command=self.on_multi).pack(side="left")

        bar3 = ttk.Frame(left)
        bar3.pack(fill="x", padx=4, pady=2)
        for text, cmd in [("Отмена (Ctrl+Z)", self.on_undo), ("Очистить всё", self.on_clear),
                          ("Разложить автоматически", self.on_layout),
                          ("Сохранить JSON", self.on_save), ("Загрузить JSON", self.on_load)]:
            ttk.Button(bar3, text=text, command=cmd).pack(side="left", padx=2)

        self.canvas = tk.Canvas(left, bg="white", highlightthickness=1, highlightbackground="#999")
        self.canvas.pack(fill="both", expand=True, padx=4)
        self.status = tk.StringVar(value=MODE_HINTS["vertex"])
        ttk.Label(left, textvariable=self.status, anchor="w").pack(fill="x", padx=6, pady=3)

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Delete>", self.on_delete_key)
        self.root.bind("<Control-z>", lambda e: self.on_undo())

        tabs = ttk.Notebook(right)
        tabs.pack(fill="both", expand=True, padx=4, pady=4)

        # tab 1: degrees and lemma
        t1 = ttk.Frame(tabs)
        tabs.add(t1, text="Степени и лемма")
        self.summary = tk.Label(t1, justify="left", anchor="w", font=("TkDefaultFont", 11))
        self.summary.pack(fill="x", padx=8, pady=(8, 4))
        self.lemma_lbl = tk.Label(t1, font=("TkDefaultFont", 11, "bold"), fg="white", pady=4)
        self.lemma_lbl.pack(fill="x", padx=8, pady=4)
        self.odd_lbl = tk.Label(t1, justify="left", anchor="w", wraplength=380)
        self.odd_lbl.pack(fill="x", padx=8, pady=4)
        self.tree = ttk.Treeview(t1, show="headings", height=15)
        self.tree.tag_configure("odd", background="#fff3e0")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        # tabs 2 and 3: matrices
        t2, t3 = ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(t2, text="Смежность")
        tabs.add(t3, text="Инцидентность")
        self.adj_view = MatrixView(t2, self.on_adj_cell)
        self.inc_view = MatrixView(t3, self.on_inc_cell)
        for tab, view in ((t2, self.adj_view), (t3, self.inc_view)):
            ttk.Button(tab, text="Копировать как CSV",
                       command=lambda v=view: self.copy_csv(v)).pack(side="bottom", anchor="e", padx=6, pady=4)
            view.pack(fill="both", expand=True)

    # ------------------------------------------------------------ refresh
    def changed(self):
        """Call after any change of the model."""
        g = self.g
        if self.sel_vertex not in g.positions:
            self.sel_vertex = None
        if self.sel_edge is not None and self.sel_edge >= len(g.edges):
            self.sel_edge = None
        if self.pending not in g.positions:
            self.pending = None
        self.hl_edges, self.hl_vertices = set(), set()
        self.redraw()
        self.refresh_panels()

    def refresh_panels(self):
        g = self.g
        verts = g.vertices
        n, m = len(verts), len(g.edges)
        deg = g.degrees()
        self.tree.delete(*self.tree.get_children())
        if g.directed:
            outd, ind = g.out_degrees(), g.in_degrees()
            cols, heads = ("v", "p", "m", "t"), ("Вершина", "deg+", "deg-", "deg")
            rows = [(v, outd[v], ind[v], deg[v]) for v in verts]
            so, si = sum(outd.values()), sum(ind.values())
            self.summary.config(text=f"|V| = {n}     |A| = {m}\n"
                                     f"Σ deg+ = {so}     Σ deg- = {si}     |A| = {m}")
        else:
            cols, heads = ("v", "d"), ("Вершина", "deg")
            rows = [(v, deg[v]) for v in verts]
            self.summary.config(text=f"|V| = {n}     |E| = {m}\n"
                                     f"Σ deg(v) = {g.degree_sum()}     2|E| = {2 * m}")
        self.tree["columns"] = cols
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=80, anchor="center")
        for row in rows:
            self.tree.insert("", "end", values=row, tags=("odd",) if deg[row[0]] % 2 else ())
        ok = g.lemma_holds()
        self.lemma_lbl.config(text="Лемма о рукопожатиях: выполняется" if ok
                              else "Лемма о рукопожатиях: нарушено",
                              bg="#2e7d32" if ok else "#c62828")
        odd = g.odd_vertices()
        listed = f" ({', '.join(map(str, odd))})" if odd else ""
        self.odd_lbl.config(text=f"Вершин нечётной степени: {len(odd)}{listed} — "
                                 f"{'чётно' if len(odd) % 2 == 0 else 'нечётно'}")
        self.adj_view.set_data(g.adjacency_matrix(), [str(v) for v in verts], [str(v) for v in verts])
        self.inc_view.set_data(g.incidence_matrix(), [str(v) for v in verts],
                               [f"e{k + 1}" for k in range(m)])

    # ------------------------------------------------------------ drawing
    def vertex_at(self, x, y):
        for v, (vx, vy) in self.g.positions.items():
            if (x - vx) ** 2 + (y - vy) ** 2 <= R * R:
                return v
        return None

    def edge_at(self, x, y):
        for k, pts in self.edge_pts.items():
            for a, b in zip(pts, pts[1:]):
                if dist_to_segment(x, y, *a, *b) <= 6:
                    return k
        return None

    def _compute_edge_points(self):
        """Polyline for each edge. Parallel edges become arcs, loops become circles."""
        g = self.g
        groups: dict[tuple[int, int], list[int]] = {}
        for k, (u, v) in enumerate(g.edges):
            groups.setdefault((min(u, v), max(u, v)), []).append(k)
        self.edge_pts = {}
        for (a, b), ks in groups.items():
            for idx, k in enumerate(ks):
                u, v = g.edges[k]
                if u == v:
                    self.edge_pts[k] = self._loop_points(*g.positions[u], idx, len(ks))
                else:
                    self.edge_pts[k] = self._edge_points(u, v, a, b, idx, len(ks))

    @staticmethod
    def _loop_points(x, y, idx, cnt):
        ang = -math.pi / 2 + idx * 2 * math.pi / cnt
        rl = 0.8 * R
        cx, cy = x + R * math.cos(ang), y + R * math.sin(ang)
        theta = math.acos(rl / (2 * R))           # where the loop circle meets the vertex
        start, end = ang + math.pi + theta, ang + 3 * math.pi - theta
        return [(cx + rl * math.cos(start + (end - start) * i / 24),
                 cy + rl * math.sin(start + (end - start) * i / 24)) for i in range(25)]

    def _edge_points(self, u, v, a, b, idx, cnt):
        pos = self.g.positions
        (x1, y1), (x2, y2) = pos[u], pos[v]
        off = 0 if cnt == 1 else (idx - (cnt - 1) / 2) * 28
        (ax, ay), (bx, by) = pos[a], pos[b]
        el = math.hypot(bx - ax, by - ay) or 1
        px, py = -(by - ay) / el, (bx - ax) / el   # same normal for all edges of a pair
        cx, cy = (x1 + x2) / 2 + px * 2 * off, (y1 + y2) / 2 + py * 2 * off

        def shorten(x, y):
            d = math.hypot(cx - x, cy - y) or 1
            return x + R * (cx - x) / d, y + R * (cy - y) / d

        p0, p1 = shorten(x1, y1), shorten(x2, y2)
        if off == 0:
            return [p0, p1]
        pts = []
        for i in range(17):
            t = i / 16
            pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * cx + t * t * p1[0],
                        (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * cy + t * t * p1[1]))
        return pts

    def redraw(self):
        c, g = self.canvas, self.g
        c.delete("all")
        self._compute_edge_points()
        for k, pts in self.edge_pts.items():
            color, width = "black", 2
            if k == self.sel_edge:
                color, width = "#1565c0", 3
            if k in self.hl_edges:
                color, width = "#e53935", 3
            c.create_line(*[p for pt in pts for p in pt], fill=color, width=width,
                          arrow=tk.LAST if g.directed else None, arrowshape=(12, 14, 5))
            mx, my = pts[len(pts) // 2] if len(pts) > 2 else (
                (pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
            t = c.create_text(mx, my, text=f"e{k + 1}", fill="#6a1b9a", font=("TkDefaultFont", 9, "bold"))
            c.create_rectangle(c.bbox(t), fill="white", outline="")
            c.tag_raise(t)
        deg = g.degrees()
        outd, ind = (g.out_degrees(), g.in_degrees()) if g.directed else ({}, {})
        for v, (x, y) in g.positions.items():
            fill = "lightblue"
            if v in self.hl_vertices:
                fill = "#ffcdd2"
            if v == self.sel_vertex:
                fill = "#b39ddb"
            if v == self.pending:
                fill = "orange"
            c.create_oval(x - R, y - R, x + R, y + R, fill=fill, outline="black", width=2)
            c.create_text(x, y, text=str(v), font=("TkDefaultFont", 10, "bold"))
            label = f"+{outd[v]}/-{ind[v]}" if g.directed else str(deg[v])
            c.create_text(x + R + 2, y - R - 2, text=label, anchor="w", fill="#2e7d32",
                          font=("TkDefaultFont", 9))

    # ------------------------------------------------------------ mouse
    def on_press(self, event):
        g, x, y = self.g, event.x, event.y
        v = self.vertex_at(x, y)
        try:
            if self.mode == "vertex":
                if v is not None:
                    return
                if any((x - vx) ** 2 + (y - vy) ** 2 < MIN_DIST ** 2
                       for vx, vy in g.positions.values()):
                    self.status.set("Вершины слишком близко.")
                    return
                g.add_vertex(x, y)
                self.changed()
            elif self.mode == "edge":
                if v is None:
                    self.pending = None
                elif self.pending is None:
                    self.pending = v
                else:
                    u, self.pending = self.pending, None
                    g.add_edge(u, v)
                    self.changed()
                    return
                self.redraw()
            elif self.mode == "delete":
                if v is not None:
                    g.remove_vertex(v)
                    self.changed()
                else:
                    k = self.edge_at(x, y)
                    if k is not None:
                        g.remove_edge(k)
                        self.changed()
            elif self.mode == "move":
                self.sel_vertex, self.sel_edge = v, None
                if v is None:
                    self.sel_edge = self.edge_at(x, y)
                self.drag, self.drag_started = v, False
                self.redraw()
        except GraphError as exc:
            self.pending = None
            self.redraw()
            messagebox.showinfo("Graph Lab", str(exc))

    def on_drag(self, event):
        if self.mode != "move" or self.drag is None:
            return
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        x, y = min(max(event.x, R), w - R), min(max(event.y, R), h - R)
        for v, (vx, vy) in self.g.positions.items():
            if v != self.drag and (x - vx) ** 2 + (y - vy) ** 2 < MIN_DIST ** 2:
                return
        if not self.drag_started:
            self.g.checkpoint()           # one undo step per drag
            self.drag_started = True
        self.g.move_vertex(self.drag, x, y)
        self.redraw()

    def on_release(self, event):
        self.drag = None

    # ------------------------------------------------------------ commands
    def on_mode(self):
        self.mode = self.mode_var.get()
        self.pending = self.sel_vertex = self.sel_edge = None
        self.status.set(MODE_HINTS[self.mode])
        self.redraw()

    def on_delete_key(self, event=None):
        try:
            if self.sel_vertex is not None:
                self.g.remove_vertex(self.sel_vertex)
            elif self.sel_edge is not None:
                self.g.remove_edge(self.sel_edge)
            else:
                return
        except GraphError as exc:
            messagebox.showinfo("Graph Lab", str(exc))
        self.sel_vertex = self.sel_edge = None
        self.changed()

    def sync_controls(self):
        self.directed_var.set(self.g.directed)
        self.multi_var.set(self.g.allow_multi)

    def on_undo(self):
        if not self.g.undo():
            self.status.set("Нечего отменять.")
            return
        self.sync_controls()
        self.changed()

    def on_clear(self):
        self.g.clear()
        self.changed()

    def on_layout(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.g.circular_layout(w / 2, h / 2, max(min(w, h) / 2 - R - 30, 40))
        self.redraw()

    def on_directed(self):
        removed = self.g.set_directed(self.directed_var.get())
        if removed:
            messagebox.showinfo("Graph Lab", f"В простом графе объединено/удалено рёбер: {removed}. "
                                             "Ctrl+Z вернёт всё обратно.")
        self.changed()

    def on_multi(self):
        flag = self.multi_var.get()
        if not flag and self.g.nonsimple_count() and not messagebox.askyesno(
                "Graph Lab", f"Будет удалено петель и кратных рёбер: {self.g.nonsimple_count()}. Продолжить?"):
            self.multi_var.set(True)
            return
        self.g.set_allow_multi(flag)
        self.changed()

    def on_save(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.g.to_json())
            except OSError as exc:
                messagebox.showerror("Graph Lab", str(exc))

    def on_load(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                self.g.load_json(f.read())
        except (OSError, GraphError) as exc:
            messagebox.showerror("Graph Lab", str(exc))
            return
        self.sync_controls()
        self.changed()

    # ------------------------------------------------------------ matrix interaction
    def on_adj_cell(self, i, j):
        vs = self.g.vertices
        a, b = vs[i], vs[j]
        self.hl_edges = set(self.g.edges_between(a, b))
        self.hl_vertices = {a, b}
        self.status.set(f"Рёбра {a}→{b}: " + (", ".join(f"e{k + 1}" for k in sorted(self.hl_edges))
                                              if self.hl_edges else "нет"))
        self.redraw()

    def on_inc_cell(self, i, k):
        self.hl_edges = {k}
        self.hl_vertices = {self.g.vertices[i]}
        self.status.set(f"Ребро e{k + 1}, вершина {self.g.vertices[i]}")
        self.redraw()

    def copy_csv(self, view: MatrixView):
        self.root.clipboard_clear()
        self.root.clipboard_append(view.to_csv())
        self.status.set("Матрица скопирована в буфер (CSV).")


def main() -> None:
    root = tk.Tk()
    GraphApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
