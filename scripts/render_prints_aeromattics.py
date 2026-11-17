"""
Gerador de prints de alta resolucao e paineis matematicos atualizados para o AeroMattics.

Le diretamente os costumes, coordenadas e ativos reais de
AeroMattics_MIT_Parkinson.sb3, renderiza o palco Scratch (480x360 em escala 2x = 960x720)
via Google Chrome headless incluindo o terreno procedural Pen Mode-7 em tempo real,
horizonte limpo dos 4 biomas, Sol, Nuvens e Props presos a coordenada Z Mundo,
gera os paineis graficos em matplotlib (09, 10 e 11) e copia tudo para prints_telas,
documentacao_pdf/imagens e pasta de artefatos.

Autoria: ThyagoToledo
"""

import base64
from io import BytesIO
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

import matplotlib
matplotlib.use("Agg")
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(r"C:\Users\thyag\OneDrive\Desktop\AeroMattics")
SB3_PATH = ROOT / "AeroMattics_MIT_Parkinson.sb3"
CEN_DIR = ROOT / "assets_organizados" / "09_cenarios_vivos"
PROPS_DIR = CEN_DIR / "props"
SEGMENTS_DIR = CEN_DIR / "segmentos_25d"
OUT_DIR = ROOT / "prints_telas"
PDF_IMG_DIR = ROOT / "documentacao_pdf" / "imagens"
ARTIFACT_DIR = Path(r"C:\Users\thyag\.gemini\antigravity\brain\59ff8bae-6f75-4b6b-9345-7ab82f0db383")
CHROME_EXE = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

STAGE_W = 480
STAGE_H = 360
SCALE_2X = 2

PALETTES_MODE7 = {
    1: {
        "fog": (108, 174, 124),
        "grass_a": (62, 144, 52),
        "grass_b": (55, 136, 46),
        "grass_outer": (48, 128, 41),
        "shore": (192, 172, 122),
        "water_a": (62, 162, 212),
        "water_b": (26, 114, 176),
        "glint": (86, 184, 224),
    },
    2: {
        "fog": (162, 168, 102),
        "grass_a": (156, 158, 62),
        "grass_b": (148, 150, 56),
        "grass_outer": (140, 142, 50),
        "shore": (206, 156, 94),
        "water_a": (72, 172, 210),
        "water_b": (32, 122, 172),
        "glint": (96, 192, 226),
    },
    3: {
        "fog": (116, 178, 134),
        "grass_a": (68, 152, 62),
        "grass_b": (61, 144, 56),
        "grass_outer": (54, 136, 50),
        "shore": (212, 198, 152),
        "water_a": (76, 176, 208),
        "water_b": (34, 124, 168),
        "glint": (98, 194, 228),
    },
    4: {
        "fog": (104, 168, 130),
        "grass_a": (56, 140, 54),
        "grass_b": (49, 132, 48),
        "grass_outer": (42, 124, 42),
        "shore": (188, 176, 146),
        "water_a": (58, 156, 210),
        "water_b": (22, 102, 166),
        "glint": (82, 176, 220),
    },
}


def river_world_x_at_z(z_w: float, etapa: int, semente: float) -> float:
    """Curva sinuosa exata do rio no motor Pen e Props Mode-7 (angulos em graus no Scratch)."""
    ang1 = 12.6 * z_w + 63.0 * etapa + 3.6 * semente
    ang2 = 6.3 * z_w
    return 42.0 * math.sin(math.radians(ang1)) + 18.0 * math.cos(math.radians(ang2))


def _mix_fog(rgb: tuple[int, int, int], fog_rgb: tuple[int, int, int], fog_t: float) -> tuple[int, int, int]:
    return (
        int(round(rgb[0] + (fog_rgb[0] - rgb[0]) * fog_t)),
        int(round(rgb[1] + (fog_rgb[1] - rgb[1]) * fog_t)),
        int(round(rgb[2] + (fog_rgb[2] - rgb[2]) * fog_t)),
    )


def _draw_capsule_polyline(
    draw: ImageDraw.ImageDraw,
    pts: list[tuple[float, float, float, tuple[int, int, int]]],
) -> None:
    """Desenha polilinha continua com largura variavel suave (identico ao Pen WebGL sem degraus)."""
    for idx in range(len(pts)):
        x1, y1, rad1, col1 = pts[idx]
        px1, py1 = 240.0 + x1, 180.0 - y1
        if idx > 0:
            x0, y0, rad0, _ = pts[idx - 1]
            px0, py0 = 240.0 + x0, 180.0 - y0
            draw.polygon([(px0 - rad0, py0), (px0 + rad0, py0), (px1 + rad1, py1), (px1 - rad1, py1)], fill=col1)
        if rad1 >= 0.8:
            draw.ellipse([px1 - rad1, py1 - rad1, px1 + rad1, py1 + rad1], fill=col1)


def render_mode7_pen_image(
    fase: int,
    z_mundo: float = 12.0,
    plane_x: float = 0.0,
    semente: float = 42.0,
) -> Image.Image:
    """Rasteriza fielmente os campos calmos + rio em polilinha continua + correnteza periodica sem quebras."""
    pal = PALETTES_MODE7[max(1, min(4, int(fase)))]
    img = Image.new("RGBA", (STAGE_W, STAGE_H), (*pal["fog"], 255))
    draw = ImageDraw.Draw(img)

    # 1) Campos e gramado em ondas simetricas (zero xadrez piscante)
    sy = 28.0
    while sy >= -114.0:
        dy = 33.0 - sy
        step = math.floor(1.8 + dy / 34.0)
        zw = z_mundo + 260.0 / dy
        tz = math.floor(zw * 0.56)
        sx = dy / 70.0
        fog = (((34.0 - dy) / 34.0) ** 2) * 0.92 if dy < 34.0 else 0.0

        rcx_grass = (-0.45 * plane_x) * sx
        tw = max(18.0, 96.0 * sx)

        py_top = int(round(180.0 - (sy + 0.5 * (step + 1.6))))
        py_bot = int(round(180.0 - (sy - 0.5 * (step + 1.6))))

        if dy < 34.0:
            draw.rectangle([0, py_top, STAGE_W, py_bot], fill=_mix_fog(pal["grass_b"], pal["fog"], fog))
        else:
            trim = tz % 4
            base_col = pal["grass_a"] if trim == 0 else (pal["grass_outer"] if trim == 2 else pal["grass_b"])
            draw.rectangle([0, py_top, STAGE_W, py_bot], fill=base_col)
            col_g = pal["grass_b"] if trim == 0 else pal["grass_outer"]
            for s1, s2 in (
                (-240.0, rcx_grass - tw),
                (rcx_grass + tw, 240.0),
            ):
                xl, xr = max(-240.0, s1), min(240.0, s2)
                if xr > xl:
                    draw.rectangle([240.0 + xl, py_top, 240.0 + xr, py_bot], fill=col_g)
        sy -= step

    # 2) Rio 100% continuo em 18 nos conectados (Areia -> Agua Rasa -> Canal Profundo)
    knots = []
    for ri in range(18):
        tk = ri / 17.0
        dy = 4.0 + 144.0 * (0.35 * tk + 0.65 * tk * tk)
        sy_k = 33.0 - dy
        zw = z_mundo + 260.0 / dy
        sx = dy / 70.0
        rcx = (river_world_x_at_z(zw, fase, semente) - 0.45 * plane_x) * sx
        rhw = max(3.2, (26.0 + 6.0 * math.sin(math.radians(8.6 * zw))) * sx)
        shw = max(1.8, 9.5 * sx)
        fog = (((34.0 - dy) / 34.0) ** 2) * 0.92 if dy < 34.0 else 0.0
        knots.append((rcx, sy_k, rhw, shw, fog))

    _draw_capsule_polyline(draw, [(rcx, sy_k, rhw + shw, _mix_fog(pal["shore"], pal["fog"], fog)) for rcx, sy_k, rhw, shw, fog in knots])
    _draw_capsule_polyline(draw, [(rcx, sy_k, rhw, _mix_fog(pal["water_a"], pal["fog"], fog)) for rcx, sy_k, rhw, shw, fog in knots])
    _draw_capsule_polyline(draw, [(rcx, sy_k, 0.80 * rhw, _mix_fog(pal["water_b"], pal["fog"], fog)) for rcx, sy_k, rhw, shw, fog in knots])

    # 3) Correnteza em loop periodico perfeito (8 filetes seguindo o curso exato do rio)
    flux = (z_mundo * 2.1) % 24.0
    for ri in range(8):
        zrel = 2.4 + ((ri * 3.0 + (24.0 - flux)) % 24.0)
        ulat = 0.34 * math.sin(math.radians(135.0 * ri + 42.0 * fase))
        pts_s = []
        for dz in (1.2, 0.6, 0.0):
            zr = zrel + dz
            zw = z_mundo + zr
            dy = 260.0 / zr
            sy_s = 33.0 - dy
            sx = dy / 70.0
            rcx = (river_world_x_at_z(zw, fase, semente) - 0.45 * plane_x) * sx
            rhw = max(3.2, (26.0 + 6.0 * math.sin(math.radians(8.6 * zw))) * sx)
            fog_s = max(0.0, min(0.92, (zrel - 8.0) / 18.0))
            col_s = _mix_fog(pal["glint"], pal["water_b"], fog_s)
            rad_s = max(0.75, 0.065 * rhw)
            pts_s.append((rcx + ulat * rhw, sy_s, rad_s, col_s))
        _draw_capsule_polyline(draw, pts_s)

    return img


def parse_svg_dimensions(svg_bytes: bytes) -> tuple[float, float]:
    """Extrai largura e altura intrinsecas do SVG em unidades Scratch."""
    text = svg_bytes.decode("utf-8", errors="replace")
    w_match = re.search(r'\bwidth="([0-9.]+)', text)
    h_match = re.search(r'\bheight="([0-9.]+)', text)
    if w_match and h_match:
        return float(w_match.group(1)), float(h_match.group(1))
    vb_match = re.search(r'\bviewBox="([0-9.\-\s]+)"', text)
    if vb_match:
        parts = [float(p) for p in vb_match.group(1).strip().split()]
        if len(parts) == 4:
            return parts[2], parts[3]
    return float(STAGE_W), float(STAGE_H)


def load_sb3_assets(sb3_path: Path):
    """Carrega project.json, metadados dos alvos e data URIs base64 de todos os costumes."""
    with zipfile.ZipFile(sb3_path, "r") as zf:
        project = json.loads(zf.read("project.json").decode("utf-8"))
        targets = {t["name"]: t for t in project["targets"]}
        costume_cache = {}
        for t in project["targets"]:
            for c in t.get("costumes", []):
                md5ext = c["md5ext"]
                if md5ext in costume_cache:
                    continue
                raw = zf.read(md5ext)
                ext = md5ext.rsplit(".", 1)[-1].lower()
                if ext == "svg":
                    mime = "image/svg+xml"
                    nat_w, nat_h = parse_svg_dimensions(raw)
                elif ext == "png":
                    mime = "image/png"
                    with Image.open(BytesIO(raw)) as im:
                        nat_w, nat_h = im.size
                elif ext in ("jpg", "jpeg"):
                    mime = "image/jpeg"
                    with Image.open(BytesIO(raw)) as im:
                        nat_w, nat_h = im.size
                else:
                    mime = "application/octet-stream"
                    nat_w, nat_h = float(STAGE_W), float(STAGE_H)

                b64 = base64.b64encode(raw).decode("ascii")
                costume_cache[md5ext] = {
                    "data_uri": f"data:{mime};base64,{b64}",
                    "nat_w": float(nat_w),
                    "nat_h": float(nat_h),
                }
    return project, targets, costume_cache


def build_sprite_element(
    targets: dict,
    costume_cache: dict,
    target_name: str,
    costume_idx: int,
    sx: float,
    sy: float,
    size_pct: float = 100.0,
    direction: float = 90.0,
    opacity: float = 1.0,
) -> str:
    """Calcula posicionamento e rotacao/espelhamento CSS exatos do Scratch 3.0."""
    target = targets[target_name]
    costume = target["costumes"][costume_idx]
    asset = costume_cache[costume["md5ext"]]
    rot_style = target.get("rotationStyle", "all around")

    res = float(costume.get("bitmapResolution", 1) or 1)
    cx = float(costume.get("rotationCenterX", asset["nat_w"] / 2.0)) / res
    cy = float(costume.get("rotationCenterY", asset["nat_h"] / 2.0)) / res
    log_w = asset["nat_w"] / res
    log_h = asset["nat_h"] / res

    scale = float(size_pct) / 100.0
    disp_w = log_w * scale
    disp_h = log_h * scale
    disp_cx = cx * scale
    disp_cy = cy * scale

    ax = (STAGE_W / 2.0) + float(sx)
    ay = (STAGE_H / 2.0) - float(sy)
    left = ax - disp_cx
    top = ay - disp_cy

    if rot_style == "left-right":
        transform = "scaleX(-1)" if float(direction) < 0 else "scaleX(1)"
    else:
        rot_deg = float(direction) - 90.0
        transform = f"rotate({rot_deg:.2f}deg)"

    style = (
        f"position:absolute;"
        f"left:{left:.2f}px;"
        f"top:{top:.2f}px;"
        f"width:{disp_w:.2f}px;"
        f"height:{disp_h:.2f}px;"
        f"transform-origin:{disp_cx:.2f}px {disp_cy:.2f}px;"
        f"transform:{transform};"
        f"opacity:{opacity:.3f};"
        f"pointer-events:none;"
    )
    return f'<img src="{asset["data_uri"]}" style="{style}" alt="{target_name}"/>'


def add_hud_layers(
    elements: list[str],
    targets: dict,
    costume_cache: dict,
    *,
    pontos: int = 0,
    tempo: int = 40,
    vidas: int = 5,
    fase: int = 1,
    combustivel: float = 100.0,
    estabilidade: float = 0.0,
) -> None:
    """Adiciona painel inferior, ponteiros de COMB.% e ESTAB., digitos base-10 e rotulos."""
    elements.append(build_sprite_element(targets, costume_cache, "HUD · painel", 0, 0, 0, 100))

    dir_comb = 2.7 * max(0.0, min(100.0, float(combustivel))) - 45.0
    dir_estab = 90.0 + 1.15 * max(-95.0, min(95.0, float(estabilidade)))
    elements.append(build_sprite_element(targets, costume_cache, "HUD · ponteiro combustível", 0, -45, -143, 82, dir_comb))
    elements.append(build_sprite_element(targets, costume_cache, "HUD · ponteiro estabilidade", 0, 44, -143, 82, dir_estab))

    pts_str = f"{max(0, min(9999, int(pontos))):04d}"
    for idx, ch in enumerate(pts_str):
        elements.append(build_sprite_element(targets, costume_cache, f"HUD · Pontos {idx}", int(ch), -142 + idx * 10, -127, 54))

    tmp_str = f"{max(0, min(9999, int(tempo))):04d}"
    for idx, ch in enumerate(tmp_str):
        elements.append(build_sprite_element(targets, costume_cache, f"HUD · Tempo {idx}", int(ch), -142 + idx * 10, -159, 54))

    v_digit = max(0, min(9, int(vidas)))
    f_digit = max(1, min(4, int(fase)))
    elements.append(build_sprite_element(targets, costume_cache, "HUD · Vidas 0", v_digit, 198, -127, 54))
    elements.append(build_sprite_element(targets, costume_cache, "HUD · Fase 0", f_digit, 198, -159, 54))

    elements.append(build_sprite_element(targets, costume_cache, "HUD · rótulos", 0, 0, 0, 100))


def compose_flight_scene(
    targets: dict,
    costume_cache: dict,
    *,
    fase: int = 1,
    pontos: int = 0,
    tempo: int = 0,
    vidas: int = 5,
    combustivel: float = 100.0,
    estabilidade: float = 0.0,
    plane_x: float = 0.0,
    plane_y: float = -58.0,
    plane_size: float = 38.0,
    plane_costume: int = 34,
    plane_opacity: float = 1.0,
    sun_frame: int = 0,
    z_mundo: float = 12.0,
    semente: float = 42.0,
    ground_props: list[tuple[float, float, int, int]] | None = None,
    clouds: list[tuple[int, float]] | None = None,
    wind_dir: int = 0,
    wind_streaks: list[tuple[float, float, int]] | None = None,
    fuels: list[tuple[float, float]] | None = None,
    breezes: list[tuple[float, float, int]] | None = None,
    birds: list[tuple[float, float, int]] | None = None,
    migratory_birds: list[tuple[int, float, int, int]] | None = None,
    migration_alert_side: int = 0,
    show_runway: bool = False,
) -> list[str]:
    """Compoe cena fiel ao motor Pen Mode-7 + Horizonte + Sol + Nuvens + Props presos em Z Mundo."""
    pen_im = render_mode7_pen_image(fase, z_mundo=z_mundo, plane_x=plane_x, semente=semente)
    buf = BytesIO()
    pen_im.save(buf, format="PNG")
    pen_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    elements = [
        f'<img src="{pen_uri}" style="position:absolute;left:0px;top:0px;width:{STAGE_W}px;height:{STAGE_H}px;pointer-events:none;" alt="Terreno Procedural"/>'
    ]

    par_cen_x = round(-0.08 * plane_x)
    cen_costume = (fase - 1) * 3 + (sun_frame % 3)
    elements.append(build_sprite_element(targets, costume_cache, "cenario", cen_costume, par_cen_x, 0, 100))

    par_sol_x = round(-0.08 * plane_x)
    elements.append(build_sprite_element(targets, costume_cache, "Sol", sun_frame % 3, 172 + par_sol_x, 130, 48, 90.0, 0.92))

    if clouds:
        for slot_idx, c_d in clouds:
            p_c = max(0.0, min(1.0, float(c_d) ** 1.65))
            cy = 82.0 + 56.0 * p_c
            scale = 18.0 + 20.0 * p_c
            c_dir = 1 if (slot_idx % 2 == 0) else -1
            cx = c_dir * (55.0 + 60.0 * p_c) + round(-0.16 * plane_x)
            cost_idx = 0 if p_c < 0.15 else (1 if p_c < 0.40 else (2 if p_c < 0.70 else 3))
            elements.append(build_sprite_element(targets, costume_cache, "Nuvens", cost_idx, cx, cy, scale, 90.0, 0.72))

    if ground_props:
        # Cada item: (uoff_lateral, z_rel, prop_tipo, q_frame) preso exatamente ao mundo Z
        for uoff, z_rel, prop_tipo, q_frame in sorted(ground_props, key=lambda item: -item[1]):
            if z_rel < 2.0:
                continue
            z_w = z_mundo + z_rel
            dy = 260.0 / z_rel
            prop_y = 33.0 - dy
            esc = min(85.0, 16.0 + 0.55 * dy)
            px = (river_world_x_at_z(z_w, fase, semente) + uoff - 0.45 * plane_x) * (dy / 70.0)
            if prop_y > 22.0 or abs(px) > 235.0:
                continue
            q_eff = 0 if z_rel > 16.0 else (q_frame % 2)
            opacity = 0.58 if z_rel > 16.0 else 1.0
            p_costume = (fase - 1) * 6 + (prop_tipo - 1) * 2 + q_eff
            elements.append(build_sprite_element(
                targets, costume_cache, "Vegetação e Cenário Vivo", p_costume, px, prop_y, esc, 90.0, opacity,
            ))

    if show_runway:
        elements.append(build_sprite_element(targets, costume_cache, "Pista", 0, 0, 0, 100))

    if wind_dir != 0 and wind_streaks:
        w_dir_deg = 90.0 if wind_dir > 0 else -90.0
        for wx, wy, wq in wind_streaks:
            elements.append(build_sprite_element(targets, costume_cache, "Rajada de Vento", wq % 4, wx, wy, 82, w_dir_deg, 0.85))

    par_air_x = round(-0.10 * plane_x)
    if fuels:
        for idx_f, (x0, f_d) in enumerate(fuels):
            p_f = max(0.0, min(1.0, float(f_d) ** 1.65))
            fx = par_air_x + x0 * (0.22 + 0.78 * p_f)
            fy = 44.0 - 148.0 * p_f
            s_fuel = 26.0 + 28.0 * p_f
            op_f = max(0.25, min(1.0, 1.0 - max(0.0, 0.24 - f_d) * 3.2))
            elements.append(build_sprite_element(targets, costume_cache, "Combustível no ar", (sun_frame + idx_f) % 4, fx, fy, s_fuel, 90.0, op_f))

    if breezes:
        for x0, b_d, frame in breezes:
            p_br = max(0.0, min(1.0, float(b_d) ** 1.65))
            by = 44.0 - 148.0 * p_br
            bx = par_air_x + x0 * (0.22 + 0.78 * p_br) + 4.0 * math.sin(math.radians(2.0 * by))
            s_breeze = 24.0 + 32.0 * p_br
            op_br = max(0.25, min(1.0, 1.0 - max(0.0, 0.24 - b_d) * 3.2))
            elements.append(build_sprite_element(targets, costume_cache, "Brisa Favorável", frame % 4, bx, by, s_breeze, 90.0, op_br))

    if birds:
        for x0, bd_d, frame in birds:
            p_bd = max(0.0, min(1.0, float(bd_d) ** 1.65))
            by = 44.0 - 148.0 * p_bd
            bx = par_air_x + x0 * (0.22 + 0.78 * p_bd) + 3.0 * math.sin(math.radians(2.0 * by))
            s_bird = 22.0 + 34.0 * p_bd
            b_costume = (fase - 1) * 4 + (frame % 4)
            op_bd = max(0.25, min(1.0, 1.0 - max(0.0, 0.24 - bd_d) * 3.2))
            elements.append(build_sprite_element(targets, costume_cache, "Pássaros", b_costume, bx, by, s_bird, 90.0, op_bd))

    if migration_alert_side != 0:
        c_idx = 6 if migration_alert_side < 0 else 7
        ax = -204 if migration_alert_side < 0 else 204
        elements.append(build_sprite_element(targets, costume_cache, "Aves Migratórias", c_idx, ax, -48, 58, 90.0, 0.92))

    if migratory_birds:
        for mig_id, t_step, side, frame in migratory_birds:
            y0 = 76.0 + (mig_id - 1) * 12.0
            mx = side * (192.0 - (mig_id - 1) * 22.0 - 0.88 * t_step) + 10.0 * math.sin(
                math.radians(4.0 * t_step + 50.0 * mig_id)
            )
            my = y0 - 1.42 * t_step
            s_mig = 38.0 + 0.25 * (76.0 - my)
            mdir = 90.0 if side < 0 else -90.0
            elements.append(build_sprite_element(targets, costume_cache, "Aves Migratórias", frame % 6, mx, my, s_mig, mdir))

    elements.append(build_sprite_element(
        targets, costume_cache, "Avião", plane_costume,
        plane_x, plane_y, plane_size, 90.0, plane_opacity,
    ))

    add_hud_layers(
        elements, targets, costume_cache,
        pontos=pontos, tempo=tempo, vidas=vidas, fase=fase,
        combustivel=combustivel, estabilidade=estabilidade,
    )
    return elements


def compose_menu_scene(targets: dict, costume_cache: dict) -> list[str]:
    """Compoe a capa inicial do AeroMattics com botoes DECOLAR e GUIA."""
    return [
        build_sprite_element(targets, costume_cache, "cenario", 0, 0, 0, 100),
        build_sprite_element(targets, costume_cache, "Telas", 0, 0, 0, 100),
        build_sprite_element(targets, costume_cache, "Start", 0, -96, -112, 100),
        build_sprite_element(targets, costume_cache, "Botão Guia", 0, 96, -112, 100),
    ]


def compose_guide_scene(targets: dict, costume_cache: dict) -> list[str]:
    """Compoe a tela de Guia ilustrado com botao Voltar Menu."""
    return [
        build_sprite_element(targets, costume_cache, "cenario", 0, 0, 0, 100),
        build_sprite_element(targets, costume_cache, "Telas", 1, 0, 0, 100),
        build_sprite_element(targets, costume_cache, "Botão Guia", 1, 0, -146, 100),
    ]


def compose_end_scene(targets: dict, costume_cache: dict, is_victory: bool = True) -> list[str]:
    """Compoe tela final de pouso limpa e sem HUD inferior."""
    if is_victory:
        return [
            build_sprite_element(targets, costume_cache, "cenario", 9, 0, 0, 100),
            build_sprite_element(targets, costume_cache, "Fundo de encerramento", 0, 0, 0, 100),
            build_sprite_element(targets, costume_cache, "Texto da conclusão", 0, 0, 0, 100),
            build_sprite_element(targets, costume_cache, "Start", 1, -96, -126, 100),
            build_sprite_element(targets, costume_cache, "Botão Guia", 2, 96, -126, 100),
        ]
    return [
        build_sprite_element(targets, costume_cache, "cenario", 6, 0, 0, 100),
        build_sprite_element(targets, costume_cache, "Fundo de encerramento", 1, 0, 0, 100),
        build_sprite_element(targets, costume_cache, "Texto da conclusão", 1, 0, 0, 100),
        build_sprite_element(targets, costume_cache, "Start", 2, -96, -126, 100),
        build_sprite_element(targets, costume_cache, "Botão Guia", 2, 96, -126, 100),
    ]


def render_html_with_chrome(elements: list[str], out_png_path: Path, tmp_dir: str) -> None:
    """Renderiza HTML do palco 480x360 em escala 2x (960x720) usando Chrome headless."""
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    width: 960px;
    height: 720px;
    overflow: hidden;
    background: #0d1b2a;
  }}
  #stage {{
    position: relative;
    width: {STAGE_W}px;
    height: {STAGE_H}px;
    overflow: hidden;
    transform: scale({SCALE_2X});
    transform-origin: top left;
    background: #10253a;
  }}
</style>
</head>
<body>
  <div id="stage">
    {''.join(elements)}
  </div>
</body>
</html>
"""
    html_file = Path(tmp_dir) / f"{out_png_path.stem}.html"
    html_file.write_text(html, encoding="utf-8")

    cmd = [
        str(CHROME_EXE),
        "--headless=new",
        "--disable-gpu",
        "--force-device-scale-factor=1",
        "--window-size=960,720",
        "--hide-scrollbars",
        f"--screenshot={out_png_path}",
        html_file.as_uri(),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0 or not out_png_path.exists():
        raise RuntimeError(f"Falha no Chrome ao renderizar {out_png_path.name}: {res.stderr}")

    with Image.open(out_png_path) as im:
        if im.size != (960, 720):
            resized = im.crop((0, 0, min(960, im.width), min(720, im.height)))
            if resized.size != (960, 720):
                resized = im.resize((960, 720), Image.Resampling.LANCZOS)
            resized.save(out_png_path)


def save_matplotlib_figure(fig: plt.Figure, out_png_path: Path) -> None:
    """Salva figura matplotlib em arquivo temporario evitando problemas com caminhos acentuados/OneDrive."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tmp_chart = Path(tf.name)
    try:
        fig.savefig(tmp_chart, dpi=100)
        shutil.copy2(tmp_chart, out_png_path)
    finally:
        tmp_chart.unlink(missing_ok=True)
    plt.close(fig)


def generate_math_panel_chart(out_png_path: Path) -> None:
    """Gera painel tecnico 2x2 atualizado (09) com controle a 30 FPS, migracao e escalas no ar."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.facecolor": "#f8fafc",
        "figure.facecolor": "#ffffff",
        "axes.edgecolor": "#cbd5e1",
        "axes.grid": True,
        "grid.alpha": 0.35,
        "grid.color": "#94a3b8",
    })

    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.8), dpi=100)
    fig.suptitle(
        "AeroMattics MIT / Reabilitacao Parkinson - Modelos Matematicos de Voo (Atualizado)",
        fontsize=14.2, fontweight="bold", color="#0f172a", y=0.97,
    )

    # (A) Raias radiais x*(0.22+0.78*p) + senoide suave e migracao monotona (115 passos)
    ax = axes[0, 0]
    d_air = np.linspace(0.04, 1.0, 260)
    p_air = d_air ** 1.65
    y_vals = 44.0 - 148.0 * p_air
    x_bird = 68.0 * (0.22 + 0.78 * p_air) + 3.0 * np.sin(np.radians(2.0 * y_vals))
    t_mig = np.linspace(0, 115, 240)
    y_mig_1 = 76.0 - 1.42 * t_mig
    x_mig_1 = -1.0 * (192.0 - 0.88 * t_mig) + 10.0 * np.sin(np.radians(4.0 * t_mig + 50.0))
    y_mig_3 = 100.0 - 1.42 * t_mig
    x_mig_3 = -1.0 * (148.0 - 0.88 * t_mig) + 10.0 * np.sin(np.radians(4.0 * t_mig + 150.0))

    ax.plot(x_bird, y_vals, color="#0284c7", linewidth=2.2, label="Ave Radial: x0*(0.22+0.78p)+3sen(2y)")
    ax.plot(x_mig_1, y_mig_1, color="#ea580c", linewidth=2.3, label="Harpia Real k=1: x = L*(192-0.88t)+10sen(4t+50k)")
    ax.plot(x_mig_3, y_mig_3, color="#fb923c", linewidth=1.6, linestyle="--", label="Harpia Real k=3: travessia paralela sem inversao")
    ax.axvspan(30, 180, color="#10b981", alpha=0.10, label="Corredor livre oposto (x in [+30, +180])")
    ax.set_title("1. Raia Radial p(d)=d^1.65 e Migracao Monotona", fontsize=11.0, fontweight="bold", color="#1e293b")
    ax.set_xlabel("Coordenada Horizontal X (Scratch)")
    ax.set_ylabel("Coordenada Vertical Y")
    ax.set_xlim(-225, 225)
    ax.set_ylim(-108, 108)
    ax.legend(loc="lower right", fontsize=7.4, frameon=True)

    # (B) Filtro passa-baixa estavel a 30 FPS (0.82/0.18, alvo +-1.85, clamp +-2.10)
    ax = axes[0, 1]
    dt = 1.0 / 30.0
    t_sec = np.arange(0, 180) * dt
    alvo = np.where((t_sec >= 1.5) & (t_sec <= 4.0), -1.85, 0.0)
    rng = np.random.default_rng(42)
    raw_in = np.clip(alvo + 1.05 * np.sin(2 * np.pi * 6.0 * t_sec) + rng.normal(0, 0.22, size=len(t_sec)), -1.85, 1.85)
    vx = np.zeros_like(t_sec)
    for i in range(1, len(t_sec)):
        vx[i] = 0.82 * vx[i - 1] + 0.18 * raw_in[i]
    vento = np.where((t_sec >= 1.0) & (t_sec <= 4.4), 1.0, 0.0)
    passo = np.clip(vx + 0.28 * vento, -2.10, 2.10)
    estab = np.clip(52.0 * vento + 22.0 * vx, -95.0, 95.0)

    ax.plot(t_sec, raw_in, color="#94a3b8", linewidth=1.0, alpha=0.80, label="Entrada com tremor (6 Hz,alvo=+-1.85)")
    ax.plot(t_sec, vx, color="#059669", linewidth=2.3, label="Filtro 30 FPS: vx = 0.82*vx + 0.18*alvo")
    ax.plot(t_sec, passo, color="#0d9488", linewidth=1.6, linestyle=":", label="Passo X clamped [-2.10, +2.10]")
    ax2 = ax.twinx()
    ax2.plot(t_sec, estab, color="#0284c7", linewidth=1.8, linestyle="--", label="Estabilidade = 52*Vento + 22*vx")
    ax2.set_ylabel("Indicador ESTAB. (-95..+95)", color="#0284c7", fontsize=8.8)
    ax2.set_ylim(-100, 100)
    ax.set_title("2. Filtro Anti-Tremor Calmo (30 FPS + Clamp +-2.10)", fontsize=11.0, fontweight="bold", color="#1e293b")
    ax.set_xlabel("Tempo (s)")
    ax.set_ylabel("Deslocamento Lateral X (px/frame)")
    ax.set_ylim(-2.4, 2.4)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="lower left", fontsize=7.2, frameon=True)

    # (C) Consumo progressivo de combustivel (0.65/s) + coleta de galoes (+28%)
    ax = axes[1, 0]
    ts = np.linspace(0, 160, 641)
    fuel_old = np.clip(100.0 - 0.11 * ts, 0, 100)
    fuel_new = np.zeros_like(ts)
    cur = 100.0
    dt_sim = ts[1] - ts[0]
    refill_times = [24.0, 62.0, 98.0, 134.0]
    refill_idx = set(int(round(rt / dt_sim)) for rt in refill_times)
    for k in range(len(ts)):
        cur = max(0.0, cur - 0.65 * dt_sim)
        if k in refill_idx:
            cur = min(100.0, cur + 28.0)
        fuel_new[k] = cur

    ax.plot(ts, fuel_old, color="#94a3b8", linewidth=1.8, linestyle=":", label="Antigo (0.11/s): ponteiro quase estatico")
    ax.plot(ts, fuel_new, color="#d97706", linewidth=2.4, label="Novo (0.65/s + galao +28%): movimento visivel")
    ax.axhline(25, color="#dc2626", linewidth=1.2, linestyle="--", label="Limiar de alerta (25%)")
    ax.set_title("3. Dinamica Progressiva do Tanque (4 Fases x 40s)", fontsize=11.0, fontweight="bold", color="#1e293b")
    ax.set_xlabel("Tempo de Voo Total (s)")
    ax.set_ylabel("Combustivel (%)")
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 108)
    ax.legend(loc="lower left", fontsize=7.6, frameon=True)

    # (D) Funcoes afins do HUD + escala de perspectiva p(d) = d^1.65 dos objetos no ar
    ax = axes[1, 1]
    u_pct = np.linspace(0, 100, 101)
    dir_comb = 2.7 * u_pct - 45.0
    estab_norm = np.linspace(-100, 100, 101)
    dir_estab = 90.0 + 1.15 * estab_norm
    d_scale = np.linspace(0.04, 1.0, 101)
    p_scale = d_scale ** 1.65
    y_mig_s = 76.0 - 1.72 * u_pct
    s_bird = 22.0 + 34.0 * p_scale
    s_brisa = 24.0 + 32.0 * p_scale
    s_comb = 26.0 + 28.0 * p_scale
    s_mig = 38.0 + 0.25 * (76.0 - y_mig_s)

    ax.plot(u_pct, dir_comb, color="#d97706", linewidth=2.2, label="COMB.%: Dir = 2.7*v - 45")
    ax.plot(u_pct, dir_estab, color="#0284c7", linewidth=2.0, linestyle="--", label="ESTAB.: Dir = 90 + 1.15*E")
    ax.set_title("4. Funcoes Afins do HUD e Escalas p(d)=d^1.65 no Ar", fontsize=11.0, fontweight="bold", color="#1e293b")
    ax.set_xlabel("Normalizacao u (%) [COMB. 0..100 | Profundidade d: 0.04 -> 1.0]")
    ax.set_ylabel("Direcao Ponteiro (graus)", color="#b45309")
    ax.set_ylim(-65, 255)

    ax2 = ax.twinx()
    ax2.plot(u_pct, s_bird, color="#7c3aed", linewidth=1.8, label="Ave Br. S = 22+34*p(d)")
    ax2.plot(u_pct, s_brisa, color="#0d9488", linewidth=1.8, label="Brisa S = 24+32*p(d)")
    ax2.plot(u_pct, s_comb, color="#ea580c", linewidth=1.8, label="Galao S = 26+28*p(d)")
    ax2.plot(u_pct, s_mig, color="#dc2626", linewidth=1.8, linestyle="-.", label="Harpia S = 38+0.25*(76-y)")
    ax2.set_ylabel("Tamanho Aparente S (%)", color="#6d28d9", fontsize=8.8)
    ax2.set_ylim(18, 92)

    l1, lb1 = ax.get_legend_handles_labels()
    l2, lb2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lb1 + lb2, loc="upper left", fontsize=7.0, frameon=True, ncol=2)

    fig.text(
        0.5, 0.015,
        "Autoria: ThyagoToledo | AeroMattics_MIT_Parkinson.sb3 (HUD Ativo em Decolar/Voar, Controle 30 FPS e Perspectiva no Ar)",
        ha="center", fontsize=9.0, color="#475569",
    )
    plt.tight_layout(rect=[0, 0.035, 1, 0.94])
    save_matplotlib_figure(fig, out_png_path)


def generate_living_scenery_math_panel(out_png_path: Path) -> None:
    """Gera painel matematico dedicado (10) explicando o motor Pen Mode-7, Z Mundo e camadas."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.facecolor": "#f8fafc",
        "figure.facecolor": "#ffffff",
        "axes.edgecolor": "#cbd5e1",
        "axes.grid": True,
        "grid.alpha": 0.35,
        "grid.color": "#94a3b8",
    })

    fig, axes = plt.subplots(2, 2, figsize=(13.6, 10.0), dpi=100)
    fig.suptitle(
        "AeroMattics MIT - Motor Pen Mode-7: Projecao Z = Z_Mundo + 260/dy, Rio Sinuoso e Props Sincronizados",
        fontsize=13.2, fontweight="bold", color="#0f172a", y=0.97,
    )

    # (A) Canal sinuoso X_rio(z) em coordenadas de mundo e faixas de margem
    ax = axes[0, 0]
    z_rel_arr = np.linspace(2.0, 26.0, 260)
    dy_arr = 260.0 / z_rel_arr
    y_arr = 33.0 - dy_arr
    z_mundo_demo = 12.0
    z_w_arr = z_mundo_demo + z_rel_arr
    sx_arr = dy_arr / 70.0
    x_rio_w = 42.0 * np.sin(np.radians(12.6 * z_w_arr + 63.0 * 1 + 3.6 * 42.0)) + 18.0 * np.cos(np.radians(6.3 * z_w_arr))
    rhw_w = np.maximum(3.0 / np.maximum(sx_arr, 1e-4), 26.0 + 6.0 * np.sin(np.radians(8.6 * z_w_arr)))
    x_rio_scr = x_rio_w * sx_arr
    rhw_scr = rhw_w * sx_arr
    shw_scr = 9.0 * sx_arr

    ax.fill_betweenx(
        y_arr,
        x_rio_scr - rhw_scr,
        x_rio_scr + rhw_scr,
        color="#38bdf8", alpha=0.35, label="Canal do Rio (RHW * dy/70)",
    )
    ax.plot(x_rio_scr, y_arr, color="#0284c7", linewidth=2.0, label="Barcos no canal (offset=0)")
    ax.plot(x_rio_scr - rhw_scr - shw_scr, y_arr, color="#ca8a04", linewidth=1.6, linestyle="--", label="Margem/Praia (+-shw)")
    ax.plot(x_rio_scr + rhw_scr + shw_scr, y_arr, color="#ca8a04", linewidth=1.6, linestyle="--")
    ax.plot((x_rio_w - 68.0) * sx_arr, y_arr, color="#059669", linewidth=1.8, linestyle="-.", label="Props nas margens (+-42..94u)")
    ax.plot((x_rio_w + 68.0) * sx_arr, y_arr, color="#059669", linewidth=1.8, linestyle="-.")

    ax.set_title("1. Curva Sinuosa X_rio(z) e Ancoragem dos Props", fontsize=10.8, fontweight="bold", color="#1e293b")
    ax.set_xlabel("Coordenada Horizontal na Tela X (Px = 0)")
    ax.set_ylabel("Varredura Vertical sy = 33 - 260/z_rel")
    ax.set_xlim(-175, 175)
    ax.set_ylim(-102, 28)
    ax.legend(loc="upper right", fontsize=6.7, frameon=True)

    # (B) Curva hiperbolica dy = 260/z_rel, Escala Mode-7 e Neblina Quadratica
    ax = axes[0, 1]
    esc_prop = np.minimum(85.0, 16.0 + 0.55 * dy_arr)
    fog_arr = np.where(dy_arr < 24.0, (((24.0 - dy_arr) / 24.0) ** 2) * 72.0, 0.0)

    ax.plot(z_rel_arr, esc_prop, color="#0284c7", linewidth=2.3, label="Escala Prop = min(85, 16 + 0.55*dy) [%]")
    ax.plot(z_rel_arr, fog_arr, color="#64748b", linewidth=2.0, linestyle=":", label="Neblina Atmosferica Fog(dy) [%]")
    ax.axvline(16.0, color="#ef4444", linewidth=1.6, linestyle="--", label="Limiar LOD/Ghost (z_rel = 16 -> Q1, ghost 42)")
    ax.set_title("2. Perspectiva Mode-7 (260/z_rel) e Neblina Quadratica", fontsize=10.8, fontweight="bold", color="#1e293b")
    ax.set_xlabel("Distancia Relativa z_rel = Z_Prop - Z_Mundo")
    ax.set_ylabel("Escala (%) / Neblina (%)")
    ax.set_xlim(2.0, 26.0)
    ax.set_ylim(0, 100)

    ax2 = ax.twinx()
    ax2.plot(z_rel_arr, y_arr, color="#7c3aed", linewidth=2.1, linestyle="-.", label="Altura Y(z_rel) = 33 - 260/z_rel")
    ax2.set_ylabel("Coordenada Y (Scratch)", color="#6d28d9")
    ax2.set_ylim(-108, 32)

    l1, lb1 = ax.get_legend_handles_labels()
    l2, lb2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lb1 + lb2, loc="center right", fontsize=6.5, frameon=True)

    # (C) Paralaxe da camera em funcao da posicao lateral do aviao
    ax = axes[1, 0]
    px_vals = np.linspace(-180, 180, 121)
    parallax_specs = [
        (-0.08, "#0ea5e9", "-", "C1/C2 Horizonte e Sol (-0.08*Px)"),
        (-0.10, "#f59e0b", "--", "Raias Aereas (-0.10*Px)"),
        (-0.16, "#64748b", ":", "Nuvens Voxel (-0.16*Px)"),
        (-0.45, "#1d4ed8", "-", "Motor Pen Mode-7 e Props (cam_x = 0.45*Px)"),
    ]
    for k_par, col, ls, lbl in parallax_specs:
        ax.plot(px_vals, k_par * px_vals, color=col, linestyle=ls, linewidth=2.0, label=lbl)
    ax.axhline(0, color="#94a3b8", linewidth=0.8)
    ax.axvline(0, color="#94a3b8", linewidth=0.8)
    ax.set_title("3. Paralaxe Multicamada em Posicao X Aviao (Px)", fontsize=10.8, fontweight="bold", color="#1e293b")
    ax.set_xlabel("Posicao Horizontal do Aviao Px (unidades Scratch)")
    ax.set_ylabel("Deslocamento Lateral Aparente (Mundo/Tela)")
    ax.set_xlim(-185, 185)
    ax.set_ylim(-90, 90)
    ax.legend(loc="upper right", fontsize=6.9, frameon=True)

    # (D) Catalogo limpo dos props naturais por bioma (sem sombras falsas/lajes)
    ax = axes[1, 1]
    ax.axis("off")
    ax.set_title("4. Catalogo Natural 3D por Bioma (Sincronizado ao Z Mundo)", fontsize=10.8, fontweight="bold", color="#1e293b")

    catalog_rows = [
        (1, "F1 Amazonia", [(1, "Castanheira (Margem)"), (2, "Barco (No Rio)"), (3, "Acaizeiro (Margem)")]),
        (2, "F2 Cerrado", [(1, "Ipe-Amarelo (Margem)"), (2, "Buriti Limpo (Margem)"), (3, "Igreja Colonial (Margem)")]),
        (3, "F3 Pantanal", [(1, "Caranda (Margem)"), (2, "Chalana (No Rio)"), (3, "Tuiuiu (Margem)")]),
        (4, "F4 Mata Atl.", [(1, "Araucaria (Margem)"), (2, "Casarao Colonial (Margem)"), (3, "Palmeira Real (Margem)")]),
    ]
    row_ys = [0.81, 0.62, 0.43, 0.24]
    col_xs = [0.34, 0.58, 0.82]

    for b_idx, b_title, items in catalog_rows:
        ry = row_ys[b_idx - 1]
        ax.text(0.01, ry, b_title, transform=ax.transAxes, fontsize=8.1, fontweight="bold", color="#0f172a", va="center")
        for idx_c, (p_idx, lbl_item) in enumerate(items):
            cx = col_xs[idx_c]
            q_file = 2 if lbl_item.endswith("Q2") else 1
            img_path = PROPS_DIR / f"b{b_idx}_prop{p_idx}_q{q_file}.png"
            with Image.open(img_path) as pim:
                arr = np.asarray(pim.convert("RGBA"))
            oi = OffsetImage(arr, zoom=0.16)
            ab = AnnotationBbox(oi, (cx, ry + 0.015), xycoords="axes fraction", frameon=False)
            ax.add_artist(ab)
            ax.text(cx, ry - 0.072, lbl_item, transform=ax.transAxes, fontsize=6.6, color="#334155", ha="center")

    ax.text(
        0.50, 0.04,
        "Pen Warp 30 FPS (sy=28..-114) + Pool fixo: 4 Props Z-locked (28.8 Z) + 2 Nuvens + 3 Rajadas + Atores (15 clones max)",
        transform=ax.transAxes, ha="center", va="center", fontsize=6.6, color="#0f172a",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#f1f5f9", "edgecolor": "#cbd5e1"},
    )

    fig.text(
        0.5, 0.015,
        "Autoria: ThyagoToledo | AeroMattics_MIT_Parkinson.sb3 (Motor Pen Mode-7 + Horizonte Limpo + 4 Props Espacados a 30 FPS)",
        ha="center", fontsize=8.6, color="#475569",
    )
    plt.tight_layout(rect=[0, 0.035, 1, 0.94])
    save_matplotlib_figure(fig, out_png_path)


def generate_depth_25d_comparison_panel(out_png_path: Path) -> None:
    """Gera comparativo visual (11) da projecao Mode-7 por profundidade Z e dos 4 biomas."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.facecolor": "#e0f2fe",
        "figure.facecolor": "#ffffff",
        "axes.edgecolor": "#94a3b8",
    })

    fig, axes = plt.subplots(2, 4, figsize=(14.4, 8.8), dpi=100)
    fig.suptitle(
        "AeroMattics MIT - Comparativo Mode-7: Projecao Z Mundo e Composicao Real dos 4 Biomas",
        fontsize=13.5, fontweight="bold", color="#0f172a", y=0.97,
    )

    # Linha 1: Progressao de aproximacao de um conjunto de props sobre o solo Mode-7 da Amazonia
    z_stages = [16.5, 11.5, 7.5, 4.8]
    with Image.open(CEN_DIR / "horizonte_bioma1_q1.png") as im_h1:
        h1_im = im_h1.convert("RGBA").resize((480, 146), Image.Resampling.LANCZOS)
    pen_base = render_mode7_pen_image(1, z_mundo=12.0, plane_x=0.0, semente=42.0)
    with Image.open(PROPS_DIR / "b1_prop1_q1.png") as im_t:
        tree_im = im_t.convert("RGBA")
    with Image.open(PROPS_DIR / "b1_prop2_q1.png") as im_b:
        boat_im = im_b.convert("RGBA")

    for col_idx, z_rel in enumerate(z_stages):
        ax = axes[0, col_idx]
        dy = 260.0 / z_rel
        y_val = 33.0 - dy
        esc = min(85.0, 16.0 + 0.55 * dy)
        z_w = 12.0 + z_rel
        x_rio_w = river_world_x_at_z(z_w, 1, 42.0)
        x_tree = (x_rio_w - 68.0) * (dy / 70.0)
        x_boat = x_rio_w * (dy / 70.0)
        lod_str = "LOD Q1 + Neblina" if z_rel > 16.0 else "LOD Q1/Q2 Nitido"

        comp = pen_base.copy()
        comp.alpha_composite(h1_im, (0, 0))
        ax.set_xlim(-240, 240)
        ax.set_ylim(-140, 100)
        ax.imshow(np.asarray(comp), extent=(-240, 240, -180, 180), zorder=0)

        zoom_p = 0.24 * (esc / 100.0)
        alpha_p = 0.58 if z_rel > 16.0 else 1.0
        ax.add_artist(AnnotationBbox(OffsetImage(np.asarray(tree_im), zoom=zoom_p, alpha=alpha_p), (x_tree, y_val + 8), frameon=False, zorder=4))
        ax.add_artist(AnnotationBbox(OffsetImage(np.asarray(boat_im), zoom=zoom_p * 0.92, alpha=alpha_p), (x_boat, y_val + 4), frameon=False, zorder=4))

        ax.set_title(f"z_rel = {z_rel:.1f} ({lod_str})", fontsize=9.4, fontweight="bold", color="#1e293b")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(
            0.5, 0.03,
            f"dy={dy:.1f} | Y={y_val:.1f} | Esc={esc:.0f}%",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=7.2, color="#0f172a",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "#ffffff", "edgecolor": "#cbd5e1", "alpha": 0.94},
            zorder=8,
        )

    # Linha 2: Composicao real Pen Mode-7 + Horizonte Limpo + Props dos 4 Biomas Brasileiros
    biome_specs = [
        (1, "F1 Amazonia (Castanheira + Barco)", 12.0, [(-68, 5.2, 1), (0, 8.0, 2), (68, 12.0, 1)]),
        (2, "F2 Cerrado (Ipe + Buriti + Igreja)", 14.0, [(-68, 5.4, 1), (68, 8.2, 3), (-42, 12.5, 2)]),
        (3, "F3 Pantanal (Caranda + Chalana + Tuiuiu)", 16.0, [(-68, 5.2, 1), (0, 7.6, 2), (68, 11.4, 3)]),
        (4, "F4 Mata Atl. (Araucaria + Casarao + Palmeira)", 18.0, [(-68, 5.0, 1), (68, 7.8, 2), (-94, 12.2, 3)]),
    ]
    for b_idx, b_title, z_m, prop_layout in biome_specs:
        ax = axes[1, b_idx - 1]
        ax.set_xlim(-240, 240)
        ax.set_ylim(-140, 100)

        pen_b = render_mode7_pen_image(b_idx, z_mundo=z_m, plane_x=0.0, semente=42.0)
        with Image.open(CEN_DIR / f"horizonte_bioma{b_idx}_q1.png") as im_hb:
            hb_im = im_hb.convert("RGBA").resize((480, 146), Image.Resampling.LANCZOS)
        pen_b.alpha_composite(hb_im, (0, 0))
        ax.imshow(np.asarray(pen_b), extent=(-240, 240, -180, 180), zorder=0)

        for idx_p, (uoff, z_rel_p, p_tipo) in enumerate(sorted(prop_layout, key=lambda it: -it[1])):
            dy_p = 260.0 / z_rel_p
            y_p = 33.0 - dy_p
            esc_p = min(85.0, 16.0 + 0.55 * dy_p)
            x_p = (river_world_x_at_z(z_m + z_rel_p, b_idx, 42.0) + uoff) * (dy_p / 70.0)
            with Image.open(PROPS_DIR / f"b{b_idx}_prop{p_tipo}_q1.png") as im_p:
                p_rgba = np.asarray(im_p.convert("RGBA"))
            zoom_p = 0.24 * (esc_p / 100.0)
            ax.add_artist(AnnotationBbox(OffsetImage(p_rgba, zoom=zoom_p), (x_p, y_p + 6), frameon=False, zorder=10 + idx_p))

        ax.set_title(b_title, fontsize=9.2, fontweight="bold", color="#1e293b")
        ax.set_xticks([])
        ax.set_yticks([])

    fig.text(
        0.5, 0.015,
        "Autoria: ThyagoToledo | Comparativo Mode-7 AeroMattics MIT: Terreno Procedural em Tempo Real, Horizonte Limpo e Props 3D Sem Sombras",
        ha="center", fontsize=8.6, color="#475569",
    )
    plt.tight_layout(rect=[0, 0.035, 1, 0.94])
    save_matplotlib_figure(fig, out_png_path)


def main() -> None:
    if not SB3_PATH.exists():
        raise FileNotFoundError(f"Arquivo sb3 nao encontrado: {SB3_PATH}")
    if not CHROME_EXE.exists():
        raise FileNotFoundError(f"Google Chrome nao encontrado: {CHROME_EXE}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_IMG_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    _, targets, costume_cache = load_sb3_assets(SB3_PATH)

    scenes = [
        ("01_menu_principal.png", compose_menu_scene(targets, costume_cache)),
        ("01b_tela_guia_como_jogar.png", compose_guide_scene(targets, costume_cache)),
        ("02_decolagem_pista.png", compose_flight_scene(
            targets, costume_cache,
            fase=1, pontos=0, tempo=0, vidas=5, combustivel=100.0, estabilidade=0.0,
            plane_x=0.0, plane_y=-96.0, plane_size=27.0, plane_costume=34, sun_frame=0,
            z_mundo=1.2,
            clouds=[(0, 0.28), (1, 0.72)], show_runway=True,
        )),
        ("03_fase1_campo_brisa_e_sol.png", compose_flight_scene(
            targets, costume_cache,
            fase=1, pontos=185, tempo=8, vidas=5, combustivel=89.0, estabilidade=-18.0,
            plane_x=-38.0, plane_y=-58.0, plane_size=38.0, plane_costume=4, sun_frame=1,
            z_mundo=12.0,
            ground_props=[(-80.0, 5.4, 1, 0), (0.0, 10.6, 2, 1), (86.0, 17.8, 3, 0)],
            clouds=[(0, 0.25), (1, 0.70)],
            breezes=[(68.0, 0.58, 0)],
            birds=[(-136.0, 0.72, 1)],
            fuels=[(0.0, 0.44)],
        )),
        ("04_fase2_floresta_rajada_vento.png", compose_flight_scene(
            targets, costume_cache,
            fase=2, pontos=490, tempo=15, vidas=5, combustivel=71.0, estabilidade=-64.0,
            plane_x=22.0, plane_y=-58.0, plane_size=38.0, plane_costume=20, sun_frame=2,
            z_mundo=16.5,
            ground_props=[(-80.0, 5.6, 1, 0), (80.0, 11.4, 3, 1), (-86.0, 18.6, 2, 0)],
            clouds=[(0, 0.65), (1, 0.22)],
            wind_dir=-1, wind_streaks=[(-85.0, 72.0, 0), (65.0, 38.0, 1)],
            breezes=[(136.0, 0.54, 1)],
            birds=[(-68.0, 0.66, 0)],
            fuels=[(0.0, 0.40)],
        )),
        ("05_fase3_deserto_migracao_aves.png", compose_flight_scene(
            targets, costume_cache,
            fase=3, pontos=860, tempo=26, vidas=4, combustivel=46.0, estabilidade=28.0,
            plane_x=96.0, plane_y=-58.0, plane_size=38.0, plane_costume=21, sun_frame=0,
            z_mundo=21.0,
            ground_props=[(84.0, 6.2, 1, 0), (0.0, 10.8, 2, 1), (-86.0, 18.2, 3, 1)],
            clouds=[(0, 0.30), (1, 0.78)],
            breezes=[(68.0, 0.48, 2)],
            birds=[(0.0, 0.62, 2)],
            migratory_birds=[(1, 78, -1, 0), (2, 54, -1, 2), (3, 30, -1, 4)],
            migration_alert_side=-1,
            fuels=[(136.0, 0.72)],
        )),
        ("06_fase4_neve_alerta_e_combustivel.png", compose_flight_scene(
            targets, costume_cache,
            fase=4, pontos=1290, tempo=34, vidas=4, combustivel=22.0, estabilidade=48.0,
            plane_x=-18.0, plane_y=-58.0, plane_size=38.0, plane_costume=35, plane_opacity=0.72, sun_frame=1,
            z_mundo=25.5,
            ground_props=[(-80.0, 5.4, 1, 0), (80.0, 11.0, 2, 1), (-86.0, 18.4, 3, 0)],
            clouds=[(0, 0.74), (1, 0.28)],
            wind_dir=1, wind_streaks=[(-75.0, 68.0, 0), (55.0, 34.0, 1)],
            breezes=[(-68.0, 0.46, 0)],
            birds=[(136.0, 0.68, 1)],
            fuels=[(0.0, 0.64)],
        )),
        ("07_tela_vitoria_missao_concluida.png", compose_end_scene(targets, costume_cache, is_victory=True)),
        ("08_tela_fim_de_voo_terapeutico.png", compose_end_scene(targets, costume_cache, is_victory=False)),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        for filename, elements in scenes:
            out_path = OUT_DIR / filename
            render_html_with_chrome(elements, out_path, tmp_dir)
            shutil.copy2(out_path, ARTIFACT_DIR / filename)
            shutil.copy2(out_path, PDF_IMG_DIR / filename)
            print(f"Print gerado: {out_path}")

    chart_name_09 = "09_painel_conceitos_matematicos_mit.png"
    chart_path_09 = OUT_DIR / chart_name_09
    generate_math_panel_chart(chart_path_09)
    shutil.copy2(chart_path_09, ARTIFACT_DIR / chart_name_09)
    shutil.copy2(chart_path_09, PDF_IMG_DIR / chart_name_09)
    print(f"Painel matematico de voo gerado: {chart_path_09}")

    chart_name_10 = "10_painel_matematica_cenario_vivo_mit.png"
    chart_path_10 = OUT_DIR / chart_name_10
    generate_living_scenery_math_panel(chart_path_10)
    shutil.copy2(chart_path_10, ARTIFACT_DIR / chart_name_10)
    shutil.copy2(chart_path_10, PDF_IMG_DIR / chart_name_10)
    print(f"Painel matematico de cenario vivo gerado: {chart_path_10}")

    chart_name_11 = "11_comparativo_profundidade_25d_rio_continuo.png"
    chart_path_11 = OUT_DIR / chart_name_11
    generate_depth_25d_comparison_panel(chart_path_11)
    shutil.copy2(chart_path_11, ARTIFACT_DIR / chart_name_11)
    shutil.copy2(chart_path_11, PDF_IMG_DIR / chart_name_11)
    print(f"Comparativo 2.5D de profundidade e biomas gerado: {chart_path_11}")

    chart_name_14 = "14_passaros_brasileiros_3d_voxel.png"
    chart_path_14 = OUT_DIR / chart_name_14
    generate_birds_showcase_panel(chart_path_14)
    shutil.copy2(chart_path_14, ARTIFACT_DIR / chart_name_14)
    shutil.copy2(chart_path_14, PDF_IMG_DIR / chart_name_14)
    print(f"Catalogo de aves brasileiras 3D voxel gerado: {chart_path_14}")

    antes_dir = ROOT / "backup" / "pre_refinamento_mode7_20261115" / "prints_antes"
    if antes_dir.exists():
        generate_before_after_boards(antes_dir)


def generate_birds_showcase_panel(out_png_path: Path) -> None:
    """Gera prancha exclusiva (14) exibindo as 5 aves brasileiras 3D Voxel unicas e suas animacoes de asa."""
    birds_dir = ROOT / "assets_organizados" / "04_passaros_biomas"
    specs = [
        (
            "Fase 1 - Amazonia: Arara-Vermelha 3D",
            [("Q1 Asas Erguidas", "aeromattics_passaro_bioma1_campo_q1.png"),
             ("Q2 Voo Aberto", "aeromattics_passaro_bioma1_campo_q2.png"),
             ("Q3 Batida Baixo", "aeromattics_passaro_bioma1_campo_q3.png"),
             ("Q4 Recuperacao", "aeromattics_passaro_bioma1_campo_q4.png")],
        ),
        (
            "Fase 2 - Cerrado: Tucano-Toco 3D",
            [("Q1 Asas Erguidas", "aeromattics_passaro_bioma2_floresta_q1.png"),
             ("Q2 Voo Aberto", "aeromattics_passaro_bioma2_floresta_q2.png"),
             ("Q3 Batida Baixo", "aeromattics_passaro_bioma2_floresta_q3.png"),
             ("Q4 Recuperacao", "aeromattics_passaro_bioma2_floresta_q4.png")],
        ),
        (
            "Fase 3 - Pantanal: Tuiuiu Pantaneiro 3D",
            [("Q1 Asas Erguidas", "aeromattics_passaro_bioma3_deserto_q1.png"),
             ("Q2 Voo Aberto", "aeromattics_passaro_bioma3_deserto_q2.png"),
             ("Q3 Batida Baixo", "aeromattics_passaro_bioma3_deserto_q3.png"),
             ("Q4 Recuperacao", "aeromattics_passaro_bioma3_deserto_q4.png")],
        ),
        (
            "Fase 4 - Mata Atlantica: Arara-Azul 3D",
            [("Q1 Asas Erguidas", "aeromattics_passaro_bioma4_neve_q1.png"),
             ("Q2 Voo Aberto", "aeromattics_passaro_bioma4_neve_q2.png"),
             ("Q3 Batida Baixo", "aeromattics_passaro_bioma4_neve_q3.png"),
             ("Q4 Recuperacao", "aeromattics_passaro_bioma4_neve_q4.png")],
        ),
        (
            "Migracao - Brasil: Harpia Real 3D (Harpia harpyja)",
            [("Q1 Ataque Alto", "ave_migratoria_q1.png"),
             ("Q2 Planando", "ave_migratoria_q2.png"),
             ("Q3 Batida Forte", "ave_migratoria_q3.png"),
             ("Q5 Subida", "ave_migratoria_q5.png")],
        ),
    ]

    fig, axes = plt.subplots(5, 4, figsize=(13.6, 12.8), dpi=100)
    fig.suptitle(
        "AeroMattics - Fauna Brasileira 3D Voxel Exclusiva (5 Especies + Quadros de Batida de Asa)",
        fontsize=13.5, fontweight="bold", color="#0f172a", y=0.985,
    )
    for row_idx, (row_title, items) in enumerate(specs):
        for col_idx, (q_label, fname) in enumerate(items):
            ax = axes[row_idx, col_idx]
            ax.set_facecolor("#dbeafe")
            p_im = birds_dir / fname
            if p_im.exists():
                with Image.open(p_im) as im:
                    ax.imshow(np.asarray(im.convert("RGBA")))
            ax.set_title(f"{q_label}" if col_idx > 0 else f"{row_title}\n({q_label})", fontsize=8.8, fontweight="bold", color="#1e293b", pad=3)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor("#93c5fd")
                spine.set_linewidth(1.2)

    fig.text(
        0.5, 0.006,
        "Autoria: ThyagoToledo | AeroMattics_MIT_Parkinson.sb3 (Assets 3D Voxel exclusivos por bioma sem recoloracao generica)",
        ha="center", fontsize=8.8, color="#475569",
    )
    plt.tight_layout(rect=[0, 0.015, 1, 0.968])
    save_matplotlib_figure(fig, out_png_path)


def generate_before_after_boards(antes_dir: Path) -> None:
    """Gera pranchas comparativas ANTES vs DEPOIS lado a lado para inspecao imediata."""
    boards = [
        (
            "12_antes_vs_depois_decolagem_guia_e_rajada.png",
            "ANTES vs DEPOIS - Pista 3D, Brisa sem Xadrez, Vento Nitido e Formulas Reais",
            [
                ("Decolagem (Pista MS-Paint -> Pista 3D Voxel)", "02_decolagem_pista.png"),
                ("Guia (Centro da Brisa com Xadrez -> Nucleo Luminoso)", "01b_tela_guia_como_jogar.png"),
                ("Cerrado + Vento + Horizonte (Arcos -> Limpo)", "04_fase2_floresta_rajada_vento.png"),
                ("Painel MIT 1 (Formulas Lineares -> p(d)=d^1.65)", "09_painel_conceitos_matematicos_mit.png"),
            ],
        ),
        (
            "13_antes_vs_depois_4_biomas_mode7.png",
            "ANTES vs DEPOIS - 4 Biomas Brasileiros (Horizonte Sem Furos + Solo Mode-7 O(1) Calmo)",
            [
                ("Fase 1 - Amazonia", "03_fase1_campo_brisa_e_sol.png"),
                ("Fase 2 - Cerrado", "04_fase2_floresta_rajada_vento.png"),
                ("Fase 3 - Pantanal (Fim do Degrau Branco)", "05_fase3_deserto_migracao_aves.png"),
                ("Fase 4 - Mata Atlantica (Pao de Acucar Integro)", "06_fase4_neve_alerta_e_combustivel.png"),
            ],
        ),
    ]
    for out_name, suptitle, items in boards:
        fig, axes = plt.subplots(4, 2, figsize=(13.6, 17.6), dpi=100)
        fig.suptitle(suptitle, fontsize=14.0, fontweight="bold", color="#0f172a", y=0.992)
        for row_idx, (row_title, fname) in enumerate(items):
            p_old = antes_dir / fname
            p_new = OUT_DIR / fname
            for col_idx, (tag, img_p) in enumerate((("ANTES", p_old), ("DEPOIS", p_new))):
                ax = axes[row_idx, col_idx]
                if img_p.exists():
                    with Image.open(img_p) as im:
                        ax.imshow(np.asarray(im.convert("RGB")))
                color_t = "#b91c1c" if col_idx == 0 else "#047857"
                ax.set_title(f"[{tag}] {row_title}", fontsize=10.2, fontweight="bold", color=color_t, pad=4)
                ax.set_xticks([])
                ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_edgecolor("#fca5a5" if col_idx == 0 else "#34d399")
                    spine.set_linewidth(2.0)

        fig.text(
            0.5, 0.005,
            "Autoria: ThyagoToledo | AeroMattics_MIT_Parkinson.sb3 (Comparativo Antes vs Depois validado em VM 30 FPS)",
            ha="center", fontsize=9.0, color="#475569",
        )
        plt.tight_layout(rect=[0, 0.012, 1, 0.985])
        out_path = OUT_DIR / out_name
        save_matplotlib_figure(fig, out_path)
        shutil.copy2(out_path, ARTIFACT_DIR / out_name)
        shutil.copy2(out_path, PDF_IMG_DIR / out_name)
        print(f"Comparativo Antes vs Depois gerado: {out_path}")


if __name__ == "__main__":
    main()
