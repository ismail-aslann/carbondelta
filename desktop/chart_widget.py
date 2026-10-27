"""24 saatlik karbon yoğunluğu + makine yükü grafiği (matplotlib QtAgg)."""
from __future__ import annotations

import warnings

import matplotlib

matplotlib.use("QtAgg")
# Gizli sayfadayken (başlangıç ekranı açıkken) grafik sıfır boyutlu olabilir; zararsız uyarı.
warnings.filterwarnings("ignore", message="constrained_layout not applied")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from PySide6.QtGui import QCursor  # noqa: E402
from PySide6.QtWidgets import QToolTip  # noqa: E402

from desktop import fmt, theme  # noqa: E402

CI_COLOR = theme.CI_COLOR
LOAD_COLOR = "#a9bfd3"
SOURCE_COLOR = "#7f8a96"
GOOD_COLOR = "#2e9d4f"
MOVED_COLOR = "#2e9d4f"   # hedef pencereye eklenen yük
BAD_COLOR = "#d03c3c"
NEUTRAL_COLOR = "#e0a030"
RESTRICTED_COLOR = "#b04040"
AXIS_TEXT = "#5b6776"


class ChartWidget(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(7, 3.2), dpi=100, layout="constrained", facecolor="white")
        super().__init__(self.figure)
        self.setParent(parent)
        self.setMinimumHeight(190)
        self.ax_ci = self.figure.add_subplot(111)
        self.ax_load = self.ax_ci.twinx()
        self._ci: list[float] = []
        self._load: list[float] = []
        self._ci_label = "tCO2"
        self._hover_hour: int | None = None
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("axes_leave_event", lambda _e: QToolTip.hideText())

    def update_chart(self, ci: list[float], load: list[float], s: int, L: int, t: int,
                     restricted: set[int], status: str, delta_pct: float | None,
                     ci_label: str, p: float = 1.0) -> None:
        self._ci, self._load, self._ci_label = list(ci), list(load), ci_label
        # Kaydırma oranı grafikte görünsün: standart penceredeki yükün p kadarı hedef pencereye taşınır.
        out_ = [0.0] * 24
        in_ = [0.0] * 24
        in_range = L >= 1 and 0 <= s and s + L <= 24 and 0 <= t and t + L <= 24
        shift_drawn = in_range and status in ("ok", "same_window") and s != t and p > 0
        if shift_drawn:
            for i in range(L):
                e = p * load[s + i]
                out_[s + i] += e
                in_[t + i] += e
        self._out, self._in = out_, in_
        ax, ax2 = self.ax_ci, self.ax_load
        ax.clear()
        ax2.clear()
        centers = [h + 0.5 for h in range(24)]

        # Yük: sağ eksen. Kalan yük soluk, hedefe eklenen yük yeşil, standarttan taşınan kısım kesikli çerçeve.
        remain = [load[h] - out_[h] for h in range(24)]
        ax2.bar(centers, remain, width=0.8, color=LOAD_COLOR, alpha=0.55, zorder=1)
        if shift_drawn:
            ax2.bar(centers, in_, bottom=remain, width=0.8, color=MOVED_COLOR, alpha=0.75, zorder=2)
            hs = [h for h in range(24) if out_[h] > 0]   # yalnızca taşınan saatlerde kesikli çerçeve
            ax2.bar([centers[h] for h in hs], [out_[h] for h in hs], bottom=[remain[h] + in_[h] for h in hs],
                    width=0.8, facecolor="none", edgecolor="#5b6776", linestyle=(0, (3, 2)), linewidth=1.0,
                    zorder=2)
        ax2.yaxis.tick_right()
        ax2.yaxis.set_label_position("right")
        ax2.set_ylabel("Yük (kWh)", color=AXIS_TEXT, fontsize=9)
        ax2.tick_params(axis="y", colors=AXIS_TEXT, labelsize=8, length=0)
        top = max(max(remain[h] + in_[h] + out_[h] for h in range(24)), 1.0)
        ax2.set_ylim(0, top * 1.45)
        if shift_drawn:
            moved = sum(in_)
            y = top * 1.18
            ax2.annotate("", xy=(t + L / 2, y), xytext=(s + L / 2, y),
                         arrowprops=dict(arrowstyle="-|>", color=MOVED_COLOR, lw=1.6, shrinkA=2, shrinkB=2),
                         zorder=7)
            overlap = abs(t - s) < L
            ax2.text(max(s, t) + L + 0.2 if overlap else (s + t + L) / 2, y * (0.98 if overlap else 1.04),
                     f"{fmt.num(moved, 1)} kWh · %{fmt.num(p * 100, 0)}",
                     ha="left" if overlap else "center", va="center" if overlap else "bottom", fontsize=8, fontweight="bold", color=MOVED_COLOR,
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.9), zorder=8)

        # Karbon yoğunluğu: sol eksen, çizgi (çubukların önünde)
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)
        ax.plot(centers, ci, color=CI_COLOR, linewidth=2.2, marker="o", markersize=3.2, zorder=5)
        ax.set_ylabel(f"Karbon yoğunluğu ({ci_label}/MWh)", color=CI_COLOR, fontsize=9)
        ax.tick_params(axis="y", colors=CI_COLOR, labelsize=8, length=0)
        lo, hi = min(ci), max(ci)
        pad = max((hi - lo) * 0.15, 0.01)
        ax.set_ylim(lo - pad, hi + pad * 2.2)  # üstte pencere etiketleri için boşluk

        legend = [
            Patch(facecolor=LOAD_COLOR, alpha=0.55, label="Makine yükü"),
            Patch(facecolor=CI_COLOR, label="Karbon yoğunluğu"),
        ]
        if shift_drawn:
            legend += [Patch(facecolor="none", edgecolor="#5b6776", linestyle="--", label="Taşınan"),
                       Patch(facecolor=MOVED_COLOR, alpha=0.75, label="Hedefe eklenen")]
        label_box = dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none", alpha=0.85)

        if in_range and status != "non_shiftable":
            ax.axvspan(s, s + L, color=SOURCE_COLOR, alpha=0.18, zorder=0, linewidth=0)
            ax.text(s + L / 2, 0.985, "Standart", transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontsize=8, fontweight="bold", color="#4a5562",
                    bbox=label_box, zorder=6)
            if s != t:
                if status == "ok" and delta_pct is not None:
                    color = GOOD_COLOR if delta_pct <= 0 else BAD_COLOR
                elif status == "restricted_conflict":
                    color = BAD_COLOR
                else:
                    color = NEUTRAL_COLOR
                ax.axvspan(t, t + L, color=color, alpha=0.20, zorder=0, linewidth=0)
                ax.text(t + L / 2, 0.985 if abs(t - s) >= L else 0.90, "Seçilen", transform=ax.get_xaxis_transform(),
                        ha="center", va="top", fontsize=8, fontweight="bold", color=color,
                        bbox=label_box, zorder=6)

        for h in sorted(restricted):
            ax.axvspan(h, h + 1, facecolor="none", edgecolor=RESTRICTED_COLOR,
                       hatch="///", linewidth=0, alpha=0.55, zorder=0)
        if restricted:
            legend.append(Patch(facecolor="none", edgecolor=RESTRICTED_COLOR, hatch="///",
                                label="Kısıtlı saat"))

        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 2))
        ax.set_xticklabels([f"{h:02d}" for h in range(0, 25, 2)], fontsize=8, color=AXIS_TEXT)
        ax.tick_params(axis="x", length=0)
        ax.set_xlabel("Saat", fontsize=9, color=AXIS_TEXT)
        ax.grid(axis="y", color="#e9edf1", linewidth=0.8)
        ax.set_axisbelow(True)
        for a in (ax, ax2):
            for side in ("top", "right", "left"):
                a.spines[side].set_visible(False)
            a.spines["bottom"].set_color("#cfd6de")
        ax.legend(handles=legend, loc="lower left", bbox_to_anchor=(0.0, 1.0),
                  ncol=len(legend), fontsize=8, frameon=False, handlelength=1.4,
                  columnspacing=1.2, borderaxespad=0.2)
        self.draw_idle()

    def _on_move(self, event) -> None:
        if event.inaxes is None or event.xdata is None or not self._ci:
            QToolTip.hideText()
            self._hover_hour = None
            return
        h = int(event.xdata)
        if not 0 <= h < 24:
            return
        if h == self._hover_hour and QToolTip.isVisible():
            return
        self._hover_hour = h
        QToolTip.showText(
            QCursor.pos(),
            f"<b>{fmt.window(h, 1)}</b><br>"
            f"Karbon yoğunluğu: {fmt.num(self._ci[h], 3)} {self._ci_label}/MWh<br>"
            f"Yük: {fmt.num(self._load[h])} kWh"
            + (f"<br>Taşınan: −{fmt.num(self._out[h])} kWh" if getattr(self, "_out", None) and self._out[h] else "")
            + (f"<br>Eklenen: +{fmt.num(self._in[h])} kWh" if getattr(self, "_in", None) and self._in[h] else ""),
            self,
        )
