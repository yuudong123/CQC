from pathlib import Path
import csv
import json

from PIL import Image, ImageDraw, ImageFont


OUTPUT_DIR = Path(__file__).resolve().parent
REPO_ROOT = OUTPUT_DIR.parents[1]
SPLIT_CSV = REPO_ROOT / "configs" / "splits" / "seed-42.csv"
SPLIT_SUMMARY = REPO_ROOT / "configs" / "splits" / "seed-42-summary.json"
VIEW_SUMMARY = REPO_ROOT / "configs" / "view-selection-summary.json"
FONT = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

NAVY, BLUE, SKY = "#17324D", "#2F6B9A", "#74B3CE"
GREEN, ORANGE, RED = "#4D8B69", "#E69F45", "#C95A49"
GRID, MUTED, WHITE = "#E8EDF2", "#52616F", "#FFFFFF"


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)


def canvas():
    image = Image.new("RGB", (1600, 900), WHITE)
    return image, ImageDraw.Draw(image)


def title(draw, text, subtitle=None):
    draw.text((110, 72), text, fill=NAVY, font=font(46, True))
    if subtitle:
        draw.text((112, 137), subtitle, fill=MUTED, font=font(23))


def footer(draw, text):
    draw.text((112, 842), text, fill=MUTED, font=font(21))


def draw_grid(draw, box, steps=5):
    x0, y0, x1, y1 = box
    for i in range(steps + 1):
        y = y1 - (y1 - y0) * i / steps
        draw.line((x0, y, x1, y), fill=GRID, width=2)


def centered(draw, xy, text, fnt, fill):
    draw.text(xy, text, font=fnt, fill=fill, anchor="mm")


def chart_dataset_composition(rows):
    cultivars, grades = ["fuji", "yanggwang"], ["L", "M", "S"]
    label = {"fuji": "부사", "yanggwang": "양광", "L": "특", "M": "상", "S": "보통"}
    counts = {(c, g): 0 for c in cultivars for g in grades}
    for row in rows:
        counts[(row["cultivar"], row["quality_grade"])] += int(row["frames"])
    image, draw = canvas()
    title(draw, "품종·품질 등급별 이미지 구성", "이미지 수와 함께 독립 사과 그룹 수를 봐야 합니다")
    plot = (190, 225, 1410, 745)
    draw_grid(draw, plot)
    max_total = max(sum(counts[(c, g)] for g in grades) for c in cultivars) * 1.08
    for center_x, cultivar in zip([560, 1040], cultivars):
        y_bottom = plot[3]
        for grade, color in zip(grades, [BLUE, SKY, ORANGE]):
            value = counts[(cultivar, grade)]
            height = value / max_total * (plot[3] - plot[1])
            y_top = y_bottom - height
            draw.rectangle((center_x - 135, y_top, center_x + 135, y_bottom), fill=color)
            centered(draw, (center_x, (y_top + y_bottom) / 2), f"{value:,}", font(25, True), WHITE)
            y_bottom = y_top
        centered(draw, (center_x, 785), label[cultivar], font(29, True), NAVY)
    for idx, (grade, color) in enumerate(zip(grades, [BLUE, SKY, ORANGE])):
        x = 1050 + idx * 145
        draw.rectangle((x, 165, x + 25, 190), fill=color)
        draw.text((x + 37, 160), label[grade], fill=NAVY, font=font(22))
    footer(draw, "전체 25,024장 · 동일 사과 179그룹")
    image.save(OUTPUT_DIR / "viz_01_dataset_composition.png")


def chart_split(summary):
    image, draw = canvas()
    title(draw, "그룹 단위 70·15·15 분할 결과", "같은 사과의 여러 각도를 한 세트에만 배치했습니다")
    labels, keys = ["학습", "검증", "시험"], ["train", "validation", "test"]
    datasets = [
        ("사과 그룹", [summary["split_groups"][k] for k in keys], "그룹"),
        ("이미지 프레임", [summary["split_frames"][k] for k in keys], "장"),
    ]
    for panel, (panel_title, values, unit) in zip([(110, 220, 770, 760), (830, 220, 1490, 760)], datasets):
        x0, y0, x1, y1 = panel
        draw.text((x0, y0 - 52), panel_title, fill=NAVY, font=font(30, True))
        draw_grid(draw, panel)
        max_v, gap = max(values) * 1.14, (x1 - x0) / 3
        for i, (name, value, color) in enumerate(zip(labels, values, [BLUE, GREEN, ORANGE])):
            center_x = x0 + gap * (i + 0.5)
            height = value / max_v * (y1 - y0)
            draw.rectangle((center_x - 60, y1 - height, center_x + 60, y1), fill=color)
            centered(draw, (center_x, y1 - height - 28), f"{value:,}{unit}", font(23, True), NAVY)
            draw.text((center_x - 32, y1 + 20), name, fill=NAVY, font=font(24, True))
    footer(draw, "Train·Validation·Test 그룹 교차 0건")
    image.save(OUTPUT_DIR / "viz_02_group_split.png")


def chart_multiview(view_summary):
    image, draw = canvas()
    title(draw, "입력 장수가 늘면 메모리·전송 부담도 커짐", "막대: 사과 1개 디코딩 메모리 · 점: 패딩이 필요한 그룹")
    plot = (155, 245, 1445, 745)
    draw_grid(draw, plot)
    views = [4, 8, 12, 16, 40]
    padded = [view_summary["targets"][str(v)]["padded_groups"] for v in views]
    decoded_mb = [v * 1000 * 1000 * 3 / 1024 / 1024 for v in views]
    gap, points = (plot[2] - plot[0]) / len(views), []
    for i, (view, mb, pad) in enumerate(zip(views, decoded_mb, padded)):
        center_x = plot[0] + gap * (i + 0.5)
        height = mb / 125 * (plot[3] - plot[1])
        draw.rectangle((center_x - 62, plot[3] - height, center_x + 62, plot[3]), fill=BLUE)
        centered(draw, (center_x, plot[3] - height - 26), f"{mb:.1f}MB", font(22, True), NAVY)
        centered(draw, (center_x, 790), f"{view}장", font(25, True), NAVY)
        points.append((center_x, plot[3] - pad / 5 * (plot[3] - plot[1])))
    for a, b in zip(points, points[1:]):
        draw.line((a[0], a[1], b[0], b[1]), fill=RED, width=6)
    for (px, py), pad in zip(points, padded):
        draw.ellipse((px - 10, py - 10, px + 10, py + 10), fill=RED)
        centered(draw, (px, py - 29), f"{pad}그룹", font(19, True), RED)
    footer(draw, "40장 입력: 사과 1개 약 114.4MB · 초당 2개 처리 시 약 228.9MB 디코딩")
    image.save(OUTPUT_DIR / "viz_03_multiview_tradeoff.png")


def main():
    with SPLIT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with SPLIT_SUMMARY.open("r", encoding="utf-8") as f:
        split_summary = json.load(f)
    with VIEW_SUMMARY.open("r", encoding="utf-8") as f:
        view_summary = json.load(f)
    chart_dataset_composition(rows)
    chart_split(split_summary)
    chart_multiview(view_summary)


if __name__ == "__main__":
    main()
