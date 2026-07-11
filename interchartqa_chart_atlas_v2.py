import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, PathPatch
from matplotlib.path import Path
from matplotlib.colors import LinearSegmentedColormap

OUTPUT = "./tex/png/interchartqa_chart_atlas_v2.png"
SEED = 42
rng = np.random.default_rng(SEED)

# Restrained palette
NAVY = "#0F4C81"
BLUE = "#3D6F99"
STEEL = "#7E97AC"
TEAL = "#82A7A8"
LIGHT_BLUE = "#B9C8D6"
PALE_BLUE = "#DDE6ED"
LIGHT_GRAY = "#E6E9EC"
MID_GRAY = "#AAB1B8"
DARK_GRAY = "#5A626B"
WHITE = "#FFFFFF"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.edgecolor": MID_GRAY,
    "axes.linewidth": 0.7,
    "xtick.color": DARK_GRAY,
    "ytick.color": DARK_GRAY,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "savefig.facecolor": WHITE,
    "figure.facecolor": WHITE,
})

fig = plt.figure(figsize=(16, 9), dpi=180, facecolor=WHITE)

# Manual 3x4 layout for precise spacing
left_margin = 0.035
right_margin = 0.025
top_margin = 0.045
bottom_margin = 0.055
h_gap = 0.045
v_gap = 0.075
ncols, nrows = 4, 3
cell_w = (1 - left_margin - right_margin - (ncols - 1) * h_gap) / ncols
cell_h = (1 - top_margin - bottom_margin - (nrows - 1) * v_gap) / nrows

axes = []
for r in range(nrows):
    for c in range(ncols):
        x = left_margin + c * (cell_w + h_gap)
        y = 1 - top_margin - (r + 1) * cell_h - r * v_gap
        axes.append(fig.add_axes([x, y, cell_w, cell_h]))


def style_axis(ax, grid=False, xlabels=True, ylabels=True):
    ax.set_facecolor(WHITE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(MID_GRAY)
    ax.spines["bottom"].set_color(MID_GRAY)
    ax.tick_params(length=2.5, width=0.6, color=MID_GRAY)
    if not xlabels:
        ax.set_xticklabels([])
    if not ylabels:
        ax.set_yticklabels([])
    if grid:
        ax.grid(True, color=LIGHT_GRAY, linewidth=0.55, linestyle=(0, (2, 3)))
        ax.set_axisbelow(True)


def clean_panel(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_facecolor(WHITE)


# 1. Bar chart
ax = axes[0]
values = np.array([54, 76, 50, 69, 83])
x = np.arange(len(values))
ax.bar(x, values, width=0.34, color=NAVY, edgecolor=NAVY, linewidth=0)
ax.set_ylim(0, 100)
ax.set_yticks([0, 20, 40, 60, 80, 100])
ax.set_xticks(x)
ax.set_xticklabels([])
style_axis(ax)

# 2. Line chart
# Keep the original coordinate system, but use three restrained series like the reference.
ax = axes[1]
x = np.arange(1, 7)
y_primary = np.array([32, 50, 68, 61, 80, 70])
y_secondary = np.array([28, 33, 43, 50, 52, 66])
y_tertiary = np.array([18, 31, 29, 36, 31, 59])

ax.plot(
    x, y_primary,
    color="#294F6D", marker="o", markersize=4.2,
    linewidth=1.55, zorder=3
)
ax.plot(
    x, y_secondary,
    color="#D5DCE2", marker="o", markersize=4.2,
    linewidth=1.25, zorder=2
)
ax.plot(
    x, y_tertiary,
    color="#8FA5B7", marker="o", markersize=4.2,
    linewidth=1.25, zorder=2
)
ax.set_xlim(1, 6)
ax.set_ylim(0, 100)
ax.set_xticks(x)
ax.set_yticks([0, 20, 40, 60, 80, 100])
style_axis(ax, grid=True)

# 3. Scatter plot
# Keep the original coordinate system, but reproduce the reference's mixed
# circles/crosses and left-to-right grouping.
ax = axes[2]

blue_circles = np.array([
    [1.0, 20], [1.3, 42], [1.6, 58], [2.0, 32], [2.3, 48],
    [2.6, 72], [2.9, 25], [3.2, 54], [3.5, 38], [3.8, 66],
    [4.2, 31], [4.6, 76], [5.0, 48], [5.4, 62], [5.8, 84]
])

gray_circles = np.array([
    [5.6, 40], [6.2, 55], [6.6, 68], [7.0, 82], [7.4, 72],
    [7.8, 88], [8.2, 76], [8.6, 64], [9.0, 84], [9.4, 58]
])

light_crosses = np.array([
    [5.7, 23], [6.1, 34], [6.5, 29], [6.9, 44], [7.3, 18],
    [7.7, 37], [8.1, 27], [8.5, 48], [8.9, 35], [9.3, 52]
])

ax.scatter(
    blue_circles[:, 0], blue_circles[:, 1],
    s=18, color="#294F6D", alpha=0.98,
    edgecolors="none", zorder=3
)
ax.scatter(
    gray_circles[:, 0], gray_circles[:, 1],
    s=18, color="#8F989F", alpha=0.95,
    edgecolors="none", zorder=2
)
ax.scatter(
    light_crosses[:, 0], light_crosses[:, 1],
    s=28, marker="x", color="#C7CFD6",
    linewidths=1.15, alpha=0.95, zorder=2
)
ax.set_xlim(0, 10)
ax.set_ylim(0, 100)
ax.set_xticks([0, 2, 4, 6, 8, 10])
ax.set_yticks([0, 20, 40, 60, 80, 100])
style_axis(ax, grid=True)

# 4. Box plot
ax = axes[3]
data = [rng.normal(45, 13, 50), rng.normal(40, 14, 50), rng.normal(48, 12, 50), rng.normal(41, 13, 50)]
ax.boxplot(
    data,
    patch_artist=True,
    widths=0.45,
    boxprops=dict(facecolor=WHITE, edgecolor=MID_GRAY, linewidth=1.0),
    medianprops=dict(color=NAVY, linewidth=1.5),
    whiskerprops=dict(color=MID_GRAY, linewidth=0.9),
    capprops=dict(color=MID_GRAY, linewidth=0.9),
    flierprops=dict(marker="o", markerfacecolor=DARK_GRAY, markeredgecolor=DARK_GRAY, markersize=2.6),
)
ax.set_ylim(0, 100)
ax.set_xticks([])
ax.set_yticks([0, 20, 40, 60, 80, 100])
style_axis(ax)

# 5. Parallel coordinates
ax = axes[4]
dims = np.arange(5)
series = rng.uniform(0.12, 0.9, size=(8, 5))
for i, row in enumerate(series):
    color = NAVY if i in (1, 5) else (TEAL if i in (3, 6) else STEEL)
    alpha = 0.9 if i in (1, 3, 5) else 0.48
    ax.plot(dims, row, color=color, linewidth=1.0, alpha=alpha)
    ax.scatter(dims, row, s=7, color=color, alpha=alpha, zorder=3)
for d in dims:
    ax.plot([d, d], [0, 1], color=MID_GRAY, linewidth=0.8, zorder=0)
ax.set_xlim(-0.15, 4.15)
ax.set_ylim(0, 1)
ax.set_xticks([])
ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)

# 6. Stacked area chart
ax = axes[5]
x = np.arange(12)
base = np.array([11, 15, 12, 14, 18, 19, 17, 20, 18, 24, 23, 21])
layer2 = np.array([13, 16, 14, 15, 17, 18, 19, 18, 20, 19, 23, 22])
layer3 = np.array([17, 20, 17, 22, 20, 24, 23, 27, 25, 28, 30, 27])
layer4 = np.array([21, 26, 24, 28, 26, 30, 28, 31, 30, 34, 36, 32])
ax.stackplot(x, base, layer2, layer3, layer4,
             colors=[NAVY, BLUE, TEAL, LIGHT_GRAY],
             linewidth=0.65, edgecolor=WHITE, alpha=0.98)
ax.set_xlim(0, 11)
ax.set_ylim(0, 100)
ax.set_xticks([])
ax.set_yticks([])
style_axis(ax, xlabels=False, ylabels=False)

# 7. Heatmap
ax = axes[6]
heat = rng.uniform(0.05, 0.9, size=(6, 8))
heat[1, 5] = 1.0
heat[2, 4] = 0.86
heat[3, 4] = 0.92
heat[5, 2] = 0.78
cmap = LinearSegmentedColormap.from_list("quiet_blues", [WHITE, PALE_BLUE, LIGHT_BLUE, BLUE, NAVY])
ax.imshow(heat, cmap=cmap, vmin=0, vmax=1, aspect="auto")
ax.set_xticks(np.arange(-0.5, 8, 1), minor=True)
ax.set_yticks(np.arange(-0.5, 6, 1), minor=True)
ax.grid(which="minor", color=WHITE, linewidth=1.6)
ax.tick_params(which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
for s in ax.spines.values():
    s.set_visible(False)

# 8. Pie chart
ax = axes[7]
ax.pie([20, 21, 19, 20, 20],
       colors=[NAVY, TEAL, LIGHT_BLUE, MID_GRAY, LIGHT_GRAY],
       startangle=90, counterclock=False,
       wedgeprops=dict(edgecolor=WHITE, linewidth=1.2))
ax.set_aspect("equal")
clean_panel(ax)

# # 9. Calendar heatmap
# ax = axes[8]
# calendar = rng.uniform(0.05, 0.72, size=(5, 7))
# calendar[1, 5] = 0.94
# calendar[2, 3] = 0.78
# calendar[4, 0] = 0.68
# ax.imshow(calendar, cmap=cmap, vmin=0, vmax=1, aspect="auto")
# ax.set_xticks(np.arange(-0.5, 7, 1), minor=True)
# ax.set_yticks(np.arange(-0.5, 5, 1), minor=True)
# ax.grid(which="minor", color=WHITE, linewidth=1.5)
# ax.tick_params(which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
# for s in ax.spines.values():
#     s.set_visible(False)



# ---------------------------------------------------------
# 9. Calendar chart
# 与热力图区分：
# 1. 每个日期先绘制白色日历单元格；
# 2. 数据颜色只显示为单元格内部的小方块；
# 3. 月首、月末保留空白日期；
# 4. 顶部使用短横线表示一周七列。
# ---------------------------------------------------------
ax = axes[8]
clean_panel(ax)

n_rows = 5
n_cols = 7

# 顶部星期标记和日历网格之间的距离
header_y = 0.20
grid_y0 = 0.72

ax.set_xlim(-0.08, n_cols + 0.08)
ax.set_ylim(grid_y0 + n_rows + 0.08, -0.08)
ax.set_aspect("equal", adjustable="box")

# 顶部七个星期短横线，不显示文字
for col in range(n_cols):
    ax.plot(
        [col + 0.34, col + 0.66],
        [header_y, header_y],
        color=DARK_GRAY,
        linewidth=1.25,
        solid_capstyle="round",
        alpha=0.9,
    )

# 绘制外层日历单元格
for row in range(n_rows):
    for col in range(n_cols):
        cell = Rectangle(
            (col, grid_y0 + row),
            1.0,
            1.0,
            facecolor=WHITE,
            edgecolor=LIGHT_GRAY,
            linewidth=0.85,
        )
        ax.add_patch(cell)

# 模拟一个月份的数据。
# np.nan 表示当月不存在的日期，因此保持为空白。
calendar_values = np.array([
    [np.nan, np.nan, np.nan, np.nan, 0.16, 0.40, 0.36],
    [0.15,   0.56,   0.18,   0.16,   0.53, 0.96, 0.42],
    [0.58,   0.22,   0.64,   0.41,   0.61, 0.36, 0.25],
    [0.47,   0.39,   0.31,   0.12,   0.55, 0.16, 0.67],
    [0.62,   0.55,   0.23,   np.nan, np.nan, 0.14, np.nan],
])

# 使用少量、克制的蓝灰与青色
def calendar_color(value: float) -> str:
    if value < 0.20:
        return PALE_BLUE
    if value < 0.40:
        return LIGHT_BLUE
    if value < 0.60:
        return STEEL
    if value < 0.80:
        return TEAL
    return NAVY

# 在每个日历单元格内部绘制较小色块
inner_margin = 0.20
inner_size = 1.0 - 2 * inner_margin

for row in range(n_rows):
    for col in range(n_cols):
        value = calendar_values[row, col]

        if np.isnan(value):
            continue

        inner_square = Rectangle(
            (
                col + inner_margin,
                grid_y0 + row + inner_margin,
            ),
            inner_size,
            inner_size,
            facecolor=calendar_color(value),
            edgecolor=WHITE,
            linewidth=0.55,
        )
        ax.add_patch(inner_square)

ax.set_xticks([])
ax.set_yticks([])

for spine in ax.spines.values():
    spine.set_visible(False)
    
    
    
# 10. Funnel chart
ax = axes[9]
clean_panel(ax)
levels = [
    (0.05, 0.95, 0.86, NAVY),
    (0.13, 0.87, 0.68, BLUE),
    (0.22, 0.78, 0.50, STEEL),
    (0.31, 0.69, 0.32, LIGHT_BLUE),
    (0.40, 0.60, 0.14, LIGHT_GRAY),
]
for i, (left, right, y_top, color) in enumerate(levels):
    y_bottom = y_top - 0.14
    next_left = levels[i + 1][0] if i < len(levels) - 1 else 0.47
    next_right = levels[i + 1][1] if i < len(levels) - 1 else 0.53
    ax.add_patch(Polygon([[left, y_top], [right, y_top], [next_right, y_bottom], [next_left, y_bottom]],
                         closed=True, facecolor=color, edgecolor=WHITE, linewidth=1.0))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

# 11. Sankey-like diagram
ax = axes[10]
clean_panel(ax)
left_nodes = [(0.06, 0.69, 0.055, 0.18, NAVY), (0.06, 0.43, 0.055, 0.22, TEAL), (0.06, 0.16, 0.055, 0.22, MID_GRAY)]
mid_nodes = [(0.49, 0.57, 0.055, 0.27, NAVY), (0.49, 0.24, 0.055, 0.24, STEEL)]
right_nodes = [(0.91, 0.73, 0.045, 0.13, NAVY), (0.91, 0.55, 0.045, 0.13, TEAL),
               (0.91, 0.36, 0.045, 0.13, MID_GRAY), (0.91, 0.15, 0.045, 0.16, LIGHT_BLUE)]
for x0, y0, w, h, color in left_nodes + mid_nodes + right_nodes:
    ax.add_patch(Rectangle((x0, y0), w, h, facecolor=color, edgecolor=WHITE, linewidth=0.8))

def flow(x0, y0, x1, y1, thickness, color, alpha=0.42):
    c = (x1 - x0) * 0.45
    verts = [
        (x0, y0 + thickness / 2),
        (x0 + c, y0 + thickness / 2),
        (x1 - c, y1 + thickness / 2),
        (x1, y1 + thickness / 2),
        (x1, y1 - thickness / 2),
        (x1 - c, y1 - thickness / 2),
        (x0 + c, y0 - thickness / 2),
        (x0, y0 - thickness / 2),
        (x0, y0 + thickness / 2),
    ]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="none", alpha=alpha))

flow(0.115, 0.80, 0.49, 0.74, 0.055, NAVY, 0.40)
flow(0.115, 0.74, 0.49, 0.65, 0.040, STEEL, 0.35)
flow(0.115, 0.54, 0.49, 0.69, 0.052, TEAL, 0.35)
flow(0.115, 0.48, 0.49, 0.36, 0.055, TEAL, 0.30)
flow(0.115, 0.30, 0.49, 0.38, 0.060, MID_GRAY, 0.33)
flow(0.545, 0.74, 0.91, 0.79, 0.050, NAVY, 0.35)
flow(0.545, 0.69, 0.91, 0.61, 0.040, STEEL, 0.30)
flow(0.545, 0.63, 0.91, 0.42, 0.040, LIGHT_BLUE, 0.28)
flow(0.545, 0.36, 0.91, 0.58, 0.050, TEAL, 0.28)
flow(0.545, 0.31, 0.91, 0.23, 0.060, MID_GRAY, 0.30)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

# 12. Treemap-like mosaic
ax = axes[11]
clean_panel(ax)
rects = [
    (0.00, 0.48, 0.42, 0.52, NAVY),
    (0.00, 0.00, 0.42, 0.46, MID_GRAY),
    (0.44, 0.35, 0.28, 0.65, TEAL),
    (0.44, 0.00, 0.14, 0.33, LIGHT_BLUE),
    (0.60, 0.00, 0.12, 0.33, STEEL),
    (0.74, 0.58, 0.26, 0.42, LIGHT_BLUE),
    (0.74, 0.24, 0.26, 0.32, MID_GRAY),
    (0.74, 0.00, 0.12, 0.22, LIGHT_GRAY),
    (0.88, 0.00, 0.12, 0.22, STEEL),
]
for x0, y0, w, h, color in rects:
    ax.add_patch(Rectangle((x0, y0), w, h, facecolor=color, edgecolor=WHITE, linewidth=1.1))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

fig.savefig(OUTPUT, bbox_inches="tight", pad_inches=0.08, facecolor=WHITE)
plt.close(fig)
print(OUTPUT)
