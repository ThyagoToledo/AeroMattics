"""
Construtor completo do AeroMattics_MIT_Parkinson.sb3.
Autor: ThyagoToledo

Combina os assets organizados de AeroMattics com:
- Conceitos matematicos explicitos para registro no MIT (funcoes senoidais,
  filtro passa-baixa discreto, geometria projetiva de perspectiva,
  decomposicao posicional base-10 e transformacao afim angular).
- Adaptacoes de acessibilidade para reabilitacao motora de pacientes com
  doenca de Parkinson (4 fases estaveis de 40s sem alternancia rapida de fundo,
  suavizacao de tremor nas teclas/setas e A/D, 5 vidas, protecao de 2.5s,
  corredor senoidal de aneis colecionaveis e HUD inferior legivel).
"""

import hashlib
import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from PIL import Image


ROOT = Path(r"C:\Users\thyag\OneDrive\Desktop\AeroMattics")
BACKUP_SB3 = ROOT / "backup" / "AeroMattics_original.sb3"
ORG_DIR = ROOT / "assets_organizados"

OUT_DESKTOP = ROOT / "AeroMattics_MIT_Parkinson.sb3"
OUT_DESKTOP_MAIN = ROOT / "AeroMattics.sb3"
OUT_DOWNLOADS_NEW = Path(r"C:\Users\thyag\Downloads\AeroMattics_MIT_Parkinson.sb3")
OUT_DOWNLOADS_MAIN = Path(r"C:\Users\thyag\Downloads\AeroMattics.sb3")
OUT_DOWNLOADS_DIR = Path(r"C:\Users\thyag\Downloads\AeroMattics")


class AssetRegistry:
    """Gerencia bytes de PNG/JPG/SVG/WAV indexados por md5ext para o .sb3."""

    def __init__(self):
        self.files = {}

    def add_bytes(self, data: bytes, ext: str) -> tuple[str, str]:
        digest = hashlib.md5(data).hexdigest()
        md5ext = f"{digest}.{ext}"
        self.files[md5ext] = data
        return digest, md5ext

    def costume_from_image(
        self,
        path: Path,
        name: str,
        bitmap_resolution: int = 1,
        center: tuple[float, float] | None = None,
    ) -> dict:
        data = path.read_bytes()
        ext = path.suffix.lstrip(".").lower()
        if ext == "jpeg":
            ext = "jpg"
        with Image.open(path) as im:
            w, h = im.size
        cx, cy = center if center is not None else (w / 2.0, h / 2.0)
        digest, md5ext = self.add_bytes(data, ext)
        return {
            "name": name,
            "bitmapResolution": bitmap_resolution,
            "dataFormat": ext,
            "assetId": digest,
            "md5ext": md5ext,
            "rotationCenterX": cx,
            "rotationCenterY": cy,
        }

    def costume_from_svg(
        self,
        svg_text: str,
        name: str,
        center: tuple[float, float] = (240.0, 180.0),
    ) -> dict:
        data = svg_text.encode("utf-8")
        digest, md5ext = self.add_bytes(data, "svg")
        return {
            "name": name,
            "bitmapResolution": 1,
            "dataFormat": "svg",
            "assetId": digest,
            "md5ext": md5ext,
            "rotationCenterX": center[0],
            "rotationCenterY": center[1],
        }

    def costume_from_raw(self, raw_costume: dict, orig_zip: zipfile.ZipFile) -> dict:
        md5ext = raw_costume["md5ext"]
        self.files[md5ext] = orig_zip.read(md5ext)
        return dict(raw_costume)

    def sound_from_raw(self, raw_sound: dict, orig_zip: zipfile.ZipFile) -> dict:
        md5ext = raw_sound["md5ext"]
        self.files[md5ext] = orig_zip.read(md5ext)
        return dict(raw_sound)


class ScriptBuilder:
    """Builder limpo e seguro para arvores de blocos Scratch 3.0 sem IDs duplicados."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.counter = 0
        self.blocks = {}
        self.top_y = 60

    def uid(self) -> str:
        self.counter += 1
        return f"{self.prefix}_b{self.counter}"

    def block(
        self,
        opcode: str,
        inputs: dict | None = None,
        fields: dict | None = None,
        shadow: bool = False,
        top: bool = False,
        x: int = 80,
        y: int | None = None,
    ) -> str:
        bid = self.uid()
        node = {
            "opcode": opcode,
            "next": None,
            "parent": None,
            "inputs": inputs or {},
            "fields": fields or {},
            "shadow": shadow,
            "topLevel": top,
        }
        if top:
            node["x"] = x
            if y is None:
                node["y"] = self.top_y
                self.top_y += 380
            else:
                node["y"] = y
        self.blocks[bid] = node
        return bid

    def chain(self, *block_ids: str) -> str | None:
        valid = [b for b in block_ids if b is not None]
        if not valid:
            return None
        for i in range(len(valid) - 1):
            cur, nxt = valid[i], valid[i + 1]
            self.blocks[cur]["next"] = nxt
            self.blocks[nxt]["parent"] = cur
        return valid[0]

    def stack(self, hat_id: str, *stmt_ids: str) -> str:
        valid = [b for b in stmt_ids if b is not None]
        if valid:
            self.chain(hat_id, *valid)
        return hat_id

    @staticmethod
    def lit_num(val) -> list:
        return [1, [4, str(val)]]

    @staticmethod
    def lit_str(val: str) -> list:
        return [1, [10, str(val)]]

    def arg(self, val, kind: int = 4, parent_id: str | None = None) -> list:
        """Retorna entrada de bloco reporter com shadow fallback ou literal direto."""
        if isinstance(val, tuple) and len(val) == 2 and val[0] == "__EXPR__":
            expr_id = val[1]
            if parent_id is not None:
                self.blocks[expr_id]["parent"] = parent_id
            return [3, expr_id, [kind, "0" if kind == 4 else ""]]
        return [1, [kind, str(val)]]

    def bind_arg(self, parent_id: str, input_name: str, val, kind: int = 4) -> None:
        self.blocks[parent_id]["inputs"][input_name] = self.arg(val, kind, parent_id=parent_id)

    def expr_in(self, parent_id: str, input_name: str, expr_id: str, kind: int | None = 4):
        self.blocks[expr_id]["parent"] = parent_id
        if kind is None:
            self.blocks[parent_id]["inputs"][input_name] = [2, expr_id]
        else:
            self.blocks[parent_id]["inputs"][input_name] = [3, expr_id, [kind, "0" if kind == 4 else ""]]

    def substack(self, parent_id: str, input_name: str, *stmt_ids: str):
        first = self.chain(*stmt_ids)
        if first:
            self.blocks[first]["parent"] = parent_id
            self.blocks[parent_id]["inputs"][input_name] = [2, first]

    # ---- Reporters ----
    def var(self, var_name: str, var_id: str) -> tuple:
        bid = self.block("data_variable", fields={"VARIABLE": [var_name, var_id]})
        return ("__EXPR__", bid)

    def timer(self) -> tuple:
        return ("__EXPR__", self.block("sensing_timer"))

    def x_pos(self) -> tuple:
        return ("__EXPR__", self.block("motion_xposition"))

    def y_pos(self) -> tuple:
        return ("__EXPR__", self.block("motion_yposition"))

    def size(self) -> tuple:
        return ("__EXPR__", self.block("looks_size"))

    def costume_num(self) -> tuple:
        return ("__EXPR__", self.block("looks_costumenumbername", fields={"NUMBER_NAME": ["number", None]}))

    def mouse_down(self) -> str:
        return self.block("sensing_mousedown")

    def mouse_x(self) -> tuple:
        return ("__EXPR__", self.block("sensing_mousex"))

    def mouse_y(self) -> tuple:
        return ("__EXPR__", self.block("sensing_mousey"))

    def key_pressed(self, key_name: str) -> str:
        bid = self.block("sensing_keypressed")
        menu_id = self.block("sensing_keyoptions", fields={"KEY_OPTION": [key_name, None]}, shadow=True)
        self.blocks[menu_id]["parent"] = bid
        self.blocks[bid]["inputs"]["KEY_OPTION"] = [1, menu_id]
        return bid

    def distance_to(self, target_name: str) -> tuple:
        bid = self.block("sensing_distanceto")
        menu_id = self.block("sensing_distancetomenu", fields={"DISTANCETOMENU": [target_name, None]}, shadow=True)
        self.blocks[menu_id]["parent"] = bid
        self.blocks[bid]["inputs"]["DISTANCETOMENU"] = [1, menu_id]
        return ("__EXPR__", bid)

    def op_bin(self, opcode: str, k1: str, v1, k2: str, v2, kind: int = 4) -> tuple:
        bid = self.block(opcode)
        for key, val in ((k1, v1), (k2, v2)):
            if isinstance(val, tuple) and len(val) == 2 and val[0] == "__EXPR__":
                self.expr_in(bid, key, val[1], kind=kind)
            else:
                self.blocks[bid]["inputs"][key] = [1, [kind, str(val)]]
        return ("__EXPR__", bid)

    def add(self, a, b) -> tuple:
        return self.op_bin("operator_add", "NUM1", a, "NUM2", b, 4)

    def sub(self, a, b) -> tuple:
        return self.op_bin("operator_subtract", "NUM1", a, "NUM2", b, 4)

    def mul(self, a, b) -> tuple:
        return self.op_bin("operator_multiply", "NUM1", a, "NUM2", b, 4)

    def div(self, a, b) -> tuple:
        return self.op_bin("operator_divide", "NUM1", a, "NUM2", b, 4)

    def mod(self, a, b) -> tuple:
        return self.op_bin("operator_mod", "NUM1", a, "NUM2", b, 4)

    def rand(self, a, b) -> tuple:
        return self.op_bin("operator_random", "FROM", a, "TO", b, 4)

    def mathop(self, op_name: str, val) -> tuple:
        bid = self.block("operator_mathop", fields={"OPERATOR": [op_name, None]})
        if isinstance(val, tuple) and val[0] == "__EXPR__":
            self.expr_in(bid, "NUM", val[1], 4)
        else:
            self.blocks[bid]["inputs"]["NUM"] = self.lit_num(val)
        return ("__EXPR__", bid)

    def round_op(self, val) -> tuple:
        bid = self.block("operator_round")
        if isinstance(val, tuple) and val[0] == "__EXPR__":
            self.expr_in(bid, "NUM", val[1], 4)
        else:
            self.blocks[bid]["inputs"]["NUM"] = self.lit_num(val)
        return ("__EXPR__", bid)

    # ---- Boolean conditions ----
    def eq(self, a, b) -> str:
        return self.op_bin("operator_equals", "OPERAND1", a, "OPERAND2", b, 10)[1]

    def lt(self, a, b) -> str:
        return self.op_bin("operator_lt", "OPERAND1", a, "OPERAND2", b, 4)[1]

    def gt(self, a, b) -> str:
        return self.op_bin("operator_gt", "OPERAND1", a, "OPERAND2", b, 4)[1]

    def bool_and(self, b1: str, b2: str) -> str:
        bid = self.block("operator_and")
        self.expr_in(bid, "OPERAND1", b1, kind=None)
        self.expr_in(bid, "OPERAND2", b2, kind=None)
        return bid

    def bool_or(self, b1: str, b2: str) -> str:
        bid = self.block("operator_or")
        self.expr_in(bid, "OPERAND1", b1, kind=None)
        self.expr_in(bid, "OPERAND2", b2, kind=None)
        return bid

    def bool_not(self, b1: str) -> str:
        bid = self.block("operator_not")
        self.expr_in(bid, "OPERAND", b1, kind=None)
        return bid

    # ---- Hats ----
    def hat_flag(self, x: int = 80, y: int | None = None) -> str:
        return self.block("event_whenflagclicked", top=True, x=x, y=y)

    def hat_broadcast(self, msg_name: str, msg_id: str, x: int = 80, y: int | None = None) -> str:
        return self.block("event_whenbroadcastreceived", fields={"BROADCAST_OPTION": [msg_name, msg_id]}, top=True, x=x, y=y)

    def hat_key(self, key_name: str, x: int = 80, y: int | None = None) -> str:
        return self.block("event_whenkeypressed", fields={"KEY_OPTION": [key_name, None]}, top=True, x=x, y=y)

    def hat_clicked(self, x: int = 80, y: int | None = None) -> str:
        return self.block("event_whenthisspriteclicked", top=True, x=x, y=y)

    def hat_clone(self, x: int = 80, y: int | None = None) -> str:
        return self.block("control_start_as_clone", top=True, x=x, y=y)

    # ---- Statements ----
    def set_var(self, var_name: str, var_id: str, val, kind: int = 4) -> str:
        bid = self.block("data_setvariableto", fields={"VARIABLE": [var_name, var_id]})
        if isinstance(val, tuple) and val[0] == "__EXPR__":
            self.expr_in(bid, "VALUE", val[1], kind=kind)
        else:
            self.blocks[bid]["inputs"]["VALUE"] = [1, [kind, str(val)]]
        return bid

    def change_var(self, var_name: str, var_id: str, val) -> str:
        bid = self.block("data_changevariableby", fields={"VARIABLE": [var_name, var_id]})
        if isinstance(val, tuple) and val[0] == "__EXPR__":
            self.expr_in(bid, "VALUE", val[1], kind=4)
        else:
            self.blocks[bid]["inputs"]["VALUE"] = self.lit_num(val)
        return bid

    def hide_var(self, var_name: str, var_id: str) -> str:
        return self.block("data_hidevariable", fields={"VARIABLE": [var_name, var_id]})

    def broadcast(self, msg_name: str, msg_id: str) -> str:
        return self.block("event_broadcast", inputs={"BROADCAST_INPUT": [1, [11, msg_name, msg_id]]})

    def wait(self, secs) -> str:
        bid = self.block("control_wait")
        if isinstance(secs, tuple) and secs[0] == "__EXPR__":
            self.expr_in(bid, "DURATION", secs[1], 4)
        else:
            self.blocks[bid]["inputs"]["DURATION"] = self.lit_num(secs)
        return bid

    def reset_timer(self) -> str:
        return self.block("sensing_resettimer")

    def forever(self, *stmt_ids: str) -> str:
        bid = self.block("control_forever")
        self.substack(bid, "SUBSTACK", *stmt_ids)
        return bid

    def repeat(self, times, *stmt_ids: str) -> str:
        bid = self.block("control_repeat")
        self.bind_arg(bid, "TIMES", times, 6)
        self.substack(bid, "SUBSTACK", *stmt_ids)
        return bid

    def repeat_until(self, cond_id: str, *stmt_ids: str) -> str:
        bid = self.block("control_repeat_until")
        self.expr_in(bid, "CONDITION", cond_id, kind=None)
        self.substack(bid, "SUBSTACK", *stmt_ids)
        return bid

    def if_then(self, cond_id: str, *stmt_ids: str) -> str:
        bid = self.block("control_if")
        self.expr_in(bid, "CONDITION", cond_id, kind=None)
        self.substack(bid, "SUBSTACK", *stmt_ids)
        return bid

    def if_else(self, cond_id: str, then_stmts: list[str], else_stmts: list[str]) -> str:
        bid = self.block("control_if_else")
        self.expr_in(bid, "CONDITION", cond_id, kind=None)
        self.substack(bid, "SUBSTACK", *then_stmts)
        self.substack(bid, "SUBSTACK2", *else_stmts)
        return bid

    def create_clone(self, target_opt: str = "_myself_") -> str:
        bid = self.block("control_create_clone_of")
        menu = self.block("control_create_clone_of_menu", fields={"CLONE_OPTION": [target_opt, None]}, shadow=True)
        self.blocks[menu]["parent"] = bid
        self.blocks[bid]["inputs"]["CLONE_OPTION"] = [1, menu]
        return bid

    def delete_clone(self) -> str:
        return self.block("control_delete_this_clone")

    def show(self) -> str:
        return self.block("looks_show")

    def hide(self) -> str:
        return self.block("looks_hide")

    def go_layer(self, front_back: str) -> str:
        return self.block("looks_gotofrontback", fields={"FRONT_BACK": [front_back, None]})

    def go_layers(self, forward_backward: str, num) -> str:
        bid = self.block(
            "looks_goforwardbackwardlayers",
            fields={"FORWARD_BACKWARD": [forward_backward, None]},
        )
        self.bind_arg(bid, "NUM", num, 4)
        return bid

    def switch_costume(self, name_or_expr) -> str:
        bid = self.block("looks_switchcostumeto")
        if isinstance(name_or_expr, tuple) and name_or_expr[0] == "__EXPR__":
            self.expr_in(bid, "COSTUME", name_or_expr[1], kind=10)
        else:
            menu = self.block("looks_costume", fields={"COSTUME": [str(name_or_expr), None]}, shadow=True)
            self.blocks[menu]["parent"] = bid
            self.blocks[bid]["inputs"]["COSTUME"] = [1, menu]
        return bid

    def next_costume(self) -> str:
        return self.block("looks_nextcostume")

    def set_size(self, pct) -> str:
        bid = self.block("looks_setsizeto")
        if isinstance(pct, tuple) and pct[0] == "__EXPR__":
            self.expr_in(bid, "SIZE", pct[1], 4)
        else:
            self.blocks[bid]["inputs"]["SIZE"] = self.lit_num(pct)
        return bid

    def change_size(self, delta) -> str:
        bid = self.block("looks_changesizeby")
        self.bind_arg(bid, "CHANGE", delta, 4)
        return bid

    def set_effect(self, effect: str, val) -> str:
        bid = self.block("looks_seteffectto", fields={"EFFECT": [effect, None]})
        self.bind_arg(bid, "VALUE", val, 4)
        return bid

    def clear_effects(self) -> str:
        return self.block("looks_cleargraphiceffects")

    def go_xy(self, x, y) -> str:
        bid = self.block("motion_gotoxy")
        for k, v in (("X", x), ("Y", y)):
            if isinstance(v, tuple) and v[0] == "__EXPR__":
                self.expr_in(bid, k, v[1], 4)
            else:
                self.blocks[bid]["inputs"][k] = self.lit_num(v)
        return bid

    def change_x(self, dx) -> str:
        bid = self.block("motion_changexby")
        if isinstance(dx, tuple) and dx[0] == "__EXPR__":
            self.expr_in(bid, "DX", dx[1], 4)
        else:
            self.blocks[bid]["inputs"]["DX"] = self.lit_num(dx)
        return bid

    def change_y(self, dy) -> str:
        bid = self.block("motion_changeyby")
        if isinstance(dy, tuple) and dy[0] == "__EXPR__":
            self.expr_in(bid, "DY", dy[1], 4)
        else:
            self.blocks[bid]["inputs"]["DY"] = self.lit_num(dy)
        return bid

    def set_x(self, x) -> str:
        bid = self.block("motion_setx")
        if isinstance(x, tuple) and x[0] == "__EXPR__":
            self.expr_in(bid, "X", x[1], 4)
        else:
            self.blocks[bid]["inputs"]["X"] = self.lit_num(x)
        return bid

    def glide(self, secs, x, y) -> str:
        bid = self.block("motion_glidesecstoxy")
        self.bind_arg(bid, "SECS", secs, 4)
        self.bind_arg(bid, "X", x, 4)
        self.bind_arg(bid, "Y", y, 4)
        return bid

    def point_dir(self, angle) -> str:
        bid = self.block("motion_pointindirection")
        if isinstance(angle, tuple) and angle[0] == "__EXPR__":
            self.expr_in(bid, "DIRECTION", angle[1], 4)
        else:
            self.blocks[bid]["inputs"]["DIRECTION"] = self.lit_num(angle)
        return bid

    def play_sound(self, sound_name: str, until_done: bool = False) -> str:
        op = "sound_playuntildone" if until_done else "sound_play"
        bid = self.block(op)
        menu = self.block("sound_sounds_menu", fields={"SOUND_MENU": [sound_name, None]}, shadow=True)
        self.blocks[menu]["parent"] = bid
        self.blocks[bid]["inputs"]["SOUND_MENU"] = [1, menu]
        return bid

    def stop_sounds(self) -> str:
        return self.block("sound_stopallsounds")

    def set_volume(self, vol) -> str:
        bid = self.block("sound_setvolumeto")
        self.bind_arg(bid, "VOLUME", vol, 4)
        return bid

    # ---- Pen Extension & Custom Procedures ----
    def pen_clear(self) -> str:
        return self.block("pen_clear")

    def pen_down(self) -> str:
        return self.block("pen_penDown")

    def pen_up(self) -> str:
        return self.block("pen_penUp")

    def pen_set_size(self, sz) -> str:
        bid = self.block("pen_setPenSizeTo")
        if isinstance(sz, tuple) and sz[0] == "__EXPR__":
            self.expr_in(bid, "SIZE", sz[1], kind=4)
        else:
            self.blocks[bid]["inputs"]["SIZE"] = self.lit_num(sz)
        return bid

    def pen_set_color(self, col_expr) -> str:
        bid = self.block("pen_setPenColorToColor")
        if isinstance(col_expr, tuple) and col_expr[0] == "__EXPR__":
            expr_id = col_expr[1]
            self.blocks[expr_id]["parent"] = bid
            self.blocks[bid]["inputs"]["COLOR"] = [3, expr_id, [9, "#409832"]]
        else:
            self.blocks[bid]["inputs"]["COLOR"] = [1, [9, str(col_expr)]]
        return bid

    def define_proc(self, proccode: str, warp: bool = True, x: int = 480, y: int = 60) -> str:
        def_id = self.block("procedures_definition", top=True, x=x, y=y)
        proto_id = self.block("procedures_prototype", shadow=True)
        self.blocks[proto_id]["parent"] = def_id
        self.blocks[proto_id]["mutation"] = {
            "tagName": "mutation",
            "children": [],
            "proccode": proccode,
            "argumentids": "[]",
            "argumentnames": "[]",
            "argumentdefaults": "[]",
            "warp": "true" if warp else "false",
        }
        self.blocks[def_id]["inputs"]["custom_block"] = [1, proto_id]
        return def_id

    def call_proc(self, proccode: str, warp: bool = True) -> str:
        bid = self.block("procedures_call")
        self.blocks[bid]["mutation"] = {
            "tagName": "mutation",
            "children": [],
            "proccode": proccode,
            "argumentids": "[]",
            "warp": "true" if warp else "false",
        }
        return bid


def make_target(
    name: str,
    is_stage: bool = False,
    costumes: list[dict] | None = None,
    sounds: list[dict] | None = None,
    blocks: dict | None = None,
    variables: dict | None = None,
    broadcasts: dict | None = None,
    x: float = 0,
    y: float = 0,
    size: float = 100,
    direction: float = 90,
    visible: bool = False,
    layer_order: int = 1,
    volume: float = 100,
    rotation_style: str = "all around",
) -> dict:
    t = {
        "isStage": is_stage,
        "name": name,
        "variables": variables or {},
        "lists": {},
        "broadcasts": broadcasts or {},
        "blocks": blocks or {},
        "comments": {},
        "currentCostume": 0,
        "costumes": costumes or [],
        "sounds": sounds or [],
        "volume": volume,
        "layerOrder": layer_order,
    }
    if is_stage:
        t["tempo"] = 60
        t["videoTransparency"] = 50
        t["videoState"] = "on"
        t["textToSpeechLanguage"] = None
    else:
        t["visible"] = visible
        t["x"] = x
        t["y"] = y
        t["size"] = size
        t["direction"] = direction
        t["draggable"] = False
        t["rotationStyle"] = rotation_style
    return t


def build_svg_hud_labels() -> str:
    # Coordenadas exatas alinhadas com aeromattics_hud_inferior_medidores_circulares.png (480x360)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">'
        '<g fill="#f3d38b" font-family="Arial,Helvetica,sans-serif" font-weight="bold">'
        '<text x="27" y="310" font-size="8.5" letter-spacing="0.6">PONTOS</text>'
        '<text x="27" y="342" font-size="8.5" letter-spacing="0.6">TEMPO</text>'
        '<text x="351" y="310" font-size="8.5" letter-spacing="0.6">VIDAS</text>'
        '<text x="351" y="342" font-size="8.5" letter-spacing="0.6">FASE</text>'
        '<text x="195" y="340" text-anchor="middle" font-size="6.2" letter-spacing="0.4" fill="#e9c878">COMB.%</text>'
        '<text x="284" y="340" text-anchor="middle" font-size="6.2" letter-spacing="0.4" fill="#8dece2">ESTAB.</text>'
        '</g>'
        '</svg>'
    )


def build_svg_victory_text() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">'
        '<g text-anchor="middle" font-family="Arial,Helvetica,sans-serif">'
        '<text x="240" y="80" fill="#fff6d6" stroke="#081424" stroke-width="2.5" paint-order="stroke" '
        'font-size="10.5" font-weight="bold">Use ESPACO ou clique abaixo para voar de novo</text>'
        '</g>'
        '</svg>'
    )


def build_svg_gameover_text() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">'
        '<g text-anchor="middle" font-family="Arial,Helvetica,sans-serif">'
        '<text x="240" y="80" fill="#e6f7ff" stroke="#081424" stroke-width="2.5" paint-order="stroke" '
        'font-size="10.5" font-weight="bold">Pouso seguro realizado! Clique abaixo ou aperte ESPACO para tentar de novo</text>'
        '</g>'
        '</svg>'
    )


def build_svg_button(text: str, width: int = 136, height: int = 24, bg: str = "#1c6368", border: str = "#f3c75f") -> tuple[str, tuple[float, float]]:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect x="1.5" y="1.5" width="{width - 3}" height="{height - 3}" rx="6" ry="6" '
        f'fill="{bg}" stroke="{border}" stroke-width="2.5"/>'
        f'<text x="{width/2}" y="{height/2 + 4}" text-anchor="middle" fill="#fff4cf" '
        'font-family="Arial,Helvetica,sans-serif" font-size="10.5" font-weight="bold">'
        f'{text}</text>'
        '</svg>'
    )
    return svg, (width / 2.0, height / 2.0)


def validate_project(project: dict, archive_files: dict[str, bytes]):
    targets = project["targets"]
    stage = targets[0]
    assert stage["isStage"] is True, "Target 0 deve ser Stage"
    layers = [t["layerOrder"] for t in targets]
    assert sorted(layers) == list(range(len(targets))), f"layerOrder invalido: {layers}"

    global_var_ids = set(stage["variables"].keys())
    broadcast_ids = set(stage["broadcasts"].keys())

    for t in targets:
        local_var_ids = set(t.get("variables", {}).keys())
        all_var_ids = global_var_ids | local_var_ids
        for c in t["costumes"]:
            assert c["md5ext"] in archive_files, f"Costume ausente no zip: {c['md5ext']} em {t['name']}"
        for s in t["sounds"]:
            assert s["md5ext"] in archive_files, f"Som ausente no zip: {s['md5ext']} em {t['name']}"

        blocks = t["blocks"]
        for bid, b in blocks.items():
            assert isinstance(b, dict), f"Bloco nao-dict em {t['name']}: {bid}"
            if b.get("next") is not None:
                assert b["next"] in blocks, f"next inexistente {b['next']} em {t['name']}:{bid}"
                assert blocks[b["next"]]["parent"] == bid, f"parent mismatch em {t['name']}:{b['next']}"
            if b.get("parent") is not None:
                assert b["parent"] in blocks, f"parent inexistente {b['parent']} em {t['name']}:{bid}"
            else:
                assert b.get("topLevel") is True, f"Bloco sem parent e sem topLevel em {t['name']}:{bid}"
            for k, v in b.get("inputs", {}).items():
                if len(v) >= 2 and isinstance(v[1], str):
                    assert v[1] in blocks, f"input {k} aponta para bloco ausente {v[1]} em {t['name']}:{bid}"
                    assert blocks[v[1]]["parent"] == bid, f"input parent mismatch em {t['name']}:{v[1]}"
            if "VARIABLE" in b.get("fields", {}):
                vid = b["fields"]["VARIABLE"][1]
                assert vid in all_var_ids, f"Variavel desconhecida {vid} em {t['name']}:{bid}"
            if "BROADCAST_OPTION" in b.get("fields", {}):
                mid = b["fields"]["BROADCAST_OPTION"][1]
                assert mid in broadcast_ids, f"Broadcast desconhecido {mid} em {t['name']}:{bid}"


def build():
    with zipfile.ZipFile(BACKUP_SB3, "r") as orig_zip:
        orig_proj = json.loads(orig_zip.read("project.json").decode("utf-8"))
        orig_targets = {t["name"]: t for t in orig_proj["targets"]}

        reg = AssetRegistry()

        # Mapeamento global de variaveis
        V = {
            "Estado": ("Estado", "v_0"),
            "Pontos": ("Pontos", "v_1"),
            "Combustível": ("Combustível", "v_2"),
            "Vidas": ("Vidas", "v_3"),
            "Etapa": ("Etapa", "v_4"),
            "Rota": ("Rota", "v_5"),
            "Recorde": ("Recorde", "v_6"),
            "Proteção": ("Proteção", "v_7"),
            "Motivo": ("Motivo", "v_8"),
            "Som": ("Som", "v_9"),
            "Tempo de fase": ("Tempo de fase", "v_tempo_fase"),
            "Estabilidade": ("Estabilidade", "v_estab"),
            "Velocidade X": ("Velocidade X", "v_vx"),
            "Amplitude (A)": ("Amplitude (A)", "v_amp"),
            "Frequencia (w)": ("Frequencia (w)", "v_freq"),
            "Brisas Coletadas": ("Brisas Coletadas", "v_brisas"),
            "Segundo pontuado": ("Segundo pontuado", "v_last_sec"),
            "Último tempo do combustível": ("Último tempo do combustível", "v_fuel_clock"),
            "Vento Forca": ("Vento Forca", "v_vento"),
            "Vento Tempo": ("Vento Tempo", "v_vento_t"),
            "Etapa Vento": ("Etapa Vento", "v_et_vento"),
            "Migracao Lado": ("Migracao Lado", "v_mig_lado"),
            "Etapa Migracao": ("Etapa Migracao", "v_et_mig"),
            "Modo Sensor": ("Modo Sensor", "v_sensor"),
            "Posicao X Aviao": ("Posicao X Aviao", "v_px"),
            "Gamma Perspectiva": ("Gamma Perspectiva", "v_gamma"),
            "Y Horizonte": ("Y Horizonte", "v_y_horiz"),
            "Y Proximo": ("Y Proximo", "v_y_prox"),
            "Largura Rio Distante": ("Largura Rio Distante", "v_rio_w_dist"),
            "Largura Rio Proxima": ("Largura Rio Proxima", "v_rio_w_prox"),
            "Curva Rio Fase": ("Curva Rio Fase", "v_curva_rio"),
            "Semente Mundo": ("Semente Mundo", "v_seed_mundo"),
            "Z Mundo": ("Z Mundo", "v_z_mundo"),
            "Raia Ave": ("Raia Ave", "v_raia_ave"),
            "Raia Comb": ("Raia Comb", "v_raia_comb"),
            "Raia Brisa": ("Raia Brisa", "v_raia_brisa"),
            "Indice Onda": ("Indice Onda", "v_wave_idx"),
        }

        B = {
            "menu": ("menu", "msg_0"),
            "decolar": ("decolar", "msg_1"),
            "voar": ("voar", "msg_2"),
            "fim": ("fim", "msg_3"),
            "coleta": ("coleta", "msg_4"),
            "impacto": ("impacto", "msg_5"),
            "etapa": ("etapa", "msg_6"),
            "vento_rajada": ("vento_rajada", "msg_7"),
            "migracao_aviso": ("migracao_aviso", "msg_8"),
            "guia": ("guia", "msg_9"),
            "onda_passaro": ("onda_passaro", "msg_10"),
            "onda_comb": ("onda_comb", "msg_11"),
            "onda_brisa": ("onda_brisa", "msg_12"),
        }

        def add_reset_statements(sb: ScriptBuilder) -> list[str]:
            return [
                sb.set_var(*V["Pontos"], 0),
                sb.set_var(*V["Segundo pontuado"], 0),
                sb.set_var(*V["Combustível"], 100),
                sb.set_var(*V["Vidas"], 5),
                sb.set_var(*V["Etapa"], 1),
                sb.set_var(*V["Rota"], "FASE 1 - AMAZONIA", kind=10),
                sb.set_var(*V["Proteção"], 0),
                sb.set_var(*V["Motivo"], "", kind=10),
                sb.set_var(*V["Tempo de fase"], 0),
                sb.set_var(*V["Estabilidade"], 0),
                sb.set_var(*V["Velocidade X"], 0),
                sb.set_var(*V["Amplitude (A)"], 25),
                sb.set_var(*V["Frequencia (w)"], 2),
                sb.set_var(*V["Brisas Coletadas"], 0),
                sb.set_var(*V["Último tempo do combustível"], 0),
                sb.set_var(*V["Vento Forca"], 0),
                sb.set_var(*V["Vento Tempo"], 0),
                sb.set_var(*V["Etapa Vento"], 0),
                sb.set_var(*V["Migracao Lado"], 0),
                sb.set_var(*V["Etapa Migracao"], 0),
                sb.set_var(*V["Posicao X Aviao"], 0),
                sb.set_var(*V["Gamma Perspectiva"], 1.65),
                sb.set_var(*V["Y Horizonte"], 16),
                sb.set_var(*V["Y Proximo"], -108),
                sb.set_var(*V["Largura Rio Distante"], 26),
                sb.set_var(*V["Largura Rio Proxima"], 132),
                sb.set_var(*V["Curva Rio Fase"], 0),
                sb.set_var(*V["Semente Mundo"], 42),
                sb.set_var(*V["Z Mundo"], 0),
                sb.set_var(*V["Raia Ave"], 2),
                sb.set_var(*V["Raia Comb"], 4),
                sb.set_var(*V["Raia Brisa"], 1),
                sb.set_var(*V["Indice Onda"], 0),
            ]

        # ---------------- 0. STAGE ----------------
        sb_st = ScriptBuilder("st")
        # Bandeira verde
        sb_st.stack(
            sb_st.hat_flag(80, 60),
            sb_st.set_var(*V["Som"], 1),
            sb_st.set_var(*V["Recorde"], 0),
            sb_st.set_var(*V["Modo Sensor"], 0),
            sb_st.set_var(*V["Estado"], "menu", kind=10),
            *add_reset_statements(sb_st),
            sb_st.broadcast(*B["menu"]),
        )
        # Ao receber menu
        sb_st.stack(
            sb_st.hat_broadcast(*B["menu"], 80, 620),
            sb_st.set_var(*V["Estado"], "menu", kind=10),
            sb_st.stop_sounds(),
            sb_st.hide_var(*V["Pontos"]),
            sb_st.hide_var(*V["Combustível"]),
            sb_st.hide_var(*V["Vidas"]),
            sb_st.hide_var(*V["Rota"]),
            sb_st.hide_var(*V["Recorde"]),
        )
        # Ao receber decolar
        sb_st.stack(
            sb_st.hat_broadcast(*B["decolar"], 80, 960),
            *add_reset_statements(sb_st),
            sb_st.set_var(*V["Semente Mundo"], sb_st.rand(1, 99)),
            sb_st.stop_sounds(),
            sb_st.set_volume(45),
            sb_st.if_then(
                sb_st.eq(sb_st.var(*V["Som"]), 1),
                sb_st.play_sound("Decolagem"),
            ),
            sb_st.wait(2.8),
            sb_st.reset_timer(),
            sb_st.set_var(*V["Último tempo do combustível"], sb_st.timer()),
            sb_st.set_var(*V["Estado"], "voo", kind=10),
            sb_st.broadcast(*B["voar"]),
        )
        # Avanco suave de camera durante decolagem na pista
        sb_st.stack(
            sb_st.hat_broadcast(*B["decolar"], 80, 1460),
            sb_st.repeat_until(
                sb_st.bool_not(sb_st.eq(sb_st.var(*V["Estado"]), "decolagem")),
                sb_st.change_var(*V["Z Mundo"], 0.04),
            ),
        )
        # Loop 1 do voo: tempo de fase atomico, pontos/s, consumo progressivo (0.65/s), protecao, vento, derrotas
        not_voo = sb_st.bool_not(sb_st.eq(sb_st.var(*V["Estado"]), "voo"))
        delta_fuel = sb_st.mul(sb_st.sub(sb_st.timer(), sb_st.var(*V["Último tempo do combustível"])), 0.65)
        phase_time_expr = sb_st.mathop("floor", sb_st.sub(sb_st.timer(), sb_st.mul(sb_st.sub(sb_st.var(*V["Etapa"]), 1), 40)))
        sec_floor = lambda: sb_st.mathop("floor", sb_st.timer())

        sb_st.stack(
            sb_st.hat_broadcast(*B["voar"], 520, 60),
            sb_st.repeat_until(
                not_voo,
                sb_st.wait(0.1),
                sb_st.if_then(
                    sb_st.eq(sb_st.var(*V["Estado"]), "voo"),
                    sb_st.if_then(
                        sb_st.bool_and(sb_st.lt(sb_st.var(*V["Etapa"]), 2), sb_st.gt(sb_st.timer(), 39.95)),
                        sb_st.set_var(*V["Etapa"], 2),
                        sb_st.set_var(*V["Rota"], "FASE 2 - CERRADO", kind=10),
                        sb_st.broadcast(*B["etapa"]),
                    ),
                    sb_st.if_then(
                        sb_st.bool_and(sb_st.lt(sb_st.var(*V["Etapa"]), 3), sb_st.gt(sb_st.timer(), 79.95)),
                        sb_st.set_var(*V["Etapa"], 3),
                        sb_st.set_var(*V["Rota"], "FASE 3 - PANTANAL", kind=10),
                        sb_st.broadcast(*B["etapa"]),
                    ),
                    sb_st.if_then(
                        sb_st.bool_and(sb_st.lt(sb_st.var(*V["Etapa"]), 4), sb_st.gt(sb_st.timer(), 119.95)),
                        sb_st.set_var(*V["Etapa"], 4),
                        sb_st.set_var(*V["Rota"], "FASE 4 - MATA ATLANTICA", kind=10),
                        sb_st.broadcast(*B["etapa"]),
                    ),
                    sb_st.set_var(*V["Tempo de fase"], phase_time_expr),
                    sb_st.if_then(
                        sb_st.lt(sb_st.var(*V["Tempo de fase"]), 0),
                        sb_st.set_var(*V["Tempo de fase"], 0),
                    ),
                    sb_st.if_then(
                        sb_st.gt(sec_floor(), sb_st.var(*V["Segundo pontuado"])),
                        sb_st.change_var(*V["Pontos"], sb_st.mul(sb_st.sub(sec_floor(), sb_st.var(*V["Segundo pontuado"])), 2)),
                        sb_st.if_then(
                            sb_st.bool_not(sb_st.gt(sb_st.mathop("abs", sb_st.var(*V["Estabilidade"])), 12)),
                            sb_st.change_var(*V["Pontos"], sb_st.sub(sec_floor(), sb_st.var(*V["Segundo pontuado"]))),
                        ),
                        sb_st.set_var(*V["Segundo pontuado"], sec_floor()),
                    ),
                    sb_st.set_var(*V["Combustível"], sb_st.sub(sb_st.var(*V["Combustível"]), delta_fuel)),
                    sb_st.set_var(*V["Último tempo do combustível"], sb_st.timer()),
                    sb_st.if_then(
                        sb_st.gt(sb_st.var(*V["Proteção"]), 0),
                        sb_st.change_var(*V["Proteção"], -0.1),
                        sb_st.if_then(
                            sb_st.lt(sb_st.var(*V["Proteção"]), 0),
                            sb_st.set_var(*V["Proteção"], 0),
                        ),
                    ),
                    sb_st.if_then(
                        sb_st.gt(sb_st.var(*V["Vento Tempo"]), 0),
                        sb_st.change_var(*V["Vento Tempo"], -0.1),
                        sb_st.if_then(
                            sb_st.lt(sb_st.var(*V["Vento Tempo"]), 0.05),
                            sb_st.set_var(*V["Vento Tempo"], 0),
                            sb_st.set_var(*V["Vento Forca"], 0),
                        ),
                    ),
                    sb_st.if_then(
                        sb_st.gt(sb_st.var(*V["Pontos"]), sb_st.var(*V["Recorde"])),
                        sb_st.set_var(*V["Recorde"], sb_st.var(*V["Pontos"])),
                    ),
                    sb_st.if_then(
                        sb_st.lt(sb_st.var(*V["Combustível"]), 1),
                        sb_st.set_var(*V["Combustível"], 0),
                        sb_st.set_var(*V["Motivo"], "O combustível acabou.", kind=10),
                        sb_st.set_var(*V["Estado"], "queda", kind=10),
                        sb_st.broadcast(*B["fim"]),
                    ),
                    sb_st.if_then(
                        sb_st.lt(sb_st.var(*V["Vidas"]), 1),
                        sb_st.set_var(*V["Vidas"], 0),
                        sb_st.set_var(*V["Motivo"], "O avião sofreu cinco impactos.", kind=10),
                        sb_st.set_var(*V["Estado"], "queda", kind=10),
                        sb_st.broadcast(*B["fim"]),
                    ),
                ),
            ),
        )
        # Loop 2 do voo: rajadas, migracao e vitoria aos 160s (fases sao atualizadas atomicamente no Loop 1)
        sb_st.stack(
            sb_st.hat_broadcast(*B["voar"], 520, 720),
            sb_st.repeat_until(
                sb_st.bool_not(sb_st.eq(sb_st.var(*V["Estado"]), "voo")),
                # 1 rajada de vento controlada por bioma (aos 12s de cada fase, duracao 6s)
                sb_st.if_then(
                    sb_st.bool_and(
                        sb_st.gt(sb_st.var(*V["Etapa"]), sb_st.var(*V["Etapa Vento"])),
                        sb_st.gt(sb_st.var(*V["Tempo de fase"]), 11.9),
                    ),
                    sb_st.set_var(*V["Etapa Vento"], sb_st.var(*V["Etapa"])),
                    sb_st.set_var(*V["Vento Tempo"], 6.0),
                    sb_st.if_else(
                        sb_st.eq(sb_st.mod(sb_st.var(*V["Etapa"]), 2), 1),
                        [sb_st.set_var(*V["Vento Forca"], 1)],
                        [sb_st.set_var(*V["Vento Forca"], -1)],
                    ),
                    sb_st.broadcast(*B["vento_rajada"]),
                ),
                # 1 bando de aves em migracao por bioma (aos 25s de cada fase)
                sb_st.if_then(
                    sb_st.bool_and(
                        sb_st.gt(sb_st.var(*V["Etapa"]), sb_st.var(*V["Etapa Migracao"])),
                        sb_st.gt(sb_st.var(*V["Tempo de fase"]), 24.9),
                    ),
                    sb_st.set_var(*V["Etapa Migracao"], sb_st.var(*V["Etapa"])),
                    sb_st.if_else(
                        sb_st.eq(sb_st.mod(sb_st.var(*V["Etapa"]), 2), 1),
                        [sb_st.set_var(*V["Migracao Lado"], -1)],
                        [sb_st.set_var(*V["Migracao Lado"], 1)],
                    ),
                    sb_st.broadcast(*B["migracao_aviso"]),
                ),
                sb_st.if_then(
                    sb_st.bool_and(
                        sb_st.bool_and(sb_st.eq(sb_st.var(*V["Etapa"]), 4), sb_st.gt(sb_st.timer(), 159.95)),
                        sb_st.bool_and(
                            sb_st.eq(sb_st.var(*V["Estado"]), "voo"),
                            sb_st.bool_and(sb_st.gt(sb_st.var(*V["Vidas"]), 0), sb_st.gt(sb_st.var(*V["Combustível"]), 0)),
                        ),
                    ),
                    sb_st.change_var(*V["Pontos"], 50),
                    sb_st.if_then(
                        sb_st.gt(sb_st.var(*V["Pontos"]), sb_st.var(*V["Recorde"])),
                        sb_st.set_var(*V["Recorde"], sb_st.var(*V["Pontos"])),
                    ),
                    sb_st.set_var(*V["Motivo"], "Missão concluída!", kind=10),
                    sb_st.set_var(*V["Estado"], "fim", kind=10),
                    sb_st.broadcast(*B["fim"]),
                ),
                sb_st.wait(0.1),
            ),
        )
        # Loop 3: alerta de combustivel baixo
        sb_st.stack(
            sb_st.hat_broadcast(*B["voar"], 960, 60),
            sb_st.repeat_until(
                sb_st.bool_not(sb_st.eq(sb_st.var(*V["Estado"]), "voo")),
                sb_st.if_then(
                    sb_st.bool_and(sb_st.lt(sb_st.var(*V["Combustível"]), 25), sb_st.eq(sb_st.var(*V["Som"]), 1)),
                    sb_st.play_sound("Alerta"),
                ),
                sb_st.wait(3.5),
            ),
        )
        # Loop 4: som suave do motor
        sb_st.stack(
            sb_st.hat_broadcast(*B["voar"], 960, 320),
            sb_st.set_volume(14),
            sb_st.repeat_until(
                sb_st.bool_not(sb_st.eq(sb_st.var(*V["Estado"]), "voo")),
                sb_st.if_else(
                    sb_st.eq(sb_st.var(*V["Som"]), 1),
                    [sb_st.play_sound("Motor", until_done=True)],
                    [sb_st.wait(0.2)],
                ),
            ),
        )
        # Loop 5: avanco continuo Z Mundo progressivo por bioma (0.11..0.14) + fase do rio a 30 FPS
        sb_st.stack(
            sb_st.hat_broadcast(*B["voar"], 960, 450),
            sb_st.repeat_until(
                sb_st.bool_not(sb_st.eq(sb_st.var(*V["Estado"]), "voo")),
                sb_st.change_var(*V["Z Mundo"], sb_st.add(0.10, sb_st.mul(0.01, sb_st.var(*V["Etapa"])))),
                sb_st.set_var(*V["Curva Rio Fase"], sb_st.mul(sb_st.timer(), 22)),
            ),
        )
        # Loop 6: Diretor sincronizado das 5 raias radiais (garante 0 sobreposicao ave / galao / brisa por onda)
        sb_st.stack(
            sb_st.hat_broadcast(*B["voar"], 1360, 880),
            sb_st.wait(1.0),
            sb_st.repeat_until(
                sb_st.bool_not(sb_st.eq(sb_st.var(*V["Estado"]), "voo")),
                sb_st.set_var(
                    *V["Semente Mundo"],
                    sb_st.mod(
                        sb_st.add(sb_st.add(sb_st.mul(sb_st.var(*V["Semente Mundo"]), 37), sb_st.mul(sb_st.var(*V["Etapa"]), 19)), 11),
                        100,
                    ),
                ),
                sb_st.set_var(*V["Raia Ave"], sb_st.mod(sb_st.var(*V["Semente Mundo"]), 5)),
                sb_st.set_var(*V["Raia Comb"], sb_st.mod(sb_st.add(sb_st.var(*V["Raia Ave"]), 2), 5)),
                sb_st.set_var(*V["Raia Brisa"], sb_st.mod(sb_st.add(sb_st.var(*V["Raia Ave"]), 4), 5)),
                sb_st.change_var(*V["Indice Onda"], 1),
                sb_st.if_then(sb_st.eq(sb_st.var(*V["Estado"]), "voo"), sb_st.broadcast(*B["onda_passaro"])),
                sb_st.wait(2.0),
                sb_st.if_then(
                    sb_st.bool_and(
                        sb_st.eq(sb_st.var(*V["Estado"]), "voo"),
                        sb_st.bool_or(
                            sb_st.lt(sb_st.var(*V["Combustível"]), 35),
                            sb_st.bool_not(sb_st.eq(sb_st.mod(sb_st.var(*V["Indice Onda"]), 3), 0)),
                        ),
                    ),
                    sb_st.broadcast(*B["onda_comb"]),
                ),
                sb_st.wait(2.0),
                sb_st.if_then(
                    sb_st.bool_and(
                        sb_st.eq(sb_st.var(*V["Estado"]), "voo"),
                        sb_st.eq(sb_st.mod(sb_st.var(*V["Indice Onda"]), 2), 1),
                    ),
                    sb_st.broadcast(*B["onda_brisa"]),
                ),
                sb_st.wait(2.2),
            ),
        )
        # Eventos de som e encerramento
        for msg_key, snd_name, yy in [("coleta", "Coleta", 580), ("impacto", "Impacto", 720), ("etapa", "Nova etapa", 860)]:
            sb_st.stack(
                sb_st.hat_broadcast(*B[msg_key], 960, yy),
                sb_st.if_then(
                    sb_st.eq(sb_st.var(*V["Som"]), 1),
                    sb_st.set_volume(50),
                    sb_st.play_sound(snd_name),
                ),
            )
        sb_st.stack(
            sb_st.hat_broadcast(*B["fim"], 960, 1020),
            sb_st.set_var(*V["Vento Forca"], 0),
            sb_st.set_var(*V["Vento Tempo"], 0),
            sb_st.set_var(*V["Migracao Lado"], 0),
            sb_st.set_var(*V["Estabilidade"], 0),
            sb_st.if_then(
                sb_st.gt(sb_st.var(*V["Pontos"]), sb_st.var(*V["Recorde"])),
                sb_st.set_var(*V["Recorde"], sb_st.var(*V["Pontos"])),
            ),
            sb_st.stop_sounds(),
            sb_st.if_then(
                sb_st.eq(sb_st.var(*V["Som"]), 1),
                sb_st.set_volume(50),
                sb_st.play_sound("Fim"),
            ),
            sb_st.if_then(
                sb_st.eq(sb_st.var(*V["Estado"]), "queda"),
                sb_st.wait(1.3),
            ),
            sb_st.set_var(*V["Estado"], "fim", kind=10),
        )
        # Teclas: M som, G guia, C modo sensor, ESPACO / R / SETA CIMA decolar ou recomecar (Makey Makey)
        sb_st.stack(
            sb_st.hat_key("m", 1360, 60),
            sb_st.if_else(
                sb_st.eq(sb_st.var(*V["Som"]), 1),
                [sb_st.set_var(*V["Som"], 0), sb_st.stop_sounds()],
                [sb_st.set_var(*V["Som"], 1)],
            ),
        )
        sb_st.stack(
            sb_st.hat_key("g", 1360, 190),
            sb_st.if_else(
                sb_st.eq(sb_st.var(*V["Estado"]), "menu"),
                [sb_st.set_var(*V["Estado"], "guia", kind=10), sb_st.broadcast(*B["guia"])],
                [sb_st.if_then(
                    sb_st.eq(sb_st.var(*V["Estado"]), "guia"),
                    sb_st.set_var(*V["Estado"], "menu", kind=10),
                    sb_st.broadcast(*B["menu"]),
                )],
            ),
        )
        sb_st.stack(
            sb_st.hat_key("c", 1360, 320),
            sb_st.if_else(
                sb_st.eq(sb_st.var(*V["Modo Sensor"]), 1),
                [sb_st.set_var(*V["Modo Sensor"], 0)],
                [sb_st.set_var(*V["Modo Sensor"], 1)],
            ),
        )
        sb_st.stack(
            sb_st.hat_key("space", 1360, 450),
            sb_st.if_then(
                sb_st.bool_or(sb_st.eq(sb_st.var(*V["Estado"]), "menu"), sb_st.eq(sb_st.var(*V["Estado"]), "fim")),
                sb_st.set_var(*V["Estado"], "decolagem", kind=10),
                sb_st.broadcast(*B["decolar"]),
            ),
        )
        sb_st.stack(
            sb_st.hat_key("up arrow", 1360, 580),
            sb_st.if_then(
                sb_st.bool_or(sb_st.eq(sb_st.var(*V["Estado"]), "menu"), sb_st.eq(sb_st.var(*V["Estado"]), "fim")),
                sb_st.set_var(*V["Estado"], "decolagem", kind=10),
                sb_st.broadcast(*B["decolar"]),
            ),
        )
        sb_st.stack(
            sb_st.hat_key("r", 1360, 710),
            sb_st.if_then(
                sb_st.eq(sb_st.var(*V["Estado"]), "fim"),
                sb_st.set_var(*V["Estado"], "decolagem", kind=10),
                sb_st.broadcast(*B["decolar"]),
            ),
        )

        stage_vars = {vid: [vname, 0] for vname, vid in V.values()}
        stage_vars["v_0"] = ["Estado", "menu"]
        stage_vars["v_2"] = ["Combustível", 100]
        stage_vars["v_3"] = ["Vidas", 5]
        stage_vars["v_4"] = ["Etapa", 1]
        stage_vars["v_5"] = ["Rota", "FASE 1 - AMAZONIA"]
        stage_vars["v_8"] = ["Motivo", ""]
        stage_vars["v_9"] = ["Som", 1]
        stage_vars["v_estab"] = ["Estabilidade", 0]
        stage_vars["v_amp"] = ["Amplitude (A)", 25]
        stage_vars["v_freq"] = ["Frequencia (w)", 2]
        stage_vars["v_sensor"] = ["Modo Sensor", 0]
        stage_vars["v_px"] = ["Posicao X Aviao", 0]
        stage_vars["v_gamma"] = ["Gamma Perspectiva", 1.65]
        stage_vars["v_y_horiz"] = ["Y Horizonte", 16]
        stage_vars["v_y_prox"] = ["Y Proximo", -108]
        stage_vars["v_rio_w_dist"] = ["Largura Rio Distante", 26]
        stage_vars["v_rio_w_prox"] = ["Largura Rio Proxima", 132]
        stage_vars["v_curva_rio"] = ["Curva Rio Fase", 0]
        stage_vars["v_seed_mundo"] = ["Semente Mundo", 42]
        stage_vars["v_raia_ave"] = ["Raia Ave", 2]
        stage_vars["v_raia_comb"] = ["Raia Comb", 4]
        stage_vars["v_raia_brisa"] = ["Raia Brisa", 1]
        stage_vars["v_wave_idx"] = ["Indice Onda", 0]

        stage_target = make_target(
            "Stage",
            is_stage=True,
            costumes=[reg.costume_from_raw(c, orig_zip) for c in orig_targets["Stage"]["costumes"]],
            sounds=[reg.sound_from_raw(s, orig_zip) for s in orig_targets["Stage"]["sounds"]],
            blocks=sb_st.blocks,
            variables=stage_vars,
            broadcasts={mid: mname for mname, mid in B.values()},
            layer_order=0,
        )

        # ---------------- FUNCOES AUXILIARES DE PROJECAO 2.5D E MUNDO PROCEDURAL ----------------
        def p_of_d(sb: ScriptBuilder, d_expr):
            return sb.mathop("e ^", sb.mul(sb.var(*V["Gamma Perspectiva"]), sb.mathop("ln", d_expr)))

        def air_y_of_p(sb: ScriptBuilder, p_expr):
            return sb.sub(44, sb.mul(148, p_expr))

        def air_x_of_dp(sb: ScriptBuilder, x0_var: tuple[str, str], p_expr):
            return sb.add(
                sb.round_op(sb.mul(-0.10, sb.var(*V["Posicao X Aviao"]))),
                sb.mul(sb.var(*x0_var), sb.add(0.22, sb.mul(0.78, p_expr))),
            )

        def river_world_x_at_z(sb: ScriptBuilder, z_var: tuple[str, str]):
            ang1 = sb.add(
                sb.mul(12.6, sb.var(*z_var)),
                sb.add(sb.mul(63, sb.var(*V["Etapa"])), sb.mul(3.6, sb.var(*V["Semente Mundo"]))),
            )
            ang2 = sb.mul(6.3, sb.var(*z_var))
            return sb.add(sb.mul(42, sb.mathop("sin", ang1)), sb.mul(18, sb.mathop("cos", ang2)))

        # ---------------- 1. CENARIO (Ceu degradê limpo + Horizonte real dos 4 biomas) ----------------
        sb_cen = ScriptBuilder("cen")
        cen_par_x = lambda: sb_cen.round_op(sb_cen.mul(-0.08, sb_cen.var(*V["Posicao X Aviao"])))
        cen_costume_expr = lambda: sb_cen.add(
            sb_cen.mul(3, sb_cen.sub(sb_cen.var(*V["Etapa"]), 1)),
            sb_cen.add(sb_cen.mod(sb_cen.mathop("floor", sb_cen.div(sb_cen.timer(), 0.45)), 3), 1),
        )
        sb_cen.stack(
            sb_cen.hat_flag(80, 60),
            sb_cen.go_xy(0, 0),
            sb_cen.set_size(100),
            sb_cen.go_layer("back"),
            sb_cen.clear_effects(),
            sb_cen.switch_costume("Horizonte 1 - Q1"),
            sb_cen.show(),
        )
        sb_cen.stack(
            sb_cen.hat_broadcast(*B["menu"], 80, 320),
            sb_cen.go_xy(0, 0),
            sb_cen.set_size(100),
            sb_cen.switch_costume("Horizonte 1 - Q1"),
            sb_cen.show(),
        )
        sb_cen.stack(
            sb_cen.hat_broadcast(*B["guia"], 80, 480),
            sb_cen.go_xy(0, 0),
            sb_cen.set_size(100),
            sb_cen.switch_costume("Horizonte 1 - Q1"),
            sb_cen.show(),
        )
        sb_cen.stack(
            sb_cen.hat_broadcast(*B["decolar"], 80, 640),
            sb_cen.go_xy(0, 0),
            sb_cen.set_size(100),
            sb_cen.switch_costume("Horizonte 1 - Q1"),
            sb_cen.show(),
        )
        sb_cen.stack(
            sb_cen.hat_broadcast(*B["fim"], 80, 800),
            sb_cen.go_xy(0, 0),
        )
        sb_cen.stack(
            sb_cen.hat_broadcast(*B["etapa"], 440, 60),
            sb_cen.switch_costume(cen_costume_expr()),
        )
        sb_cen.stack(
            sb_cen.hat_broadcast(*B["voar"], 440, 260),
            sb_cen.set_volume(12),
            sb_cen.repeat_until(
                sb_cen.bool_not(sb_cen.eq(sb_cen.var(*V["Estado"]), "voo")),
                sb_cen.if_else(
                    sb_cen.eq(sb_cen.var(*V["Som"]), 1),
                    [sb_cen.play_sound("Cloud Glider", until_done=True)],
                    [sb_cen.wait(0.2)],
                ),
            ),
        )
        sb_cen.stack(
            sb_cen.hat_broadcast(*B["voar"], 440, 560),
            sb_cen.set_size(100),
            sb_cen.repeat_until(
                sb_cen.bool_not(sb_cen.eq(sb_cen.var(*V["Estado"]), "voo")),
                sb_cen.switch_costume(cen_costume_expr()),
                sb_cen.go_xy(cen_par_x(), 0),
            ),
            sb_cen.go_xy(0, 0),
        )
        cen_costumes = []
        for b_idx in range(1, 5):
            for q_idx in range(1, 4):
                cen_costumes.append(
                    reg.costume_from_image(
                        ORG_DIR / "09_cenarios_vivos" / f"horizonte_bioma{b_idx}_q{q_idx}.png",
                        f"Horizonte {b_idx} - Q{q_idx}",
                        bitmap_resolution=2,
                        center=(560, 360),
                    )
                )
        cen_target = make_target(
            "cenario",
            costumes=cen_costumes,
            sounds=[reg.sound_from_raw(s, orig_zip) for s in orig_targets["cenario"]["sounds"]],
            blocks=sb_cen.blocks,
            size=100,
            visible=True,
            layer_order=1,
            volume=12,
        )

        # ---------------- 2. SOL VOXEL QUADRADO (Ceu direito livre + pulso suave sem poluir) ----------------
        sb_sol = ScriptBuilder("sol")
        sol_par_x = lambda: sb_sol.round_op(sb_sol.mul(-0.08, sb_sol.var(*V["Posicao X Aviao"])))
        sol_par_y = lambda: sb_sol.round_op(sb_sol.mul(1.5, sb_sol.mathop("sin", sb_sol.mul(sb_sol.timer(), 20))))
        sol_costume_expr = lambda: sb_sol.add(sb_sol.mod(sb_sol.mathop("floor", sb_sol.div(sb_sol.timer(), 0.45)), 3), 1)
        sb_sol.stack(sb_sol.hat_flag(80, 60), sb_sol.go_xy(172, 130), sb_sol.set_size(48), sb_sol.hide())
        sb_sol.stack(sb_sol.hat_broadcast(*B["menu"], 80, 220), sb_sol.hide())
        sb_sol.stack(sb_sol.hat_broadcast(*B["guia"], 80, 320), sb_sol.hide())
        sb_sol.stack(sb_sol.hat_broadcast(*B["fim"], 80, 420), sb_sol.hide())
        sb_sol.stack(
            sb_sol.hat_broadcast(*B["decolar"], 80, 540),
            sb_sol.go_xy(172, 130),
            sb_sol.set_size(48),
            sb_sol.set_effect("ghost", 8),
            sb_sol.show(),
            sb_sol.repeat_until(
                sb_sol.bool_or(
                    sb_sol.bool_or(sb_sol.eq(sb_sol.var(*V["Estado"]), "menu"), sb_sol.eq(sb_sol.var(*V["Estado"]), "guia")),
                    sb_sol.eq(sb_sol.var(*V["Estado"]), "fim"),
                ),
                sb_sol.next_costume(),
                sb_sol.wait(0.45),
            ),
            sb_sol.hide(),
        )
        sb_sol.stack(
            sb_sol.hat_broadcast(*B["voar"], 460, 60),
            sb_sol.set_size(48),
            sb_sol.set_effect("ghost", 8),
            sb_sol.show(),
            sb_sol.repeat_until(
                sb_sol.bool_not(sb_sol.eq(sb_sol.var(*V["Estado"]), "voo")),
                sb_sol.switch_costume(sol_costume_expr()),
                sb_sol.go_xy(sb_sol.add(172, sol_par_x()), sb_sol.add(130, sol_par_y())),
            ),
            sb_sol.hide(),
        )
        sol_costumes = [
            reg.costume_from_image(ORG_DIR / "05_nuvens_voxel" / f"sol_voxel_q{i}.png", f"Sol {i}", bitmap_resolution=2, center=(80, 80))
            for i in range(1, 4)
        ]
        sol_target = make_target(
            "Sol",
            costumes=sol_costumes,
            blocks=sb_sol.blocks,
            x=172,
            y=130,
            size=48,
            visible=False,
            layer_order=2,
        )

        # ---------------- 3. TERRENO PROCEDURAL PEN (Mode-7 O(1) rapido para 30 FPS reais no Scratch 3.0) ----------------
        sb_pen = ScriptBuilder("pen")
        pen_vars_spec = [
            ("sy", "v_p_sy", 28), ("dy", "v_p_dy", 5), ("step", "v_p_step", 2),
            ("zw", "v_p_zw", 0), ("tz", "v_p_tz", 0), ("sx", "v_p_sx", 0.1),
            ("fog", "v_p_fog", 0), ("ft", "v_p_ft", 0),
            ("rcx", "v_p_rcx", 0), ("rhw", "v_p_rhw", 10), ("shw", "v_p_shw", 3), ("tw", "v_p_tw", 10),
            ("xl", "v_p_xl", 0), ("xr", "v_p_xr", 0),
            ("cap", "v_p_cap", 2), ("trim", "v_p_trim", 2), ("glx", "v_p_glx", 0), ("glw", "v_p_glw", 2),
            ("ri", "v_p_ri", 0), ("tk", "v_p_tk", 0), ("pass", "v_p_pass", 1),
            ("flux", "v_p_flux", 0), ("zrel", "v_p_zrel", 4), ("ulat", "v_p_ulat", 0),
            ("x2", "v_p_x2", 0), ("y2", "v_p_y2", 0),
            ("rf", "v_p_rf", 108), ("gf", "v_p_gf", 174), ("bf", "v_p_bf", 124),
            ("ra", "v_p_ra", 62), ("ga", "v_p_ga", 138), ("ba", "v_p_ba", 48),
            ("rb", "v_p_rb", 52), ("gb", "v_p_gb", 122), ("bb", "v_p_bb", 42),
            ("ro", "v_p_ro", 46), ("go", "v_p_go", 112), ("bo", "v_p_bo", 38),
            ("rs", "v_p_rs", 190), ("gs", "v_p_gs", 170), ("bs", "v_p_bs", 120),
            ("rw1", "v_p_rw1", 32), ("gw1", "v_p_gw1", 126), ("bw1", "v_p_bw1", 184),
            ("rw2", "v_p_rw2", 28), ("gw2", "v_p_gw2", 114), ("bw2", "v_p_bw2", 168),
            ("rgl", "v_p_rgl", 86), ("ggl", "v_p_ggl", 178), ("bgl", "v_p_bgl", 224),
            ("ca", "v_p_ca", 4098608), ("cb", "v_p_cb", 3439146), ("co", "v_p_co", 3043366),
            ("cs", "v_p_cs", 12495480), ("cw1", "v_p_cw1", 2129592), ("cw2", "v_p_cw2", 1864360), ("cgl", "v_p_cgl", 5681888),
        ]
        PV = {k: (f"Pen {k}", vid) for k, vid, _ in pen_vars_spec}

        def pack_fog_rgb(rv, gv, bv):
            mix = lambda cur, fogc: sb_pen.round_op(
                sb_pen.add(sb_pen.var(*cur), sb_pen.mul(sb_pen.sub(sb_pen.var(*fogc), sb_pen.var(*cur)), sb_pen.var(*PV["fog"])))
            )
            return sb_pen.add(
                sb_pen.add(sb_pen.mul(mix(rv, PV["rf"]), 65536), sb_pen.mul(mix(gv, PV["gf"]), 256)),
                mix(bv, PV["bf"]),
            )

        def draw_hspan(x1_expr, x2_expr) -> list[str]:
            return [
                sb_pen.set_var(*PV["xl"], x1_expr),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["xl"]), -240), sb_pen.set_var(*PV["xl"], -240)),
                sb_pen.set_var(*PV["xr"], x2_expr),
                sb_pen.if_then(sb_pen.gt(sb_pen.var(*PV["xr"]), 240), sb_pen.set_var(*PV["xr"], 240)),
                sb_pen.if_then(
                    sb_pen.gt(sb_pen.var(*PV["xr"]), sb_pen.var(*PV["xl"])),
                    sb_pen.go_xy(sb_pen.var(*PV["xl"]), sb_pen.var(*PV["sy"])),
                    sb_pen.pen_down(),
                    sb_pen.set_x(sb_pen.var(*PV["xr"])),
                    sb_pen.pen_up(),
                ),
            ]

        def set_biome_palette(pal_tuple: tuple) -> list[str]:
            keys = ("rf", "gf", "bf", "ra", "ga", "ba", "rb", "gb", "bb", "ro", "go", "bo", "rs", "gs", "bs", "rw1", "gw1", "bw1", "rw2", "gw2", "bw2", "rgl", "ggl", "bgl")
            stmts = [sb_pen.set_var(*PV[k], val) for k, val in zip(keys, pal_tuple)]
            for cname, (rk, gk, bk) in (
                ("ca", ("ra", "ga", "ba")),
                ("cb", ("rb", "gb", "bb")),
                ("co", ("ro", "go", "bo")),
                ("cs", ("rs", "gs", "bs")),
                ("cw1", ("rw1", "gw1", "bw1")),
                ("cw2", ("rw2", "gw2", "bw2")),
                ("cgl", ("rgl", "ggl", "bgl")),
            ):
                r_v, g_v, b_v = pal_tuple[keys.index(rk)], pal_tuple[keys.index(gk)], pal_tuple[keys.index(bk)]
                stmts.append(sb_pen.set_var(*PV[cname], (r_v << 16) + (g_v << 8) + b_v))
            return stmts

        # Paletas naturais calmas por bioma (baixo contraste <= 14 RGB no solo anti-tontura + rio em 3 camadas)
        pal_b1 = (108, 174, 124, 62, 144, 52, 55, 136, 46, 48, 128, 41, 192, 172, 122, 62, 162, 212, 26, 114, 176, 86, 184, 224)
        pal_b2 = (162, 168, 102, 156, 158, 62, 148, 150, 56, 140, 142, 50, 206, 156, 94, 72, 172, 210, 32, 122, 172, 96, 192, 226)
        pal_b3 = (116, 178, 134, 68, 152, 62, 61, 144, 56, 54, 136, 50, 212, 198, 152, 76, 176, 208, 34, 124, 168, 98, 194, 228)
        pal_b4 = (104, 168, 130, 56, 140, 54, 49, 132, 48, 42, 124, 42, 188, 176, 146, 58, 156, 210, 22, 102, 166, 82, 176, 220)

        def draw_fast_center_span(hw_fn) -> list[str]:
            """Desenha faixa centrada em rcx com nos de expressao frescos para xl e xr."""
            return [
                sb_pen.set_var(*PV["xl"], sb_pen.sub(sb_pen.var(*PV["rcx"]), hw_fn())),
                sb_pen.set_var(*PV["xr"], sb_pen.add(sb_pen.var(*PV["rcx"]), hw_fn())),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["xl"]), -240), sb_pen.set_var(*PV["xl"], -240)),
                sb_pen.if_then(sb_pen.gt(sb_pen.var(*PV["xr"]), 240), sb_pen.set_var(*PV["xr"], 240)),
                sb_pen.if_then(
                    sb_pen.gt(sb_pen.var(*PV["xr"]), sb_pen.var(*PV["xl"])),
                    sb_pen.go_xy(sb_pen.var(*PV["xl"]), sb_pen.var(*PV["sy"])),
                    sb_pen.pen_down(),
                    sb_pen.set_x(sb_pen.var(*PV["xr"])),
                    sb_pen.pen_up(),
                ),
            ]

        def pack_mix_rgb(rv, gv, bv, tr, tg, tb):
            mix = lambda cur, tgt: sb_pen.round_op(
                sb_pen.add(sb_pen.var(*cur), sb_pen.mul(sb_pen.sub(sb_pen.var(*tgt), sb_pen.var(*cur)), sb_pen.var(*PV["fog"])))
            )
            return sb_pen.add(
                sb_pen.add(sb_pen.mul(mix(rv, tr), 65536), sb_pen.mul(mix(gv, tg), 256)),
                mix(bv, tb),
            )

        def eval_river_knot_at_ri() -> list[str]:
            """Calcula geometria exata (sy, dy, zw, sx, rcx, rhw, shw, fog) no no ri in [0..21]."""
            return [
                sb_pen.set_var(*PV["tk"], sb_pen.div(sb_pen.var(*PV["ri"]), 17)),
                sb_pen.set_var(
                    *PV["dy"],
                    sb_pen.add(
                        4,
                        sb_pen.mul(
                            144,
                            sb_pen.add(
                                sb_pen.mul(0.35, sb_pen.var(*PV["tk"])),
                                sb_pen.mul(0.65, sb_pen.mul(sb_pen.var(*PV["tk"]), sb_pen.var(*PV["tk"]))),
                            ),
                        ),
                    ),
                ),
                sb_pen.set_var(*PV["sy"], sb_pen.sub(33, sb_pen.var(*PV["dy"]))),
                sb_pen.set_var(*PV["zw"], sb_pen.add(sb_pen.var(*V["Z Mundo"]), sb_pen.div(260, sb_pen.var(*PV["dy"])))),
                sb_pen.set_var(*PV["sx"], sb_pen.div(sb_pen.var(*PV["dy"]), 70)),
                sb_pen.set_var(
                    *PV["rcx"],
                    sb_pen.mul(
                        sb_pen.sub(river_world_x_at_z(sb_pen, PV["zw"]), sb_pen.mul(0.45, sb_pen.var(*V["Posicao X Aviao"]))),
                        sb_pen.var(*PV["sx"]),
                    ),
                ),
                sb_pen.set_var(
                    *PV["rhw"],
                    sb_pen.mul(
                        sb_pen.add(26, sb_pen.mul(6, sb_pen.mathop("sin", sb_pen.mul(8.6, sb_pen.var(*PV["zw"]))))),
                        sb_pen.var(*PV["sx"]),
                    ),
                ),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["rhw"]), 3.2), sb_pen.set_var(*PV["rhw"], 3.2)),
                sb_pen.set_var(*PV["shw"], sb_pen.mul(9.5, sb_pen.var(*PV["sx"]))),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["shw"]), 1.8), sb_pen.set_var(*PV["shw"], 1.8)),
                sb_pen.if_else(
                    sb_pen.lt(sb_pen.var(*PV["dy"]), 34),
                    [
                        sb_pen.set_var(*PV["ft"], sb_pen.div(sb_pen.sub(34, sb_pen.var(*PV["dy"])), 34)),
                        sb_pen.set_var(*PV["fog"], sb_pen.mul(sb_pen.mul(sb_pen.var(*PV["ft"]), sb_pen.var(*PV["ft"])), 0.92)),
                    ],
                    [sb_pen.set_var(*PV["fog"], 0)],
                ),
            ]

        def draw_continuous_river_pass(diam_fn, rgb_keys: tuple[str, str, str], flat_col_key: str) -> list[str]:
            """Desenha uma faixa do rio como polilinha continua de 22 nos sem levantar o lapis (zero quebras)."""
            rk, gk, bk = rgb_keys
            make_style = lambda: [
                sb_pen.pen_set_size(diam_fn()),
                sb_pen.if_else(
                    sb_pen.gt(sb_pen.var(*PV["fog"]), 0),
                    [sb_pen.pen_set_color(pack_fog_rgb(PV[rk], PV[gk], PV[bk]))],
                    [sb_pen.pen_set_color(sb_pen.var(*PV[flat_col_key]))],
                ),
            ]
            return [
                sb_pen.set_var(*PV["ri"], 0),
                *eval_river_knot_at_ri(),
                *make_style(),
                sb_pen.go_xy(sb_pen.var(*PV["rcx"]), sb_pen.var(*PV["sy"])),
                sb_pen.pen_down(),
                sb_pen.set_var(*PV["ri"], 1),
                sb_pen.repeat(
                    17,
                    *eval_river_knot_at_ri(),
                    *make_style(),
                    sb_pen.go_xy(sb_pen.var(*PV["rcx"]), sb_pen.var(*PV["sy"])),
                    sb_pen.change_var(*PV["ri"], 1),
                ),
                sb_pen.pen_up(),
            ]

        def eval_stream_pt(z_offset: float) -> list[str]:
            return [
                sb_pen.set_var(
                    *PV["tz"],
                    sb_pen.add(sb_pen.var(*PV["zrel"]), z_offset) if z_offset != 0.0 else sb_pen.var(*PV["zrel"]),
                ),
                sb_pen.set_var(*PV["zw"], sb_pen.add(sb_pen.var(*V["Z Mundo"]), sb_pen.var(*PV["tz"]))),
                sb_pen.set_var(*PV["dy"], sb_pen.div(260, sb_pen.var(*PV["tz"]))),
                sb_pen.set_var(*PV["sy"], sb_pen.sub(33, sb_pen.var(*PV["dy"]))),
                sb_pen.set_var(*PV["sx"], sb_pen.div(sb_pen.var(*PV["dy"]), 70)),
                sb_pen.set_var(
                    *PV["rcx"],
                    sb_pen.mul(
                        sb_pen.sub(river_world_x_at_z(sb_pen, PV["zw"]), sb_pen.mul(0.45, sb_pen.var(*V["Posicao X Aviao"]))),
                        sb_pen.var(*PV["sx"]),
                    ),
                ),
                sb_pen.set_var(
                    *PV["rhw"],
                    sb_pen.mul(
                        sb_pen.add(26, sb_pen.mul(6, sb_pen.mathop("sin", sb_pen.mul(8.6, sb_pen.var(*PV["zw"]))))),
                        sb_pen.var(*PV["sx"]),
                    ),
                ),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["rhw"]), 3.2), sb_pen.set_var(*PV["rhw"], 3.2)),
                sb_pen.set_var(*PV["glx"], sb_pen.add(sb_pen.var(*PV["rcx"]), sb_pen.mul(sb_pen.var(*PV["ulat"]), sb_pen.var(*PV["rhw"])))),
            ]

        PEN_PROC = "desenhar_terreno_procedural"
        sb_pen.stack(
            sb_pen.define_proc(PEN_PROC, warp=True, x=480, y=60),
            sb_pen.if_else(
                sb_pen.eq(sb_pen.var(*V["Etapa"]), 1),
                set_biome_palette(pal_b1),
                [sb_pen.if_else(
                    sb_pen.eq(sb_pen.var(*V["Etapa"]), 2),
                    set_biome_palette(pal_b2),
                    [sb_pen.if_else(
                        sb_pen.eq(sb_pen.var(*V["Etapa"]), 3),
                        set_biome_palette(pal_b3),
                        set_biome_palette(pal_b4),
                    )],
                )],
            ),
            # 1) Campos e gramado calmos em ondas simetricas (zero xadrez central, horizonte sem cintilacao)
            sb_pen.set_var(*PV["sy"], 28),
            sb_pen.repeat_until(
                sb_pen.lt(sb_pen.var(*PV["sy"]), -114),
                sb_pen.set_var(*PV["dy"], sb_pen.sub(33, sb_pen.var(*PV["sy"]))),
                sb_pen.set_var(*PV["step"], sb_pen.mathop("floor", sb_pen.add(1.8, sb_pen.div(sb_pen.var(*PV["dy"]), 34)))),
                sb_pen.set_var(*PV["zw"], sb_pen.add(sb_pen.var(*V["Z Mundo"]), sb_pen.div(260, sb_pen.var(*PV["dy"])))),
                sb_pen.set_var(*PV["tz"], sb_pen.mathop("floor", sb_pen.mul(sb_pen.var(*PV["zw"]), 0.56))),
                sb_pen.set_var(*PV["sx"], sb_pen.div(sb_pen.var(*PV["dy"]), 70)),
                sb_pen.set_var(*PV["rcx"], sb_pen.mul(sb_pen.mul(-0.45, sb_pen.var(*V["Posicao X Aviao"])), sb_pen.var(*PV["sx"]))),
                sb_pen.set_var(*PV["tw"], sb_pen.mul(96, sb_pen.var(*PV["sx"]))),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["tw"]), 18), sb_pen.set_var(*PV["tw"], 18)),
                sb_pen.pen_set_size(sb_pen.add(sb_pen.var(*PV["step"]), 1.6)),
                sb_pen.if_else(
                    sb_pen.lt(sb_pen.var(*PV["dy"]), 34),
                    [
                        sb_pen.set_var(*PV["ft"], sb_pen.div(sb_pen.sub(34, sb_pen.var(*PV["dy"])), 34)),
                        sb_pen.set_var(*PV["fog"], sb_pen.mul(sb_pen.mul(sb_pen.var(*PV["ft"]), sb_pen.var(*PV["ft"])), 0.92)),
                        sb_pen.pen_set_color(pack_fog_rgb(PV["rb"], PV["gb"], PV["bb"])),
                        sb_pen.go_xy(-240, sb_pen.var(*PV["sy"])),
                        sb_pen.pen_down(),
                        sb_pen.set_x(240),
                        sb_pen.pen_up(),
                    ],
                    [
                        sb_pen.set_var(*PV["trim"], sb_pen.mod(sb_pen.var(*PV["tz"]), 4)),
                        sb_pen.if_else(
                            sb_pen.eq(sb_pen.var(*PV["trim"]), 0),
                            [sb_pen.pen_set_color(sb_pen.var(*PV["ca"]))],
                            [sb_pen.if_else(
                                sb_pen.eq(sb_pen.var(*PV["trim"]), 2),
                                [sb_pen.pen_set_color(sb_pen.var(*PV["co"]))],
                                [sb_pen.pen_set_color(sb_pen.var(*PV["cb"]))],
                            )],
                        ),
                        sb_pen.go_xy(-240, sb_pen.var(*PV["sy"])),
                        sb_pen.pen_down(),
                        sb_pen.set_x(240),
                        sb_pen.pen_up(),
                        sb_pen.if_else(
                            sb_pen.eq(sb_pen.var(*PV["trim"]), 0),
                            [sb_pen.pen_set_color(sb_pen.var(*PV["cb"]))],
                            [sb_pen.pen_set_color(sb_pen.var(*PV["co"]))],
                        ),
                        *draw_hspan(-240, sb_pen.sub(sb_pen.var(*PV["rcx"]), sb_pen.var(*PV["tw"]))),
                        *draw_hspan(sb_pen.add(sb_pen.var(*PV["rcx"]), sb_pen.var(*PV["tw"])), 240),
                    ],
                ),
                sb_pen.change_var(*PV["sy"], sb_pen.mul(-1, sb_pen.var(*PV["step"]))),
            ),
            # 2) Rio 100% continuo em polilinha conectada (Areia -> Agua Rasa -> Canal Profundo, zero degraus/quebras)
            *draw_continuous_river_pass(
                lambda: sb_pen.mul(2, sb_pen.add(sb_pen.var(*PV["rhw"]), sb_pen.var(*PV["shw"]))),
                ("rs", "gs", "bs"),
                "cs",
            ),
            *draw_continuous_river_pass(
                lambda: sb_pen.mul(2, sb_pen.var(*PV["rhw"])),
                ("rw1", "gw1", "bw1"),
                "cw1",
            ),
            *draw_continuous_river_pass(
                lambda: sb_pen.mul(1.60, sb_pen.var(*PV["rhw"])),
                ("rw2", "gw2", "bw2"),
                "cw2",
            ),
            # 3) Correnteza animada em loop periodico perfeito (Z_rel em [2.4, 26.4), zero cortes)
            sb_pen.set_var(*PV["flux"], sb_pen.mod(sb_pen.mul(sb_pen.var(*V["Z Mundo"]), 2.1), 24)),
            sb_pen.set_var(*PV["ri"], 0),
            sb_pen.repeat(
                8,
                sb_pen.set_var(
                    *PV["zrel"],
                    sb_pen.add(
                        2.4,
                        sb_pen.mod(
                            sb_pen.add(sb_pen.mul(sb_pen.var(*PV["ri"]), 3), sb_pen.sub(24, sb_pen.var(*PV["flux"]))),
                            24,
                        ),
                    ),
                ),
                sb_pen.set_var(
                    *PV["ulat"],
                    sb_pen.mul(0.34, sb_pen.mathop("sin", sb_pen.add(sb_pen.mul(sb_pen.var(*PV["ri"]), 135), sb_pen.mul(42, sb_pen.var(*V["Etapa"]))))),
                ),
                *eval_stream_pt(1.2),
                sb_pen.go_xy(sb_pen.var(*PV["glx"]), sb_pen.var(*PV["sy"])),
                *eval_stream_pt(0.6),
                sb_pen.set_var(*PV["x2"], sb_pen.var(*PV["glx"])),
                sb_pen.set_var(*PV["y2"], sb_pen.var(*PV["sy"])),
                sb_pen.set_var(*PV["fog"], sb_pen.div(sb_pen.sub(sb_pen.var(*PV["zrel"]), 8), 18)),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["fog"]), 0), sb_pen.set_var(*PV["fog"], 0)),
                sb_pen.if_then(sb_pen.gt(sb_pen.var(*PV["fog"]), 0.92), sb_pen.set_var(*PV["fog"], 0.92)),
                sb_pen.pen_set_color(pack_mix_rgb(PV["rgl"], PV["ggl"], PV["bgl"], PV["rw2"], PV["gw2"], PV["bw2"])),
                sb_pen.set_var(*PV["glw"], sb_pen.mul(0.13, sb_pen.var(*PV["rhw"]))),
                sb_pen.if_then(sb_pen.lt(sb_pen.var(*PV["glw"]), 1.5), sb_pen.set_var(*PV["glw"], 1.5)),
                sb_pen.pen_set_size(sb_pen.var(*PV["glw"])),
                sb_pen.pen_down(),
                sb_pen.go_xy(sb_pen.var(*PV["x2"]), sb_pen.var(*PV["y2"])),
                *eval_stream_pt(0.0),
                sb_pen.go_xy(sb_pen.var(*PV["glx"]), sb_pen.var(*PV["sy"])),
                sb_pen.pen_up(),
                sb_pen.change_var(*PV["ri"], 1),
            ),
        )

        sb_pen.stack(sb_pen.hat_flag(80, 60), sb_pen.hide(), sb_pen.pen_clear())
        sb_pen.stack(sb_pen.hat_broadcast(*B["menu"], 80, 200), sb_pen.hide(), sb_pen.pen_clear())
        sb_pen.stack(sb_pen.hat_broadcast(*B["guia"], 80, 300), sb_pen.hide(), sb_pen.pen_clear())
        sb_pen.stack(sb_pen.hat_broadcast(*B["fim"], 80, 400), sb_pen.hide(), sb_pen.pen_clear())
        sb_pen.stack(
            sb_pen.hat_broadcast(*B["decolar"], 80, 520),
            sb_pen.hide(),
            sb_pen.repeat_until(
                sb_pen.bool_not(
                    sb_pen.bool_or(sb_pen.eq(sb_pen.var(*V["Estado"]), "decolagem"), sb_pen.eq(sb_pen.var(*V["Estado"]), "voo"))
                ),
                sb_pen.pen_clear(),
                sb_pen.call_proc(PEN_PROC, warp=True),
            ),
            sb_pen.pen_clear(),
        )
        pen_target = make_target(
            "Terreno Procedural",
            costumes=[reg.costume_from_svg('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>', "Motor Pen", (0, 0))],
            blocks=sb_pen.blocks,
            variables={vid: [f"Pen {k}", dval] for k, vid, dval in pen_vars_spec},
            size=100,
            visible=False,
            layer_order=4,
        )

        # ---------------- 4. VEGETACAO E CENARIO VIVO (6 clones presos ao mundo Mode-7 por Z Mundo) ----------------
        sb_prop = ScriptBuilder("prop")
        v_p_slot_init = ("Prox Slot Prop", "vp_slot_init")
        v_p_slot = ("Slot Prop", "vp_slot")
        v_p_z = ("Z Prop", "vp_z")
        v_p_zrel = ("Z Rel Prop", "vp_zrel")
        v_p_dy = ("dy Prop", "vp_dy")
        v_p_seed = ("Seed Prop", "vp_seed")
        v_p_side = ("Lado Prop", "vp_side")
        v_p_uoff = ("Offset Lateral Prop", "vp_uoff")
        v_p_subq = ("Quadro LOD Prop", "vp_subq")
        v_p_tipo = ("Tipo Prop", "vp_tipo")
        v_p_bioma = ("Bioma Prop", "vp_bioma")
        v_p_esc = ("Escala Prop", "vp_esc")
        v_p_y = ("Y Prop", "vp_y")
        v_p_x = ("X Prop", "vp_x")

        def prop_assign_tipo_and_offset() -> list[str]:
            # 1 unico barco no rio por ciclo (slot 1 em B1/B3); demais slots espacados nas margens sem acumulo
            return [
                sb_prop.set_var(*v_p_bioma, sb_prop.var(*V["Etapa"])),
                sb_prop.if_else(
                    sb_prop.eq(sb_prop.var(*v_p_bioma), 1),
                    [sb_prop.if_else(
                        sb_prop.eq(sb_prop.var(*v_p_slot), 1),
                        [sb_prop.set_var(*v_p_tipo, 2)],
                        [sb_prop.if_else(sb_prop.lt(sb_prop.var(*v_p_seed), 72), [sb_prop.set_var(*v_p_tipo, 1)], [sb_prop.set_var(*v_p_tipo, 3)])],
                    )],
                    [sb_prop.if_else(
                        sb_prop.eq(sb_prop.var(*v_p_bioma), 2),
                        [sb_prop.if_else(
                            sb_prop.lt(sb_prop.var(*v_p_seed), 45),
                            [sb_prop.set_var(*v_p_tipo, 1)],
                            [sb_prop.if_else(sb_prop.lt(sb_prop.var(*v_p_seed), 75), [sb_prop.set_var(*v_p_tipo, 2)], [sb_prop.set_var(*v_p_tipo, 3)])],
                        )],
                        [sb_prop.if_else(
                            sb_prop.eq(sb_prop.var(*v_p_bioma), 3),
                            [sb_prop.if_else(
                                sb_prop.eq(sb_prop.var(*v_p_slot), 1),
                                [sb_prop.set_var(*v_p_tipo, 2)],
                                [sb_prop.if_else(sb_prop.lt(sb_prop.var(*v_p_seed), 54), [sb_prop.set_var(*v_p_tipo, 1)], [sb_prop.set_var(*v_p_tipo, 3)])],
                            )],
                            [sb_prop.if_else(
                                sb_prop.lt(sb_prop.var(*v_p_seed), 42),
                                [sb_prop.set_var(*v_p_tipo, 1)],
                                [sb_prop.if_else(sb_prop.lt(sb_prop.var(*v_p_seed), 72), [sb_prop.set_var(*v_p_tipo, 2)], [sb_prop.set_var(*v_p_tipo, 3)])],
                            )],
                        )],
                    )],
                ),
                sb_prop.if_else(
                    sb_prop.bool_or(
                        sb_prop.bool_and(sb_prop.eq(sb_prop.var(*v_p_bioma), 1), sb_prop.eq(sb_prop.var(*v_p_tipo), 2)),
                        sb_prop.bool_and(sb_prop.eq(sb_prop.var(*v_p_bioma), 3), sb_prop.eq(sb_prop.var(*v_p_tipo), 2)),
                    ),
                    [sb_prop.set_var(*v_p_uoff, 0)],
                    [sb_prop.set_var(
                        *v_p_uoff,
                        sb_prop.mul(
                            sb_prop.var(*v_p_side),
                            sb_prop.add(52, sb_prop.mul(sb_prop.mod(sb_prop.var(*v_p_seed), 3), 28)),
                        ),
                    )],
                ),
            ]

        def prop_update_transform() -> list[str]:
            return [
                sb_prop.set_var(*v_p_zrel, sb_prop.sub(sb_prop.var(*v_p_z), sb_prop.var(*V["Z Mundo"]))),
                sb_prop.if_then(
                    sb_prop.eq(sb_prop.var(*v_p_uoff), 0),
                    sb_prop.if_else(
                        sb_prop.gt(sb_prop.var(*v_p_zrel), 9.0),
                        [sb_prop.change_var(*v_p_z, -0.045)],
                        [sb_prop.change_var(*v_p_z, 0.032)],
                    ),
                    sb_prop.set_var(*v_p_zrel, sb_prop.sub(sb_prop.var(*v_p_z), sb_prop.var(*V["Z Mundo"]))),
                ),
                sb_prop.if_then(
                    sb_prop.lt(sb_prop.var(*v_p_zrel), 2.2),
                    sb_prop.change_var(*v_p_z, 28.8),
                    sb_prop.set_var(
                        *v_p_seed,
                        sb_prop.mod(
                            sb_prop.add(
                                sb_prop.add(sb_prop.mul(sb_prop.var(*v_p_seed), 31), sb_prop.mul(sb_prop.var(*V["Etapa"]), 17)),
                                sb_prop.add(sb_prop.mul(sb_prop.var(*v_p_slot), 7), sb_prop.var(*V["Semente Mundo"])),
                            ),
                            100,
                        ),
                    ),
                    sb_prop.set_var(*v_p_side, sb_prop.mul(sb_prop.var(*v_p_side), -1)),
                    *prop_assign_tipo_and_offset(),
                    sb_prop.go_layer("back"),
                    sb_prop.go_layers("forward", 5),
                    sb_prop.set_var(*v_p_zrel, sb_prop.sub(sb_prop.var(*v_p_z), sb_prop.var(*V["Z Mundo"]))),
                ),
                sb_prop.if_then(
                    sb_prop.bool_and(
                        sb_prop.bool_not(sb_prop.eq(sb_prop.var(*v_p_bioma), sb_prop.var(*V["Etapa"]))),
                        sb_prop.gt(sb_prop.var(*v_p_zrel), 10.5),
                    ),
                    *prop_assign_tipo_and_offset(),
                ),
                sb_prop.set_var(*v_p_dy, sb_prop.div(260, sb_prop.var(*v_p_zrel))),
                sb_prop.set_var(*v_p_y, sb_prop.sub(33, sb_prop.var(*v_p_dy))),
                sb_prop.if_then(
                    sb_prop.eq(sb_prop.var(*v_p_uoff), 0),
                    sb_prop.change_var(
                        *v_p_y,
                        sb_prop.mul(
                            1.6,
                            sb_prop.mathop("sin", sb_prop.add(sb_prop.mul(sb_prop.timer(), 140), sb_prop.mul(sb_prop.var(*v_p_slot), 60))),
                        ),
                    ),
                ),
                sb_prop.if_else(
                    sb_prop.eq(sb_prop.var(*v_p_uoff), 0),
                    [
                        # Navio vindo de frente: cresce em porcentagem (12%..108%) com suavizacao perto da borda
                        sb_prop.set_var(*v_p_esc, sb_prop.add(12, sb_prop.mul(0.85, sb_prop.var(*v_p_dy)))),
                        sb_prop.if_then(sb_prop.gt(sb_prop.var(*v_p_esc), 108), sb_prop.set_var(*v_p_esc, 108)),
                    ],
                    [
                        sb_prop.set_var(*v_p_esc, sb_prop.add(16, sb_prop.mul(0.55, sb_prop.var(*v_p_dy)))),
                        sb_prop.if_then(sb_prop.gt(sb_prop.var(*v_p_esc), 85), sb_prop.set_var(*v_p_esc, 85)),
                    ],
                ),
                sb_prop.set_size(sb_prop.var(*v_p_esc)),
                sb_prop.set_var(
                    *v_p_x,
                    sb_prop.mul(
                        sb_prop.sub(
                            sb_prop.add(river_world_x_at_z(sb_prop, v_p_z), sb_prop.var(*v_p_uoff)),
                            sb_prop.mul(0.45, sb_prop.var(*V["Posicao X Aviao"])),
                        ),
                        sb_prop.div(sb_prop.var(*v_p_dy), 70),
                    ),
                ),
                sb_prop.if_else(
                    sb_prop.gt(sb_prop.var(*v_p_zrel), 16),
                    [sb_prop.set_var(*v_p_subq, 1), sb_prop.set_effect("ghost", 42)],
                    [
                        sb_prop.set_var(*v_p_subq, sb_prop.add(sb_prop.mod(sb_prop.mathop("floor", sb_prop.div(sb_prop.timer(), 0.30)), 2), 1)),
                        sb_prop.set_effect("ghost", 0),
                    ],
                ),
                sb_prop.switch_costume(prop_costume_expr()),
                sb_prop.go_xy(sb_prop.var(*v_p_x), sb_prop.var(*v_p_y)),
                sb_prop.if_else(
                    sb_prop.bool_or(sb_prop.gt(sb_prop.var(*v_p_y), 22), sb_prop.gt(sb_prop.mathop("abs", sb_prop.var(*v_p_x)), 235)),
                    [sb_prop.hide()],
                    [sb_prop.show()],
                ),
            ]

        prop_costume_expr = lambda: sb_prop.add(
            sb_prop.add(
                sb_prop.mul(6, sb_prop.sub(sb_prop.var(*v_p_bioma), 1)),
                sb_prop.mul(2, sb_prop.sub(sb_prop.var(*v_p_tipo), 1)),
            ),
            sb_prop.var(*v_p_subq),
        )

        sb_prop.stack(
            sb_prop.hat_flag(80, 60),
            sb_prop.hide(),
            sb_prop.set_var(*v_p_slot_init, 0),
        )
        sb_prop.stack(
            sb_prop.hat_broadcast(*B["voar"], 80, 260),
            sb_prop.hide(),
            sb_prop.set_var(*v_p_slot_init, 0),
            sb_prop.repeat(
                4,
                sb_prop.create_clone("_myself_"),
                sb_prop.change_var(*v_p_slot_init, 1),
            ),
        )
        sb_prop.stack(
            sb_prop.hat_clone(480, 60),
            sb_prop.hide(),
            sb_prop.set_var(*v_p_slot, sb_prop.var(*v_p_slot_init)),
            sb_prop.set_var(*v_p_z, sb_prop.add(sb_prop.var(*V["Z Mundo"]), sb_prop.add(5.5, sb_prop.mul(sb_prop.var(*v_p_slot), 7.2)))),
            sb_prop.set_var(
                *v_p_seed,
                sb_prop.mod(
                    sb_prop.add(sb_prop.mul(sb_prop.var(*V["Semente Mundo"]), 37), sb_prop.mul(sb_prop.add(sb_prop.var(*v_p_slot), 1), 19)),
                    100,
                ),
            ),
            sb_prop.if_else(
                sb_prop.eq(sb_prop.mod(sb_prop.var(*v_p_slot), 2), 0),
                [sb_prop.set_var(*v_p_side, 1)],
                [sb_prop.set_var(*v_p_side, -1)],
            ),
            *prop_assign_tipo_and_offset(),
            *prop_update_transform(),
            sb_prop.repeat_until(
                sb_prop.bool_not(sb_prop.eq(sb_prop.var(*V["Estado"]), "voo")),
                *prop_update_transform(),
            ),
            sb_prop.delete_clone(),
        )
        sb_prop.stack(sb_prop.hat_broadcast(*B["menu"], 80, 660), sb_prop.delete_clone())
        sb_prop.stack(sb_prop.hat_broadcast(*B["guia"], 80, 760), sb_prop.delete_clone())
        sb_prop.stack(sb_prop.hat_broadcast(*B["fim"], 80, 860), sb_prop.delete_clone())

        prop_costumes = []
        for b_idx in range(1, 5):
            for p_idx in range(1, 4):
                for q_idx in (1, 2):
                    prop_costumes.append(
                        reg.costume_from_image(
                            ORG_DIR / "09_cenarios_vivos" / "props" / f"b{b_idx}_prop{p_idx}_q{q_idx}.png",
                            f"B{b_idx}_P{p_idx}_Q{q_idx}",
                            bitmap_resolution=2,
                            center=(120, 176),
                        )
                    )
        prop_target = make_target(
            "Vegetação e Cenário Vivo",
            costumes=prop_costumes,
            blocks=sb_prop.blocks,
            variables={
                v_p_slot_init[1]: [v_p_slot_init[0], 0],
                v_p_slot[1]: [v_p_slot[0], 0],
                v_p_z[1]: [v_p_z[0], 4.5],
                v_p_zrel[1]: [v_p_zrel[0], 4.5],
                v_p_dy[1]: [v_p_dy[0], 57],
                v_p_seed[1]: [v_p_seed[0], 0],
                v_p_side[1]: [v_p_side[0], 1],
                v_p_uoff[1]: [v_p_uoff[0], 42],
                v_p_subq[1]: [v_p_subq[0], 1],
                v_p_tipo[1]: [v_p_tipo[0], 1],
                v_p_bioma[1]: [v_p_bioma[0], 1],
                v_p_esc[1]: [v_p_esc[0], 20],
                v_p_y[1]: [v_p_y[0], -24],
                v_p_x[1]: [v_p_x[0], 0],
            },
            size=20,
            visible=False,
            layer_order=5,
        )

        # ---------------- 7. PISTA (Pista 3D Voxel limpa com crossfade suave para o voo) ----------------
        sb_pista = ScriptBuilder("pista")
        v_pista_g = ("Ghost Pista", "vpista_g")
        sb_pista.stack(
            sb_pista.hat_flag(80, 60),
            sb_pista.clear_effects(),
            sb_pista.set_var(*v_pista_g, 0),
            sb_pista.go_xy(0, 0),
            sb_pista.hide(),
        )
        sb_pista.stack(
            sb_pista.hat_broadcast(*B["menu"], 80, 220),
            sb_pista.clear_effects(),
            sb_pista.hide(),
        )
        sb_pista.stack(
            sb_pista.hat_broadcast(*B["guia"], 80, 320),
            sb_pista.clear_effects(),
            sb_pista.hide(),
        )
        sb_pista.stack(
            sb_pista.hat_broadcast(*B["decolar"], 80, 440),
            sb_pista.clear_effects(),
            sb_pista.set_var(*v_pista_g, 0),
            sb_pista.go_xy(0, 0),
            sb_pista.set_size(100),
            sb_pista.show(),
            sb_pista.glide(2.6, 0, -140),
            sb_pista.hide(),
            sb_pista.clear_effects(),
        )
        sb_pista.stack(
            sb_pista.hat_broadcast(*B["decolar"], 460, 440),
            sb_pista.wait(1.75),
            sb_pista.repeat(
                14,
                sb_pista.if_then(
                    sb_pista.eq(sb_pista.var(*V["Estado"]), "decolagem"),
                    sb_pista.change_var(*v_pista_g, 7.2),
                    sb_pista.set_effect("ghost", sb_pista.var(*v_pista_g)),
                    sb_pista.wait(0.05),
                ),
            ),
            sb_pista.hide(),
            sb_pista.clear_effects(),
        )
        sb_pista.stack(
            sb_pista.hat_broadcast(*B["fim"], 80, 660),
            sb_pista.clear_effects(),
            sb_pista.hide(),
        )
        pista_target = make_target(
            "Pista",
            costumes=[
                reg.costume_from_image(
                    ORG_DIR / "07_telas_e_overlays" / "pista_decolagem_voxel.png",
                    "Pista Voxel 3D",
                    bitmap_resolution=2,
                    center=(480, 360),
                )
            ],
            blocks=sb_pista.blocks,
            variables={v_pista_g[1]: [v_pista_g[0], 0]},
            size=100,
            visible=False,
            layer_order=6,
        )

        # ---------------- 5. NUVENS (Pool fixo de 2 clones confinados estritamente ao ceu alto y>=82) ----------------
        sb_nuv = ScriptBuilder("nuv")
        v_nuv_slot_init = ("Prox Slot Nuvem", "vn_slot_init")
        v_nuv_slot = ("Slot Nuvem", "vn_slot")
        v_nuv_d = ("Profundidade Nuvem", "vn_d")
        v_nuv_p = ("Perspectiva Nuvem", "vn_p")
        v_nuv_dir = ("Direcao nuvem", "vn_dir")
        v_nuv_x = ("X Nuvem", "vn_x")
        v_nuv_phase = ("Fase nuvem", "vn_phase")
        v_nuv_lim = ("Limite X", "vn_lim")
        sb_nuv.stack(
            sb_nuv.hat_flag(80, 60),
            sb_nuv.hide(),
            sb_nuv.set_var(*v_nuv_slot_init, 0),
        )
        sb_nuv.stack(
            sb_nuv.hat_broadcast(*B["voar"], 80, 260),
            sb_nuv.hide(),
            sb_nuv.set_var(*v_nuv_slot_init, 0),
            sb_nuv.wait(0.8),
            sb_nuv.repeat(
                2,
                sb_nuv.create_clone("_myself_"),
                sb_nuv.change_var(*v_nuv_slot_init, 1),
            ),
        )
        nuv_y_expr = lambda: sb_nuv.add(82, sb_nuv.mul(56, sb_nuv.var(*v_nuv_p)))
        nuv_scale_expr = lambda: sb_nuv.add(18, sb_nuv.mul(20, sb_nuv.var(*v_nuv_p)))
        nuv_screen_x_expr = lambda: sb_nuv.add(
            sb_nuv.var(*v_nuv_x),
            sb_nuv.round_op(sb_nuv.mul(-0.16, sb_nuv.var(*V["Posicao X Aviao"]))),
        )
        sb_nuv.stack(
            sb_nuv.hat_clone(460, 60),
            sb_nuv.set_var(*v_nuv_slot, sb_nuv.var(*v_nuv_slot_init)),
            sb_nuv.set_var(*v_nuv_d, sb_nuv.add(0.04, sb_nuv.mul(sb_nuv.var(*v_nuv_slot), 0.48))),
            sb_nuv.if_else(
                sb_nuv.eq(sb_nuv.mod(sb_nuv.var(*v_nuv_slot), 2), 0),
                [sb_nuv.set_var(*v_nuv_dir, 1)],
                [sb_nuv.set_var(*v_nuv_dir, -1)],
            ),
            sb_nuv.set_var(*v_nuv_x, sb_nuv.mul(sb_nuv.var(*v_nuv_dir), sb_nuv.add(45, sb_nuv.mul(sb_nuv.var(*v_nuv_slot), 55)))),
            sb_nuv.set_var(*v_nuv_phase, sb_nuv.mul(sb_nuv.var(*v_nuv_slot), 60)),
            sb_nuv.set_var(*v_nuv_p, p_of_d(sb_nuv, sb_nuv.var(*v_nuv_d))),
            sb_nuv.set_size(nuv_scale_expr()),
            sb_nuv.go_xy(nuv_screen_x_expr(), nuv_y_expr()),
            sb_nuv.switch_costume("Nuvem 1"),
            sb_nuv.set_effect("ghost", 28),
            sb_nuv.show(),
            sb_nuv.repeat_until(
                sb_nuv.bool_not(sb_nuv.eq(sb_nuv.var(*V["Estado"]), "voo")),
                sb_nuv.change_var(*v_nuv_d, 0.0026),
                sb_nuv.if_then(
                    sb_nuv.gt(sb_nuv.var(*v_nuv_d), 1.0),
                    sb_nuv.change_var(*v_nuv_d, -0.96),
                    sb_nuv.set_var(*v_nuv_x, sb_nuv.rand(-110, 110)),
                    sb_nuv.set_var(*v_nuv_dir, sb_nuv.mul(sb_nuv.var(*v_nuv_dir), -1)),
                ),
                sb_nuv.set_var(*v_nuv_p, p_of_d(sb_nuv, sb_nuv.var(*v_nuv_d))),
                sb_nuv.set_size(nuv_scale_expr()),
                sb_nuv.if_else(
                    sb_nuv.lt(sb_nuv.var(*v_nuv_p), 0.15),
                    [sb_nuv.switch_costume("Nuvem 1")],
                    [sb_nuv.if_else(
                        sb_nuv.lt(sb_nuv.var(*v_nuv_p), 0.40),
                        [sb_nuv.switch_costume("Nuvem 2")],
                        [sb_nuv.if_else(
                            sb_nuv.lt(sb_nuv.var(*v_nuv_p), 0.70),
                            [sb_nuv.switch_costume("Nuvem 3")],
                            [sb_nuv.switch_costume("Nuvem 4")],
                        )],
                    )],
                ),
                sb_nuv.change_var(*v_nuv_phase, 2),
                sb_nuv.change_var(
                    *v_nuv_x,
                    sb_nuv.add(
                        sb_nuv.mul(sb_nuv.var(*v_nuv_dir), 0.25),
                        sb_nuv.mul(0.08, sb_nuv.mathop("sin", sb_nuv.var(*v_nuv_phase))),
                    ),
                ),
                sb_nuv.set_var(*v_nuv_lim, sb_nuv.sub(230, sb_nuv.mul(1.5, sb_nuv.size()))),
                sb_nuv.if_then(
                    sb_nuv.gt(sb_nuv.var(*v_nuv_x), sb_nuv.var(*v_nuv_lim)),
                    sb_nuv.set_var(*v_nuv_x, sb_nuv.var(*v_nuv_lim)),
                    sb_nuv.set_var(*v_nuv_dir, -0.4),
                ),
                sb_nuv.if_then(
                    sb_nuv.lt(sb_nuv.var(*v_nuv_x), sb_nuv.mul(-1, sb_nuv.var(*v_nuv_lim))),
                    sb_nuv.set_var(*v_nuv_x, sb_nuv.mul(-1, sb_nuv.var(*v_nuv_lim))),
                    sb_nuv.set_var(*v_nuv_dir, 0.4),
                ),
                sb_nuv.go_xy(nuv_screen_x_expr(), nuv_y_expr()),
            ),
            sb_nuv.delete_clone(),
        )
        sb_nuv.stack(sb_nuv.hat_broadcast(*B["menu"], 80, 620), sb_nuv.delete_clone())
        sb_nuv.stack(sb_nuv.hat_broadcast(*B["guia"], 80, 720), sb_nuv.delete_clone())
        sb_nuv.stack(sb_nuv.hat_broadcast(*B["fim"], 80, 820), sb_nuv.delete_clone())

        nuv_costumes = [
            reg.costume_from_image(ORG_DIR / "05_nuvens_voxel" / f"nuvem_quadro_{i}.png", f"Nuvem {i}", bitmap_resolution=1, center=(160, 90))
            for i in range(1, 5)
        ]
        nuv_target = make_target(
            "Nuvens",
            costumes=nuv_costumes,
            blocks=sb_nuv.blocks,
            variables={
                v_nuv_slot_init[1]: [v_nuv_slot_init[0], 0],
                v_nuv_slot[1]: [v_nuv_slot[0], 0],
                v_nuv_d[1]: [v_nuv_d[0], 0.04],
                v_nuv_p[1]: [v_nuv_p[0], 0.005],
                v_nuv_dir[1]: [v_nuv_dir[0], 1],
                v_nuv_x[1]: [v_nuv_x[0], 0],
                v_nuv_phase[1]: [v_nuv_phase[0], 0],
                v_nuv_lim[1]: [v_nuv_lim[0], 180],
            },
            size=18,
            visible=False,
            layer_order=5,
        )

        # ---------------- 9. RAJADA DE VENTO (Nitida no ceu superior, espacada e sem acumulo) ----------------
        sb_wind = ScriptBuilder("wind")
        sb_wind.stack(sb_wind.hat_flag(80, 60), sb_wind.hide(), sb_wind.set_effect("ghost", 18))
        sb_wind.stack(
            sb_wind.hat_broadcast(*B["vento_rajada"], 80, 240),
            sb_wind.hide(),
            sb_wind.repeat_until(
                sb_wind.bool_or(sb_wind.bool_not(sb_wind.eq(sb_wind.var(*V["Estado"]), "voo")), sb_wind.eq(sb_wind.var(*V["Vento Forca"]), 0)),
                sb_wind.create_clone("_myself_"),
                sb_wind.wait(1.45),
            ),
        )
        sb_wind.stack(
            sb_wind.hat_clone(460, 60),
            sb_wind.set_size(82),
            sb_wind.set_effect("ghost", 18),
            sb_wind.if_else(
                sb_wind.gt(sb_wind.var(*V["Vento Forca"]), 0),
                [sb_wind.point_dir(90), sb_wind.go_xy(-190, sb_wind.rand(18, 92))],
                [sb_wind.point_dir(-90), sb_wind.go_xy(190, sb_wind.rand(18, 92))],
            ),
            sb_wind.show(),
            sb_wind.repeat_until(
                sb_wind.bool_or(
                    sb_wind.bool_or(
                        sb_wind.bool_not(sb_wind.eq(sb_wind.var(*V["Estado"]), "voo")),
                        sb_wind.eq(sb_wind.var(*V["Vento Forca"]), 0),
                    ),
                    sb_wind.bool_or(sb_wind.lt(sb_wind.x_pos(), -195), sb_wind.gt(sb_wind.x_pos(), 195)),
                ),
                sb_wind.change_x(sb_wind.mul(sb_wind.var(*V["Vento Forca"]), 3.8)),
                sb_wind.switch_costume(
                    sb_wind.add(sb_wind.mod(sb_wind.mathop("floor", sb_wind.div(sb_wind.timer(), 0.08)), 4), 1)
                ),
            ),
            sb_wind.delete_clone(),
        )
        sb_wind.stack(sb_wind.hat_broadcast(*B["menu"], 80, 560), sb_wind.delete_clone())
        sb_wind.stack(sb_wind.hat_broadcast(*B["guia"], 80, 660), sb_wind.delete_clone())
        sb_wind.stack(sb_wind.hat_broadcast(*B["fim"], 80, 760), sb_wind.delete_clone())
        wind_costumes = [
            reg.costume_from_image(ORG_DIR / "05_nuvens_voxel" / f"rajada_vento_q{i}.png", f"Rajada {i}", bitmap_resolution=2, center=(160, 90))
            for i in range(1, 5)
        ]
        wind_target = make_target(
            "Rajada de Vento",
            costumes=wind_costumes,
            blocks=sb_wind.blocks,
            size=78,
            visible=False,
            layer_order=9,
            rotation_style="left-right",
        )

        # ---------------- 7. COMBUSTIVEL NO AR (5 raias radiais p(d)=d^gamma, +2 raias de distancia do passaro) ----------------
        sb_fuel = ScriptBuilder("fuel")
        v_fuel_d = ("Profundidade Comb", "vf_d")
        v_fuel_p = ("Perspectiva Comb", "vf_p")
        v_fuel_x0 = ("x0 Comb", "vf_x0")
        fuel_scale_expr = lambda: sb_fuel.add(26, sb_fuel.mul(28, sb_fuel.var(*v_fuel_p)))
        fuel_y_expr = lambda: sb_fuel.add(
            air_y_of_p(sb_fuel, sb_fuel.var(*v_fuel_p)),
            sb_fuel.mul(2.2, sb_fuel.mathop("sin", sb_fuel.mul(sb_fuel.timer(), 180))),
        )
        fuel_x_expr = lambda: air_x_of_dp(sb_fuel, v_fuel_x0, sb_fuel.var(*v_fuel_p))
        fuel_costume_expr = lambda: sb_fuel.add(
            sb_fuel.mod(sb_fuel.mathop("floor", sb_fuel.div(sb_fuel.timer(), 0.14)), 4),
            1,
        )
        sb_fuel.stack(sb_fuel.hat_flag(80, 60), sb_fuel.hide())
        sb_fuel.stack(
            sb_fuel.hat_broadcast(*B["onda_comb"], 80, 220),
            sb_fuel.hide(),
            sb_fuel.if_then(
                sb_fuel.eq(sb_fuel.var(*V["Estado"]), "voo"),
                sb_fuel.create_clone("_myself_"),
            ),
        )
        sb_fuel.stack(
            sb_fuel.hat_clone(460, 60),
            sb_fuel.hide(),
            sb_fuel.set_var(*v_fuel_d, 0.04),
            sb_fuel.set_var(*v_fuel_p, p_of_d(sb_fuel, sb_fuel.var(*v_fuel_d))),
            sb_fuel.set_var(
                *v_fuel_x0,
                sb_fuel.mul(
                    sb_fuel.sub(sb_fuel.var(*V["Raia Comb"]), 2),
                    68,
                ),
            ),
            sb_fuel.set_size(fuel_scale_expr()),
            sb_fuel.switch_costume(fuel_costume_expr()),
            sb_fuel.go_xy(fuel_x_expr(), fuel_y_expr()),
            sb_fuel.set_effect("ghost", 64),
            sb_fuel.show(),
            sb_fuel.repeat_until(
                sb_fuel.bool_or(sb_fuel.bool_not(sb_fuel.eq(sb_fuel.var(*V["Estado"]), "voo")), sb_fuel.gt(sb_fuel.var(*v_fuel_d), 1.0)),
                sb_fuel.change_var(*v_fuel_d, 0.0072),
                sb_fuel.set_var(*v_fuel_p, p_of_d(sb_fuel, sb_fuel.var(*v_fuel_d))),
                sb_fuel.if_else(
                    sb_fuel.lt(sb_fuel.var(*v_fuel_d), 0.24),
                    [sb_fuel.set_effect("ghost", sb_fuel.round_op(sb_fuel.mul(sb_fuel.sub(0.24, sb_fuel.var(*v_fuel_d)), 320)))],
                    [sb_fuel.set_effect("ghost", 0)],
                ),
                sb_fuel.set_size(fuel_scale_expr()),
                sb_fuel.switch_costume(fuel_costume_expr()),
                sb_fuel.go_xy(fuel_x_expr(), fuel_y_expr()),
                sb_fuel.if_then(
                    sb_fuel.lt(sb_fuel.distance_to("Avião"), 52),
                    sb_fuel.change_var(*V["Combustível"], 28),
                    sb_fuel.if_then(
                        sb_fuel.gt(sb_fuel.var(*V["Combustível"]), 100),
                        sb_fuel.set_var(*V["Combustível"], 100),
                    ),
                    sb_fuel.change_var(*V["Pontos"], 10),
                    sb_fuel.broadcast(*B["coleta"]),
                    sb_fuel.delete_clone(),
                ),
            ),
            sb_fuel.delete_clone(),
        )
        sb_fuel.stack(sb_fuel.hat_broadcast(*B["menu"], 80, 560), sb_fuel.delete_clone())
        sb_fuel.stack(sb_fuel.hat_broadcast(*B["guia"], 80, 660), sb_fuel.delete_clone())
        sb_fuel.stack(sb_fuel.hat_broadcast(*B["fim"], 80, 760), sb_fuel.delete_clone())
        fuel_costumes = [
            reg.costume_from_image(
                ORG_DIR / "06_itens_e_aneis" / f"galao_voxel_q{i}.png",
                f"Galao Voxel {i}",
                bitmap_resolution=2,
                center=(48, 48),
            )
            for i in range(1, 5)
        ]
        fuel_target = make_target(
            "Combustível no ar",
            costumes=fuel_costumes,
            blocks=sb_fuel.blocks,
            variables={
                v_fuel_d[1]: [v_fuel_d[0], 0.04],
                v_fuel_p[1]: [v_fuel_p[0], 0.005],
                v_fuel_x0[1]: [v_fuel_x0[0], 0],
            },
            size=26,
            visible=False,
            layer_order=7,
        )

        # ---------------- 8. BRISA FAVORAVEL (5 raias radiais, +4 raias do passaro, estabiliza voo) ----------------
        sb_breeze = ScriptBuilder("brisa")
        v_breeze_idx = ("Indice Brisa", "vbr_idx")
        v_breeze_x0 = ("x0 Brisa", "vbr_x0")
        v_breeze_d = ("Profundidade Brisa", "vbr_d")
        v_breeze_p = ("Perspectiva Brisa", "vbr_p")
        sb_breeze.stack(
            sb_breeze.hat_flag(80, 60),
            sb_breeze.hide(),
            sb_breeze.set_size(24),
            sb_breeze.set_var(*v_breeze_idx, 0),
        )
        sb_breeze.stack(
            sb_breeze.hat_broadcast(*B["onda_brisa"], 80, 260),
            sb_breeze.hide(),
            sb_breeze.if_then(
                sb_breeze.eq(sb_breeze.var(*V["Estado"]), "voo"),
                sb_breeze.create_clone("_myself_"),
            ),
        )
        breeze_x_expr = lambda: sb_breeze.add(
            air_x_of_dp(sb_breeze, v_breeze_x0, sb_breeze.var(*v_breeze_p)),
            sb_breeze.mul(
                4,
                sb_breeze.mathop("sin", sb_breeze.mul(sb_breeze.var(*V["Frequencia (w)"]), sb_breeze.y_pos())),
            ),
        )
        breeze_y_expr = lambda: air_y_of_p(sb_breeze, sb_breeze.var(*v_breeze_p))
        breeze_scale_expr = lambda: sb_breeze.add(24, sb_breeze.mul(32, sb_breeze.var(*v_breeze_p)))
        breeze_costume_expr = lambda: sb_breeze.add(
            sb_breeze.mod(sb_breeze.mathop("floor", sb_breeze.div(sb_breeze.timer(), 0.11)), 4),
            1,
        )

        sb_breeze.stack(
            sb_breeze.hat_clone(460, 60),
            sb_breeze.hide(),
            sb_breeze.change_var(*v_breeze_idx, 1),
            sb_breeze.set_var(
                *v_breeze_x0,
                sb_breeze.mul(
                    sb_breeze.sub(sb_breeze.var(*V["Raia Brisa"]), 2),
                    68,
                ),
            ),
            sb_breeze.set_var(*v_breeze_d, 0.04),
            sb_breeze.set_var(*v_breeze_p, p_of_d(sb_breeze, sb_breeze.var(*v_breeze_d))),
            sb_breeze.set_size(breeze_scale_expr()),
            sb_breeze.switch_costume(breeze_costume_expr()),
            sb_breeze.go_xy(breeze_x_expr(), breeze_y_expr()),
            sb_breeze.set_effect("ghost", 64),
            sb_breeze.show(),
            sb_breeze.repeat_until(
                sb_breeze.bool_or(sb_breeze.bool_not(sb_breeze.eq(sb_breeze.var(*V["Estado"]), "voo")), sb_breeze.gt(sb_breeze.var(*v_breeze_d), 1.0)),
                sb_breeze.change_var(*v_breeze_d, 0.0070),
                sb_breeze.set_var(*v_breeze_p, p_of_d(sb_breeze, sb_breeze.var(*v_breeze_d))),
                sb_breeze.if_else(
                    sb_breeze.lt(sb_breeze.var(*v_breeze_d), 0.24),
                    [sb_breeze.set_effect("ghost", sb_breeze.round_op(sb_breeze.mul(sb_breeze.sub(0.24, sb_breeze.var(*v_breeze_d)), 320)))],
                    [sb_breeze.set_effect("ghost", 0)],
                ),
                sb_breeze.set_size(breeze_scale_expr()),
                sb_breeze.switch_costume(breeze_costume_expr()),
                sb_breeze.go_xy(breeze_x_expr(), breeze_y_expr()),
                sb_breeze.if_then(
                    sb_breeze.lt(sb_breeze.distance_to("Avião"), 56),
                    sb_breeze.change_var(*V["Pontos"], 15),
                    sb_breeze.if_else(
                        sb_breeze.lt(sb_breeze.var(*V["Brisas Coletadas"]), 4),
                        [sb_breeze.change_var(*V["Pontos"], sb_breeze.mul(5, sb_breeze.var(*V["Brisas Coletadas"])))],
                        [sb_breeze.change_var(*V["Pontos"], 20)],
                    ),
                    sb_breeze.change_var(*V["Combustível"], 3),
                    sb_breeze.if_then(
                        sb_breeze.gt(sb_breeze.var(*V["Combustível"]), 100),
                        sb_breeze.set_var(*V["Combustível"], 100),
                    ),
                    sb_breeze.set_var(*V["Estabilidade"], sb_breeze.round_op(sb_breeze.mul(0.35, sb_breeze.var(*V["Estabilidade"])))),
                    sb_breeze.change_var(*V["Brisas Coletadas"], 1),
                    sb_breeze.broadcast(*B["coleta"]),
                    sb_breeze.delete_clone(),
                ),
            ),
            sb_breeze.delete_clone(),
        )
        sb_breeze.stack(sb_breeze.hat_broadcast(*B["menu"], 80, 620), sb_breeze.delete_clone())
        sb_breeze.stack(sb_breeze.hat_broadcast(*B["guia"], 80, 720), sb_breeze.delete_clone())
        sb_breeze.stack(sb_breeze.hat_broadcast(*B["fim"], 80, 820), sb_breeze.delete_clone())

        breeze_costumes = [
            reg.costume_from_image(ORG_DIR / "06_itens_e_aneis" / f"brisa_favoravel_q{i}.png", f"Brisa {i}", bitmap_resolution=2, center=(80, 80))
            for i in range(1, 5)
        ]
        breeze_target = make_target(
            "Brisa Favorável",
            costumes=breeze_costumes,
            blocks=sb_breeze.blocks,
            variables={
                v_breeze_idx[1]: [v_breeze_idx[0], 0],
                v_breeze_x0[1]: [v_breeze_x0[0], 0],
                v_breeze_d[1]: [v_breeze_d[0], 0.04],
                v_breeze_p[1]: [v_breeze_p[0], 0.005],
            },
            size=24,
            visible=False,
            layer_order=8,
        )

        # ---------------- 9. PASSAROS 3D (5 raias radiais p(d)=d^gamma -> 22%..56%, trajetoria limpa) ----------------
        sb_bird = ScriptBuilder("bird")
        v_bird_x0 = ("x0 Passaro", "vb_x0")
        v_bird_q = ("Quadro Passaro", "vb_q")
        v_bird_d = ("Profundidade Passaro", "vb_d")
        v_bird_p = ("Perspectiva Passaro", "vb_p")
        sb_bird.stack(sb_bird.hat_flag(80, 60), sb_bird.hide())
        sb_bird.stack(
            sb_bird.hat_broadcast(*B["onda_passaro"], 80, 220),
            sb_bird.hide(),
            sb_bird.if_then(
                sb_bird.eq(sb_bird.var(*V["Estado"]), "voo"),
                sb_bird.create_clone("_myself_"),
            ),
        )
        bird_scale_expr = lambda: sb_bird.add(22, sb_bird.mul(34, sb_bird.var(*v_bird_p)))
        bird_y_expr = lambda: air_y_of_p(sb_bird, sb_bird.var(*v_bird_p))
        bird_x_expr = lambda: sb_bird.add(
            air_x_of_dp(sb_bird, v_bird_x0, sb_bird.var(*v_bird_p)),
            sb_bird.mul(
                3,
                sb_bird.mathop("sin", sb_bird.mul(sb_bird.var(*V["Frequencia (w)"]), sb_bird.y_pos())),
            ),
        )
        bird_q_expr = lambda: sb_bird.add(
            sb_bird.mod(sb_bird.mathop("floor", sb_bird.div(sb_bird.timer(), 0.11)), 4),
            1,
        )
        bird_costume_idx_expr = lambda: sb_bird.add(
            sb_bird.mul(sb_bird.sub(sb_bird.var(*V["Etapa"]), 1), 4),
            sb_bird.var(*v_bird_q),
        )
        sb_bird.stack(
            sb_bird.hat_clone(460, 60),
            sb_bird.hide(),
            sb_bird.set_var(*v_bird_q, bird_q_expr()),
            sb_bird.switch_costume(bird_costume_idx_expr()),
            sb_bird.set_var(*v_bird_d, 0.04),
            sb_bird.set_var(*v_bird_p, p_of_d(sb_bird, sb_bird.var(*v_bird_d))),
            sb_bird.set_size(bird_scale_expr()),
            sb_bird.set_var(
                *v_bird_x0,
                sb_bird.mul(sb_bird.sub(sb_bird.var(*V["Raia Ave"]), 2), 68),
            ),
            sb_bird.go_xy(bird_x_expr(), bird_y_expr()),
            sb_bird.set_effect("ghost", 64),
            sb_bird.show(),
            sb_bird.repeat_until(
                sb_bird.bool_or(sb_bird.bool_not(sb_bird.eq(sb_bird.var(*V["Estado"]), "voo")), sb_bird.gt(sb_bird.var(*v_bird_d), 1.0)),
                sb_bird.change_var(*v_bird_d, sb_bird.add(0.0066, sb_bird.mul(0.0005, sb_bird.var(*V["Etapa"])))),
                sb_bird.set_var(*v_bird_p, p_of_d(sb_bird, sb_bird.var(*v_bird_d))),
                sb_bird.if_else(
                    sb_bird.lt(sb_bird.var(*v_bird_d), 0.24),
                    [sb_bird.set_effect("ghost", sb_bird.round_op(sb_bird.mul(sb_bird.sub(0.24, sb_bird.var(*v_bird_d)), 320)))],
                    [sb_bird.set_effect("ghost", 0)],
                ),
                sb_bird.set_var(*v_bird_q, bird_q_expr()),
                sb_bird.switch_costume(bird_costume_idx_expr()),
                sb_bird.set_size(bird_scale_expr()),
                sb_bird.go_xy(bird_x_expr(), bird_y_expr()),
                sb_bird.if_then(
                    sb_bird.bool_and(sb_bird.lt(sb_bird.distance_to("Avião"), 34), sb_bird.lt(sb_bird.var(*V["Proteção"]), 0.1)),
                    sb_bird.set_var(*V["Proteção"], 2.5),
                    sb_bird.change_var(*V["Vidas"], -1),
                    sb_bird.change_var(*V["Pontos"], -10),
                    sb_bird.if_then(sb_bird.lt(sb_bird.var(*V["Pontos"]), 0), sb_bird.set_var(*V["Pontos"], 0)),
                    sb_bird.broadcast(*B["impacto"]),
                    sb_bird.delete_clone(),
                ),
            ),
            sb_bird.if_then(
                sb_bird.eq(sb_bird.var(*V["Estado"]), "voo"),
                sb_bird.change_var(*V["Pontos"], 5),
            ),
            sb_bird.delete_clone(),
        )
        sb_bird.stack(sb_bird.hat_broadcast(*B["menu"], 80, 620), sb_bird.delete_clone())
        sb_bird.stack(sb_bird.hat_broadcast(*B["guia"], 80, 720), sb_bird.delete_clone())
        sb_bird.stack(sb_bird.hat_broadcast(*B["fim"], 80, 820), sb_bird.delete_clone())

        bird_costumes = []
        for b_idx, b_slug, br_label in [
            (1, "campo", "Amazonia"),
            (2, "floresta", "Cerrado"),
            (3, "deserto", "Pantanal"),
            (4, "neve", "Mata Atlantica"),
        ]:
            for q_idx in range(1, 5):
                bird_costumes.append(
                    reg.costume_from_image(
                        ORG_DIR / "04_passaros_biomas" / f"aeromattics_passaro_bioma{b_idx}_{b_slug}_q{q_idx}.png",
                        f"{br_label} - quadro {q_idx}",
                        bitmap_resolution=2,
                        center=(160, 90),
                    )
                )
        bird_target = make_target(
            "Pássaros",
            costumes=bird_costumes,
            blocks=sb_bird.blocks,
            variables={
                v_bird_x0[1]: [v_bird_x0[0], 0],
                v_bird_q[1]: [v_bird_q[0], 1],
                v_bird_d[1]: [v_bird_d[0], 0.04],
                v_bird_p[1]: [v_bird_p[0], 0.005],
            },
            size=22,
            visible=False,
            layer_order=9,
        )

        # ---------------- 11. AVES MIGRATORIAS (6 quadros, perspectiva S_mig e voo direcional sem inversao) ----------------
        sb_mig = ScriptBuilder("mig")
        v_mig_id = ("Mig Id", "vm_id")
        v_mig_t = ("Mig Passo", "vm_t")
        v_mig_side = ("Mig LadoLocal", "vm_side")
        v_mig_y0 = ("Mig Y0", "vm_y0")

        sb_mig.stack(sb_mig.hat_flag(80, 60), sb_mig.hide(), sb_mig.set_var(*v_mig_id, 0))
        sb_mig.stack(sb_mig.hat_broadcast(*B["menu"], 80, 220), sb_mig.hide(), sb_mig.delete_clone())
        sb_mig.stack(sb_mig.hat_broadcast(*B["guia"], 80, 320), sb_mig.hide(), sb_mig.delete_clone())
        sb_mig.stack(sb_mig.hat_broadcast(*B["decolar"], 80, 370), sb_mig.hide(), sb_mig.delete_clone())
        sb_mig.stack(sb_mig.hat_broadcast(*B["fim"], 80, 420), sb_mig.hide(), sb_mig.delete_clone())
        sb_mig.stack(
            sb_mig.hat_broadcast(*B["migracao_aviso"], 80, 560),
            sb_mig.set_size(58),
            sb_mig.point_dir(90),
            sb_mig.if_else(
                sb_mig.lt(sb_mig.var(*V["Migracao Lado"]), 0),
                [sb_mig.switch_costume("Alerta Esquerda"), sb_mig.go_xy(-204, -48)],
                [sb_mig.switch_costume("Alerta Direita"), sb_mig.go_xy(204, -48)],
            ),
            sb_mig.show(),
            sb_mig.repeat(
                5,
                sb_mig.if_then(
                    sb_mig.eq(sb_mig.var(*V["Estado"]), "voo"),
                    sb_mig.set_effect("ghost", 0),
                    sb_mig.wait(0.28),
                    sb_mig.set_effect("ghost", 35),
                    sb_mig.wait(0.27),
                ),
            ),
            sb_mig.clear_effects(),
            sb_mig.hide(),
            sb_mig.if_then(
                sb_mig.eq(sb_mig.var(*V["Estado"]), "voo"),
                sb_mig.set_var(*v_mig_id, 1),
                sb_mig.create_clone("_myself_"),
                sb_mig.wait(0.55),
                sb_mig.if_then(
                    sb_mig.eq(sb_mig.var(*V["Estado"]), "voo"),
                    sb_mig.set_var(*v_mig_id, 2),
                    sb_mig.create_clone("_myself_"),
                    sb_mig.wait(0.55),
                    sb_mig.if_then(
                        sb_mig.eq(sb_mig.var(*V["Estado"]), "voo"),
                        sb_mig.set_var(*v_mig_id, 3),
                        sb_mig.create_clone("_myself_"),
                    ),
                ),
            ),
        )

        # Equacoes da travessia diagonal monotona (115 passos):
        # x_k(t) = L * (192 - 22*(k-1) - 0.88*t) + 10*sin(4*t + 50*k) -> min |x| >= 36 > 0 (lado oposto livre!)
        # y_k(t) = 76 + 12*(k-1) - 1.42*t
        # S_mig(y) = 38 + 0.25*(76 - y)
        mig_x_expr = lambda: sb_mig.add(
            sb_mig.mul(
                sb_mig.var(*v_mig_side),
                sb_mig.sub(
                    sb_mig.sub(192, sb_mig.mul(sb_mig.sub(sb_mig.var(*v_mig_id), 1), 22)),
                    sb_mig.mul(0.88, sb_mig.var(*v_mig_t)),
                ),
            ),
            sb_mig.mul(
                10,
                sb_mig.mathop(
                    "sin",
                    sb_mig.add(sb_mig.mul(4, sb_mig.var(*v_mig_t)), sb_mig.mul(50, sb_mig.var(*v_mig_id))),
                ),
            ),
        )
        mig_y_expr = lambda: sb_mig.sub(sb_mig.var(*v_mig_y0), sb_mig.mul(sb_mig.var(*v_mig_t), 1.42))
        mig_scale_expr = lambda: sb_mig.add(38, sb_mig.mul(0.25, sb_mig.sub(76, sb_mig.y_pos())))
        mig_costume_expr = lambda: sb_mig.add(
            sb_mig.mod(
                sb_mig.add(sb_mig.mathop("floor", sb_mig.div(sb_mig.var(*v_mig_t), 2)), sb_mig.mul(2, sb_mig.var(*v_mig_id))),
                6,
            ),
            1,
        )

        sb_mig.stack(
            sb_mig.hat_clone(520, 60),
            sb_mig.hide(),
            sb_mig.clear_effects(),
            sb_mig.set_var(*v_mig_t, 0),
            sb_mig.set_var(*v_mig_side, sb_mig.var(*V["Migracao Lado"])),
            sb_mig.set_var(*v_mig_y0, sb_mig.add(76, sb_mig.mul(sb_mig.sub(sb_mig.var(*v_mig_id), 1), 12))),
            sb_mig.if_else(
                sb_mig.lt(sb_mig.var(*v_mig_side), 0),
                [sb_mig.point_dir(90)],
                [sb_mig.point_dir(-90)],
            ),
            sb_mig.set_size(38),
            sb_mig.switch_costume(mig_costume_expr()),
            sb_mig.go_xy(mig_x_expr(), sb_mig.var(*v_mig_y0)),
            sb_mig.show(),
            sb_mig.repeat_until(
                sb_mig.bool_or(sb_mig.bool_not(sb_mig.eq(sb_mig.var(*V["Estado"]), "voo")), sb_mig.gt(sb_mig.var(*v_mig_t), 115)),
                sb_mig.change_var(*v_mig_t, 1),
                sb_mig.go_xy(mig_x_expr(), mig_y_expr()),
                sb_mig.set_size(mig_scale_expr()),
                sb_mig.switch_costume(mig_costume_expr()),
                sb_mig.if_then(
                    sb_mig.bool_and(sb_mig.lt(sb_mig.distance_to("Avião"), 32), sb_mig.lt(sb_mig.var(*V["Proteção"]), 0.1)),
                    sb_mig.set_var(*V["Proteção"], 2.5),
                    sb_mig.change_var(*V["Vidas"], -1),
                    sb_mig.change_var(*V["Pontos"], -10),
                    sb_mig.if_then(sb_mig.lt(sb_mig.var(*V["Pontos"]), 0), sb_mig.set_var(*V["Pontos"], 0)),
                    sb_mig.broadcast(*B["impacto"]),
                    sb_mig.delete_clone(),
                ),
                sb_mig.wait(0.04),
            ),
            sb_mig.if_then(
                sb_mig.bool_and(sb_mig.eq(sb_mig.var(*V["Estado"]), "voo"), sb_mig.eq(sb_mig.var(*v_mig_id), 1)),
                sb_mig.change_var(*V["Pontos"], 25),
            ),
            sb_mig.delete_clone(),
        )

        mig_costumes = [
            reg.costume_from_image(ORG_DIR / "04_passaros_biomas" / f"ave_migratoria_q{i}.png", f"Harpia Real {i}", bitmap_resolution=2, center=(160, 90))
            for i in range(1, 7)
        ] + [
            reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "alerta_migracao_esq.png", "Alerta Esquerda", bitmap_resolution=2, center=(60, 60)),
            reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "alerta_migracao_dir.png", "Alerta Direita", bitmap_resolution=2, center=(60, 60)),
        ]
        mig_target = make_target(
            "Aves Migratórias",
            costumes=mig_costumes,
            blocks=sb_mig.blocks,
            variables={
                v_mig_id[1]: [v_mig_id[0], 0],
                v_mig_t[1]: [v_mig_t[0], 0],
                v_mig_side[1]: [v_mig_side[0], 0],
                v_mig_y0[1]: [v_mig_y0[0], 76],
            },
            size=38,
            visible=False,
            layer_order=13,
            rotation_style="left-right",
        )

        # ---------------- 12. AVIAO (30 FPS constantes sem jitter, clamping [-2.10,+2.10], sensor com tecla C) ----------------
        sb_av = ScriptBuilder("av")
        v_alvo = ("Alvo X", "va_alvo")
        v_passo = ("Passo X", "va_passo")
        sb_av.stack(sb_av.hat_flag(80, 60), sb_av.hide())
        sb_av.stack(sb_av.hat_broadcast(*B["menu"], 80, 200), sb_av.hide())
        sb_av.stack(sb_av.hat_broadcast(*B["guia"], 80, 300), sb_av.hide())
        sb_av.stack(
            sb_av.hat_broadcast(*B["decolar"], 80, 420),
            sb_av.clear_effects(),
            sb_av.set_size(24),
            sb_av.switch_costume("Voando Em linha Reta"),
            sb_av.go_xy(0, -112),
            sb_av.show(),
            sb_av.glide(2.65, 0, -58),
        )
        sb_av.stack(
            sb_av.hat_broadcast(*B["decolar"], 80, 620),
            sb_av.wait(0.6),
            sb_av.repeat(
                14,
                sb_av.if_then(
                    sb_av.eq(sb_av.var(*V["Estado"]), "decolagem"),
                    sb_av.change_size(1),
                    sb_av.wait(0.11),
                ),
            ),
        )
        key_left_any = sb_av.bool_or(sb_av.key_pressed("left arrow"), sb_av.key_pressed("a"))
        key_right_any = sb_av.bool_or(sb_av.key_pressed("right arrow"), sb_av.key_pressed("d"))
        sensor_active = sb_av.eq(sb_av.var(*V["Modo Sensor"]), 1)

        # Em 30 FPS fixos (sem wait 0.03 que causava batimento): alvo in {-1.85, 0, +1.85},
        # vx = 0.82*vx + 0.18*alvo, Passo X = clamp(vx + 0.28*Vento Forca, -2.10, +2.10)
        vx_smooth = sb_av.add(sb_av.mul(0.82, sb_av.var(*V["Velocidade X"])), sb_av.mul(0.18, sb_av.var(*v_alvo)))
        wind_drift = sb_av.mul(0.28, sb_av.var(*V["Vento Forca"]))
        estab_expr = sb_av.round_op(
            sb_av.add(
                sb_av.mul(0.85, sb_av.var(*V["Estabilidade"])),
                sb_av.mul(
                    0.15,
                    sb_av.add(
                        sb_av.mul(52, sb_av.var(*V["Vento Forca"])),
                        sb_av.mul(22.0, sb_av.var(*V["Velocidade X"])),
                    ),
                ),
            )
        )

        sb_av.stack(
            sb_av.hat_broadcast(*B["voar"], 460, 60),
            sb_av.go_xy(0, -58),
            sb_av.set_size(38),
            sb_av.set_var(*V["Velocidade X"], 0),
            sb_av.set_var(*v_passo, 0),
            sb_av.set_var(*V["Estabilidade"], 0),
            sb_av.set_var(*V["Posicao X Aviao"], 0),
            sb_av.show(),
            sb_av.repeat_until(
                sb_av.bool_not(sb_av.eq(sb_av.var(*V["Estado"]), "voo")),
                sb_av.if_else(
                    key_left_any,
                    [sb_av.set_var(*v_alvo, -1.85)],
                    [sb_av.if_else(
                        key_right_any,
                        [sb_av.set_var(*v_alvo, 1.85)],
                        [sb_av.if_else(
                            sensor_active,
                            [sb_av.if_else(
                                sb_av.lt(sb_av.mouse_x(), sb_av.sub(sb_av.x_pos(), 24)),
                                [sb_av.set_var(*v_alvo, -1.85)],
                                [sb_av.if_else(
                                    sb_av.gt(sb_av.mouse_x(), sb_av.add(sb_av.x_pos(), 24)),
                                    [sb_av.set_var(*v_alvo, 1.85)],
                                    [sb_av.set_var(*v_alvo, 0)],
                                )],
                            )],
                            [sb_av.set_var(*v_alvo, 0)],
                        )],
                    )],
                ),
                sb_av.set_var(*V["Velocidade X"], vx_smooth),
                sb_av.set_var(*v_passo, sb_av.add(sb_av.var(*V["Velocidade X"]), wind_drift)),
                sb_av.if_then(sb_av.gt(sb_av.var(*v_passo), 2.10), sb_av.set_var(*v_passo, 2.10)),
                sb_av.if_then(sb_av.lt(sb_av.var(*v_passo), -2.10), sb_av.set_var(*v_passo, -2.10)),
                sb_av.set_var(*V["Estabilidade"], estab_expr),
                sb_av.if_then(sb_av.gt(sb_av.var(*V["Estabilidade"]), 95), sb_av.set_var(*V["Estabilidade"], 95)),
                sb_av.if_then(sb_av.lt(sb_av.var(*V["Estabilidade"]), -95), sb_av.set_var(*V["Estabilidade"], -95)),
                sb_av.change_x(sb_av.var(*v_passo)),
                sb_av.if_then(sb_av.lt(sb_av.x_pos(), -180), sb_av.set_x(-180), sb_av.set_var(*V["Velocidade X"], 0)),
                sb_av.if_then(sb_av.gt(sb_av.x_pos(), 180), sb_av.set_x(180), sb_av.set_var(*V["Velocidade X"], 0)),
                sb_av.set_var(*V["Posicao X Aviao"], sb_av.x_pos()),
                sb_av.if_else(
                    sb_av.gt(sb_av.var(*V["Proteção"]), 0),
                    [sb_av.set_effect("ghost", 45)],
                    [sb_av.set_effect("ghost", 0)],
                ),
            ),
        )
        # Animacao de inclinacao das asas (responde a setas / A-D e sensor filtrado)
        bank_left = sb_av.bool_or(
            sb_av.bool_or(sb_av.key_pressed("left arrow"), sb_av.key_pressed("a")),
            sb_av.lt(sb_av.var(*V["Velocidade X"]), -0.35),
        )
        bank_right = sb_av.bool_or(
            sb_av.bool_or(sb_av.key_pressed("right arrow"), sb_av.key_pressed("d")),
            sb_av.gt(sb_av.var(*V["Velocidade X"]), 0.35),
        )
        sb_av.stack(
            sb_av.hat_broadcast(*B["voar"], 920, 60),
            sb_av.switch_costume("Voando Em linha Reta"),
            sb_av.repeat_until(
                sb_av.bool_not(sb_av.eq(sb_av.var(*V["Estado"]), "voo")),
                sb_av.if_else(
                    bank_left,
                    [sb_av.if_else(
                        sb_av.bool_or(sb_av.lt(sb_av.costume_num(), 1), sb_av.gt(sb_av.costume_num(), 7)),
                        [sb_av.switch_costume("Virando para esquerda")],
                        [
                            sb_av.if_then(sb_av.lt(sb_av.costume_num(), 7), sb_av.next_costume()),
                            sb_av.wait(0.03),
                        ],
                    )],
                    [sb_av.if_else(
                        bank_right,
                        [sb_av.if_else(
                            sb_av.bool_or(sb_av.lt(sb_av.costume_num(), 18), sb_av.gt(sb_av.costume_num(), 23)),
                            [sb_av.switch_costume("Interlúdio")],
                            [
                                sb_av.if_then(sb_av.lt(sb_av.costume_num(), 23), sb_av.next_costume()),
                                sb_av.wait(0.03),
                            ],
                        )],
                        [sb_av.if_else(
                            sb_av.bool_and(sb_av.gt(sb_av.costume_num(), 0), sb_av.lt(sb_av.costume_num(), 18)),
                            [
                                sb_av.if_else(
                                    sb_av.lt(sb_av.costume_num(), 8),
                                    [sb_av.switch_costume("desvirando para esquerda")],
                                    [sb_av.if_else(
                                        sb_av.lt(sb_av.costume_num(), 17),
                                        [sb_av.next_costume()],
                                        [sb_av.switch_costume("Voando Em linha Reta")],
                                    )],
                                ),
                                sb_av.wait(0.03),
                            ],
                            [sb_av.if_else(
                                sb_av.bool_and(sb_av.gt(sb_av.costume_num(), 17), sb_av.lt(sb_av.costume_num(), 29)),
                                [
                                    sb_av.if_then(sb_av.lt(sb_av.costume_num(), 24), sb_av.switch_costume("desvirando da direita")),
                                    sb_av.next_costume(),
                                    sb_av.wait(0.03),
                                ],
                                [
                                    sb_av.if_else(
                                        sb_av.bool_or(sb_av.lt(sb_av.costume_num(), 30), sb_av.gt(sb_av.costume_num(), 46)),
                                        [sb_av.switch_costume("Voando Em linha Reta")],
                                        [sb_av.next_costume()],
                                    ),
                                    sb_av.wait(0.03),
                                ],
                            )],
                        )],
                    )],
                ),
            ),
        )
        sb_av.stack(
            sb_av.hat_broadcast(*B["fim"], 460, 720),
            sb_av.clear_effects(),
            sb_av.if_then(
                sb_av.eq(sb_av.var(*V["Estado"]), "queda"),
                sb_av.repeat(
                    24,
                    sb_av.change_y(-5.5),
                    sb_av.change_size(-0.5),
                    sb_av.wait(0.04),
                ),
            ),
            sb_av.hide(),
        )
        av_target = make_target(
            "Avião",
            costumes=[reg.costume_from_raw(c, orig_zip) for c in orig_targets["Avião"]["costumes"]],
            blocks=sb_av.blocks,
            variables={v_alvo[1]: [v_alvo[0], 0], v_passo[1]: [v_passo[0], 0]},
            x=0,
            y=-58,
            size=38,
            visible=False,
            layer_order=14,
        )

        # ---------------- 13. FUNDO DE ENCERRAMENTO (Cenas geradas de pouso sem HUD inferior) ----------------
        sb_endbg = ScriptBuilder("endbg")
        sb_endbg.stack(sb_endbg.hat_flag(80, 60), sb_endbg.go_xy(0, 0), sb_endbg.hide())
        sb_endbg.stack(sb_endbg.hat_broadcast(*B["menu"], 80, 200), sb_endbg.hide())
        sb_endbg.stack(sb_endbg.hat_broadcast(*B["guia"], 80, 310), sb_endbg.hide())
        sb_endbg.stack(sb_endbg.hat_broadcast(*B["decolar"], 80, 420), sb_endbg.hide())
        sb_endbg.stack(
            sb_endbg.hat_broadcast(*B["fim"], 80, 560),
            sb_endbg.go_xy(0, 0),
            sb_endbg.if_else(
                sb_endbg.eq(sb_endbg.var(*V["Motivo"]), "Missão concluída!"),
                [sb_endbg.switch_costume("Pouso Vitoria")],
                [sb_endbg.switch_costume("Pouso Fim de Voo")],
            ),
            sb_endbg.repeat_until(sb_endbg.eq(sb_endbg.var(*V["Estado"]), "fim"), sb_endbg.wait(0.05)),
            sb_endbg.show(),
        )
        endbg_target = make_target(
            "Fundo de encerramento",
            costumes=[
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "tela_Fim_Pouso_Vitoria.png", "Pouso Vitoria", bitmap_resolution=2, center=(480, 360)),
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "tela_Fim_Pouso_GameOver.png", "Pouso Fim de Voo", bitmap_resolution=2, center=(480, 360)),
            ],
            blocks=sb_endbg.blocks,
            x=0,
            y=0,
            size=100,
            visible=False,
            layer_order=15,
        )

        def is_hud_visible(sb: ScriptBuilder) -> str:
            return sb.bool_or(sb.eq(sb.var(*V["Estado"]), "voo"), sb.eq(sb.var(*V["Estado"]), "decolagem"))

        # ---------------- 14. HUD · PAINEL INFERIOR ----------------
        sb_panel = ScriptBuilder("pnl")
        sb_panel.stack(sb_panel.hat_flag(80, 60), sb_panel.go_xy(0, 0), sb_panel.hide())
        sb_panel.stack(
            sb_panel.hat_broadcast(*B["decolar"], 80, 220),
            sb_panel.go_xy(0, 0),
            sb_panel.show(),
            sb_panel.repeat_until(sb_panel.bool_not(is_hud_visible(sb_panel)), sb_panel.wait(0.1)),
            sb_panel.hide(),
        )
        sb_panel.stack(
            sb_panel.hat_broadcast(*B["voar"], 80, 440),
            sb_panel.go_xy(0, 0),
            sb_panel.show(),
            sb_panel.repeat_until(sb_panel.bool_not(is_hud_visible(sb_panel)), sb_panel.wait(0.1)),
            sb_panel.hide(),
        )
        sb_panel.stack(sb_panel.hat_broadcast(*B["menu"], 80, 660), sb_panel.hide())
        sb_panel.stack(sb_panel.hat_broadcast(*B["guia"], 80, 760), sb_panel.hide())
        sb_panel.stack(sb_panel.hat_broadcast(*B["fim"], 80, 860), sb_panel.hide())
        panel_target = make_target(
            "HUD · painel",
            costumes=[reg.costume_from_image(
                ORG_DIR / "03_hud_cockpit" / "aeromattics_hud_inferior_medidores_circulares.png",
                "Cockpit inferior - medidores",
                bitmap_resolution=1,
                center=(240, 180),
            )],
            blocks=sb_panel.blocks,
            x=0,
            y=0,
            size=100,
            visible=False,
            layer_order=16,
        )

        # ---------------- 15 e 16. PONTEIROS ANGULARES (COMB.% e ESTAB.) ----------------
        def make_fuel_needle(name: str, img_name: str, var_tuple: tuple[str, str], x: int, y: int, layer: int) -> dict:
            sb_n = ScriptBuilder(f"ndl{layer}")
            ang_expr = lambda: sb_n.sub(sb_n.mul(2.7, sb_n.var(*var_tuple)), 45)
            sb_n.stack(
                sb_n.hat_flag(80, 60),
                sb_n.go_xy(x, y),
                sb_n.set_size(82),
                sb_n.point_dir(ang_expr()),
                sb_n.hide(),
            )
            sb_n.stack(
                sb_n.hat_broadcast(*B["decolar"], 80, 260),
                sb_n.go_xy(x, y),
                sb_n.set_size(82),
                sb_n.point_dir(ang_expr()),
                sb_n.show(),
                sb_n.repeat_until(
                    sb_n.bool_not(is_hud_visible(sb_n)),
                    sb_n.point_dir(ang_expr()),
                    sb_n.wait(0.05),
                ),
                sb_n.hide(),
            )
            sb_n.stack(
                sb_n.hat_broadcast(*B["voar"], 80, 560),
                sb_n.go_xy(x, y),
                sb_n.set_size(82),
                sb_n.point_dir(ang_expr()),
                sb_n.show(),
                sb_n.repeat_until(
                    sb_n.bool_not(is_hud_visible(sb_n)),
                    sb_n.point_dir(ang_expr()),
                    sb_n.wait(0.05),
                ),
                sb_n.hide(),
            )
            sb_n.stack(sb_n.hat_broadcast(*B["menu"], 80, 860), sb_n.hide())
            sb_n.stack(sb_n.hat_broadcast(*B["guia"], 80, 960), sb_n.hide())
            sb_n.stack(sb_n.hat_broadcast(*B["fim"], 80, 1060), sb_n.hide())
            return make_target(
                name,
                costumes=[reg.costume_from_image(ORG_DIR / "03_hud_cockpit" / img_name, "Ponteiro", bitmap_resolution=1, center=(32, 32))],
                blocks=sb_n.blocks,
                x=x,
                y=y,
                size=82,
                direction=225,
                visible=False,
                layer_order=layer,
            )

        def make_estab_needle(name: str, img_name: str, var_tuple: tuple[str, str], x: int, y: int, layer: int) -> dict:
            sb_n = ScriptBuilder(f"ndl{layer}")
            ang_expr = lambda: sb_n.add(90, sb_n.mul(1.15, sb_n.var(*var_tuple)))
            sb_n.stack(
                sb_n.hat_flag(80, 60),
                sb_n.go_xy(x, y),
                sb_n.set_size(82),
                sb_n.point_dir(ang_expr()),
                sb_n.hide(),
            )
            sb_n.stack(
                sb_n.hat_broadcast(*B["decolar"], 80, 260),
                sb_n.go_xy(x, y),
                sb_n.set_size(82),
                sb_n.point_dir(ang_expr()),
                sb_n.show(),
                sb_n.repeat_until(
                    sb_n.bool_not(is_hud_visible(sb_n)),
                    sb_n.point_dir(ang_expr()),
                    sb_n.wait(0.05),
                ),
                sb_n.hide(),
            )
            sb_n.stack(
                sb_n.hat_broadcast(*B["voar"], 80, 560),
                sb_n.go_xy(x, y),
                sb_n.set_size(82),
                sb_n.point_dir(ang_expr()),
                sb_n.show(),
                sb_n.repeat_until(
                    sb_n.bool_not(is_hud_visible(sb_n)),
                    sb_n.point_dir(ang_expr()),
                    sb_n.wait(0.05),
                ),
                sb_n.hide(),
            )
            sb_n.stack(sb_n.hat_broadcast(*B["menu"], 80, 860), sb_n.hide())
            sb_n.stack(sb_n.hat_broadcast(*B["guia"], 80, 960), sb_n.hide())
            sb_n.stack(sb_n.hat_broadcast(*B["fim"], 80, 1060), sb_n.hide())
            return make_target(
                name,
                costumes=[reg.costume_from_image(ORG_DIR / "03_hud_cockpit" / img_name, "Ponteiro", bitmap_resolution=1, center=(32, 32))],
                blocks=sb_n.blocks,
                x=x,
                y=y,
                size=82,
                direction=90,
                visible=False,
                layer_order=layer,
            )

        needle_fuel_target = make_fuel_needle("HUD · ponteiro combustível", "aeromattics_hud_ponteiro_combustivel.png", V["Combustível"], -45, -143, 17)
        needle_estab_target = make_estab_needle("HUD · ponteiro estabilidade", "aeromattics_hud_ponteiro_estabilidade.png", V["Estabilidade"], 44, -143, 18)

        # ---------------- 17..26. DIGITOS BASE-10 DO HUD ----------------
        digit_costumes = []
        for idx_c, raw_c in enumerate(orig_targets["HUD · Pontos 0"]["costumes"]):
            c_info = reg.costume_from_raw(raw_c, orig_zip)
            c_info["name"] = f"digito_{idx_c}"
            digit_costumes.append(c_info)

        def make_digit(name: str, var_tuple: tuple[str, str], divisor: int, x: int, y: int, layer: int) -> dict:
            sb_d = ScriptBuilder(f"dig{layer}")
            digit_expr = lambda: sb_d.add(
                sb_d.mod(sb_d.mathop("floor", sb_d.div(sb_d.var(*var_tuple), divisor)), 10),
                1,
            )
            sb_d.stack(
                sb_d.hat_flag(80, 60),
                sb_d.go_xy(x, y),
                sb_d.set_size(54),
                sb_d.switch_costume(digit_expr()),
                sb_d.hide(),
            )
            sb_d.stack(
                sb_d.hat_broadcast(*B["decolar"], 80, 260),
                sb_d.go_xy(x, y),
                sb_d.set_size(54),
                sb_d.switch_costume(digit_expr()),
                sb_d.show(),
                sb_d.repeat_until(
                    sb_d.bool_not(is_hud_visible(sb_d)),
                    sb_d.switch_costume(digit_expr()),
                    sb_d.wait(0.05),
                ),
                sb_d.hide(),
            )
            sb_d.stack(
                sb_d.hat_broadcast(*B["voar"], 80, 560),
                sb_d.go_xy(x, y),
                sb_d.set_size(54),
                sb_d.switch_costume(digit_expr()),
                sb_d.show(),
                sb_d.repeat_until(
                    sb_d.bool_not(is_hud_visible(sb_d)),
                    sb_d.switch_costume(digit_expr()),
                    sb_d.wait(0.05),
                ),
                sb_d.hide(),
            )
            sb_d.stack(sb_d.hat_broadcast(*B["menu"], 80, 860), sb_d.hide())
            sb_d.stack(sb_d.hat_broadcast(*B["guia"], 80, 960), sb_d.hide())
            sb_d.stack(sb_d.hat_broadcast(*B["fim"], 80, 1060), sb_d.hide())
            return make_target(
                name,
                costumes=[dict(c) for c in digit_costumes],
                blocks=sb_d.blocks,
                x=x,
                y=y,
                size=54,
                visible=False,
                layer_order=layer,
            )

        digit_targets = []
        layer_cur = 19
        for idx, div_val in enumerate([1000, 100, 10, 1]):
            digit_targets.append(make_digit(f"HUD · Pontos {idx}", V["Pontos"], div_val, -142 + idx * 10, -127, layer_cur))
            layer_cur += 1
        for idx, div_val in enumerate([1000, 100, 10, 1]):
            digit_targets.append(make_digit(f"HUD · Tempo {idx}", V["Tempo de fase"], div_val, -142 + idx * 10, -159, layer_cur))
            layer_cur += 1
        digit_targets.append(make_digit("HUD · Vidas 0", V["Vidas"], 1, 198, -127, layer_cur))
        layer_cur += 1
        digit_targets.append(make_digit("HUD · Fase 0", V["Etapa"], 1, 198, -159, layer_cur))
        layer_cur += 1  # 27

        # ---------------- 27. HUD · ROTULOS VETORIAIS ----------------
        sb_lbl = ScriptBuilder("lbl")
        sb_lbl.stack(sb_lbl.hat_flag(80, 60), sb_lbl.go_xy(0, 0), sb_lbl.hide())
        sb_lbl.stack(
            sb_lbl.hat_broadcast(*B["decolar"], 80, 220),
            sb_lbl.go_xy(0, 0),
            sb_lbl.show(),
            sb_lbl.repeat_until(sb_lbl.bool_not(is_hud_visible(sb_lbl)), sb_lbl.wait(0.1)),
            sb_lbl.hide(),
        )
        sb_lbl.stack(
            sb_lbl.hat_broadcast(*B["voar"], 80, 440),
            sb_lbl.go_xy(0, 0),
            sb_lbl.show(),
            sb_lbl.repeat_until(sb_lbl.bool_not(is_hud_visible(sb_lbl)), sb_lbl.wait(0.1)),
            sb_lbl.hide(),
        )
        sb_lbl.stack(sb_lbl.hat_broadcast(*B["menu"], 80, 660), sb_lbl.hide())
        sb_lbl.stack(sb_lbl.hat_broadcast(*B["guia"], 80, 760), sb_lbl.hide())
        sb_lbl.stack(sb_lbl.hat_broadcast(*B["fim"], 80, 860), sb_lbl.hide())
        labels_target = make_target(
            "HUD · rótulos",
            costumes=[reg.costume_from_svg(build_svg_hud_labels(), "Rotulos painel inferior")],
            blocks=sb_lbl.blocks,
            x=0,
            y=0,
            size=100,
            visible=False,
            layer_order=layer_cur,
        )
        layer_cur += 1  # 26

        # ---------------- 26. CAMADA DE CONCLUSAO (Oculta nas telas de pouso para preservar cena limpa) ----------------
        sb_ov = ScriptBuilder("ov")
        sb_ov.stack(sb_ov.hat_flag(80, 60), sb_ov.go_xy(0, 0), sb_ov.hide())
        sb_ov.stack(sb_ov.hat_broadcast(*B["menu"], 80, 220), sb_ov.hide())
        sb_ov.stack(sb_ov.hat_broadcast(*B["guia"], 80, 320), sb_ov.hide())
        sb_ov.stack(sb_ov.hat_broadcast(*B["decolar"], 80, 420), sb_ov.hide())
        sb_ov.stack(sb_ov.hat_broadcast(*B["fim"], 80, 520), sb_ov.hide())
        ov_target = make_target(
            "Camada de conclusão",
            costumes=[
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "aeromattics_missao_concluida_moldura_limpa.png", "Moldura de vitoria", bitmap_resolution=1, center=(240, 180)),
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "aeromattics_tela_fim_missao_overlay_alpha.png", "Moldura fim de voo", bitmap_resolution=1, center=(240, 180)),
            ],
            blocks=sb_ov.blocks,
            x=0,
            y=0,
            size=100,
            visible=False,
            layer_order=layer_cur,
        )
        layer_cur += 1  # 27

        # ---------------- 27. TEXTO DA CONCLUSAO (Subtitulo enxuto no ceu aberto) ----------------
        sb_txt = ScriptBuilder("txt")
        sb_txt.stack(sb_txt.hat_flag(80, 60), sb_txt.go_xy(0, 0), sb_txt.hide())
        sb_txt.stack(sb_txt.hat_broadcast(*B["menu"], 80, 220), sb_txt.hide())
        sb_txt.stack(sb_txt.hat_broadcast(*B["guia"], 80, 320), sb_txt.hide())
        sb_txt.stack(sb_txt.hat_broadcast(*B["decolar"], 80, 420), sb_txt.hide())
        sb_txt.stack(
            sb_txt.hat_broadcast(*B["fim"], 80, 540),
            sb_txt.go_xy(0, 0),
            sb_txt.set_size(100),
            sb_txt.if_else(
                sb_txt.eq(sb_txt.var(*V["Motivo"]), "Missão concluída!"),
                [sb_txt.switch_costume("Texto vitoria")],
                [sb_txt.switch_costume("Texto fim de voo")],
            ),
            sb_txt.repeat_until(sb_txt.eq(sb_txt.var(*V["Estado"]), "fim"), sb_txt.wait(0.05)),
            sb_txt.show(),
            sb_txt.go_layer("front"),
        )
        txt_target = make_target(
            "Texto da conclusão",
            costumes=[
                reg.costume_from_svg(build_svg_victory_text(), "Texto vitoria"),
                reg.costume_from_svg(build_svg_gameover_text(), "Texto fim de voo"),
            ],
            blocks=sb_txt.blocks,
            x=0,
            y=0,
            size=100,
            visible=False,
            layer_order=layer_cur,
        )
        layer_cur += 1  # 28

        # ---------------- 28. TELAS (Capa Inicial Limpa + Tela de Guia) ----------------
        sb_telas = ScriptBuilder("telas")
        sb_telas.stack(
            sb_telas.hat_flag(80, 60),
            sb_telas.go_xy(0, 0),
            sb_telas.switch_costume("Capa AeroMattics"),
            sb_telas.show(),
        )
        sb_telas.stack(
            sb_telas.hat_broadcast(*B["menu"], 80, 260),
            sb_telas.go_xy(0, 0),
            sb_telas.switch_costume("Capa AeroMattics"),
            sb_telas.show(),
        )
        sb_telas.stack(
            sb_telas.hat_broadcast(*B["guia"], 80, 440),
            sb_telas.go_xy(0, 0),
            sb_telas.switch_costume("Tela Guia"),
            sb_telas.show(),
        )
        sb_telas.stack(sb_telas.hat_broadcast(*B["decolar"], 80, 620), sb_telas.hide())
        sb_telas.stack(sb_telas.hat_broadcast(*B["fim"], 80, 740), sb_telas.hide())

        telas_target = make_target(
            "Telas",
            costumes=[
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "tela_Capa_Menu_Limpa.png", "Capa AeroMattics", bitmap_resolution=2, center=(480, 360)),
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "tela_Guia_AeroMattics.png", "Tela Guia", bitmap_resolution=2, center=(480, 360)),
            ],
            blocks=sb_telas.blocks,
            x=0,
            y=0,
            size=100,
            visible=True,
            layer_order=layer_cur,
        )
        layer_cur += 1  # 29

        # ---------------- 29. START / BOTAO DECOLAR / VOAR DE NOVO ----------------
        sb_start = ScriptBuilder("start")
        sb_start.stack(
            sb_start.hat_flag(80, 60),
            sb_start.go_xy(-96, -112),
            sb_start.switch_costume("Botao da capa"),
            sb_start.show(),
            sb_start.go_layer("front"),
        )
        sb_start.stack(
            sb_start.hat_broadcast(*B["menu"], 80, 260),
            sb_start.go_xy(-96, -112),
            sb_start.switch_costume("Botao da capa"),
            sb_start.show(),
            sb_start.go_layer("front"),
        )
        sb_start.stack(sb_start.hat_broadcast(*B["guia"], 80, 440), sb_start.hide())
        sb_start.stack(sb_start.hat_broadcast(*B["decolar"], 80, 560), sb_start.hide())
        sb_start.stack(
            sb_start.hat_broadcast(*B["fim"], 80, 680),
            sb_start.go_xy(-96, -126),
            sb_start.if_else(
                sb_start.eq(sb_start.var(*V["Motivo"]), "Missão concluída!"),
                [sb_start.switch_costume("RECOMECAR VITORIA")],
                [sb_start.switch_costume("RECOMECAR DERROTA")],
            ),
            sb_start.repeat_until(sb_start.eq(sb_start.var(*V["Estado"]), "fim"), sb_start.wait(0.05)),
            sb_start.show(),
            sb_start.go_layer("front"),
        )
        sb_start.stack(
            sb_start.hat_clicked(460, 60),
            sb_start.if_then(
                sb_start.bool_or(sb_start.eq(sb_start.var(*V["Estado"]), "menu"), sb_start.eq(sb_start.var(*V["Estado"]), "fim")),
                sb_start.set_var(*V["Estado"], "decolagem", kind=10),
                sb_start.broadcast(*B["decolar"]),
            ),
        )
        start_target = make_target(
            "Start",
            costumes=[
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "botao_menu_decolar.png", "Botao da capa", bitmap_resolution=2, center=(130, 42)),
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "botao_fim_jogar_novamente.png", "RECOMECAR VITORIA", bitmap_resolution=2, center=(130, 42)),
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "botao_fim_tentar_novamente.png", "RECOMECAR DERROTA", bitmap_resolution=2, center=(130, 42)),
            ],
            blocks=sb_start.blocks,
            x=-96,
            y=-112,
            size=100,
            visible=True,
            layer_order=layer_cur,
        )
        layer_cur += 1  # 30

        # ---------------- 30. BOTAO GUIA (Abrir Guia / Voltar Menu / Menu Final) ----------------
        sb_guia = ScriptBuilder("guia")
        sb_guia.stack(
            sb_guia.hat_flag(80, 60),
            sb_guia.go_xy(96, -112),
            sb_guia.switch_costume("Abrir Guia"),
            sb_guia.show(),
            sb_guia.go_layer("front"),
        )
        sb_guia.stack(
            sb_guia.hat_broadcast(*B["menu"], 80, 260),
            sb_guia.go_xy(96, -112),
            sb_guia.switch_costume("Abrir Guia"),
            sb_guia.show(),
            sb_guia.go_layer("front"),
        )
        sb_guia.stack(
            sb_guia.hat_broadcast(*B["guia"], 80, 460),
            sb_guia.go_xy(0, -146),
            sb_guia.switch_costume("Voltar Menu"),
            sb_guia.show(),
            sb_guia.go_layer("front"),
        )
        sb_guia.stack(sb_guia.hat_broadcast(*B["decolar"], 80, 660), sb_guia.hide())
        sb_guia.stack(
            sb_guia.hat_broadcast(*B["fim"], 80, 780),
            sb_guia.go_xy(96, -126),
            sb_guia.switch_costume("Menu Final"),
            sb_guia.repeat_until(sb_guia.eq(sb_guia.var(*V["Estado"]), "fim"), sb_guia.wait(0.05)),
            sb_guia.show(),
            sb_guia.go_layer("front"),
        )
        sb_guia.stack(
            sb_guia.hat_clicked(460, 60),
            sb_guia.if_else(
                sb_guia.eq(sb_guia.var(*V["Estado"]), "menu"),
                [sb_guia.set_var(*V["Estado"], "guia", kind=10), sb_guia.broadcast(*B["guia"])],
                [sb_guia.if_then(
                    sb_guia.bool_or(sb_guia.eq(sb_guia.var(*V["Estado"]), "guia"), sb_guia.eq(sb_guia.var(*V["Estado"]), "fim")),
                    sb_guia.set_var(*V["Estado"], "menu", kind=10),
                    sb_guia.broadcast(*B["menu"]),
                )],
            ),
        )
        guia_btn_target = make_target(
            "Botão Guia",
            costumes=[
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "botao_menu_guia.png", "Abrir Guia", bitmap_resolution=2, center=(130, 42)),
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "botao_guia_voltar.png", "Voltar Menu", bitmap_resolution=2, center=(130, 42)),
                reg.costume_from_image(ORG_DIR / "07_telas_e_overlays" / "botao_fim_menu.png", "Menu Final", bitmap_resolution=2, center=(130, 42)),
            ],
            blocks=sb_guia.blocks,
            x=96,
            y=-112,
            size=100,
            visible=True,
            layer_order=layer_cur,
        )

        targets = [
            stage_target,
            cen_target,
            sol_target,
            nuv_target,
            pen_target,
            prop_target,
            pista_target,
            wind_target,
            fuel_target,
            breeze_target,
            bird_target,
            mig_target,
            av_target,
            endbg_target,
            panel_target,
            needle_fuel_target,
            needle_estab_target,
            *digit_targets,
            labels_target,
            ov_target,
            txt_target,
            telas_target,
            start_target,
            guia_btn_target,
        ]
        for idx, t in enumerate(targets):
            t["layerOrder"] = idx

        project = {
            "targets": targets,
            "monitors": [],
            "extensions": ["pen"],
            "meta": {
                "semver": "3.0.0",
                "vm": "2.3.4",
                "agent": "AeroMattics Builder by ThyagoToledo",
            },
        }

        validate_project(project, reg.files)

        project_bytes = json.dumps(project, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        reg.files["project.json"] = project_bytes

        # Salvar em formato .sb3 com verificacao CRC
        tmp = OUT_DESKTOP.with_suffix(".sb3.tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
            for fname, data in reg.files.items():
                zout.writestr(fname, data)
        os.replace(tmp, OUT_DESKTOP)

        with zipfile.ZipFile(OUT_DESKTOP, "r") as zchk:
            bad = zchk.testzip()
            assert bad is None, f"CRC falhou no arquivo: {bad}"

        dest_paths = [
            OUT_DESKTOP_MAIN,
            OUT_DOWNLOADS_NEW,
            OUT_DOWNLOADS_MAIN,
        ]
        if OUT_DOWNLOADS_DIR.exists():
            dest_paths.extend([
                OUT_DOWNLOADS_DIR / "AeroMattics.sb3",
                OUT_DOWNLOADS_DIR / "AeroMattics_MIT_Parkinson.sb3",
            ])
        for dst in dest_paths:
            shutil.copy2(OUT_DESKTOP, dst)

        # Salvar tambem project_mit_formatado.json em sb3_extraido para consulta facil
        with open(ROOT / "sb3_extraido" / "project_mit_formatado.json", "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False, indent=2)

        print(f"Build concluido com sucesso! Targets: {len(targets)}, Assets: {len(reg.files)}")
        print(f"Tamanho final: {OUT_DESKTOP.stat().st_size:,} bytes")
        print(f"Salvo em: {OUT_DESKTOP}")
        for dst in dest_paths:
            print(f"Sincronizado: {dst}")


if __name__ == "__main__":
    build()
