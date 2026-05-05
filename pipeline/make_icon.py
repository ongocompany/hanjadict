#!/usr/bin/env python3
"""앱 아이콘 1024x1024 PNG 생성. tauri icon으로 모든 사이즈 자동 변환."""

from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "src-tauri" / "icons" / "icon-source.png"

SIZE = 1024
MARGIN = 96
RADIUS = 200
BG = (240, 238, 232, 255)        # 종이톤 베이지 (시안 라이트 모드 --bg와 일관)
GLYPH_COLOR = (139, 58, 58, 255) # 적갈 (시안 --accent와 일관)
SHADOW = (0, 0, 0, 28)           # 미세 inner shadow

TEXT = "字"

# macOS 시스템 명조 한자 폰트
FONT_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 1),  # Songti SC Bold
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 4),  # PingFang SC Heavy
]


def pick_font(size_px: int) -> ImageFont.FreeTypeFont:
    for path, idx in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size_px, index=idx)
            except Exception:
                continue
    sys.exit("적절한 한자 폰트를 찾지 못했습니다.")


def main():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 미세 그림자 (배경 한 픽셀 아래)
    shadow_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.rounded_rectangle(
        (MARGIN, MARGIN + 6, SIZE - MARGIN, SIZE - MARGIN + 6),
        radius=RADIUS, fill=SHADOW,
    )
    img.alpha_composite(shadow_layer.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(8)))

    # 둥근 사각형 배경
    draw.rounded_rectangle(
        (MARGIN, MARGIN, SIZE - MARGIN, SIZE - MARGIN),
        radius=RADIUS, fill=BG,
    )

    # 가운데 한자
    font_size = 720
    font = pick_font(font_size)
    bbox = draw.textbbox((0, 0), TEXT, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (SIZE - w) // 2 - bbox[0]
    y = (SIZE - h) // 2 - bbox[1] - 20  # 시각적 중앙은 약간 위로
    draw.text((x, y), TEXT, font=font, fill=GLYPH_COLOR)

    # 작은 인장풍 표시: 좌상단에 작은 점/마커 (옵셔널, 깔끔함 위해 생략 가능)
    # — 일단 단순하게.

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"saved: {OUT} ({OUT.stat().st_size:,} bytes)")

    # tauri icon으로 모든 사이즈 생성
    print("\ntauri icon 실행…")
    r = subprocess.run(
        ["pnpm", "exec", "tauri", "icon", str(OUT)],
        cwd=REPO,
    )
    if r.returncode != 0:
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
