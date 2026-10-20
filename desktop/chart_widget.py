"""24 saatlik karbon yoğunluğu + makine yükü grafiği (matplotlib QtAgg)."""
from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

CI_COLOR = "#1f4e79"
LOAD_COLOR = "#9fb6cd"
SOURCE_COLOR = "#7f7f7f"
GOOD_COLOR = "#2e9d4f"
BAD_COLOR = "#d03c3c"
NEUTRAL_COLOR = "#e0a030"
RESTRICTED_COLOR = "#b04040"


class ChartWidget(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(7, 3.4), dpi=100, layout="constrained")
        super().__init__(self.figure)
        self.setParent(parent)
        self.setMinimumHeight(280)
        self.ax_ci = self.figure.add_subplot(111)
        self.ax_load = self.ax_ci.twinx()

    def update_chart(self, ci: list[float], load: list[float], s: int, L: int, t: int,
                     restricted: set[int], status: str, delta_pct: float | None,
                     ci_label: str) -> None:
        ax, ax2 = self.ax_ci, self.ax_load
        ax.clear()
        ax2.clear()
        centers = [h + 0.5 for h in range(24)]

        # Yük: sağ eksen, soluk çubuk
        ax2.bar(centers, load, width=0.85, color=LOAD_COLOR, alpha=0.55, zorder=1)
        ax2.yaxis.tick_right()
        ax2.yaxis.set_label_position("right")
        ax2.set_ylabel("Yük (kWh)", color="#5a7a99")
        ax2.tick_params(axis="y", colors="#5a7a99")
        ax2.set_ylim(0, max(max(load) * 1.15, 1.0))

        # Karbon yoğunluğu: sol eksen, çizgi (çubukların önünde)
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)
        ax.plot(centers, ci, color=CI_COLOR, linewidth=2.2, marker="o", markersize=3.5)
        ax.set_ylabel(f"Karbon yoğunluğu ({ci_label}/MWh)", color=CI_COLOR)
        ax.tick_params(axis="y", colors=CI_COLOR)
        lo, hi = min(ci), max(ci)
        pad = max((hi - lo) * 0.15, 0.01)
        ax.set_ylim(lo - pad, hi + pad)

        legend = [
            Patch(facecolor=LOAD_COLOR, alpha=0.55, label="Makine yükü"),
            Patch(facecolor=CI_COLOR, label="Karbon yoğunluğu"),
        ]

        in_range = L >= 1 and 0 <= s and s + L <= 24 and 0 <= t and t + L <= 24
        if in_range and status != "non_shiftable":
            ax.axvspan(s, s + L, color=SOURCE_COLOR, alpha=0.22, zorder=0)
            legend.append(Patch(facecolor=SOURCE_COLOR, alpha=0.3, label="Standart pencere"))
            if s != t:
                if status == "ok" and delta_pct is not None:
                    color = GOOD_COLOR if delta_pct <= 0 else BAD_COLOR
                elif status == "restricted_conflict":
                    color = BAD_COLOR
                else:
                    color = NEUTRAL_COLOR
                ax.axvspan(t, t + L, color=color, alpha=0.25, zorder=0)
                legend.append(Patch(facecolor=color, alpha=0.3, label="Seçilen pencere"))

        for h in sorted(restricted):
            ax.axvspan(h, h + 1, facecolor="none", edgecolor=RESTRICTED_COLOR,
                       hatch="///", linewidth=0, alpha=0.6, zorder=0)
        if restricted:
            legend.append(Patch(facecolor="none", edgecolor=RESTRICTED_COLOR, hatch="///",
                                label="Kısıtlı saat"))

        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 2))
        ax.set_xticklabels([f"{h:02d}" for h in range(0, 25, 2)], fontsize=8)
        ax.set_xlabel("Saat")
        ax.grid(axis="y", alpha=0.25)
        for a in (ax, ax2):
            a.spines["top"].set_visible(False)
        ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  ncol=len(legend), fontsize=8, frameon=False)
        self.draw_idle()
