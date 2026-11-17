"""
Gerador e refinador de assets voxel/pixel-art naturais para o AeroMattics.

Cria e atualiza sprites coerentes com o universo de aviacao (sem simbolos matematicos no jogo):
- Brisa Favoravel de alto contraste (corrente termica/vento voxel nitida)
- Aves Migratorias: Harpia Real Brasileira (Harpia harpyja) em voo horizontal (6 quadros)
- Fauna brasileira por bioma (Arara-Vermelha, Tucano-Toco, Tuiuiu Pantaneiro e Arara-Azul)
- Panoramas voxel dos 4 biomas do Brasil (Amazonia, Cerrado, Pantanal e Mata Atlantica)
- Indicadores de alerta de migracao (bordas esquerda e direita)
- Sol animado ampliado para sobrepor o sol da Fase 1 (3 quadros)
- Rajada de vento limpa e delicada (2 fitas aerodinamicas translucidas)
- Ponteiros do cockpit refinados (combustivel ambar e estabilidade ciano)
- Capa do menu higienizada, botoes voxel com asas, tela de Guia ilustrada e telas de Pouso finais

Autoria: ThyagoToledo
"""

from collections import deque
import json
import math
from pathlib import Path
import zipfile
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(r"C:\Users\thyag\OneDrive\Desktop\AeroMattics")
ASSETS_DIR = ROOT / "assets_organizados"
BACKUP_SB3 = ROOT / "backup" / "AeroMattics_original.sb3"

FONTS_DIR = Path(r"C:\Windows\Fonts")


def load_font(preferred: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Carrega fonte TrueType em negrito/legivel no Windows com fallback seguro."""
    for fname in preferred:
        fpath = FONTS_DIR / fname
        if fpath.exists():
            return ImageFont.truetype(str(fpath), size=size)
    return ImageFont.load_default()


def draw_voxel_block(draw: ImageDraw.ImageDraw, gx: int, gy: int, cell: int, color: tuple[int, int, int, int]) -> None:
    """Desenha um bloco quadrado alinhado a grade voxel."""
    x0 = gx * cell
    y0 = gy * cell
    draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=color)


def draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] = (10, 20, 36, 255),
    anchor: str = "mm",
    stroke_width: int = 3,
) -> None:
    """Desenha texto com contorno de alto contraste para leitura acessivel."""
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=outline,
    )


def _cutout_white_studio_voxel(
    raw_path: Path,
    min_lum: int = 230,
    max_sat: int = 22,
    punch_holes: bool = True,
    max_hole_px: int = 24000,
    protect_center_radius_frac: float = 0.0,
) -> Image.Image:
    """Recorta sprite 3D voxel de fundo branco com descontaminacao de halos de borda."""
    rgb = np.array(Image.open(raw_path).convert("RGB"), dtype=np.uint8)
    h, w, _ = rgb.shape
    bg = _border_flood_background(rgb, min_lum=min_lum, max_sat=max_sat)
    fg = ~bg

    if punch_holes:
        cmax = rgb.max(axis=2)
        cmin = rgb.min(axis=2)
        hole_cand = fg & (cmin >= max(226, min_lum)) & ((cmax - cmin) <= max(14, max_sat - 4))
        if protect_center_radius_frac > 0.0:
            yy, xx = np.mgrid[0:h, 0:w]
            dist = np.hypot(xx - w * 0.5, yy - h * 0.5)
            hole_cand = hole_cand & (dist > min(h, w) * protect_center_radius_frac)
        seen = np.zeros((h, w), dtype=bool)
        ys, xs = np.nonzero(hole_cand)
        for sy, sx in zip(ys.tolist(), xs.tolist()):
            if seen[sy, sx]:
                continue
            q = deque([(sy, sx)])
            seen[sy, sx] = True
            pixels = []
            while q:
                cy, cx = q.popleft()
                pixels.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and hole_cand[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if len(pixels) <= max_hole_px:
                for py, px in pixels:
                    fg[py, px] = False

    alpha = np.where(fg, 255, 0).astype(np.uint8)
    padded = np.pad(fg, 1, mode="constant", constant_values=False)
    outer_ring = fg & (~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]))
    cmax = rgb.max(axis=2)
    cmin = rgb.min(axis=2)
    white_fringe = outer_ring & (cmin >= 180) & ((cmax - cmin) <= 36)
    alpha[white_fringe] = np.clip(255.0 - (cmin[white_fringe].astype(np.float32) - 166.0) * 3.4, 0.0, 255.0).astype(np.uint8)

    # Descontamina pixels claros semitransparentes puxando cor do vizinho interno opaco
    out_rgb = rgb.copy()
    fy, fx = np.nonzero(white_fringe)
    interior = fg & (~outer_ring)
    for py, px in zip(fy.tolist(), fx.tolist()):
        y0, y1 = max(0, py - 2), min(h, py + 3)
        x0, x1 = max(0, px - 2), min(w, px + 3)
        sub_mask = interior[y0:y1, x0:x1]
        if sub_mask.any():
            out_rgb[py, px] = rgb[y0:y1, x0:x1][sub_mask].mean(axis=0).astype(np.uint8)

    rgba = Image.fromarray(np.dstack([out_rgb, alpha]), mode="RGBA")
    bbox = rgba.getbbox()
    return rgba.crop(bbox) if bbox else rgba


def make_breeze_frames() -> None:
    """Gera 4 quadros 160x160 RGBA da Brisa Favoravel 3D Voxel animada e luminosa."""
    out_dir = ASSETS_DIR / "06_itens_e_aneis"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_breeze = out_dir / "raw_brisa_voxel.png"
    size = 160

    if raw_breeze.exists():
        cut = _cutout_white_studio_voxel(
            raw_breeze,
            min_lum=238,
            max_sat=18,
            punch_holes=True,
            max_hole_px=6500,
            protect_center_radius_frac=0.14,
        )
        base_core = cut.copy()
        base_core.thumbnail((126, 126), Image.Resampling.LANCZOS)

        for q in range(1, 5):
            angle = (-10.0, -3.0, 4.0, 11.0)[q - 1]
            scale_pct = (0.96, 1.00, 1.04, 1.00)[q - 1]
            glow_boost = (0, 10, 18, 8)[q - 1]

            nw = max(16, int(round(base_core.width * scale_pct)))
            nh = max(16, int(round(base_core.height * scale_pct)))
            scaled = base_core.resize((nw, nh), Image.Resampling.LANCZOS)
            rot = scaled.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)

            arr = np.array(rot, dtype=np.int16)
            fg_m = arr[:, :, 3] > 20
            if glow_boost > 0 and fg_m.any():
                arr[fg_m, 0] = np.clip(arr[fg_m, 0] + glow_boost // 2, 0, 255)
                arr[fg_m, 1] = np.clip(arr[fg_m, 1] + glow_boost, 0, 255)
                arr[fg_m, 2] = np.clip(arr[fg_m, 2] + glow_boost, 0, 255)
            sprite = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")

            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            aura = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ad = ImageDraw.Draw(aura)
            rad_a = 48 + (q % 2) * 3
            ad.ellipse([80 - rad_a, 80 - rad_a, 80 + rad_a, 80 + rad_a], fill=(96, 232, 255, 36 + glow_boost))
            aura = aura.filter(ImageFilter.GaussianBlur(7))
            canvas = Image.alpha_composite(canvas, aura)

            px = (size - sprite.width) // 2
            py = (size - sprite.height) // 2
            canvas.paste(sprite, (px, py), sprite)
            canvas.save(out_dir / f"brisa_favoravel_q{q}.png")
        return

    # Fallback procedural caso arquivo bruto nao exista
    cell = 5
    for q in range(1, 5):
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        phase = (q - 1) * (2.0 * math.pi / 4.0)
        for gy in range(32):
            for gx in range(32):
                r = math.hypot(gx - 15.5, gy - 15.5)
                ang = math.atan2(gy - 15.5, gx - 15.5)
                if 4.2 <= r <= 13.4 and math.sin(ang * 2.0 - r * 0.44 + phase) > 0.25:
                    draw_voxel_block(draw, gx, gy, cell, (76, 224, 255, 255))
                elif r < 3.4:
                    draw_voxel_block(draw, gx, gy, cell, (255, 252, 224, 255))
        im.save(out_dir / f"brisa_favoravel_q{q}.png")


def _cutout_chroma_studio_voxel(raw_path: Path, key_mode: str) -> Image.Image:
    """Recorta sprite 3D voxel por flood-fill de borda em chroma verde/magenta sem furar asas ou peito."""
    rgb_u8 = np.array(Image.open(raw_path).convert("RGB"), dtype=np.uint8)
    rgb = rgb_u8.astype(np.float32)
    h, w, _ = rgb.shape
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    if key_mode == "green":
        key_dom = g - np.maximum(r, b)
        lo_flood, pocket_thr = 22.0, 48.0
    elif key_mode == "magenta":
        key_dom = np.minimum(r, b) - g
        lo_flood, pocket_thr = 26.0, 88.0
    else:
        raise ValueError(f"Chroma key nao suportado: {key_mode}")

    # 1) Flood-fill conectado as 4 bordas: garante zero transparentes internos nas asas/plumagem
    cand_bg = key_dom >= lo_flood
    bg = np.zeros((h, w), dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(w):
        if cand_bg[0, x] and not bg[0, x]:
            bg[0, x] = True
            queue.append((0, x))
        if cand_bg[h - 1, x] and not bg[h - 1, x]:
            bg[h - 1, x] = True
            queue.append((h - 1, x))
    for y in range(h):
        if cand_bg[y, 0] and not bg[y, 0]:
            bg[y, 0] = True
            queue.append((y, 0))
        if cand_bg[y, w - 1] and not bg[y, w - 1]:
            bg[y, w - 1] = True
            queue.append((y, w - 1))
    while queue:
        cy, cx = queue.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not bg[ny, nx] and cand_bg[ny, nx]:
                bg[ny, nx] = True
                queue.append((ny, nx))

    fg = ~bg
    # 2) Abre apenas bolsos puros de chroma brilhante presos entre garras/crista (nunca sombras internas)
    pocket_cand = fg & (key_dom >= pocket_thr)
    seen = np.zeros((h, w), dtype=bool)
    ys, xs = np.nonzero(pocket_cand)
    for sy_p, sx_p in zip(ys.tolist(), xs.tolist()):
        if seen[sy_p, sx_p]:
            continue
        q = deque([(sy_p, sx_p)])
        seen[sy_p, sx_p] = True
        px_list = []
        while q:
            cy, cx = q.popleft()
            px_list.append((cy, cx))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and pocket_cand[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(px_list) <= 12000:
            for py_i, px_i in px_list:
                fg[py_i, px_i] = False

    alpha = np.where(fg, 255.0, 0.0)
    padded = np.pad(fg, 1, mode="constant", constant_values=False)
    outer_ring = fg & (~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]))
    fade_edge = outer_ring & (key_dom > 4.0)
    alpha[fade_edge] = np.clip(255.0 - (key_dom[fade_edge] - 4.0) * (220.0 / max(8.0, lo_flood)), 40.0, 255.0)

    # Descontaminacao de cor sem nunca furar alpha interior (asas permanecem 100% opacas)
    out_rgb = rgb.copy()
    if key_mode == "green":
        fringe = (key_dom > 8.0) & (alpha > 4.0)
        neutral_cap = np.maximum(r, b) + 3.0
        out_rgb[:, :, 1] = np.where(fringe, np.minimum(g, neutral_cap), g)
    else:
        mag_spill = (key_dom > 2.0) & (alpha > 2.0)
        neutral_val = np.clip(g + 2.0, 0.0, 255.0)
        out_rgb[:, :, 0] = np.where(mag_spill, np.minimum(r, neutral_val), r)
        out_rgb[:, :, 2] = np.where(mag_spill, np.minimum(b, neutral_val), b)

    rgba = Image.fromarray(
        np.dstack([np.clip(out_rgb, 0, 255).astype(np.uint8), np.clip(alpha, 0, 255).astype(np.uint8)]),
        mode="RGBA",
    )
    bbox = rgba.getbbox()
    return rgba.crop(bbox) if bbox else rgba


def _bilinear_sample_rgba(src_arr: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> np.ndarray:
    """Amostra imagem RGBA (H, W, 4) por interpolacao bilinear com borda transparente."""
    h, w, _ = src_arr.shape
    valid = (sx >= 0.0) & (sx <= w - 1.0) & (sy >= 0.0) & (sy <= h - 1.0)
    sx_c = np.clip(sx, 0.0, w - 1.0)
    sy_c = np.clip(sy, 0.0, h - 1.0)

    x0 = np.floor(sx_c).astype(np.int32)
    y0 = np.floor(sy_c).astype(np.int32)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)

    fx = (sx_c - x0)[:, :, None]
    fy = (sy_c - y0)[:, :, None]

    # Pre-multiplica RGB por Alpha para evitar halo escuro ou branco em bordas transparentes
    src_f = src_arr.astype(np.float32)
    a_src = src_f[:, :, 3:4] / 255.0
    pm_rgb = src_f[:, :, :3] * a_src
    pm = np.concatenate([pm_rgb, src_f[:, :, 3:4]], axis=2)

    p00 = pm[y0, x0]
    p10 = pm[y0, x1]
    p01 = pm[y1, x0]
    p11 = pm[y1, x1]

    out_pm = (
        p00 * (1.0 - fx) * (1.0 - fy)
        + p10 * fx * (1.0 - fy)
        + p01 * (1.0 - fx) * fy
        + p11 * fx * fy
    )
    out_pm[~valid] = 0.0

    out_a = np.clip(out_pm[:, :, 3:4], 0.0, 255.0)
    out_rgb = np.where(out_a > 1.0, (out_pm[:, :, :3] / np.maximum(out_a / 255.0, 1e-4)), 0.0)
    return np.concatenate([np.clip(out_rgb, 0, 255), out_a], axis=2).astype(np.uint8)


def _animate_voxel_bird_frame(
    bird_cut: Image.Image,
    max_box: tuple[int, int],
    flap_px: float,
    wing_start_frac: float = 0.14,
    tilt_deg: float = 0.0,
    light_boost: int = 0,
) -> Image.Image:
    """Articula asas por curva suave e oscilacao vertical de voo em canvas 320x180 RGBA."""
    cw, ch = 320, 180
    fit = bird_cut.copy()
    fit.thumbnail(max_box, Image.Resampling.LANCZOS)

    base = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    px = (cw - fit.width) // 2
    py = (ch - fit.height) // 2 + 4
    base.paste(fit, (px, max(8, py)), fit)
    src_arr = np.array(base, dtype=np.uint8)

    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    dx = xx - (cw * 0.5)
    adx = np.abs(dx)
    shoulder_px = max(14.0, fit.width * wing_start_frac)
    wing_span = max(12.0, fit.width * 0.50 - shoulder_px)
    t_wing = np.clip((adx - shoulder_px) / wing_span, 0.0, 1.0)

    # Inverso geometrico: desloca asa verticalmente + leve encurtamento perspectivo nas pontas
    bob_y = -0.16 * flap_px
    wing_dy = flap_px * (t_wing ** 1.15)
    wing_pull = np.sign(dx) * (abs(flap_px) * 0.20) * t_wing

    sx = xx + wing_pull
    sy = yy - (wing_dy + bob_y)
    warped = _bilinear_sample_rgba(src_arr, sx, sy)

    if light_boost != 0:
        w_f = warped.astype(np.int16)
        fg = w_f[:, :, 3] > 24
        for c in range(3):
            w_f[fg, c] = np.clip(w_f[fg, c] + light_boost, 0, 255)
        warped = w_f.astype(np.uint8)

    out_im = Image.fromarray(warped, mode="RGBA")
    if abs(tilt_deg) > 0.1:
        rot = out_im.rotate(tilt_deg, resample=Image.Resampling.BICUBIC, expand=True)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(rot, ((cw - rot.width) // 2, (ch - rot.height) // 2), rot)
        return canvas
    return out_im


def make_migratory_bird_frames() -> None:
    """Gera 6 quadros 320x180 RGBA solidos da Harpia Real Brasileira voltada nativamente para a direita (+90)."""
    out_dir = ASSETS_DIR / "04_passaros_biomas"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_harpia = out_dir / "raw_passaro_harpia_real.jpg"
    # Espelha horizontalmente para alinhar com Scratch (+90 = direita; -90 left-right = esquerda)
    cut = _cutout_chroma_studio_voxel(raw_harpia, key_mode="magenta").transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    # Ciclo suave e harmonico de planar/bater asas sem distorcao angular
    cycle_specs = [
        (-11.0, 7.0, 6),
        (-3.0, 4.5, 3),
        (12.0, 2.0, -2),
        (4.0, 3.5, 0),
        (-8.0, 6.0, 4),
        (0.0, 4.0, 2),
    ]
    for idx, (flap_px, tilt, boost) in enumerate(cycle_specs, start=1):
        eagle = _animate_voxel_bird_frame(
            cut,
            max_box=(236, 128),
            flap_px=flap_px,
            wing_start_frac=0.21,
            tilt_deg=tilt,
            light_boost=boost,
        )
        eagle.save(out_dir / f"ave_migratoria_q{idx}.png")


def make_brazilian_biome_birds() -> None:
    """Gera sprites 3D Voxel exclusivos para cada ave tipica dos 4 biomas do Brasil."""
    out_dir = ASSETS_DIR / "04_passaros_biomas"
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = [
        # (bioma_idx, slug_legado, arquivo_bruto, modo_extracao, box_max, ombro_frac)
        (1, "campo", "raw_passaro_b1_arara_vermelha.jpg", "white", (250, 128), 0.13),
        (2, "floresta", "raw_passaro_b2_tucano.jpg", "white", (250, 126), 0.13),
        (3, "deserto", "raw_passaro_b3_tuiuiu.jpg", "green", (246, 128), 0.14),
        (4, "neve", "raw_passaro_b4_arara_azul.jpg", "white", (250, 128), 0.13),
    ]
    flap_cycle = [
        (-15.0, 6),   # q1: asas erguidas sem corte no topo
        (0.0, 2),     # q2: planando aberto
        (19.0, -3),   # q3: batida firme para baixo
        (-5.0, 3),    # q4: recuperacao suave
    ]

    for b_idx, legacy_slug, raw_name, ext_mode, max_box, shoulder in specs:
        raw_path = out_dir / raw_name
        if ext_mode == "white":
            cut = _cutout_white_studio_voxel(
                raw_path,
                min_lum=232,
                max_sat=20,
                punch_holes=False,
            )
        else:
            cut = _cutout_chroma_studio_voxel(raw_path, key_mode=ext_mode)

        frames: list[Image.Image] = []
        for q_idx, (flap_px, boost) in enumerate(flap_cycle, start=1):
            im = _animate_voxel_bird_frame(
                cut,
                max_box=max_box,
                flap_px=flap_px,
                wing_start_frac=shoulder,
                tilt_deg=0.0,
                light_boost=boost,
            )
            im.save(out_dir / f"aeromattics_passaro_bioma{b_idx}_{legacy_slug}_q{q_idx}.png")
            frames.append(im)

        sheet = Image.new("RGBA", (640, 360), (0, 0, 0, 0))
        for idx_f, frm in enumerate(frames):
            sheet.paste(frm, ((idx_f % 2) * 320, (idx_f // 2) * 180), frm)
        sheet.save(out_dir / f"aeromattics_passaro_bioma{b_idx}_{legacy_slug}_4frames.png")


def make_migration_alerts() -> None:
    """Gera 2 indicadores suaves de borda (120x120) para avisar lado da migracao."""
    out_dir = ASSETS_DIR / "07_telas_e_overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    for side in ("esq", "dir"):
        im = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        draw.ellipse([16, 16, 104, 104], fill=(14, 34, 54, 215), outline=(245, 198, 92, 245), width=5)
        if side == "esq":
            draw.polygon([(46, 36), (78, 60), (46, 84), (46, 70), (30, 70), (30, 50), (46, 50)], fill=(255, 224, 130, 255))
        else:
            draw.polygon([(74, 36), (42, 60), (74, 84), (74, 70), (90, 70), (90, 50), (74, 50)], fill=(255, 224, 130, 255))
        im.save(out_dir / f"alerta_migracao_{side}.png")


def make_sun_frames() -> None:
    """Gera 3 quadros 160x160 RGBA do Sol Voxel 3D Minecraft com brilho quente descontaminado."""
    out_dir = ASSETS_DIR / "05_nuvens_voxel"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_sun = out_dir / "raw_sol_voxel.png"
    size = 160

    if raw_sun.exists():
        rgb = np.array(Image.open(raw_sun).convert("RGB"), dtype=np.float32)
        bg_sample = np.median(rgb[:32, :32, :], axis=(0, 1))
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

        # Energia dourada contra fundo azul-cobalto: sol sempre tem calor (R+G) muito acima de B
        warmth = (r * 1.10 + g * 0.85) - (b * 1.35)
        alpha_f = np.clip((warmth - 18.0) / 145.0, 0.0, 1.0)
        solid_sun = (r > 135.0) & ((r + g) > (1.85 * b + 30.0))
        alpha_f = np.where(solid_sun, 1.0, alpha_f)
        alpha_u8 = np.clip(alpha_f * 255.0, 0.0, 255.0).astype(np.uint8)

        # Descontamina bordas semitransparentes removendo contribuicao azul do fundo
        a_nz = np.maximum(alpha_f, 0.08)[:, :, None]
        clean_rgb = np.clip((rgb - (1.0 - alpha_f[:, :, None]) * bg_sample[None, None, :]) / a_nz, 0.0, 255.0)
        clean_rgb = np.where(solid_sun[:, :, None], rgb, clean_rgb).astype(np.uint8)

        cut = Image.fromarray(np.dstack([clean_rgb, alpha_u8]), mode="RGBA")
        bbox = cut.getbbox()
        if bbox:
            cut = cut.crop(bbox)
        base_sun = cut.copy()
        base_sun.thumbnail((116, 116), Image.Resampling.LANCZOS)

        for q in range(1, 4):
            sc = (0.97, 1.00, 1.03)[q - 1]
            boost = (0, 8, 16)[q - 1]
            nw = max(16, int(round(base_sun.width * sc)))
            nh = max(16, int(round(base_sun.height * sc)))
            sprite = base_sun.resize((nw, nh), Image.Resampling.LANCZOS)
            arr_s = np.array(sprite, dtype=np.int16)
            fg_m = arr_s[:, :, 3] > 24
            if boost > 0 and fg_m.any():
                arr_s[fg_m, 0] = np.clip(arr_s[fg_m, 0] + boost, 0, 255)
                arr_s[fg_m, 1] = np.clip(arr_s[fg_m, 1] + boost, 0, 255)
            sprite = Image.fromarray(np.clip(arr_s, 0, 255).astype(np.uint8), mode="RGBA")

            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            aura = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ad = ImageDraw.Draw(aura)
            rad = 50 + q * 3
            ad.ellipse([80 - rad, 80 - rad, 80 + rad, 80 + rad], fill=(255, 224, 118, 42 + boost))
            aura = aura.filter(ImageFilter.GaussianBlur(8))
            canvas = Image.alpha_composite(canvas, aura)
            canvas.paste(sprite, ((size - sprite.width) // 2, (size - sprite.height) // 2), sprite)
            canvas.save(out_dir / f"sol_voxel_q{q}.png")
        return

    cx = cy = size // 2
    for q in range(1, 4):
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        pulse = (-2, 0, 2)[q - 1]
        for half, col in ((44 + pulse, (255, 224, 118, 42)), (30, (255, 226, 98, 175)), (20, (255, 250, 210, 255))):
            draw.rectangle([cx - half, cy - half, cx + half - 1, cy + half - 1], fill=col)
        im.save(out_dir / f"sol_voxel_q{q}.png")


def make_wind_gust_frames() -> None:
    """Gera 4 quadros 320x180 RGBA com fitas aerodinamicas voxel fluidas e particulas de ar."""
    out_dir = ASSETS_DIR / "05_nuvens_voxel"
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 320, 180

    # Tres fitas onduladas em camadas de profundidade + cubos aerodinamicos soltos
    streams = [
        (36, 48, 172, 6, (242, 252, 255), (86, 176, 228), 215, 0.0),
        (78, 88, 188, 7, (224, 248, 255), (62, 154, 216), 232, 1.4),
        (52, 128, 152, 5, (236, 250, 255), (78, 168, 222), 198, 2.7),
    ]
    for q in range(1, 5):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        phase = (q - 1) * (2.0 * math.pi / 4.0)
        shift_x = (q - 1) * 10

        for x0, y0, length, thick, hi_col, sh_col, max_a, off_ph in streams:
            sx0 = x0 + shift_x
            if sx0 + length > w - 12:
                sx0 -= 40
            for dx in range(0, length, 4):
                u = dx / max(1.0, float(length))
                # Envelope suave nas pontas (sem corte quadrado)
                env = math.sin(math.pi * u) ** 0.72
                al_hi = int(round(max_a * env))
                al_sh = int(round(max_a * 0.65 * env))
                if al_hi < 12:
                    continue
                px = sx0 + dx
                wave_y = int(round(y0 + 5.5 * math.sin(u * 3.1 * math.pi - phase + off_ph)))
                th_here = max(2, int(round(thick * (0.45 + 0.55 * env))))
                draw.rectangle([px, wave_y + th_here, px + 3, wave_y + th_here + 2], fill=(*sh_col, al_sh))
                draw.rectangle([px, wave_y, px + 3, wave_y + th_here], fill=(*hi_col, al_hi))

            # Crista de vento na dianteira + 2 cubos voxel flutuantes atras
            tip_x = sx0 + length - 8
            tip_y = int(round(y0 + 5.5 * math.sin(3.1 * math.pi - phase + off_ph)))
            for m in range(3):
                mx = (tip_x + 8 + m * 12) % (w - 20)
                my = tip_y + (-4, 3, -2)[m]
                al_m = max(45, max_a - m * 48)
                draw.rectangle([mx, my, mx + 4, my + 4], fill=(246, 253, 255, al_m))

        im.save(out_dir / f"rajada_vento_q{q}.png")


def make_sharp_needles() -> None:
    """Refina ambos os ponteiros 64x64 para ponteiro fino comprido (cima) e base curta escura."""
    out_dir = ASSETS_DIR / "03_hud_cockpit"
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = [
        ("aeromattics_hud_ponteiro_combustivel.png", (252, 188, 52, 255), (255, 238, 170, 255)),
        ("aeromattics_hud_ponteiro_estabilidade.png", (56, 208, 245, 255), (205, 248, 255, 255)),
    ]
    for fname, body_col, tip_col in specs:
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        draw.polygon([(32, 7), (34, 15), (34, 32), (30, 32), (30, 15)], fill=body_col)
        draw.line([(32, 8), (32, 26)], fill=tip_col, width=1)
        draw.rectangle([30, 33, 33, 37], fill=(42, 54, 72, 255))
        draw.ellipse([27, 27, 36, 36], fill=(214, 168, 74, 255), outline=(28, 36, 48, 255), width=1)
        draw.ellipse([29, 29, 34, 34], fill=(248, 214, 128, 255))
        im.save(out_dir / fname)


def clean_victory_frame() -> None:
    """Remove os 4 cantos soltos externos da moldura de vitoria mantendo o cartao intacto."""
    in_path = ASSETS_DIR / "07_telas_e_overlays" / "aeromattics_missao_concluida_moldura_alpha_4x3.png"
    out_path = ASSETS_DIR / "07_telas_e_overlays" / "aeromattics_missao_concluida_moldura_limpa.png"
    im = Image.open(in_path).convert("RGBA")
    arr = np.array(im)
    arr[:45, :, :] = 0
    arr[313:, :, :] = 0
    Image.fromarray(arr, mode="RGBA").save(out_path)


def make_clean_menu_cover() -> None:
    """Remove o botao fixo da capa original e prepara faixa inferior limpa com atalhos adaptados."""
    ov_dir = ASSETS_DIR / "07_telas_e_overlays"
    src = Image.open(ov_dir / "tela_Capa_AeroMattics.jpg").convert("RGBA")
    arr = np.array(src)

    # Remover botao antigo em x=246..714, y=520..654 combinando gramado adjacente sem costura central
    left_grass = arr[520:654, 12:246, :].astype(np.float32)
    right_grass = arr[520:654, 714:948, :].astype(np.float32)
    # Espelhar nas bordas x=246 e x=714 para continuidade exata e suavizar largamente o centro
    patch_l = left_grass[:, ::-1, :]
    patch_r = right_grass[:, ::-1, :]
    patch = np.concatenate([patch_l, patch_r], axis=1)
    half = 234
    rad_blend = 55
    for k in range(-rad_blend, rad_blend):
        idx = half + k
        if 0 <= idx < 468:
            t = 0.5 + 0.5 * math.sin((k / float(rad_blend)) * (math.pi / 2.0))
            patch[:, idx, :] = (1.0 - t) * patch_l[:, min(233, idx), :] + t * patch_r[:, max(0, idx - half), :]
    # Blend suave nas bordas superior e inferior
    orig_patch = arr[520:654, 246:714, :].astype(np.float32)
    for row in range(10):
        a = row / 10.0
        patch[row, :, :] = (1.0 - a) * orig_patch[row, :, :] + a * patch[row, :, :]
        patch[-1 - row, :, :] = (1.0 - a) * orig_patch[-1 - row, :, :] + a * patch[-1 - row, :, :]
    arr[520:654, 246:714, :] = np.clip(patch, 0, 255).astype(np.uint8)

    # Limpar texto antigo na faixa inferior (y=672..715) clonando gramado de fundo escuro abaixo
    strip_src = arr[656:668, :, :]
    for row_start in range(672, 720, 12):
        h_slice = min(12, 720 - row_start)
        arr[row_start : row_start + h_slice, :, :] = strip_src[:h_slice, :, :]

    im_out = Image.fromarray(arr, mode="RGBA")
    draw = ImageDraw.Draw(im_out)
    # Faixa sutil translucida na base com controles completos de teclado/Makey Makey/sensor/guia
    draw.rectangle([0, 678, 960, 720], fill=(10, 26, 40, 185))
    f_hint = load_font(("segoeuib.ttf", "arialbd.ttf"), 20)
    draw_outlined_text(
        draw,
        (480, 699),
        "SETAS / MAKEY MAKEY / SENSOR (C): PILOTAR  |  G: GUIA  |  M: SOM",
        f_hint,
        fill=(250, 250, 240, 255),
        outline=(8, 18, 28, 255),
        stroke_width=3,
    )
    im_out.save(ov_dir / "tela_Capa_Menu_Limpa.png")


def make_voxel_winged_button(filename: str, label: str, scheme: str) -> None:
    """Cria botoes voxel com asas laterais (260x84 RGBA, bitmapResolution=2 -> 130x42 Scratch)."""
    ov_dir = ASSETS_DIR / "07_telas_e_overlays"
    w, h = 260, 84
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    schemes = {
        "gold": {
            "outer": (94, 42, 6, 255),
            "rim": (235, 134, 18, 255),
            "body": (255, 206, 28, 255),
            "hi": (255, 240, 135, 255),
            "text": (16, 44, 98, 255),
            "text_outline": (255, 236, 150, 255),
            "wing_outer": (16, 72, 132, 255),
            "wing_fill": (44, 206, 255, 255),
            "wing_hi": (175, 244, 255, 255),
        },
        "cyan": {
            "outer": (12, 48, 86, 255),
            "rim": (28, 146, 198, 255),
            "body": (44, 198, 238, 255),
            "hi": (162, 242, 255, 255),
            "text": (14, 34, 62, 255),
            "text_outline": (232, 252, 255, 255),
            "wing_outer": (122, 62, 8, 255),
            "wing_fill": (255, 198, 36, 255),
            "wing_hi": (255, 238, 148, 255),
        },
        "navy": {
            "outer": (10, 24, 42, 255),
            "rim": (214, 164, 52, 255),
            "body": (22, 62, 98, 255),
            "hi": (48, 108, 154, 255),
            "text": (255, 234, 152, 255),
            "text_outline": (8, 18, 32, 255),
            "wing_outer": (104, 54, 8, 255),
            "wing_fill": (244, 186, 44, 255),
            "wing_hi": (255, 230, 138, 255),
        },
    }
    pal = schemes[scheme]

    # Asas voxel em degraus dos dois lados (esquerdo: x=4..42, direito: x=218..256)
    wing_tiers = [
        (4, 20, 42, 32),
        (12, 34, 42, 46),
        (20, 48, 42, 60),
    ]
    for x0, y0, x1, y1 in wing_tiers:
        # Asa esquerda
        draw.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill=pal["wing_outer"])
        draw.rectangle([x0, y0, x1, y1], fill=pal["wing_fill"])
        draw.rectangle([x0 + 2, y0 + 2, x1 - 2, y0 + 5], fill=pal["wing_hi"])
        # Asa direita espelhada
        rx0 = w - x1
        rx1 = w - x0
        draw.rectangle([rx0 - 2, y0 - 2, rx1 + 2, y1 + 2], fill=pal["wing_outer"])
        draw.rectangle([rx0, y0, rx1, y1], fill=pal["wing_fill"])
        draw.rectangle([rx0 + 2, y0 + 2, rx1 - 2, y0 + 5], fill=pal["wing_hi"])

    # Placa central voxel em degraus (x=38..222, y=10..74)
    draw.rectangle([42, 10, 218, 74], fill=pal["outer"])
    draw.rectangle([38, 14, 222, 70], fill=pal["outer"])
    draw.rectangle([44, 14, 216, 70], fill=pal["rim"])
    draw.rectangle([42, 18, 218, 66], fill=pal["rim"])
    draw.rectangle([48, 18, 212, 62], fill=pal["body"])
    draw.rectangle([48, 18, 212, 24], fill=pal["hi"])

    font_size = 24 if len(label) <= 9 else (18 if len(label) <= 13 else 16)
    font = load_font(("arialbd.ttf", "segoeuib.ttf", "verdanab.ttf"), font_size)
    draw.text(
        (w / 2.0, h / 2.0 + 1),
        label,
        font=font,
        fill=pal["text"],
        anchor="mm",
        stroke_width=2,
        stroke_fill=pal["text_outline"],
    )
    im.save(ov_dir / filename)


def load_plane_thumbnail() -> Image.Image:
    """Extrai o sprite real do aviao reto do .sb3 original e recorta margens transparentes."""
    with zipfile.ZipFile(BACKUP_SB3, "r") as zf:
        proj = json.loads(zf.read("project.json").decode("utf-8"))
        av = next(t for t in proj["targets"] if t["name"] == "Avião")
        costume = next(c for c in av["costumes"] if "linha Reta" in c["name"])
        im = Image.open(BytesIO(zf.read(costume["md5ext"]))).convert("RGBA")
        bbox = im.getbbox()
        if bbox:
            im = im.crop(bbox)
        return im


def make_mini_gauge(label: str, needle_deg: float, accent: tuple[int, int, int, int]) -> Image.Image:
    """Cria um mini mostrador circular 92x92 estilizado para ilustrar o Guia."""
    im = Image.new("RGBA", (92, 92), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.ellipse([6, 6, 86, 86], fill=(16, 32, 50, 255), outline=(212, 168, 72, 255), width=5)
    draw.ellipse([12, 12, 80, 80], outline=(82, 182, 194, 220), width=2)
    rad = math.radians(needle_deg - 90.0)
    nx = 46 + 24 * math.cos(rad)
    ny = 46 + 24 * math.sin(rad)
    draw.line([(46, 46), (nx, ny)], fill=accent, width=4)
    draw.ellipse([41, 41, 51, 51], fill=(242, 198, 92, 255))
    f_mini = load_font(("arialbd.ttf", "segoeuib.ttf"), 11)
    draw.text((46, 70), label, font=f_mini, fill=accent, anchor="mm")
    return im


def paste_fit(base: Image.Image, sprite: Image.Image, center_xy: tuple[int, int], max_size: tuple[int, int]) -> None:
    """Redimensiona sprite mantendo proporcao e cola centralizado na tela guia."""
    copy = sprite.copy()
    bbox = copy.getbbox()
    if bbox:
        copy = copy.crop(bbox)
    copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    bx = int(center_xy[0] - copy.width / 2)
    by = int(center_xy[1] - copy.height / 2)
    base.paste(copy, (bx, by), copy)


def make_guide_screen() -> None:
    """Compoe tela ilustrada 960x720 de Guia de Voo com imagens grandes e texto acessivel."""
    ov_dir = ASSETS_DIR / "07_telas_e_overlays"
    w, h = 960, 720

    # Fundo baseado no bioma Amazonia (panorama brasileiro) escurecido para maximo contraste
    bg_path = ASSETS_DIR / "09_cenarios_vivos" / "raw_bioma1.png"
    if not bg_path.exists():
        bg_path = ASSETS_DIR / "01_cenarios_biomas" / "02_principal_bioma2_floresta.png"
    bg = Image.open(bg_path).convert("RGBA")
    bg = ImageOps.fit(bg, (w, h), method=Image.Resampling.LANCZOS)
    dim = Image.new("RGBA", (w, h), (10, 26, 46, 178))
    canvas = Image.alpha_composite(bg, dim)
    draw = ImageDraw.Draw(canvas)

    # Cabecalho superior limpo e grande
    draw.rectangle([28, 16, 932, 78], fill=(14, 38, 64, 240), outline=(242, 196, 78, 255), width=4)
    f_title = load_font(("arialbd.ttf", "segoeuib.ttf"), 28)
    draw_outlined_text(
        draw,
        (480, 47),
        "GUIA DE VOO - COMO JOGAR (AEROMATTICS)",
        f_title,
        fill=(255, 224, 114, 255),
        outline=(8, 18, 30, 255),
        stroke_width=3,
    )

    f_card_title = load_font(("arialbd.ttf", "segoeuib.ttf"), 20)
    f_card_body = load_font(("segoeuib.ttf", "arialbd.ttf"), 18)

    # Grade 2x2 de cartoes grandes (y=92..594 -> faixa inferior y=605..720 livre para VOLTAR MENU)
    cards = [
        {
            "box": (28, 92, 468, 332),
            "border": (255, 134, 96, 255),
            "title": "1. AVES DO BRASIL E HARPIA",
            "title_col": (255, 192, 132, 255),
            "lines": [
                "Araras, Tucanos e a Harpia Real",
                "causam DANO no aviao (-1 VIDA)",
                "se colidirem em pleno voo.",
                "Se o alerta piscar na borda,",
                "voe para o outro lado!",
            ],
        },
        {
            "box": (492, 92, 932, 332),
            "border": (96, 224, 255, 255),
            "title": "2. BRISA E VENTO (ESTABILIDADE)",
            "title_col": (128, 236, 255, 255),
            "lines": [
                "A brisa (+15 pts) e as rajadas",
                "movem o aviao para o lado e",
                "alteram o mostrador ESTAB.",
                "Compense aos poucos para",
                "manter o voo nivelado.",
            ],
        },
        {
            "box": (28, 348, 468, 588),
            "border": (248, 204, 82, 255),
            "title": "3. COMBUSTIVEL NO AR (TANQUE)",
            "title_col": (255, 224, 122, 255),
            "lines": [
                "O tanque baixa aos poucos no",
                "mostrador dourado COMB.%.",
                "Colete os galoes no ar para",
                "reabastecer (+28% no tanque)",
                "e cruzar todos os 4 biomas.",
            ],
        },
        {
            "box": (492, 348, 932, 588),
            "border": (118, 238, 168, 255),
            "title": "4. CONTROLES ADAPTADOS (MATTICS)",
            "title_col": (152, 248, 186, 255),
            "lines": [
                "Movimento calmo anti-tremor:",
                "- Teclado / Makey Makey: Setas,",
                "  A/D ou W/F para os lados.",
                "- Sensor de movimento: tecla C",
                "  ou ponteiro guia o aviao.",
            ],
        },
    ]

    for c in cards:
        x0, y0, x1, y1 = c["box"]
        draw.rectangle([x0, y0, x1, y1], fill=(12, 32, 56, 236), outline=c["border"], width=4)
        # Barra de titulo do cartao
        draw.rectangle([x0 + 4, y0 + 4, x1 - 4, y0 + 44], fill=(20, 48, 82, 245))
        draw.text((x0 + 16, y0 + 24), c["title"], font=f_card_title, fill=c["title_col"], anchor="lm")

    # Ilustracoes com sprites reais do jogo na coluna esquerda de cada cartao
    bird1 = Image.open(ASSETS_DIR / "04_passaros_biomas" / "aeromattics_passaro_bioma1_campo_q1.png").convert("RGBA")
    mig1 = Image.open(ASSETS_DIR / "04_passaros_biomas" / "ave_migratoria_q1.png").convert("RGBA")
    alert1 = Image.open(ov_dir / "alerta_migracao_esq.png").convert("RGBA")
    paste_fit(canvas, bird1, (82, 182), (80, 68))
    paste_fit(canvas, mig1, (84, 248), (82, 48))
    paste_fit(canvas, alert1, (82, 296), (40, 40))

    breeze1 = Image.open(ASSETS_DIR / "06_itens_e_aneis" / "brisa_favoravel_q1.png").convert("RGBA")
    wind1 = Image.open(ASSETS_DIR / "05_nuvens_voxel" / "rajada_vento_q1.png").convert("RGBA")
    g_estab = make_mini_gauge("ESTAB.", 42.0, (72, 224, 255, 255))
    paste_fit(canvas, breeze1, (548, 178), (70, 70))
    paste_fit(canvas, wind1, (548, 232), (82, 26))
    paste_fit(canvas, g_estab, (548, 288), (64, 64))

    fuel1 = Image.open(ASSETS_DIR / "06_itens_e_aneis" / "aeromattics_combustivel_galao_pixel.png").convert("RGBA")
    g_comb = make_mini_gauge("COMB.%", 115.0, (252, 198, 66, 255))
    paste_fit(canvas, fuel1, (82, 444), (78, 78))
    paste_fit(canvas, g_comb, (82, 534), (74, 74))

    plane_img = load_plane_thumbnail()
    paste_fit(canvas, plane_img, (548, 448), (90, 64))
    # Icone simplificado de setas esquerda/direita + sensor
    draw.rectangle([504, 502, 542, 540], fill=(26, 68, 108, 255), outline=(146, 232, 192, 255), width=2)
    draw.text((523, 521), "<", font=f_card_title, fill=(255, 255, 255, 255), anchor="mm")
    draw.rectangle([554, 502, 592, 540], fill=(26, 68, 108, 255), outline=(146, 232, 192, 255), width=2)
    draw.text((573, 521), ">", font=f_card_title, fill=(255, 255, 255, 255), anchor="mm")

    # Textos grandes de cada cartao (a direita dos icones, folga garantida na direita)
    draw = ImageDraw.Draw(canvas)
    for c in cards:
        x0, y0, _, _ = c["box"]
        tx = x0 + 114
        ty = y0 + 74
        for i, line in enumerate(c["lines"]):
            fill = (255, 246, 212, 255) if i in (1, 2) else (238, 246, 255, 255)
            draw.text((tx, ty + i * 32), line, font=f_card_body, fill=fill, anchor="lm")

    canvas.save(ov_dir / "tela_Guia_AeroMattics.png")


def make_landing_end_screens() -> None:
    """Compoe telas finais 960x720 com imagens geradas de pouso e titulos curtos no topo."""
    ov_dir = ASSETS_DIR / "07_telas_e_overlays"
    specs = [
        (
            ov_dir / "pouso_vitoria_raw.png",
            ov_dir / "tela_Fim_Pouso_Vitoria.png",
            "POUSO CONCLUIDO!",
            "4 BIOMAS ATRAVESSADOS COM SEGURANCA",
            (255, 218, 92, 255),
            (138, 245, 238, 255),
        ),
        (
            ov_dir / "pouso_gameover_raw.png",
            ov_dir / "tela_Fim_Pouso_GameOver.png",
            "FIM DE VOO",
            "POUSO DE SEGURANCA - TENTE NOVAMENTE",
            (255, 218, 92, 255),
            (158, 238, 248, 255),
        ),
    ]
    f_big = load_font(("arialbd.ttf", "segoeuib.ttf"), 40)
    f_sub = load_font(("arialbd.ttf", "segoeuib.ttf"), 20)

    for src_path, dst_path, title, subtitle, t_col, s_col in specs:
        im = Image.open(src_path).convert("RGBA")
        fitted = ImageOps.fit(im, (960, 720), method=Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", (960, 720), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        # Placa superior enxuta no ceu aberto (nao cobre o aviao na pista)
        d.rectangle([150, 22, 810, 128], fill=(12, 32, 54, 198), outline=(238, 192, 74, 245), width=4)
        draw_outlined_text(d, (480, 62), title, f_big, fill=t_col, outline=(8, 18, 30, 255), stroke_width=4)
        draw_outlined_text(d, (480, 103), subtitle, f_sub, fill=s_col, outline=(8, 18, 30, 255), stroke_width=2)
        out = Image.alpha_composite(fitted, overlay)
        out.save(dst_path)


def _biome_palettes() -> dict[int, dict]:
    """Paletas voxel harmonizadas para os 4 biomas brasileiros."""
    return {
        1: {"name": "Amazonia", "accent": (54, 178, 84)},
        2: {"name": "Cerrado", "accent": (236, 178, 48)},
        3: {"name": "Pantanal", "accent": (228, 92, 168)},
        4: {"name": "Mata Atlantica", "accent": (52, 138, 224)},
    }


def make_clean_voxel_biome_terrains() -> None:
    """Sintetiza os 4 terrenos 3D Minecraft voxel limpos (1200x896) sem casas, barcos ou arvores estaticas."""
    out_dir = ASSETS_DIR / "09_cenarios_vivos"
    base_path = out_dir / "raw_terreno_base_voxel.png"
    if not base_path.exists():
        raise FileNotFoundError(f"Terreno base 3D voxel ausente: {base_path}")

    base = np.array(Image.open(base_path).convert("RGB"), dtype=np.float32)
    h, w, _ = base.shape
    r, g, b = base[:, :, 0], base[:, :, 1], base[:, :, 2]
    yy, xx = np.mgrid[0:h, 0:w]

    # Segmentacao semantica com pesos suaves preservando 100% do relevo e sombreamento 3D original
    sky_raw = (yy < 190) & (b > 175) & (r > 130) & (b >= g)
    water_raw = (~sky_raw) & (
        ((b > r * 1.15) & (g > 105) & (b > g * 0.92))
        | ((np.abs(xx - 600) < 155) & (yy > 470) & (r > 195) & (g > 205) & (b > 205))
    )
    sand_raw = (~sky_raw) & (~water_raw) & (np.abs(xx - 600) < 350) & (r > 175) & (g > 155) & (r > b * 1.12)
    dirt_raw = (~sky_raw) & (~water_raw) & (~sand_raw) & (r >= g * 0.98) & (g >= b) & (yy >= 120)
    stone_raw = (~sky_raw) & (~water_raw) & (~sand_raw) & (~dirt_raw) & (np.abs(r - g) < 18) & (np.abs(g - b) < 22) & (yy >= 120) & (np.abs(xx - 600) < 360)
    grass_raw = (~sky_raw) & (~water_raw) & (~sand_raw) & (~dirt_raw) & (~stone_raw)

    def soft_mask(mask: np.ndarray, blur_r: int = 1) -> np.ndarray:
        if blur_r <= 0:
            return mask.astype(np.float32)
        im_m = Image.fromarray((mask.astype(np.uint8) * 255), mode="L").filter(ImageFilter.BoxBlur(blur_r))
        return np.array(im_m, dtype=np.float32) / 255.0

    w_sky = soft_mask(sky_raw, 2)
    w_water = soft_mask(water_raw, 1)
    w_sand = soft_mask(sand_raw, 1)
    w_dirt = soft_mask(dirt_raw, 1)
    w_stone = soft_mask(stone_raw, 1)
    w_grass = soft_mask(grass_raw, 1)
    w_sum = np.maximum(1e-5, w_sky + w_water + w_sand + w_dirt + w_stone + w_grass)
    w_sky, w_water, w_sand, w_dirt, w_stone, w_grass = [
        m / w_sum for m in (w_sky, w_water, w_sand, w_dirt, w_stone, w_grass)
    ]

    # Estatisticas da base original por material
    base_stats = {}
    for m_name, m_bin in [
        ("water", water_raw),
        ("sand", sand_raw),
        ("dirt", dirt_raw),
        ("stone", stone_raw),
        ("grass", grass_raw),
    ]:
        vals = base[m_bin]
        base_stats[m_name] = (vals.mean(axis=0), np.maximum(8.0, vals.std(axis=0)))

    def transfer_rgb(arr: np.ndarray, src_mean: np.ndarray, src_std: np.ndarray, tgt_mean: np.ndarray, tgt_std: np.ndarray) -> np.ndarray:
        norm = (arr - src_mean[None, None, :]) / src_std[None, None, :]
        return np.clip(norm * tgt_std[None, None, :] + tgt_mean[None, None, :], 0.0, 255.0)

    # Semantica limpa do horizonte superior (evita recolorir colinas acima de y=145)
    far_horizon = (yy < 145) & (w_water < 0.25)

    # Paletas reais amostradas de raw_bioma1..4.png preservando 100% dos blocos 3D sem retalhos ou objetos fantasmas
    biome_recipes = {
        1: {  # Amazonia: verde esmeralda tropical intenso, barranco de musgo/areia e rio azul-turquesa amazonico
            "grass_tgt": (np.array([56.0, 106.0, 36.0]), np.array([28.0, 42.0, 22.0])),
            "dirt_tgt": (np.array([62.0, 54.0, 34.0]), np.array([22.0, 18.0, 14.0])),
            "sand_tgt": (np.array([218.0, 210.0, 158.0]), np.array([16.0, 14.0, 14.0])),
            "stone_tgt": (np.array([76.0, 88.0, 72.0]), np.array([18.0, 18.0, 16.0])),
            "water_tgt": (np.array([44.0, 136.0, 164.0]), np.array([38.0, 24.0, 28.0])),
        },
        2: {  # Cerrado: grama dourado-oliva da savana, terra ocre-avermelhada e rio azul-petroleo
            "grass_tgt": (np.array([148.0, 146.0, 50.0]), np.array([36.0, 38.0, 24.0])),
            "dirt_tgt": (np.array([118.0, 72.0, 40.0]), np.array([26.0, 18.0, 14.0])),
            "sand_tgt": (np.array([226.0, 208.0, 144.0]), np.array([18.0, 16.0, 14.0])),
            "stone_tgt": (np.array([134.0, 102.0, 74.0]), np.array([20.0, 18.0, 16.0])),
            "water_tgt": (np.array([70.0, 134.0, 162.0]), np.array([36.0, 24.0, 26.0])),
        },
        3: {  # Pantanal: varzea verde viva, extensos bancos de areia clara e rio espelhado azul-celeste
            "grass_tgt": (np.array([86.0, 134.0, 56.0]), np.array([34.0, 44.0, 26.0])),
            "dirt_tgt": (np.array([92.0, 76.0, 48.0]), np.array([24.0, 20.0, 16.0])),
            "sand_tgt": (np.array([240.0, 234.0, 198.0]), np.array([16.0, 14.0, 14.0])),
            "stone_tgt": (np.array([124.0, 132.0, 108.0]), np.array([18.0, 18.0, 16.0])),
            "water_tgt": (np.array([108.0, 148.0, 168.0]), np.array([36.0, 30.0, 32.0])),
        },
        4: {  # Mata Atlantica: encostas verde-vivas escalonadas, pedra costeira e rio azul cobalto profundo
            "grass_tgt": (np.array([66.0, 124.0, 42.0]), np.array([34.0, 44.0, 24.0])),
            "dirt_tgt": (np.array([68.0, 68.0, 44.0]), np.array([20.0, 20.0, 16.0])),
            "sand_tgt": (np.array([212.0, 206.0, 170.0]), np.array([18.0, 18.0, 18.0])),
            "stone_tgt": (np.array([116.0, 124.0, 128.0]), np.array([22.0, 22.0, 22.0])),
            "water_tgt": (np.array([36.0, 102.0, 166.0]), np.array([38.0, 26.0, 30.0])),
        },
    }

    for b_idx in range(1, 5):
        raw_path = out_dir / f"raw_bioma{b_idx}.png"
        if not raw_path.exists():
            raise FileNotFoundError(f"Panorama brasileiro ausente: {raw_path}")

        rec = biome_recipes[b_idx]
        g_layer = transfer_rgb(base, *base_stats["grass"], *rec["grass_tgt"])
        d_layer = transfer_rgb(base, *base_stats["dirt"], *rec["dirt_tgt"])
        s_layer = transfer_rgb(base, *base_stats["sand"], *rec["sand_tgt"])
        st_layer = transfer_rgb(base, *base_stats["stone"], *rec["stone_tgt"])
        wa_layer = transfer_rgb(base, *base_stats["water"], *rec["water_tgt"])

        out = (
            w_sky[:, :, None] * base
            + w_grass[:, :, None] * g_layer
            + w_dirt[:, :, None] * d_layer
            + w_sand[:, :, None] * s_layer
            + w_stone[:, :, None] * st_layer
            + w_water[:, :, None] * wa_layer
        )
        # Mantem colinas distantes acima da linha do horizonte neutras/suaves sem recoloracao forte
        out[far_horizon] = 0.65 * base[far_horizon] + 0.35 * out[far_horizon]
        # Mantem brilho specular puro dentro da agua intacto para reflexos solares suaves
        glint_px = water_raw & (r > 210) & (g > 215) & (b > 215)
        out[glint_px] = np.clip(0.55 * out[glint_px] + 0.45 * base[glint_px], 0.0, 255.0)
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="RGB").save(out_dir / f"raw_terreno_bioma{b_idx}.png")


def make_voxel_runway() -> None:
    """Cria pista 3D voxel 960x720 mantendo nuvens/sol/paisagem originais e apagando so titulo e aviao."""
    ov_dir = ASSETS_DIR / "07_telas_e_overlays"
    nb_raw = ov_dir / "pista_decolagem_nb_raw.png"
    if nb_raw.exists():
        im_nb = Image.open(nb_raw).convert("RGBA")
        if im_nb.size != (960, 720):
            im_nb = im_nb.resize((960, 720), Image.Resampling.LANCZOS)
        im_nb.save(ov_dir / "pista_decolagem_voxel.png")
        return

    import cv2

    clean_cover = ov_dir / "tela_Capa_Menu_Limpa.png"
    src_path = clean_cover if clean_cover.exists() else (ov_dir / "tela_Capa_AeroMattics.jpg")
    im = Image.open(src_path).convert("RGB")
    arr_orig = np.array(im, dtype=np.uint8)

    # 1) Estende suavemente apenas o gramado abaixo da cabeceira da pista (y=520..674 -> 520..720, zero emenda)
    arr = np.zeros((720, 960, 3), dtype=np.uint8)
    arr[:520] = arr_orig[:520]
    grass_bot = Image.fromarray(arr_orig[520:674]).resize((960, 200), Image.Resampling.LANCZOS)
    arr[520:720] = np.array(grass_bot, dtype=np.uint8)

    rgb_i = arr.astype(np.int16)
    r, g, b = rgb_i[:, :, 0], rgb_i[:, :, 1], rgb_i[:, :, 2]
    yy, xx = np.mgrid[0:720, 0:960]

    # 2) Mascara exata do titulo "AEROMATTICS" em y=[48..214], x=[114..840]
    logo_seed = (
        (yy >= 48) & (yy <= 214) & (xx >= 114) & (xx <= 840)
        & (((r - b > 34) & (r > 110)) | ((r < 122) & (g < 118) & (b < 140)))
    )
    logo_mask = cv2.dilate(
        logo_seed.astype(np.uint8) * 255,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
    ) > 0

    # 3) Remove o titulo com interpolacao horizontal suave (ceu limpo acima de y=216)
    work = arr.astype(np.float32)
    h, w, _ = work.shape
    for y in range(h):
        m_row = logo_mask[y]
        if not m_row.any():
            continue
        xs = np.where(m_row)[0]
        for seg in np.split(xs, np.where(np.diff(xs) > 1)[0] + 1):
            xl = max(0, int(seg[0]) - 1)
            xr = min(w - 1, int(seg[-1]) + 1)
            span = max(1, xr - xl)
            cl = work[y, xl]
            cr = work[y, xr]
            for x in seg:
                t = (int(x) - xl) / span
                horiz = (1.0 - t) * cl + t * cr
                work[y, x] = horiz
                if y >= 2 and not logo_mask[y - 2, x]:
                    work[y, x] = 0.72 * horiz + 0.28 * work[y - 2, x]

    work_u8 = np.clip(work, 0, 255).astype(np.uint8)

    # 4) Silhueta suave e enxuta do aviao da capa (sem caixote retangular nem linha de corte em y=296)
    tail_band = (yy >= 184) & (yy <= 264) & (xx >= 436) & (xx <= 492)
    wing_band = (yy >= 258) & (yy <= 298) & (xx >= 240) & (xx <= 726)
    center_fuse = (yy >= 240) & (yy <= 348) & (xx >= 384) & (xx <= 588)
    prop_l = ((xx - 410.0) ** 2 + (yy - 255.0) ** 2) <= 34.0 ** 2
    prop_r = ((xx - 562.0) ** 2 + (yy - 255.0) ** 2) <= 34.0 ** 2
    sun_core = (xx >= 644) & (xx <= 712) & (yy >= 234) & (yy <= 306) & (r > 238) & (g > 224) & ((yy < 260) | (yy > 294))

    plane_seed = (tail_band | wing_band | center_fuse | prop_l | prop_r) & (~sun_core)
    plane_mask = cv2.dilate(
        plane_seed.astype(np.uint8) * 255,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)),
    ) > 0

    # 5) Reconstroi dentro de plane_mask por interpolacao horizontal continua + microtextura + blend borda suave
    work2 = work_u8.astype(np.float32)
    h2, w2, _ = work2.shape
    horiz_fill = work2.copy()
    for y in range(h2):
        m_row = plane_mask[y]
        if not m_row.any():
            continue
        xs = np.where(m_row)[0]
        for seg in np.split(xs, np.where(np.diff(xs) > 1)[0] + 1):
            xl = max(0, int(seg[0]) - 2)
            xr = min(w2 - 1, int(seg[-1]) + 2)
            span = max(1, xr - xl)
            # Media de 5 pixels limpos fora da borda evita puxar ruido de contorno
            cl = work2[y, max(0, xl - 4) : xl + 1].mean(axis=0)
            cr = work2[y, xr : min(w2, xr + 5)].mean(axis=0)
            for x in seg:
                t = (int(x) - xl) / span
                s = t * t * (3.0 - 2.0 * t)
                val = (1.0 - s) * cl + s * cr
                if y < 292 and y >= 4 and not plane_mask[y - 4, x]:
                    # Em ceu puro acima dos morros, mistura suavemente com o ceu logo acima para manter raios/nuvens naturais
                    val = 0.72 * val + 0.28 * horiz_fill[y - 1, x]
                horiz_fill[y, x] = val

    # Combina com leve suavizacao apenas na zona restaurada para eliminar qualquer transicao visivel
    mask_u8 = (plane_mask.astype(np.uint8) * 255)
    soft_interior = cv2.GaussianBlur(horiz_fill, (11, 11), 2.8)
    w_blend = cv2.GaussianBlur((mask_u8 > 0).astype(np.float32), (17, 17), 5.0)[:, :, None]
    final_rgb = np.clip((1.0 - w_blend) * work2 + w_blend * (0.55 * horiz_fill + 0.45 * soft_interior), 0, 255).astype(np.float32)

    # Restaura miolo solar nitido onde a asa direita cruzou a borda do sol
    sun_box = ((xx - 676.0) ** 2 / 32.0 ** 2 + (yy - 270.0) ** 2 / 30.0 ** 2) <= 1.0
    wing_in_sun = sun_box & plane_mask
    if wing_in_sun.any():
        sun_px = arr[sun_box & (~plane_mask)]
        if len(sun_px):
            sun_col = np.median(sun_px, axis=0).astype(np.float32)
            sun_w = cv2.GaussianBlur(wing_in_sun.astype(np.float32), (9, 9), 2.5)[:, :, None]
            final_rgb = (1.0 - sun_w) * final_rgb + sun_w * sun_col

    out_rgb = np.clip(final_rgb, 0, 255).astype(np.uint8)
    out_rgba = np.dstack([out_rgb, np.full((720, 960), 255, dtype=np.uint8)])
    Image.fromarray(out_rgba, mode="RGBA").save(ov_dir / "pista_decolagem_voxel.png")


def make_fuel_can_frames() -> None:
    """Gera 4 quadros 96x96 RGBA do Galao de Combustivel 3D Voxel animado sem halos."""
    item_dir = ASSETS_DIR / "06_itens_e_aneis"
    raw_can = item_dir / "raw_galao_voxel.png"
    fuel_legacy = item_dir / "aeromattics_combustivel_galao_pixel.png"

    if raw_can.exists():
        cut = _cutout_white_studio_voxel(
            raw_can,
            min_lum=236,
            max_sat=20,
            punch_holes=True,
            max_hole_px=4500,
        )
        base_can = cut.copy()
        base_can.thumbnail((78, 78), Image.Resampling.LANCZOS)

        for q in range(1, 5):
            dy = (0, -2, 0, 2)[q - 1]
            boost = (0, 12, 18, 10)[q - 1]
            canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))

            # Aura ambar suave para visibilidade perfeita contra ceu, rio ou mata
            aura = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            ad = ImageDraw.Draw(aura)
            rad_a = 38 + (q % 2) * 2
            ad.ellipse([48 - rad_a, 48 + dy - rad_a, 48 + rad_a, 48 + dy + rad_a], fill=(255, 206, 84, 34 + boost))
            aura = aura.filter(ImageFilter.GaussianBlur(6))
            canvas = Image.alpha_composite(canvas, aura)

            sprite = base_can.copy()
            arr_s = np.array(sprite, dtype=np.int16)
            fg_m = arr_s[:, :, 3] > 24
            if boost > 0 and fg_m.any():
                arr_s[fg_m, 0] = np.clip(arr_s[fg_m, 0] + boost, 0, 255)
                arr_s[fg_m, 1] = np.clip(arr_s[fg_m, 1] + int(boost * 0.85), 0, 255)
            sprite = Image.fromarray(np.clip(arr_s, 0, 255).astype(np.uint8), mode="RGBA")

            px = (96 - sprite.width) // 2
            py = max(2, min(94 - sprite.height, (96 - sprite.height) // 2 + dy))
            canvas.paste(sprite, (px, py), sprite)
            canvas.save(item_dir / f"galao_voxel_q{q}.png")
            if q == 1:
                canvas.save(fuel_legacy)
        return

    if fuel_legacy.exists():
        im = Image.open(fuel_legacy).convert("RGBA")
        arr = np.array(im, dtype=np.uint8)
        r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
        magenta_fringe = (a > 0) & (r > g + 16) & (b > g + 16) & (r < 95) & (b < 95)
        arr[magenta_fringe, 3] = 0
        cleaned = Image.fromarray(arr, mode="RGBA")
        cleaned.save(fuel_legacy)
        for q in range(1, 5):
            cleaned.save(item_dir / f"galao_voxel_q{q}.png")


clean_fuel_can_fringe = make_fuel_can_frames


def make_clean_horizon_skies() -> None:
    """Gera 12 horizontes limpos (4 biomas x 3 quadros, 1120x340 RGBA) sem buracos em montanhas ou degraus."""
    out_dir = ASSETS_DIR / "09_cenarios_vivos"
    out_dir.mkdir(parents=True, exist_ok=True)
    w, th = 1120, 340

    fog_colors = {
        1: np.array([108.0, 174.0, 124.0]),
        2: np.array([162.0, 168.0, 102.0]),
        3: np.array([116.0, 178.0, 134.0]),
        4: np.array([104.0, 168.0, 130.0]),
    }
    sky_top = np.array([58.0, 146.0, 236.0])
    sky_bot = np.array([178.0, 222.0, 248.0])

    for b_idx in range(1, 5):
        raw_path = out_dir / f"raw_bioma{b_idx}.png"
        if not raw_path.exists():
            raise FileNotFoundError(f"Base do bioma {b_idx} ausente em {out_dir}")

        fitted = ImageOps.fit(Image.open(raw_path).convert("RGB"), (w, 760), method=Image.Resampling.LANCZOS, centering=(0.5, 0.52))
        top = np.array(fitted, dtype=np.float32)[:th, :, :]
        r, g, b = top[:, :, 0], top[:, :, 1], top[:, :, 2]
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        sat = cmax - cmin

        if b_idx == 4:
            # No Bioma 4 preservamos 100% da rocha iluminada do Pao de Acucar, mas absorvemos filetes de nuvens e bruma central
            lum_px = 0.299 * r + 0.587 * g + 0.114 * b
            is_sky = (
                ((b > 170.0) & (b >= r + 14.0) & (b >= g + 2.0) & (g < 236.0))
                | ((cmin > 178.0) & (sat < 48.0) & (g <= r + 16.0))
                | ((np.arange(th)[:, None] < 245) & (lum_px > 186.0) & (b >= r - 2.0) & (sat < 54.0))
            )
        elif b_idx == 3:
            # No Pantanal ha bruma branca-azulada na linha do horizonte ate o verde da mata (g > r + 10)
            is_sky = (
                ((b > 165.0) & (b >= r + 8.0) & (g <= b + 4.0))
                | ((cmin > 186.0) & (sat < 44.0) & (g <= r + 12.0))
            )
        elif b_idx == 2:
            # No Cerrado inclui fenda central clara entre chapadas e limpa arcos estranhos acima da chapada direita
            is_sky = (
                ((b > 170.0) & (b >= r + 8.0))
                | ((cmin > 188.0) & (sat < 42.0))
            )
            # Remove artefatos em arco sobre a chapada direita (y < 268) sem tocar a escarpa abaixo
            arches_roi = (np.arange(th)[:, None] < 267) & (np.arange(w)[None, :] >= 610) & (np.arange(w)[None, :] <= 845)
            is_sky = is_sky | arches_roi
        else:
            # Amazonia: preserva copas e cupula do Teatro Amazonas (amarelo/verde escuro) e limpa bruma clara do fundo
            is_sky = (
                ((b > 172.0) & (b >= r + 10.0))
                | ((cmin > 192.0) & (sat < 38.0) & (g <= r + 12.0))
            )

        sky_limit_y = 278 if b_idx == 1 else (284 if b_idx == 2 else (290 if b_idx == 3 else 274))

        # BFS flood-fill estritamente conectado ao topo y=0 (zero buracos dentro de montanhas)
        sky_mask = np.zeros((th, w), dtype=bool)
        q = deque()
        for x in range(w):
            sky_mask[0, x] = True
            q.append((0, x))
        while q:
            cy, cx = q.popleft()
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < sky_limit_y and 0 <= nx < w and not sky_mask[ny, nx] and is_sky[ny, nx]:
                    sky_mask[ny, nx] = True
                    q.append((ny, nx))

        pure_top_y = {1: 92, 2: 218, 3: 242, 4: 145}[b_idx]
        sky_mask[:pure_top_y, :] = True

        # Remove pontinhos isolados sem furar terrenos
        pad_s = np.pad(sky_mask, 1, mode="edge")
        nb_count = (
            pad_s[:-2, 1:-1].astype(np.int32)
            + pad_s[2:, 1:-1].astype(np.int32)
            + pad_s[1:-1, :-2].astype(np.int32)
            + pad_s[1:-1, 2:].astype(np.int32)
        )
        sky_mask = sky_mask & (nb_count >= 2)

        # Mascara suavizada 1px para eliminar serrilhado duro entre montanhas e ceu
        sky_soft = np.array(Image.fromarray((sky_mask.astype(np.uint8) * 255), mode="L").filter(ImageFilter.BoxBlur(0.8)), dtype=np.float32) / 255.0

        sky_palettes = {
            1: (np.array([44.0, 134.0, 232.0]), np.array([174.0, 224.0, 250.0]), np.array([255.0, 240.0, 196.0])),
            2: (np.array([52.0, 138.0, 228.0]), np.array([204.0, 224.0, 232.0]), np.array([255.0, 236.0, 186.0])),
            3: (np.array([56.0, 148.0, 232.0]), np.array([186.0, 228.0, 244.0]), np.array([252.0, 242.0, 206.0])),
            4: (np.array([42.0, 128.0, 226.0]), np.array([172.0, 222.0, 248.0]), np.array([255.0, 238.0, 198.0])),
        }
        b_sky_top, b_sky_bot, b_sun_tint = sky_palettes[b_idx]

        # Constroi ceu atmosferico rico com dispersao solar no canto direito superior
        yy_g, xx_g = np.mgrid[0:th, 0:w]
        t_sky = np.clip((yy_g.astype(np.float32) / 302.0) ** 1.18, 0.0, 1.0)[:, :, None]
        sky_grad = (1.0 - t_sky) * b_sky_top[None, None, :] + t_sky * b_sky_bot[None, None, :]
        sun_dist = np.hypot((xx_g.astype(np.float32) - 920.0) / 420.0, (yy_g.astype(np.float32) - 92.0) / 185.0)
        sun_scatter = (np.clip(1.0 - sun_dist, 0.0, 1.0) ** 1.9)[:, :, None] * 0.28
        sky_rich = (1.0 - sun_scatter) * sky_grad + sun_scatter * b_sun_tint[None, None, :]

        # Mantem serras/florestas 100% nitidas com corte atmosferico apenas na borda extrema (y=300..324)
        base_rgba = np.dstack([top, np.full((th, w), 255.0, dtype=np.float32)])
        w_s = sky_soft[:, :, None]
        base_rgba[:, :, :3] = (1.0 - w_s) * base_rgba[:, :, :3] + w_s * sky_rich

        fog_arr = fog_colors[b_idx]
        for y in range(298, th):
            if y < 324:
                mix = (y - 298) / 26.0
                base_rgba[y, :, :3] = (1.0 - mix * 0.48) * base_rgba[y, :, :3] + (mix * 0.48) * fog_arr
                base_rgba[y, :, 3] = 255.0 * (1.0 - max(0.0, (y - 302) / 22.0))
            else:
                base_rgba[y, :, 3] = 0.0

        # Cirros voxel distantes sutis no ceu alto (somente dentro de sky_soft > 0.7) que derivam entre Q1..Q3
        cirrus_bands = [
            (180, 54, 150, 12),
            (460, 38, 190, 14),
            (720, 76, 130, 10),
            (310, 108, 120, 10),
        ]
        for q in (1, 2, 3):
            q_arr = base_rgba.copy()
            drift = (q - 1) * 8
            glow = (-1.5, 0.0, 2.0)[q - 1]
            q_arr[:298, :, :3] = np.clip(q_arr[:298, :, :3] + glow, 0.0, 255.0)
            for cx0, cy0, cw, ch in cirrus_bands:
                cx = (cx0 + drift + b_idx * 35) % (w - 180)
                ux = np.maximum(0.0, 1.0 - ((xx_g - cx) / (cw * 0.5)) ** 2)
                uy = np.maximum(0.0, 1.0 - ((yy_g - cy0) / (ch * 0.5)) ** 2)
                w_c = (ux * uy) * (sky_soft ** 2) * 0.28
                q_arr[:, :, :3] = (1.0 - w_c[:, :, None]) * q_arr[:, :, :3] + w_c[:, :, None] * 255.0
            Image.fromarray(np.clip(q_arr, 0, 255).astype(np.uint8), mode="RGBA").save(
                out_dir / f"horizonte_bioma{b_idx}_q{q}.png"
            )


def make_living_biome_backgrounds() -> None:
    """Compoe o cenario de fundo (1120x760) diretamente a partir de raw_bioma{1..4}.png."""
    out_dir = ASSETS_DIR / "09_cenarios_vivos"
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1120, 760

    yy, xx = np.mgrid[0:h, 0:w]
    y_norm = yy.astype(np.float32) / float(h)
    x_norm = xx.astype(np.float32) / float(w)
    corridor = (y_norm >= 0.40) & (y_norm <= 0.86) & (np.abs(x_norm - 0.5) <= 0.24)

    for b_idx in range(1, 5):
        raw_path = out_dir / f"raw_bioma{b_idx}.png"
        if not raw_path.exists():
            raise FileNotFoundError(f"Base do bioma {b_idx} ausente em {out_dir}")

        top_base = Image.open(raw_path).convert("RGB")
        top_fitted = ImageOps.fit(top_base, (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.52))
        arr = np.array(top_fitted, dtype=np.float32)

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        raw_water = corridor & (b > r * 1.14) & (b > g * 0.98) & (b > 95.0)
        soft_mask_img = Image.fromarray((raw_water.astype(np.uint8) * 255), mode="L").filter(
            ImageFilter.BoxBlur(4)
        )
        water_alpha = (np.array(soft_mask_img, dtype=np.float32) / 255.0)[:, :, None]

        for q in (1, 2, 3):
            phase = (q - 1) * (2.0 * np.pi / 3.0)
            wave = np.sin(yy * 0.14 + xx * 0.025 + phase) + 0.5 * np.cos(yy * 0.24 - xx * 0.03 + phase)
            glint = np.clip((wave - 0.35) * 9.0, -3.0, 11.0)[:, :, None] * water_alpha
            frame = np.clip(arr + np.concatenate([glint * 0.75, glint * 0.90, glint * 1.15], axis=2), 0, 255)
            Image.fromarray(frame.astype(np.uint8), mode="RGB").convert("RGBA").save(
                out_dir / f"bioma{b_idx}_vivo_q{q}.png"
            )


def make_horizon_relief_layers() -> None:
    """Gera 8 camadas transparentes 1200x360 RGBA com bruma atmosferica suave nas laterais do horizonte."""
    out_dir = ASSETS_DIR / "09_cenarios_vivos"
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1200, 360

    tints = {
        1: (238, 250, 255),  # Amazonia: bruma matinal leve sobre as copas
        2: (255, 246, 224),  # Cerrado: bruma dourada suave nas chapadas
        3: (242, 252, 250),  # Pantanal: neblina úmida suave nas bordas
        4: (238, 248, 255),  # Mata Atlantica: bruma costeira leve
    }

    for b_idx in range(1, 5):
        r, g, b = tints[b_idx]
        for q in (1, 2):
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            shift = 0 if q == 1 else 6

            wisps = [
                (64 + shift, 74, 152, 28, 30),
                (148 + shift, 96, 176, 32, 36),
                (212 + shift, 66, 128, 24, 28),
                (944 - shift, 70, 140, 26, 28),
                (1038 - shift, 92, 184, 34, 38),
                (1108 - shift, 64, 128, 24, 30),
            ]
            for cx, cy, rx, ry, alpha in wisps:
                x0 = max(4, cx - rx // 2)
                y0 = max(4, cy - ry // 2)
                x1 = min(w - 4, cx + rx // 2)
                y1 = min(h - 4, cy + ry // 2)
                draw.ellipse([x0, y0, x1, y1], fill=(r, g, b, alpha))

            im = im.filter(ImageFilter.GaussianBlur(6))
            im.save(out_dir / f"relevo_bioma{b_idx}_q{q}.png")


def _border_flood_background(rgb: np.ndarray, min_lum: int = 224, max_sat: int = 24) -> np.ndarray:
    """Identifica o fundo branco externo conectado as bordas preservando paredes claras internas."""
    h, w, _ = rgb.shape
    cmax = rgb.max(axis=2)
    cmin = rgb.min(axis=2)
    is_cand = (cmin >= min_lum) & ((cmax - cmin) <= max_sat)
    visited = np.zeros((h, w), dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(w):
        if is_cand[0, x] and not visited[0, x]:
            visited[0, x] = True
            queue.append((0, x))
        if is_cand[h - 1, x] and not visited[h - 1, x]:
            visited[h - 1, x] = True
            queue.append((h - 1, x))
    for y in range(h):
        if is_cand[y, 0] and not visited[y, 0]:
            visited[y, 0] = True
            queue.append((y, 0))
        if is_cand[y, w - 1] and not visited[y, w - 1]:
            visited[y, w - 1] = True
            queue.append((y, w - 1))
    while queue:
        cy, cx = queue.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and is_cand[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))
    return visited


def _punch_neutral_white_holes(rgb: np.ndarray, mask_fg: np.ndarray) -> np.ndarray:
    """Remove pequenos vaos de fundo branco presos entre galhos/arcos sem afetar paredes creme."""
    h, w, _ = rgb.shape
    cmax = rgb.max(axis=2)
    cmin = rgb.min(axis=2)
    hole_cand = mask_fg & (cmin >= 242) & ((cmax - cmin) <= 12)
    seen = np.zeros((h, w), dtype=bool)
    out_fg = mask_fg.copy()
    ys, xs = np.nonzero(hole_cand)
    for sy, sx in zip(ys.tolist(), xs.tolist()):
        if seen[sy, sx]:
            continue
        q = deque([(sy, sx)])
        seen[sy, sx] = True
        pixels = []
        while q:
            cy, cx = q.popleft()
            pixels.append((cy, cx))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and hole_cand[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(pixels) <= 35000:
            for py, px in pixels:
                out_fg[py, px] = False
    return out_fg


def _segment_3d_prop_sheet(raw_path: Path) -> list[Image.Image]:
    """Separa os 3 objetos 3D Minecraft voxel isolados de raw_props_bioma{i}.png em recortes RGBA limpos."""
    rgb = np.array(Image.open(raw_path).convert("RGB"))
    bg = _border_flood_background(rgb)
    fg = ~bg
    h, w = fg.shape
    comp_id = np.zeros((h, w), dtype=np.int32)
    comps: list[tuple[float, tuple[int, int, int, int], np.ndarray]] = []
    cid = 0
    ys, xs = np.nonzero(fg)
    for sy, sx in zip(ys.tolist(), xs.tolist()):
        if comp_id[sy, sx] != 0:
            continue
        cid += 1
        q = deque([(sy, sx)])
        comp_id[sy, sx] = cid
        pixels = []
        sum_x = 0
        min_x = max_x = sx
        min_y = max_y = sy
        while q:
            cy, cx = q.popleft()
            pixels.append((cy, cx))
            sum_x += cx
            if cx < min_x:
                min_x = cx
            if cx > max_x:
                max_x = cx
            if cy < min_y:
                min_y = cy
            if cy > max_y:
                max_y = cy
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and fg[ny, nx] and comp_id[ny, nx] == 0:
                    comp_id[ny, nx] = cid
                    q.append((ny, nx))
        if len(pixels) >= 2000:
            bw, bh = max_x - min_x + 1, max_y - min_y + 1
            sub_fg = np.zeros((bh, bw), dtype=bool)
            for py, px in pixels:
                sub_fg[py - min_y, px - min_x] = True
            comps.append((sum_x / len(pixels), (min_x, min_y, max_x + 1, max_y + 1), sub_fg))

    comps.sort(key=lambda item: item[0])
    if len(comps) != 3:
        raise RuntimeError(f"Esperados 3 componentes em {raw_path.name}, encontrados {len(comps)}")

    crops_rgba: list[Image.Image] = []
    for _, (x0, y0, x1, y1), sub_fg in comps:
        sub_rgb = rgb[y0:y1, x0:x1].copy()
        clean_fg = _punch_neutral_white_holes(sub_rgb, sub_fg)
        alpha = np.where(clean_fg, 255, 0).astype(np.uint8)
        # Suaviza eventual halo branco na borda 1px externa
        padded = np.pad(clean_fg, 1, mode="constant", constant_values=False)
        outer_ring = clean_fg & (~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]))
        cmax = sub_rgb.max(axis=2)
        cmin = sub_rgb.min(axis=2)
        white_fringe = outer_ring & (cmin >= 188) & ((cmax - cmin) <= 32)
        alpha[white_fringe] = np.clip(255.0 - (cmin[white_fringe].astype(np.float32) - 172.0) * 3.2, 0.0, 255.0).astype(
            np.uint8
        )
        rgba = np.dstack([sub_rgb, alpha])
        crops_rgba.append(Image.fromarray(rgba, mode="RGBA"))
    return crops_rgba


def _compose_240_prop(prop_rgba: Image.Image, add_ground_shadow: bool = True) -> Image.Image:
    """Enquadra o recorte 3D voxel em 240x240 RGBA com ancora em (120, 176) e sombra suave opcional."""
    bbox = prop_rgba.getbbox()
    if bbox is None:
        return Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    tight = prop_rgba.crop(bbox)
    sw, sh = tight.size
    scale = min(192.0 / max(1, sw), 164.0 / max(1, sh))
    nw, nh = max(16, int(round(sw * scale))), max(16, int(round(sh * scale)))
    resized = tight.resize((nw, nh), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    if add_ground_shadow:
        sh_layer = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
        sh_draw = ImageDraw.Draw(sh_layer)
        sh_rx = min(84, max(32, int(nw * 0.44)))
        sh_draw.ellipse([120 - sh_rx, 176 - 11, 120 + sh_rx, 176 + 13], fill=(14, 24, 34, 72))
        sh_layer = sh_layer.filter(ImageFilter.BoxBlur(3))
        canvas = Image.alpha_composite(canvas, sh_layer)

    px = 120 - nw // 2
    py = 178 - nh  # Base do objeto pousada sobre o centro da sombra (py=176)
    canvas.paste(resized, (px, max(4, py)), resized)
    return canvas


def _animate_prop_frame2(base_im: Image.Image, b_idx: int, p_idx: int) -> Image.Image:
    """Gera quadro 2 com micro-animacao natural coerente com o objeto 3D (flutuacao, brisa ou brilho)."""
    arr = np.array(base_im, dtype=np.uint8)
    h, w, _ = arr.shape
    out = arr.copy()

    if (b_idx, p_idx) in ((1, 2), (3, 2)):
        # Barcos fluviais (Amazonia e Pantanal): flutuacao suave (-2 px vertical) + cintilacao azul na linha d'agua
        out[2:h - 12, :, :] = arr[4:h - 10, :, :]
        ys = np.arange(h)[:, None]
        is_water = (out[:, :, 3] > 120) & (out[:, :, 2] > out[:, :, 0] + 15) & (ys >= 136)
        out[is_water, 0] = np.clip(out[is_water, 0].astype(np.int32) + 18, 0, 255).astype(np.uint8)
        out[is_water, 1] = np.clip(out[is_water, 1].astype(np.int32) + 22, 0, 255).astype(np.uint8)
        out[is_water, 2] = np.clip(out[is_water, 2].astype(np.int32) + 24, 0, 255).astype(np.uint8)
    elif (b_idx, p_idx) in ((1, 1), (1, 3), (2, 1), (2, 2), (3, 1), (3, 3), (4, 1), (4, 3)):
        # Arvores e palmeiras (inclui Palmeira B4-P3): base fixa + copa alta balancando na brisa + brilho solar
        out[:, :, :] = 0
        out[125:, :, :] = arr[125:, :, :]
        for y in range(125):
            shift = 2 if y < 65 else (1 if y < 100 else 0)
            if shift == 0:
                out[y] = arr[y]
            else:
                out[y, shift:] = arr[y, : w - shift]
        foliage = (out[:, :, 3] > 160) & (np.arange(h)[:, None] < 115) & ((out[:, :, 1] > 120) | (out[:, :, 0] > 180))
        out[foliage, :3] = np.clip(out[foliage, :3].astype(np.int32) + 10, 0, 255).astype(np.uint8)
    else:
        # Pier e construcoes coloniais: brilho suave nas flores/cruz/janelas e leve reflexo
        warm = (out[:, :, 3] > 180) & (out[:, :, 0] > 195) & (out[:, :, 1] > 140)
        out[warm, 0] = np.clip(out[warm, 0].astype(np.int32) + 16, 0, 255).astype(np.uint8)
        out[warm, 1] = np.clip(out[warm, 1].astype(np.int32) + 14, 0, 255).astype(np.uint8)
        water_base = (out[:, :, 3] > 120) & (out[:, :, 2] > out[:, :, 0] + 15) & (np.arange(h)[:, None] >= 136)
        out[water_base, :3] = np.clip(out[water_base, :3].astype(np.int32) + 16, 0, 255).astype(np.uint8)

    return Image.fromarray(out, mode="RGBA")


def _soften_water_pedestal(im_rgba: Image.Image) -> Image.Image:
    """Remove integralmente a base retangular de agua ciano dos barcos para flutuarem limpos sobre o rio Mode-7."""
    arr = np.array(im_rgba, dtype=np.float32)
    h, w, _ = arr.shape
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    yy = np.arange(h)[:, None]
    cmin = np.minimum(np.minimum(r, g), b)
    cmax = np.maximum(np.maximum(r, g), b)
    sat = cmax - cmin

    # Identifica placa ciano/turquesa/branco-azulada em volta do casco de madeira
    is_water = (
        (yy >= int(h * 0.42))
        & (a > 10)
        & (
            ((b > r * 1.04) & (b >= g * 0.82) & (g > 60.0))
            | ((cmin > 160.0) & (sat < 52.0) & (b >= r - 8.0) & (yy >= int(h * 0.46)))
        )
    )
    if not is_water.any():
        return im_rgba

    # Remove integralmente toda a placa ciano mantendo apenas o barco limpo sobre o rio
    new_a = np.where(is_water, 0.0, a)
    arr[:, :, 3] = np.clip(new_a, 0.0, 255.0)
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def make_distant_vegetation_layers() -> None:
    """Extrai o dossel 3D voxel real da linha do horizonte (1200x240 RGBA) sem blocos 2D chapados."""
    out_dir = ASSETS_DIR / "09_cenarios_vivos"
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 1200, 240

    yy, xx = np.mgrid[0:h, 0:w]
    top_fade = np.clip((yy.astype(np.float32) - 14.0) / 38.0, 0.0, 1.0)
    bottom_fade = np.clip((225.0 - yy.astype(np.float32)) / 60.0, 0.0, 1.0)
    side_fade = np.clip(np.minimum(xx.astype(np.float32) / 90.0, (w - 1.0 - xx.astype(np.float32)) / 90.0), 0.0, 1.0)
    dist_center = np.abs(xx.astype(np.float32) - 600.0)
    center_window = np.clip((dist_center - 155.0) / 90.0, 0.0, 1.0)

    for b_idx in range(1, 5):
        raw_path = out_dir / f"raw_bioma{b_idx}.png"
        if not raw_path.exists():
            raise FileNotFoundError(f"Panorama brasileiro ausente: {raw_path}")
        raw_im = Image.open(raw_path).convert("RGB")
        rw, rh = raw_im.size
        band = raw_im.crop((0, int(rh * 0.26), rw, int(rh * 0.44))).resize((w, h), Image.Resampling.LANCZOS)
        arr = np.array(band, dtype=np.float32)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        is_sky = (b >= g * 0.94) & (b >= r * 1.04) & (b > 135.0)
        is_cloud = (cmin > 195.0) & ((cmax - cmin) < 28.0) & (yy < int(h * 0.65))
        foliage = (~(is_sky | is_cloud)).astype(np.float32) * 255.0
        foliage_soft = np.array(Image.fromarray(foliage.astype(np.uint8), mode="L").filter(ImageFilter.BoxBlur(1.5)), dtype=np.float32) / 255.0

        alpha = np.clip(foliage_soft * top_fade * bottom_fade * side_fade * center_window * 230.0, 0.0, 255.0)
        q1_rgba = np.dstack([arr, alpha]).astype(np.uint8)
        Image.fromarray(q1_rgba, mode="RGBA").save(out_dir / f"floresta_distante_b{b_idx}_q1.png")

        # Quadro 2: brisa sutil de 1 px na metade superior do dossel sem deslocar a base
        q2_rgba = q1_rgba.copy()
        q2_rgba[:140, 1:, :] = q1_rgba[:140, :-1, :]
        Image.fromarray(q2_rgba, mode="RGBA").save(out_dir / f"floresta_distante_b{b_idx}_q2.png")


def make_segmented_river_terrain_slices() -> None:
    """Fatia e retifica os terrenos 3D voxel limpos em 24 faixas 1200x180 RGBA de largura total (v1, v2, v3)."""
    out_dir = ASSETS_DIR / "09_cenarios_vivos"
    seg_dir = out_dir / "segmentos_25d"
    seg_dir.mkdir(parents=True, exist_ok=True)
    w_out, h_out = 1200, 180

    # Envelope vertical ultra-suave (36px topo/base) + 100% opacidade horizontal em [40..1160] para cobrir [-240,+240]
    yy_o, xx_o = np.mgrid[0:h_out, 0:w_out]
    v_top = np.clip(yy_o.astype(np.float32) / 36.0, 0.0, 1.0)
    v_bot = np.clip((h_out - 1.0 - yy_o.astype(np.float32)) / 36.0, 0.0, 1.0)
    v_env = np.sin(0.5 * np.pi * np.minimum(v_top, v_bot)) ** 0.85
    side_env = np.clip(np.minimum(xx_o.astype(np.float32) / 40.0, (w_out - 1.0 - xx_o.astype(np.float32)) / 40.0), 0.0, 1.0)
    env_alpha = np.clip(v_env * side_env, 0.0, 1.0)

    # Zonas de profundidade com largura do canal ajustada a Escala_rio(d)=84+32*p(d) e Largura(d)=26+106*p(d)
    zone_specs = [
        (1, 210, 410, 36.0, 52.0),   # v1 Distante: canal 72..104 px
        (2, 415, 645, 52.0, 78.0),   # v2 Media: canal 104..156 px
        (3, 640, 885, 78.0, 114.0),  # v3 Proxima: canal 156..228 px
    ]

    for b_idx in range(1, 5):
        terr_path = out_dir / f"raw_terreno_bioma{b_idx}.png"
        if not terr_path.exists():
            raise FileNotFoundError(f"Terreno limpo ausente: {terr_path}")
        terr = np.array(Image.open(terr_path).convert("RGB"), dtype=np.float32)
        th, tw, _ = terr.shape
        r, g, b = terr[:, :, 0], terr[:, :, 1], terr[:, :, 2]

        # Detecta eixo e meia-largura do canal de agua por linha com suavizacao vertical
        water_bin = (
            ((b > r * 1.12) & (b >= g * 0.90) & (g > 85.0))
            | ((np.abs(np.arange(tw)[None, :] - tw * 0.5) < 165) & (np.arange(th)[:, None] > 460) & (r > 200) & (g > 205) & (b > 205))
        )
        cx_rows = np.full(th, tw * 0.5, dtype=np.float32)
        hw_rows = np.linspace(55.0, 240.0, th).astype(np.float32)
        for ry in range(150, th):
            cols_w = np.where(water_bin[ry, 300:900])[0] + 300
            if len(cols_w) >= 24:
                c_l, c_r = float(cols_w[0]), float(cols_w[-1])
                cx_rows[ry] = 0.5 * (c_l + c_r)
                hw_rows[ry] = max(36.0, 0.5 * (c_r - c_l + 1.0))
        # Suaviza perfil do rio com janela ampla (35 linhas) para bordas retas em perspectiva
        k_smooth = np.ones(35, dtype=np.float32) / 35.0
        cx_rows = np.convolve(np.pad(cx_rows, 17, mode="edge"), k_smooth, mode="valid")
        hw_rows = np.convolve(np.pad(hw_rows, 17, mode="edge"), k_smooth, mode="valid")

        x_out = xx_o[0, :].astype(np.float32)
        cx_out = 600.0

        for v_idx, y0_src, y1_src, hw0_tgt, hw1_tgt in zone_specs:
            y_src_rows = np.linspace(float(y0_src), float(y1_src), h_out)
            slice_rgb = np.zeros((h_out, w_out, 3), dtype=np.float32)
            water_mask = np.zeros((h_out, w_out), dtype=np.float32)

            for row_i in range(h_out):
                t_row = row_i / float(h_out - 1)
                sy = y_src_rows[row_i]
                sy0 = int(min(th - 2, max(0, math.floor(sy))))
                fy = sy - sy0
                row_rgb = (1.0 - fy) * terr[sy0] + fy * terr[sy0 + 1]
                cx_s = (1.0 - fy) * cx_rows[sy0] + fy * cx_rows[sy0 + 1]
                hw_s = (1.0 - fy) * hw_rows[sy0] + fy * hw_rows[sy0 + 1]

                hw_tgt = hw0_tgt + (hw1_tgt - hw0_tgt) * t_row
                src_l = cx_s - hw_s
                src_r = cx_s + hw_s
                dst_l = cx_out - hw_tgt
                dst_r = cx_out + hw_tgt

                sx = np.empty(w_out, dtype=np.float32)
                m_left = x_out < dst_l
                m_mid = (~m_left) & (x_out <= dst_r)
                m_right = x_out > dst_r

                sx[m_left] = (x_out[m_left] / max(1.0, dst_l)) * max(1.0, src_l)
                sx[m_mid] = src_l + ((x_out[m_mid] - dst_l) / max(1.0, dst_r - dst_l)) * (src_r - src_l)
                sx[m_right] = src_r + ((x_out[m_right] - dst_r) / max(1.0, (w_out - 1) - dst_r)) * max(1.0, (tw - 1) - src_r)

                sx0 = np.clip(np.floor(sx).astype(np.int32), 0, tw - 2)
                fx = (sx - sx0)[:, None]
                slice_rgb[row_i] = (1.0 - fx) * row_rgb[sx0] + fx * row_rgb[sx0 + 1]

                # Mascara suave estrita dentro da agua para adveccao exclusiva da correnteza
                dist_in = (hw_tgt - np.abs(x_out - cx_out)) / 8.0
                water_mask[row_i] = np.clip(dist_in, 0.0, 1.0)

            for q in (1, 2):
                frame_rgb = slice_rgb.copy()
                phase = (q - 1) * math.pi
                ripple = (
                    np.sin(yy_o * 0.20 + phase + np.abs(xx_o - 600.0) * 0.03)
                    + 0.45 * np.cos(yy_o * 0.34 - phase - xx_o * 0.04)
                )
                glint = (np.clip((ripple - 0.30) * 11.0, -4.0, 13.0) * water_mask)[:, :, None]
                frame_rgb = np.clip(
                    frame_rgb + np.concatenate([glint * 0.72, glint * 0.88, glint * 1.15], axis=2),
                    0.0,
                    255.0,
                )
                if q == 2:
                    # Adveccao longitudinal discreta de 4 px somente no interior do canal de agua
                    adv = np.roll(frame_rgb, 4, axis=0)
                    blend_w = (water_mask * np.clip(yy_o / 18.0, 0.0, 1.0) * np.clip((h_out - 1.0 - yy_o) / 18.0, 0.0, 1.0))[:, :, None]
                    frame_rgb = np.clip(0.55 * frame_rgb + 0.45 * adv * blend_w + 0.45 * frame_rgb * (1.0 - blend_w), 0.0, 255.0)

                rgba = np.dstack([frame_rgb, env_alpha * 255.0]).astype(np.uint8)
                Image.fromarray(rgba, mode="RGBA").save(
                    seg_dir / f"segmento_rio_b{b_idx}_v{v_idx}_q{q}.png"
                )


def make_animated_ground_props() -> None:
    """Extrai os 12 props 3D Minecraft voxel gerados com base nos cenarios e cria 24 quadros 240x240 RGBA."""
    prop_dir = ASSETS_DIR / "09_cenarios_vivos" / "props"
    prop_dir.mkdir(parents=True, exist_ok=True)

    for b_idx in range(1, 5):
        raw_sheet = prop_dir / f"raw_props_bioma{b_idx}.png"
        if not raw_sheet.exists():
            raise FileNotFoundError(f"Folha de props 3D ausente: {raw_sheet}")
        crops = _segment_3d_prop_sheet(raw_sheet)
        for p_idx, crop_rgba in enumerate(crops, start=1):
            # Substitui antiga ponte com vitorias-regias (B1-P3) por Touceira de Acaizeiro Amazonico 3D limpa
            if b_idx == 1 and p_idx == 3:
                acai_raw = prop_dir / "raw_acaizeiro_b1.png"
                if acai_raw.exists():
                    crop_rgba = _cutout_white_studio_voxel(
                        acai_raw,
                        min_lum=230,
                        max_sat=20,
                        punch_holes=True,
                        max_hole_px=14000,
                    )
            # Substitui o antigo barco com cachoeira (B4-P3) por Palmeira Real 3D Voxel limpa da Mata Atlantica
            if b_idx == 4 and p_idx == 3:
                palm_raw = prop_dir / "raw_palmeira_b4.png"
                if palm_raw.exists():
                    crop_rgba = _cutout_white_studio_voxel(
                        palm_raw,
                        min_lum=228,
                        max_sat=22,
                        punch_holes=True,
                        max_hole_px=14000,
                    )
            # Remove cubo laranja artificial da base dos Buritis (B2 P2) para assentar troncos diretamente no solo
            if b_idx == 2 and p_idx == 2:
                arr_c = np.array(crop_rgba, dtype=np.uint8)
                h_c = arr_c.shape[0]
                cut_y = int(round(h_c * 0.755))
                arr_c[cut_y:, :, 3] = 0
                crop_rgba = Image.fromarray(arr_c, mode="RGBA")
            is_water_prop = (b_idx, p_idx) in ((1, 2), (3, 2))
            q1 = _compose_240_prop(crop_rgba, add_ground_shadow=False)
            if is_water_prop:
                q1 = _soften_water_pedestal(q1)
            q2 = _animate_prop_frame2(q1, b_idx, p_idx)
            q1.save(prop_dir / f"b{b_idx}_prop{p_idx}_q1.png")
            q2.save(prop_dir / f"b{b_idx}_prop{p_idx}_q2.png")


def main() -> None:
    make_breeze_frames()
    make_migratory_bird_frames()
    make_brazilian_biome_birds()
    make_migration_alerts()
    make_sun_frames()
    make_wind_gust_frames()
    make_sharp_needles()
    clean_victory_frame()
    make_clean_menu_cover()
    make_voxel_runway()
    make_fuel_can_frames()
    make_voxel_winged_button("botao_menu_decolar.png", "DECOLAR", "gold")
    make_voxel_winged_button("botao_menu_guia.png", "GUIA", "cyan")
    make_voxel_winged_button("botao_guia_voltar.png", "VOLTAR MENU", "navy")
    make_voxel_winged_button("botao_fim_jogar_novamente.png", "VOAR DE NOVO", "gold")
    make_voxel_winged_button("botao_fim_tentar_novamente.png", "TENTAR DE NOVO", "cyan")
    make_voxel_winged_button("botao_fim_menu.png", "MENU INICIAL", "navy")
    make_living_biome_backgrounds()
    make_clean_horizon_skies()
    make_animated_ground_props()
    make_guide_screen()
    make_landing_end_screens()
    print("Todos os novos assets, cenarios vivos e telas gerados com sucesso em:", ASSETS_DIR)


if __name__ == "__main__":
    main()
