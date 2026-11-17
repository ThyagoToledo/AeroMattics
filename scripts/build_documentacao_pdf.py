#!/usr/bin/env python3
"""Compilador oficial de documentacao PDF do AeroMattics (MIT / Parkinson).

Autoria exclusiva: ThyagoToledo
Gera PDFs A4 nativos em UTF-8 TrueType com diagramas, tabelas e capturas reais
a partir dos arquivos e imagens validadas em documentacao_pdf/.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Sequence

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = ROOT / "documentacao_pdf"
IMG_DIR = DOC_DIR / "imagens"
DOWNLOADS_DIR = Path.home() / "Downloads" / "AeroMattics"

PDF_COMPLETO = DOC_DIR / "AeroMattics_MIT_Parkinson_Documentacao_Completa.pdf"
PDF_GUIA = DOC_DIR / "AeroMattics_Guia_Rapido_Clinico_e_Pedagogico.pdf"

# Paleta institucional sobria e de alto conforto visual (sem emojis)
NAVY = colors.HexColor("#0F2942")
TEAL = colors.HexColor("#0E7490")
GOLD = colors.HexColor("#B45309")
SLATE_DARK = colors.HexColor("#1E293B")
SLATE_MUTED = colors.HexColor("#475569")
BORDER = colors.HexColor("#CBD5E1")
BG_LIGHT = colors.HexColor("#F8FAFC")
BG_CODE = colors.HexColor("#F1F5F9")
BG_WARM = colors.HexColor("#FFFBEB")


def register_fonts() -> tuple[str, str, str, str]:
    """Registra fontes TrueType Unicode (Segoe UI / Consolas ou Arial fallback)."""
    win_fonts = Path(r"C:\Windows\Fonts")
    sans, sans_b, sans_i, mono = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"

    segoe_map = [
        ("SegoeUI", win_fonts / "segoeui.ttf"),
        ("SegoeUI-Bold", win_fonts / "segoeuib.ttf"),
        ("SegoeUI-Italic", win_fonts / "segoeuii.ttf"),
    ]
    if all(p.exists() for _, p in segoe_map):
        for name, p in segoe_map:
            pdfmetrics.registerFont(TTFont(name, str(p)))
        sans, sans_b, sans_i = "SegoeUI", "SegoeUI-Bold", "SegoeUI-Italic"
    elif (win_fonts / "arial.ttf").exists() and (win_fonts / "arialbd.ttf").exists():
        pdfmetrics.registerFont(TTFont("ArialUni", str(win_fonts / "arial.ttf")))
        pdfmetrics.registerFont(TTFont("ArialUni-Bold", str(win_fonts / "arialbd.ttf")))
        pdfmetrics.registerFont(TTFont("ArialUni-Italic", str(win_fonts / "ariali.ttf")))
        sans, sans_b, sans_i = "ArialUni", "ArialUni-Bold", "ArialUni-Italic"

    if (win_fonts / "consola.ttf").exists():
        pdfmetrics.registerFont(TTFont("ConsolasUni", str(win_fonts / "consola.ttf")))
        mono = "ConsolasUni"

    return sans, sans_b, sans_i, mono


def build_styles(sans: str, sans_b: str, sans_i: str, mono: str) -> dict[str, ParagraphStyle]:
    """Constroi folha de estilos tipografica coesa para documento A4."""
    base = getSampleStyleSheet()
    return {
        "hero_title": ParagraphStyle(
            "HeroTitle",
            parent=base["Title"],
            fontName=sans_b,
            fontSize=20,
            leading=24,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "hero_sub": ParagraphStyle(
            "HeroSub",
            parent=base["Normal"],
            fontName=sans,
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#E2E8F0"),
            alignment=TA_LEFT,
        ),
        "h1": ParagraphStyle(
            "H1Sec",
            parent=base["Heading1"],
            fontName=sans_b,
            fontSize=13.5,
            leading=17,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2Sec",
            parent=base["Heading2"],
            fontName=sans_b,
            fontSize=10.8,
            leading=14,
            textColor=TEAL,
            spaceBefore=7,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "BodyTextPT",
            parent=base["Normal"],
            fontName=sans,
            fontSize=9.3,
            leading=13.2,
            textColor=SLATE_DARK,
            alignment=TA_JUSTIFY,
            spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "BulletPT",
            parent=base["Normal"],
            fontName=sans,
            fontSize=9.1,
            leading=12.8,
            textColor=SLATE_DARK,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=3,
        ),
        "eq": ParagraphStyle(
            "EquationBox",
            parent=base["Code"],
            fontName=mono,
            fontSize=8.4,
            leading=11.8,
            textColor=NAVY,
            alignment=TA_LEFT,
        ),
        "caption": ParagraphStyle(
            "CaptionPT",
            parent=base["Normal"],
            fontName=sans_i,
            fontSize=8.0,
            leading=10.5,
            textColor=SLATE_MUTED,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=6,
        ),
        "tbl_hdr": ParagraphStyle(
            "TableHdr",
            parent=base["Normal"],
            fontName=sans_b,
            fontSize=8.2,
            leading=10.5,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "tbl_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName=sans,
            fontSize=8.0,
            leading=10.4,
            textColor=SLATE_DARK,
            alignment=TA_LEFT,
        ),
        "tbl_cell_b": ParagraphStyle(
            "TableCellB",
            parent=base["Normal"],
            fontName=sans_b,
            fontSize=8.0,
            leading=10.4,
            textColor=NAVY,
            alignment=TA_LEFT,
        ),
    }


def make_page_decorator(doc_label: str, sans: str, sans_b: str):
    """Retorna cabecalho e rodape vetorial com autoria exclusiva ThyagoToledo."""
    def draw_chrome(canvas, doc) -> None:
        canvas.saveState()
        w, h = A4
        # Linha superior discreta nas paginas internas
        if doc.page > 1:
            canvas.setStrokeColor(BORDER)
            canvas.setLineWidth(0.6)
            canvas.line(16 * mm, h - 13 * mm, w - 16 * mm, h - 13 * mm)
            canvas.setFont(sans_b, 7.6)
            canvas.setFillColor(NAVY)
            canvas.drawString(16 * mm, h - 11.2 * mm, doc_label)
            canvas.setFont(sans, 7.6)
            canvas.setFillColor(SLATE_MUTED)
            canvas.drawRightString(w - 16 * mm, h - 11.2 * mm, "Autoria exclusiva: ThyagoToledo")

        # Rodape em todas as paginas
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        canvas.line(16 * mm, 13 * mm, w - 16 * mm, 13 * mm)
        canvas.setFont(sans, 7.6)
        canvas.setFillColor(SLATE_MUTED)
        canvas.drawString(
            16 * mm,
            9.2 * mm,
            "AeroMattics (Scratch 3.0 / MIT App Inventor Hackathon / Reabilitacao Parkinson) | Autor: ThyagoToledo",
        )
        canvas.setFont(sans_b, 7.8)
        canvas.setFillColor(NAVY)
        canvas.drawRightString(w - 16 * mm, 9.2 * mm, f"Pagina {doc.page}")
        canvas.restoreState()

    return draw_chrome


def scaled_image(filename: str, max_w: float, max_h: float) -> RLImage:
    """Carrega PNG local preservando proporcao exata dentro dos limites em pontos."""
    img_path = IMG_DIR / filename
    if not img_path.exists():
        raise FileNotFoundError(f"Imagem obrigatoria ausente para o PDF: {img_path}")
    with PILImage.open(img_path) as im:
        iw, ih = im.size
    scale = min(max_w / float(iw), max_h / float(ih))
    return RLImage(str(img_path), width=iw * scale, height=ih * scale)


def make_callout(lines: Sequence[str], st: dict[str, ParagraphStyle], width: float, bg=BG_CODE, accent=TEAL) -> Table:
    """Bloco destacado com barra lateral para formulas matematicas ou notas tecnicas."""
    html_text = "<br/>".join(lines)
    tbl = Table([[Paragraph(html_text, st["eq"])]], colWidths=[width])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("LINEBEFORE", (0, 0), (0, -1), 3.2, accent),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    return tbl


def make_styled_table(headers: Sequence[str], rows: Sequence[Sequence[str]], col_widths: Sequence[float], st: dict[str, ParagraphStyle]) -> Table:
    """Constroi tabela A4 padronizada com cabecalho azul-marinho e zebra suave."""
    data = [[Paragraph(h, st["tbl_hdr"]) for h in headers]]
    for row in rows:
        data.append([
            Paragraph(str(val), st["tbl_cell_b"] if idx == 0 else st["tbl_cell"])
            for idx, val in enumerate(row)
        ])
    tbl = Table(data, colWidths=list(col_widths), repeatRows=1)
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    return tbl


def make_figure_grid(
    items: Sequence[tuple[str, str]],
    cols: int,
    avail_w: float,
    img_h: float,
    st: dict[str, ParagraphStyle],
) -> Table:
    """Organiza capturas de tela em grade alinhada com legendas."""
    cell_w = avail_w / float(cols)
    img_max_w = cell_w - 8
    rows_data = []
    for i in range(0, len(items), cols):
        chunk = items[i : i + cols]
        img_row = []
        cap_row = []
        for fname, cap in chunk:
            img_row.append(scaled_image(fname, img_max_w, img_h))
            cap_row.append(Paragraph(cap, st["caption"]))
        while len(img_row) < cols:
            img_row.append("")
            cap_row.append("")
        rows_data.append(img_row)
        rows_data.append(cap_row)

    tbl = Table(rows_data, colWidths=[cell_w] * cols)
    tbl.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    return tbl


def build_complete_technical_pdf(st: dict[str, ParagraphStyle], sans: str, sans_b: str) -> None:
    """Compila o dossie tecnico completo (AeroMattics_MIT_Parkinson_Documentacao_Completa.pdf)."""
    avail_w = A4[0] - 32 * mm
    doc = SimpleDocTemplate(
        str(PDF_COMPLETO),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="AeroMattics - Documentacao Tecnica MIT e Reabilitacao Parkinson",
        author="ThyagoToledo",
    )

    story = []

    # ---- CAPA EXECUTIVA + VISAO GERAL ----
    banner = Table(
        [[
            Paragraph("AeroMattics — Simulacao Aerea Terapeutica e Matematica Aplicada", st["hero_title"]),
        ], [
            Paragraph(
                "Edicao MIT / Reabilitacao Motora em Parkinson | Mundo Procedural Mode-7 Continuo e Fauna 3D do Brasil",
                st["hero_sub"],
            ),
        ]],
        colWidths=[avail_w],
    )
    banner.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("LINEBELOW", (0, -1), (-1, -1), 3.0, GOLD),
            ("TOPPADDING", (0, 0), (-1, 0), 11),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 1),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 11),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ])
    )
    story.append(banner)
    story.append(Spacer(1, 5 * mm))

    story.append(make_styled_table(
        ["Campo", "Especificacao Verificada do Pacote"],
        [
            ["Autoria Exclusiva", "ThyagoToledo"],
            ["Arquivo Principal", "AeroMattics_MIT_Parkinson.sb3 (33 targets, extensao Pen ativa, 166 assets, 23.930.082 bytes)"],
            ["Arquitetura de Build", "Compilacao programatica deterministica em Python (scripts/build_aeromattics.py) + assets 3D Voxel"],
            ["Taxa e Validacao", "Lacos sincronos a 30 FPS verificados em VM Scratch real (scripts/test_aeromattics.py: 20/20 OK em 18.525 s)"],
            ["Publico e Objetivo", "Reabilitacao motora suave para Doenca de Parkinson (tremor 4-6 Hz / bradicinesia) e ensino de matematica aplicada"],
        ],
        [44 * mm, avail_w - 44 * mm],
        st,
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("1. Proposito Clinico, Pedagogico e Fluxo de Telas", st["h1"]))
    story.append(Paragraph(
        "O AeroMattics integra exercicios motores de baixa sobrecarga cognitiva ao ensino pratico de modelagem matematica. "
        "As equacoes governam a filtragem de tremor involuntario, a dinamica energetica do tanque, a inclinacao aerodinamica, "
        "a separacao modular de objetos no ar e a projecao em perspectiva Mode-7 de quatro biomas brasileiros, mantendo a tela de jogo "
        "totalmente livre de formulas ou textos distrativos.",
        st["body"],
    ))
    story.append(make_figure_grid(
        [
            ("01_menu_principal.png", "Menu Principal: controles acessiveis (Setas, A/D, C Sensor, G Guia, M Som)"),
            ("01b_tela_guia_como_jogar.png", "Tela Guia (G): iconografia 3D Voxel para Galao, Brisa e Rajada de Vento"),
            ("02_decolagem_pista.png", "Decolagem em Pista 3D Voxel: HUD inferior ativado somente em voo e rampa"),
        ],
        cols=3,
        avail_w=avail_w,
        img_h=43 * mm,
        st=st,
    ))

    # ---- SECAO 2: CONTROLE PARKINSON 30 FPS & PLAYTEST ----
    story.append(Paragraph("2. Controle Motor Anti-Tremor (30 FPS) e Evidencia de Playtest (160 s)", st["h1"]))
    story.append(Paragraph(
        "Para atenuar tremores posturais de 4 Hz a 6 Hz sem criar atraso excessivo ao comando intencional do paciente, "
        "o controle do aviao executa em taxa fixa de 30 FPS (zero blocos wait no loop de pilotagem) com filtro passa-baixa IIR de 1a ordem "
        "e saturacao clinica estrita do passo lateral:",
        st["body"],
    ))
    story.append(make_callout(
        [
            "vx(t)    = 0.82 * vx(t - 1) + 0.18 * alvo(t)      [alvo in {-1.85, 0, +1.85}; sensor C: mouse_x / 24]",
            "Passo X  = clamp(vx(t) + 0.28 * Vento_Forca, -2.10, +2.10)   px/frame a 30 FPS",
            "Estab    = clamp(round(0.85 * Estab + 0.15 * (52 * Vento + 22 * vx)), -95, +95)",
        ],
        st,
        avail_w,
        bg=BG_CODE,
        accent=TEAL,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "O ganho alpha = 0.18 reduz em mais de 60% o desvio padrao de sinais alternados a 6 Hz mantendo resposta previsivel ao volante, "
        "setas, A/D, Makey Makey ou modo Sensor (tecla C). Nas telas de encerramento (Vitoria aos 160 s ou Pouso Terapeutico), o HUD inferior "
        "oculta-se automaticamente e todos os clones sao encerrados sem vazamentos.",
        st["body"],
    ))
    story.append(make_styled_table(
        ["Cenario de Playtest (160 s em VM)", "Desfecho Verificado", "Pontos", "Vidas / Combustivel", "Suavidade / Clones"],
        [
            ["idle (sem comando)", "queda@62.7s (Fase 2)", "228", "0 vidas | 83.8% (min 82.6%)", "Confirma que inativo nao vence"],
            ["skillful (desvio + coleta ativa)", "Missao concluida! (162.9s)", "1.184", "5 vidas | 92.8% (min 90.5%)", "Aviao media 0.541 / max 2.100 px"],
            ["tremor_sensor_c (Modo C + 6 Hz)", "Missao concluida! (162.9s)", "1.099", "4 vidas | 81.3% (min 80.3%)", "11 brisas | 68.7% em equilibrio"],
        ],
        [44 * mm, 36 * mm, 16 * mm, 39 * mm, avail_w - 135 * mm],
        st,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(make_figure_grid(
        [
            ("07_tela_vitoria_missao_concluida.png", "Vitoria (160 s concluidos): pouso ao por do sol sem HUD inferior"),
            ("08_tela_fim_de_voo_terapeutico.png", "Fim de Voo Terapeutico: aterrissagem segura acolhedora sem HUD"),
        ],
        cols=2,
        avail_w=avail_w,
        img_h=46 * mm,
        st=st,
    ))

    story.append(PageBreak())

    # ---- SECAO 3: MATEMATICA DA GAMEPLAY & 5 RAIAS RADIAIS ----
    story.append(Paragraph("3. Modelagem Matematica da Gameplay e Cinco Raias Radiais", st["h1"]))
    story.append(Paragraph(
        "A pontuacao, a gestao energetica e o surgimento de obstaculos foram estruturados em torno de funcoes matematicas continuas "
        "que criam progressao clara nas 4 fases de 40 s (160 s totais) sem punir o tempo de reacao do jogador:",
        st["body"],
    ))
    story.append(make_callout(
        [
            "Equilibrio (Stage Loop 1):    +2 pts/s base  +  1 pt/s bonus enquanto |Estabilidade| <= 12",
            "Sequencia de Brisas:          Estab -> round(0.35 * Estab), +3% comb., +(15 + 5 * min(Brisas, 4)) pts",
            "Economia do Tanque (-0.65%/s): Galao (+28% comb., +10 pts); garantia adaptativa se Combustivel < 35%",
            "Curva Progressiva por Bioma:  dZ_mundo = 0.10 + 0.01 * Etapa   |   d_ave = 0.0066 + 0.0005 * Etapa",
            "Raias Radiais Disjuntas:      p(d) = d^1.65; Y = 44 - 148*p; Ave=S%5, Comb=(S+2)%5, Brisa=(S+4)%5",
        ],
        st,
        avail_w,
        bg=BG_WARM,
        accent=GOLD,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(make_styled_table(
        ["Fase / Janela", "Bioma Brasileiro", "Ave 3D Voxel Exclusiva", "Marcos 3D Voxel no Solo", "Velocidade Solo / Ave"],
        [
            ["Fase 1 (0-40 s)", "Amazonia", "Arara-Vermelha 3D", "Castanheira, Barco Amazonico, Acaizeiro", "0.11 Z/f  |  0.0071 d/f"],
            ["Fase 2 (40-80 s)", "Cerrado", "Tucano-Toco 3D", "Ipe-Amarelo, Buriti Limpo, Igreja Colonial", "0.12 Z/f  |  0.0076 d/f"],
            ["Fase 3 (80-120 s)", "Pantanal", "Tuiuiu Pantaneiro 3D", "Caranda, Chalana sem placa, Ninho Tuiuiu", "0.13 Z/f  |  0.0081 d/f"],
            ["Fase 4 (120-160 s)", "Mata Atlantica", "Arara-Azul 3D", "Araucaria, Casarao Colonial, Palmeira Real", "0.14 Z/f  |  0.0086 d/f"],
        ],
        [27 * mm, 27 * mm, 33 * mm, 55 * mm, avail_w - 142 * mm],
        st,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(KeepTogether([
        scaled_image("09_painel_conceitos_matematicos_mit.png", avail_w, 114 * mm),
        Paragraph(
            "Figura 1: Curvas de trigonometria das aves e Harpia Real, atenuacao IIR anti-tremor a 30 FPS, consumo com coleta de tanque e funcoes afins do HUD.",
            st["caption"],
        ),
    ]))

    story.append(PageBreak())

    # ---- SECAO 4: MOTOR MODE-7 CONTINUO & ANTI-TONTURA ----
    story.append(Paragraph("4. Motor Pen Mode-7 Continuo, Loop Periodico e Conforto Anti-Tontura", st["h1"]))
    story.append(Paragraph(
        "Para eliminar o efeito estroboscopico de quadriculados de alto contraste e corrigir quebras em degraus horizontais ao longo das curvas do rio, "
        "o ator Terreno Procedural executa dentro de bloco customizado warp=true em tres passadas integradas:",
        st["body"],
    ))
    for bullet in [
        "- <b>1) Campos calmos anti-tontura:</b> ondas simetricas em 4 tempos (floor(zw * 0.56) mod 4) com variacao cromatica maxima de 14 niveis RGB; no horizonte distante (dy &lt; 34), a neblina quadratica mistura um tom unico sem alternancia.",
        "- <b>2) Rio em polilinha continua de 18 nos conectados:</b> Areia (2*(rhw+shw)), Agua Rasa Turquesa (2*rhw) e Canal Profundo (1.60*rhw) sao desenhados sem levantar o lapis (pen_down continuo de sy = +29 a -115), zerando quebras nas curvas.",
        "- <b>3) Correnteza em loop periodico fechado:</b> 8 filetes percorrem continuamente z_rel de 26.4 a 2.4 via flux = mod(Z_Mundo * 2.1, 24), seguindo o eixo curvo X_rio(zw) sem saltos ou quebras de ciclo.",
    ]:
        story.append(Paragraph(bullet, st["bullet"]))

    story.append(Spacer(1, 2 * mm))
    story.append(make_styled_table(
        ["Bioma Auditado (30 FPS VM)", "Tracos Pen/Quadro", "Avaliacoes/Quadro", "MAE Luminancia", "Cintilacao Horizonte", "Poluicao Media / Max"],
        [
            ["Fase 1 - Amazonia", "296", "12.527 (< 13k)", "1.61 / 255", "0.64 / 255", "TotalTela: 7.44 / 11"],
            ["Fase 2 - Cerrado", "296", "12.483 (< 13k)", "0.33 / 255", "0.17 / 255", "Solo: 3.00 / 4 clones"],
            ["Fase 3 - Pantanal", "296", "12.484 (< 13k)", "1.26 / 255", "0.25 / 255", "Nuvens: 1.99 / 2 clones"],
            ["Fase 4 - Mata Atlantica", "296", "12.502 (< 13k)", "1.01 / 255", "0.46 / 255", "Max clones VM: 12 / 300"],
        ],
        [38 * mm, 26 * mm, 30 * mm, 26 * mm, 28 * mm, avail_w - 148 * mm],
        st,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(KeepTogether([
        scaled_image("10_painel_matematica_cenario_vivo_mit.png", avail_w, 114 * mm),
        Paragraph(
            "Figura 2: Equacoes de projecao 260/dy, canal sinuoso X_rio(z), paralaxe multicamada e catalogo atualizado com Acaizeiro (F1) e Palmeira Real (F4).",
            st["caption"],
        ),
    ]))

    story.append(PageBreak())

    # ---- SECAO 5: TELAS DOS 4 BIOMAS & COMPARATIVOS ----
    story.append(Paragraph("5. Composicao Visual dos 4 Biomas Brasileiros em Voo (Estado Atual)", st["h1"]))
    story.append(make_figure_grid(
        [
            ("03_fase1_campo_brisa_e_sol.png", "Fase 1 - Amazonia: Arara-Vermelha 3D, Barco limpo, Acaizeiro e rio continuo"),
            ("04_fase2_floresta_rajada_vento.png", "Fase 2 - Cerrado: Tucano-Toco 3D, Ipe-Amarelo, Igreja Colonial e vento"),
            ("05_fase3_deserto_migracao_aves.png", "Fase 3 - Pantanal: Tuiuiu 3D, Chalana sem placa e 3 Harpias voltadas a direita"),
            ("06_fase4_neve_alerta_e_combustivel.png", "Fase 4 - Mata Atlantica: Arara-Azul 3D, Pao de Acucar, Palmeira Real e Casarao"),
        ],
        cols=2,
        avail_w=avail_w,
        img_h=56 * mm,
        st=st,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(KeepTogether([
        scaled_image("11_comparativo_profundidade_25d_rio_continuo.png", avail_w, 96 * mm),
        Paragraph(
            "Figura 3: Progressao de profundidade z_rel = Z_Prop - Z_Mundo e composicao fiel do rio em polilinha continua nos 4 biomas.",
            st["caption"],
        ),
    ]))

    story.append(PageBreak())

    # ---- SECAO 6: FAUNA EXCLUSIVA & ANTES VS DEPOIS ----
    story.append(Paragraph("6. Fauna Brasileira 3D Voxel Exclusiva e Quadros de Animacao", st["h1"]))
    story.append(Paragraph(
        "Cada fase apresenta uma especie nativa esculpida individualmente em 3D Voxel, com articulacao suave de asas em 4 quadros (0,11 s/quadro) "
        "e surgimento gradual pela neblina do horizonte (ghost progressivo quando d < 0.24). A Harpia Real (Harpia harpyja) utiliza recortes por flood-fill "
        "conectado a borda, garantindo 100% de opacidade interna nas asas e orientacao automatica na direcao real do deslocamento (+90 direita / -90 esquerda).",
        st["body"],
    ))
    story.append(KeepTogether([
        scaled_image("14_passaros_brasileiros_3d_voxel.png", avail_w, 134 * mm),
        Paragraph(
            "Figura 4: Catalogo de animacao da Fauna Brasileira 3D Voxel (Arara-Vermelha, Tucano-Toco, Tuiuiu Pantaneiro, Arara-Azul e Harpia Real).",
            st["caption"],
        ),
    ]))
    story.append(Spacer(1, 2 * mm))
    story.append(KeepTogether([
        scaled_image("12_antes_vs_depois_decolagem_guia_e_rajada.png", avail_w, 95 * mm),
        Paragraph(
            "Figura 5: Comparativo ANTES vs DEPOIS — Pista Voxel 3D, Brisa sem xadrez, Rajadas no Cerrado e Painel Matematico atualizado.",
            st["caption"],
        ),
    ]))

    story.append(PageBreak())

    # ---- SECAO 7: COMPARATIVO BIOMAS, INVENTARIO & ENGENHARIA ----
    story.append(Paragraph("7. Evolucao Antes vs Depois nos 4 Biomas e Arquitetura Programatica", st["h1"]))
    story.append(KeepTogether([
        scaled_image("13_antes_vs_depois_4_biomas_mode7.png", avail_w, 150 * mm),
        Paragraph(
            "Figura 6: Comparativo completo ANTES vs DEPOIS nos 4 biomas — remocao do xadrez piscante, rio continuo e fauna exclusiva.",
            st["caption"],
        ),
    ]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("8. Inventario Consolidado (33 Targets), Clones e Verificacao Automatizada (20/20 OK)", st["h1"]))
    story.append(make_styled_table(
        ["Camada / Grupo", "Targets no Scratch", "Limite Clones / Papel Principal"],
        [
            ["Palco e Ceu", "Stage, cenario, Sol, Nuvens", "Estado/loops 1-6; panoramas sem corte; Sol (172, 130); 2 nuvens altas"],
            ["Mundo Mode-7", "Terreno Procedural, Vegetacao e Cenario Vivo, Pista", "Shader Pen warp=true (296 tracos); 4 props Z-locked (28.8 Z); pista 3D"],
            ["Atores Aereos", "Combustivel no ar, Brisa Favoravel, Passaros, Aves Migratorias, Rajada de Vento", "Raias disjuntas p(d)=d^1.65 (max 1+1+1+3+3 clones); Harpia bilateral"],
            ["Aviao e HUD", "Aviao + 16 sprites HUD (painel, ponteiros, digitos, alerta)", "Controle 30 FPS (IIR 0.82/0.18); HUD ativo apenas em decolagem/voo"],
            ["Telas e Navegacao", "Fundo de encerramento, Camada conclusao, Texto conclusao, Telas, Start, Botao Guia", "Menu, Guia (G), Pouso Vitoria (160 s) e Pouso Fim de Voo"],
        ],
        [32 * mm, 64 * mm, avail_w - 96 * mm],
        st,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<b>Engenharia programatica em Scratch 3.0:</b> o projeto e compilado diretamente via Python (zipfile + project.json + hashes MD5), "
        "adotando praticas da comunidade para jogos 2.5D/Mode-7 como blocos Run without screen refresh (warp=true), agrupamento de faixas por profundidade, "
        "teto rigido de clones (maximo 15 previstos, 12 observados) e compatibilidade com compiladores textuais (goboscript, Tosh, TB3) e TurboWarp JIT. "
        "Toda a bateria em scripts/test_aeromattics.py alcancou <b>20/20 testes aprovados (OK) em 18.525 s</b> sobre o pacote final de 23.930.082 bytes.",
        st["body"],
    ))

    on_page = make_page_decorator("AeroMattics MIT / Parkinson — Documentacao Tecnica Completa", sans, sans_b)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def build_quick_guide_pdf(st: dict[str, ParagraphStyle], sans: str, sans_b: str) -> None:
    """Compila o guia rapido de operacao para avaliadores, clinicos e docentes (2 paginas)."""
    avail_w = A4[0] - 32 * mm
    doc = SimpleDocTemplate(
        str(PDF_GUIA),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="AeroMattics - Guia Rapido Clinico, Controles e Resumo Matematico",
        author="ThyagoToledo",
    )

    story = []
    header = Table(
        [[
            Paragraph("AeroMattics — Guia Rapido de Operacao, Controles e Matematica", st["hero_title"]),
        ], [
            Paragraph("Manual de Consulta Rapida para Terapia em Parkinson e Avaliacao MIT | Autoria: ThyagoToledo", st["hero_sub"]),
        ]],
        colWidths=[avail_w],
    )
    header.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), TEAL),
            ("LINEBELOW", (0, -1), (-1, -1), 3.0, GOLD),
            ("TOPPADDING", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 1),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ])
    )
    story.append(header)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1. Como Jogar e Controles Adaptados (Acessibilidade Motora)", st["h1"]))
    story.append(make_styled_table(
        ["Comando / Tecla", "Acao no Jogo", "Beneficio Terapeutico / Adaptacao"],
        [
            ["Seta Esq / Dir ou A / D", "Move o aviao suavemente na horizontal", "Passo limitado a [-2.10, +2.10] px/frame com filtro passa-baixa"],
            ["Tecla C (Modo Sensor)", "Ativa/desativa acompanhamento pelo cursor", "Ideal para joystick, touchpad adaptado ou movimento continuo de braco"],
            ["Makey Makey (Seta/Espaco)", "Decolar, reiniciar e pilotar via sensores externos", "Suporte nativo a botoes grandes de baixo esforco ou superficies condutivas"],
            ["Tecla G / Botao Guia", "Alterna entre Menu e Tela Guia Ilustrada", "Apresenta alvos positivos (Brisa, Galao) e desvios (Passaros, Vento)"],
            ["Tecla M", "Liga ou silencia efeitos sonoros", "Evita sobrecarga sensorial durante sessoes clinicas ou em sala"],
        ],
        [44 * mm, 52 * mm, avail_w - 96 * mm],
        st,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(make_figure_grid(
        [
            ("01_menu_principal.png", "1. Clique DECOLAR (ou Espaco/Seta Cima) ou GUIA (tecla G)"),
            ("01b_tela_guia_como_jogar.png", "2. Tela Guia: coletar Galao e Brisa; desviar das Aves e compensar vento"),
        ],
        cols=2,
        avail_w=avail_w,
        img_h=48 * mm,
        st=st,
    ))

    story.append(Paragraph("2. Elementos do Voo, Pontuacao e Equilibrio Matematico", st["h1"]))
    story.append(make_styled_table(
        ["Elemento / Indicador", "Efeito na Gameplay", "Regra Matematica Subjacente"],
        [
            ["Voo Estabilizado (ESTAB.)", "Recompensa controle calmo no centro da tela", "+2 pts/s base e +1 pt/s extra enquanto |Estabilidade| <= 12 (Dir = 90 + 1.15*E)"],
            ["Brisa Favoravel (3D Ciano)", "Acalma a aeronave e recupera energia leve", "Estab = round(0.35 * Estab), +3% comb., +(15 + 5 * min(Brisas, 4)) pts"],
            ["Galao Voxel (Combustivel)", "Impede pane seca ao longo dos 160 s", "+28% combustivel, +10 pts; resgate garantido se tanque cair abaixo de 35%"],
            ["Aves 3D / Harpias Reais", "Obstaculos aereos com 2,5 s de protecao apos toque", "5 raias disjuntas (mod 5); Harpias deixam o lado oposto sempre livre (|X| >= 25)"],
        ],
        [42 * mm, 52 * mm, avail_w - 94 * mm],
        st,
    ))

    story.append(PageBreak())

    story.append(Paragraph("3. Roteiro dos 4 Biomas Brasileiros (40 s por Fase = 160 s)", st["h1"]))
    story.append(make_figure_grid(
        [
            ("03_fase1_campo_brisa_e_sol.png", "Fase 1 (0-40 s): Amazonia | Arara-Vermelha 3D e Acaizeiro"),
            ("04_fase2_floresta_rajada_vento.png", "Fase 2 (40-80 s): Cerrado | Tucano-Toco 3D e Chapadas"),
            ("05_fase3_deserto_migracao_aves.png", "Fase 3 (80-120 s): Pantanal | Tuiuiu 3D e Harpias Reais"),
            ("06_fase4_neve_alerta_e_combustivel.png", "Fase 4 (120-160 s): Mata Atlantica | Arara-Azul e Palmeira Real"),
        ],
        cols=2,
        avail_w=avail_w,
        img_h=56 * mm,
        st=st,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("4. Encerramento Terapeutico e Verificacao Tecnica", st["h1"]))
    story.append(Paragraph(
        "Em qualquer resultado (Missao Concluida aos 160 s ou Fim de Voo), o encerramento apresenta mensagem positiva de incentivo "
        "com opcoes imediatas de reinicio (Espaco, R, Seta Cima ou clique nos botoes alados). O pacote AeroMattics_MIT_Parkinson.sb3 "
        "(33 targets, 166 assets, 23.930.082 bytes) foi integralmente verificado por 20/20 testes automatizados e simulacoes de conforto a 30 FPS.",
        st["body"],
    ))
    story.append(make_figure_grid(
        [
            ("07_tela_vitoria_missao_concluida.png", "Conclusao aos 160 s: Missao Concluida!"),
            ("08_tela_fim_de_voo_terapeutico.png", "Aterrissagem Segura Terapeutica"),
        ],
        cols=2,
        avail_w=avail_w,
        img_h=44 * mm,
        st=st,
    ))

    on_page = make_page_decorator("AeroMattics MIT / Parkinson — Guia Rapido Clinico e Pedagogico", sans, sans_b)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def main() -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    sans, sans_b, sans_i, mono = register_fonts()
    st = build_styles(sans, sans_b, sans_i, mono)

    build_complete_technical_pdf(st, sans, sans_b)
    build_quick_guide_pdf(st, sans, sans_b)

    # Espelha os PDFs prontos tambem em Downloads/AeroMattics e na raiz do projeto para envio rapido
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for pdf_path in (PDF_COMPLETO, PDF_GUIA):
        shutil.copy2(pdf_path, DOWNLOADS_DIR / pdf_path.name)
    shutil.copy2(PDF_COMPLETO, ROOT / PDF_COMPLETO.name)

    print("PDFs gerados e sincronizados com sucesso:")
    print(f" - {PDF_COMPLETO} ({PDF_COMPLETO.stat().st_size:,} bytes)")
    print(f" - {PDF_GUIA} ({PDF_GUIA.stat().st_size:,} bytes)")
    print(f" - Copias em {ROOT / PDF_COMPLETO.name} e {DOWNLOADS_DIR}")


if __name__ == "__main__":
    main()
