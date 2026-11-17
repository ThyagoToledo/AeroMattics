"""
Simulador headless deterministico da VM do Scratch 3.0 (30 FPS) para AeroMattics.

Executa os blocos reais de project.json dentro de AeroMattics_MIT_Parkinson.sb3,
incluindo threads concorrentes, clones com variaveis locais isoladas, blocos Pen,
procedimentos customizados com warp=true, entradas de teclado/sensor e medicao de carga.

Autoria: ThyagoToledo
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import random
from pathlib import Path
from typing import Any
import zipfile


def _to_num(val: Any) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, bool):
        return 1.0 if val else 0.0
    try:
        s = str(val).strip()
        return 0.0 if s == "" else float(s)
    except ValueError:
        return 0.0


def _to_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    return s not in ("", "0", "false")


def _scratch_eq(a: Any, b: Any) -> bool:
    try:
        return abs(float(str(a).strip()) - float(str(b).strip())) < 1e-9
    except (ValueError, TypeError):
        return str(a).lower() == str(b).lower()


@dataclass
class SpriteInstance:
    name: str
    is_stage: bool
    is_clone: bool
    costumes: list[dict]
    blocks: dict
    local_vars: dict[str, Any]
    x: float = 0.0
    y: float = 0.0
    size: float = 100.0
    direction: float = 90.0
    visible: bool = True
    layer_order: int = 0
    costume_idx: int = 0  # 0-based
    ghost: float = 0.0
    pen_down: bool = False
    pen_size: float = 1.0
    pen_color: int = 0x409832
    deleted: bool = False


@dataclass
class VMThread:
    instance: SpriteInstance
    stack: list[dict] = field(default_factory=list)
    wait_until: float | None = None
    glide_state: dict | None = None
    finished: bool = False


class ScratchVMSimulator:
    """Executor fiel dos blocos Scratch 3.0 a 30 FPS sobre um .sb3 compilado."""

    def __init__(self, sb3_path: Path, seed: int = 12345) -> None:
        with zipfile.ZipFile(sb3_path, "r") as zf:
            self.project = json.loads(zf.read("project.json").decode("utf-8"))
        self.rng = random.Random(seed)
        self.sim_time: float = 0.0
        self.timer_zero: float = 0.0
        self.dt: float = 1.0 / 30.0
        self.keys_pressed: set[str] = set()
        self.mouse_x: float = 0.0
        self.mouse_y: float = 0.0

        self.stage: SpriteInstance | None = None
        self.instances: list[SpriteInstance] = []
        self.threads: list[VMThread] = []
        self.pen_strokes: list[tuple[float, float, float, float, float, int]] = []
        self.last_frame_block_evals: int = 0
        self.last_frame_pen_strokes: int = 0
        self.max_clones_seen: int = 0
        self.broadcasts_seen: list[str] = []
        self._procs: dict[tuple[str, str], tuple[str | None, bool]] = {}

        for t in self.project["targets"]:
            lvars = {vid: val[1] for vid, val in t.get("variables", {}).items()}
            inst = SpriteInstance(
                name=t["name"],
                is_stage=bool(t.get("isStage")),
                is_clone=False,
                costumes=t.get("costumes", []),
                blocks=t.get("blocks", {}),
                local_vars=lvars,
                x=float(t.get("x", 0.0)),
                y=float(t.get("y", 0.0)),
                size=float(t.get("size", 100.0)),
                direction=float(t.get("direction", 90.0)),
                visible=bool(t.get("visible", True)),
                layer_order=int(t.get("layerOrder", 0)),
                costume_idx=int(t.get("currentCostume", 0)),
            )
            self.instances.append(inst)
            if inst.is_stage:
                self.stage = inst
            for bid, b in inst.blocks.items():
                if b.get("opcode") == "procedures_definition":
                    proto_inp = b.get("inputs", {}).get("custom_block")
                    if proto_inp and len(proto_inp) >= 2:
                        proto = inst.blocks.get(proto_inp[1], {})
                        mut = proto.get("mutation", {})
                        proccode = mut.get("proccode", "")
                        warp = str(mut.get("warp", "false")).lower() == "true"
                        self._procs[(inst.name, proccode)] = (b.get("next"), warp)

        self.var_name_to_id: dict[str, str] = {}
        assert self.stage is not None
        for vid, val in self.project["targets"][0].get("variables", {}).items():
            self.var_name_to_id[val[0]] = vid

    def get_global(self, name_or_id: str) -> Any:
        assert self.stage is not None
        vid = self.var_name_to_id.get(name_or_id, name_or_id)
        return self.stage.local_vars.get(vid)

    def get_sprite(self, name: str) -> SpriteInstance:
        for inst in self.instances:
            if not inst.is_clone and inst.name == name:
                return inst
        raise KeyError(name)

    def get_clones(self, name: str) -> list[SpriteInstance]:
        return [i for i in self.instances if i.is_clone and not i.deleted and i.name == name]

    def total_clones(self) -> int:
        return sum(1 for i in self.instances if i.is_clone and not i.deleted)

    def green_flag(self) -> None:
        self.sim_time = 0.0
        self.timer_zero = 0.0
        self.pen_strokes.clear()
        self.instances = [i for i in self.instances if not i.is_clone]
        self.threads.clear()
        self._trigger_hat("event_whenflagclicked")

    def click_sprite(self, sprite_name: str) -> None:
        for inst in list(self.instances):
            if not inst.deleted and inst.name == sprite_name:
                self._spawn_hats(inst, "event_whenthisspriteclicked")

    def press_key_hat(self, key_name: str) -> None:
        for inst in list(self.instances):
            if inst.deleted:
                continue
            for bid, b in inst.blocks.items():
                if b.get("topLevel") and b.get("opcode") == "event_whenkeypressed":
                    opt = b.get("fields", {}).get("KEY_OPTION", [""])[0]
                    if opt == key_name and b.get("next"):
                        self._start_block_thread(inst, b["next"])

    def _trigger_hat(self, opcode: str, msg_id: str | None = None) -> None:
        for inst in list(self.instances):
            if not inst.deleted:
                self._spawn_hats(inst, opcode, msg_id=msg_id)

    def _spawn_hats(self, inst: SpriteInstance, opcode: str, msg_id: str | None = None) -> None:
        for bid, b in inst.blocks.items():
            if not b.get("topLevel") or b.get("opcode") != opcode:
                continue
            if msg_id is not None:
                opt = b.get("fields", {}).get("BROADCAST_OPTION", [None, None])
                if len(opt) < 2 or opt[1] != msg_id:
                    continue
            if b.get("next"):
                # Cancel identical top-hat already running on same sprite (Scratch 3.0 hat behavior)
                self._start_block_thread(inst, b["next"])

    def _start_block_thread(self, inst: SpriteInstance, first_bid: str) -> None:
        self.threads.append(VMThread(instance=inst, stack=[{"type": "block", "bid": first_bid}]))

    def _read_var(self, inst: SpriteInstance, vid: str) -> Any:
        if vid in inst.local_vars:
            return inst.local_vars[vid]
        assert self.stage is not None
        return self.stage.local_vars.get(vid, 0)

    def _write_var(self, inst: SpriteInstance, vid: str, value: Any) -> None:
        if vid in inst.local_vars:
            inst.local_vars[vid] = value
        else:
            assert self.stage is not None
            self.stage.local_vars[vid] = value

    def _eval_input(self, inst: SpriteInstance, inp: Any) -> Any:
        if not isinstance(inp, list) or len(inp) < 2:
            return 0
        payload = inp[1]
        if isinstance(payload, str):
            return self._eval_block(inst, payload)
        if isinstance(payload, list) and len(payload) >= 2:
            return payload[1]
        return 0

    def _eval_block(self, inst: SpriteInstance, bid: str) -> Any:
        self.last_frame_block_evals += 1
        b = inst.blocks[bid]
        op = b["opcode"]
        inps = b.get("inputs", {})
        flds = b.get("fields", {})

        if op == "data_variable":
            return self._read_var(inst, flds["VARIABLE"][1])
        if op == "sensing_timer":
            return max(0.0, self.sim_time - self.timer_zero)
        if op == "sensing_mousex":
            return self.mouse_x
        if op == "sensing_mousey":
            return self.mouse_y
        if op == "sensing_keypressed":
            menu_id = inps["KEY_OPTION"][1]
            key = inst.blocks[menu_id]["fields"]["KEY_OPTION"][0]
            return key in self.keys_pressed
        if op == "sensing_distanceto":
            menu_id = inps["DISTANCETOMENU"][1]
            tgt_name = inst.blocks[menu_id]["fields"]["DISTANCETOMENU"][0]
            tgt = self.get_sprite(tgt_name)
            return math.hypot(inst.x - tgt.x, inst.y - tgt.y)
        if op == "motion_xposition":
            return inst.x
        if op == "motion_yposition":
            return inst.y
        if op == "looks_size":
            return inst.size
        if op == "looks_costumenumbername":
            if flds.get("NUMBER_NAME", ["number"])[0] == "number":
                return inst.costume_idx + 1
            return inst.costumes[inst.costume_idx]["name"] if inst.costumes else ""

        if op == "operator_add":
            return _to_num(self._eval_input(inst, inps["NUM1"])) + _to_num(self._eval_input(inst, inps["NUM2"]))
        if op == "operator_subtract":
            return _to_num(self._eval_input(inst, inps["NUM1"])) - _to_num(self._eval_input(inst, inps["NUM2"]))
        if op == "operator_multiply":
            return _to_num(self._eval_input(inst, inps["NUM1"])) * _to_num(self._eval_input(inst, inps["NUM2"]))
        if op == "operator_divide":
            d = _to_num(self._eval_input(inst, inps["NUM2"]))
            return 0.0 if d == 0 else _to_num(self._eval_input(inst, inps["NUM1"])) / d
        if op == "operator_mod":
            a = _to_num(self._eval_input(inst, inps["NUM1"]))
            m = _to_num(self._eval_input(inst, inps["NUM2"]))
            return 0.0 if m == 0 else (a % m)
        if op == "operator_round":
            return int(math.floor(_to_num(self._eval_input(inst, inps["NUM"])) + 0.5))
        if op == "operator_random":
            a = _to_num(self._eval_input(inst, inps["FROM"]))
            z = _to_num(self._eval_input(inst, inps["TO"]))
            lo, hi = (a, z) if a <= z else (z, a)
            if float(int(lo)) == lo and float(int(hi)) == hi and ("." not in str(inps["FROM"][1][1])) and ("." not in str(inps["TO"][1][1])):
                return self.rng.randint(int(lo), int(hi))
            return self.rng.uniform(lo, hi)
        if op == "operator_mathop":
            fn = flds["OPERATOR"][0]
            x = _to_num(self._eval_input(inst, inps["NUM"]))
            if fn == "abs":
                return abs(x)
            if fn == "floor":
                return math.floor(x)
            if fn == "sin":
                return math.sin(math.radians(x))
            if fn == "cos":
                return math.cos(math.radians(x))
            if fn == "ln":
                return math.log(x) if x > 0 else float("-inf")
            if fn == "e ^":
                return math.exp(x)
            raise KeyError(f"Unsupported mathop: {fn}")
        if op == "operator_equals":
            return _scratch_eq(self._eval_input(inst, inps["OPERAND1"]), self._eval_input(inst, inps["OPERAND2"]))
        if op == "operator_lt":
            return _to_num(self._eval_input(inst, inps["OPERAND1"])) < _to_num(self._eval_input(inst, inps["OPERAND2"]))
        if op == "operator_gt":
            return _to_num(self._eval_input(inst, inps["OPERAND1"])) > _to_num(self._eval_input(inst, inps["OPERAND2"]))
        if op == "operator_and":
            return _to_bool(self._eval_input(inst, inps["OPERAND1"])) and _to_bool(self._eval_input(inst, inps["OPERAND2"]))
        if op == "operator_or":
            return _to_bool(self._eval_input(inst, inps["OPERAND1"])) or _to_bool(self._eval_input(inst, inps["OPERAND2"]))
        if op == "operator_not":
            return not _to_bool(self._eval_input(inst, inps["OPERAND"]))
        if op == "looks_costume":
            return flds["COSTUME"][0]
        raise KeyError(f"Unsupported reporter opcode: {op}")

    def _run_stmt(self, th: VMThread, bid: str, in_warp: bool) -> bool:
        """Executa um bloco statement. Retorna True se a thread deve ceder o quadro agora."""
        inst = th.instance
        if inst.deleted:
            th.finished = True
            return True
        self.last_frame_block_evals += 1
        b = inst.blocks[bid]
        op = b["opcode"]
        inps = b.get("inputs", {})
        flds = b.get("fields", {})

        def advance_next():
            nxt = b.get("next")
            if nxt:
                th.stack.append({"type": "block", "bid": nxt, "warp": in_warp})

        if op == "data_setvariableto":
            vid = flds["VARIABLE"][1]
            val = self._eval_input(inst, inps["VALUE"])
            self._write_var(inst, vid, val)
            advance_next()
            return False
        if op == "data_changevariableby":
            vid = flds["VARIABLE"][1]
            dv = _to_num(self._eval_input(inst, inps["VALUE"]))
            self._write_var(inst, vid, _to_num(self._read_var(inst, vid)) + dv)
            advance_next()
            return False
        if op == "data_hidevariable":
            advance_next()
            return False
        if op == "sensing_resettimer":
            self.timer_zero = self.sim_time
            advance_next()
            return False
        if op == "event_broadcast":
            msg_id = inps["BROADCAST_INPUT"][1][2]
            self.broadcasts_seen.append(msg_id)
            self._trigger_hat("event_whenbroadcastreceived", msg_id=msg_id)
            advance_next()
            return False
        if op in ("sound_play", "sound_setvolumeto", "sound_stopallsounds"):
            advance_next()
            return False
        if op == "sound_playuntildone":
            advance_next()
            if not in_warp:
                th.wait_until = self.sim_time + 1.0
                return True
            return False

        if op == "motion_gotoxy":
            nx = _to_num(self._eval_input(inst, inps["X"]))
            ny = _to_num(self._eval_input(inst, inps["Y"]))
            if inst.pen_down:
                self.pen_strokes.append((inst.x, inst.y, nx, ny, inst.pen_size, inst.pen_color))
                self.last_frame_pen_strokes += 1
            inst.x, inst.y = nx, ny
            advance_next()
            return False
        if op == "motion_setx":
            nx = _to_num(self._eval_input(inst, inps["X"]))
            if inst.pen_down:
                self.pen_strokes.append((inst.x, inst.y, nx, inst.y, inst.pen_size, inst.pen_color))
                self.last_frame_pen_strokes += 1
            inst.x = nx
            advance_next()
            return False
        if op == "motion_changexby":
            inst.x += _to_num(self._eval_input(inst, inps["DX"]))
            advance_next()
            return False
        if op == "motion_changeyby":
            inst.y += _to_num(self._eval_input(inst, inps["DY"]))
            advance_next()
            return False
        if op == "motion_pointindirection":
            inst.direction = _to_num(self._eval_input(inst, inps["DIRECTION"]))
            advance_next()
            return False
        if op == "motion_glidesecstoxy":
            secs = max(0.0, _to_num(self._eval_input(inst, inps["SECS"])))
            tx = _to_num(self._eval_input(inst, inps["X"]))
            ty = _to_num(self._eval_input(inst, inps["Y"]))
            advance_next()
            if secs == 0 or in_warp:
                inst.x, inst.y = tx, ty
                return False
            th.glide_state = {
                "x0": inst.x, "y0": inst.y, "x1": tx, "y1": ty,
                "t0": self.sim_time, "t1": self.sim_time + secs,
            }
            return True

        if op == "looks_show":
            inst.visible = True
            advance_next()
            return False
        if op == "looks_hide":
            inst.visible = False
            advance_next()
            return False
        if op == "looks_setsizeto":
            inst.size = max(5.0, min(500.0, _to_num(self._eval_input(inst, inps["SIZE"]))))
            advance_next()
            return False
        if op == "looks_changesizeby":
            inst.size = max(5.0, min(500.0, inst.size + _to_num(self._eval_input(inst, inps["CHANGE"]))))
            advance_next()
            return False
        if op == "looks_seteffectto":
            if flds.get("EFFECT", [""])[0].lower() == "ghost":
                inst.ghost = max(0.0, min(100.0, _to_num(self._eval_input(inst, inps["VALUE"]))))
            advance_next()
            return False
        if op == "looks_cleargraphiceffects":
            inst.ghost = 0.0
            advance_next()
            return False
        if op == "looks_gotofrontback":
            fb = flds.get("FRONT_BACK", ["front"])[0]
            inst.layer_order = 999 if fb == "front" else 1
            advance_next()
            return False
        if op == "looks_goforwardbackwardlayers":
            advance_next()
            return False
        if op == "looks_nextcostume":
            if inst.costumes:
                inst.costume_idx = (inst.costume_idx + 1) % len(inst.costumes)
            advance_next()
            return False
        if op == "looks_switchcostumeto":
            c_val = self._eval_input(inst, inps["COSTUME"])
            if inst.costumes:
                matched = False
                for idx_c, c in enumerate(inst.costumes):
                    if c["name"] == str(c_val):
                        inst.costume_idx = idx_c
                        matched = True
                        break
                if not matched:
                    n = int(round(_to_num(c_val)))
                    inst.costume_idx = (n - 1) % len(inst.costumes)
            advance_next()
            return False

        if op == "pen_clear":
            self.pen_strokes.clear()
            advance_next()
            return False
        if op == "pen_penDown":
            inst.pen_down = True
            self.pen_strokes.append((inst.x, inst.y, inst.x, inst.y, inst.pen_size, inst.pen_color))
            self.last_frame_pen_strokes += 1
            advance_next()
            return False
        if op == "pen_penUp":
            inst.pen_down = False
            advance_next()
            return False
        if op == "pen_setPenSizeTo":
            inst.pen_size = max(1.0, _to_num(self._eval_input(inst, inps["SIZE"])))
            advance_next()
            return False
        if op == "pen_setPenColorToColor":
            col_val = self._eval_input(inst, inps["COLOR"])
            if isinstance(col_val, str) and col_val.startswith("#"):
                inst.pen_color = int(col_val[1:], 16)
            else:
                inst.pen_color = int(round(_to_num(col_val))) & 0xFFFFFF
            advance_next()
            return False

        if op == "control_wait":
            secs = max(0.0, _to_num(self._eval_input(inst, inps["DURATION"])))
            advance_next()
            if not in_warp:
                th.wait_until = self.sim_time + max(self.dt, secs)
                return True
            return False
        if op == "control_if":
            advance_next()
            if _to_bool(self._eval_input(inst, inps["CONDITION"])) and "SUBSTACK" in inps:
                th.stack.append({"type": "block", "bid": inps["SUBSTACK"][1], "warp": in_warp})
            return False
        if op == "control_if_else":
            advance_next()
            if _to_bool(self._eval_input(inst, inps["CONDITION"])):
                if "SUBSTACK" in inps and inps["SUBSTACK"][1]:
                    th.stack.append({"type": "block", "bid": inps["SUBSTACK"][1], "warp": in_warp})
            elif "SUBSTACK2" in inps and inps["SUBSTACK2"][1]:
                th.stack.append({"type": "block", "bid": inps["SUBSTACK2"][1], "warp": in_warp})
            return False
        if op == "control_repeat":
            times = max(0, int(round(_to_num(self._eval_input(inst, inps["TIMES"])))))
            advance_next()
            if times > 0 and "SUBSTACK" in inps and inps["SUBSTACK"][1]:
                th.stack.append({"type": "repeat", "left": times, "body": inps["SUBSTACK"][1], "warp": in_warp})
            return False
        if op == "control_repeat_until":
            advance_next()
            if not _to_bool(self._eval_input(inst, inps["CONDITION"])) and "SUBSTACK" in inps and inps["SUBSTACK"][1]:
                th.stack.append({"type": "repeat_until", "cond": inps["CONDITION"], "body": inps["SUBSTACK"][1], "warp": in_warp})
            return False
        if op == "control_create_clone_of":
            if self.total_clones() < 300:
                clone = SpriteInstance(
                    name=inst.name,
                    is_stage=False,
                    is_clone=True,
                    costumes=inst.costumes,
                    blocks=inst.blocks,
                    local_vars=dict(inst.local_vars),
                    x=inst.x,
                    y=inst.y,
                    size=inst.size,
                    direction=inst.direction,
                    visible=inst.visible,
                    layer_order=inst.layer_order,
                    costume_idx=inst.costume_idx,
                    ghost=inst.ghost,
                )
                self.instances.append(clone)
                self.max_clones_seen = max(self.max_clones_seen, self.total_clones())
                self._spawn_hats(clone, "control_start_as_clone")
            advance_next()
            return False
        if op == "control_delete_this_clone":
            if inst.is_clone:
                inst.deleted = True
            th.finished = True
            return True
        if op == "procedures_call":
            proccode = b["mutation"]["proccode"]
            body_first, proc_warp = self._procs[(inst.name, proccode)]
            advance_next()
            if body_first:
                th.stack.append({"type": "block", "bid": body_first, "warp": in_warp or proc_warp})
            return False
        raise KeyError(f"Unsupported stmt opcode: {op}")

    def _step_thread(self, th: VMThread) -> None:
        if th.finished or th.instance.deleted:
            th.finished = True
            return
        if th.glide_state is not None:
            gs = th.glide_state
            if self.sim_time >= gs["t1"]:
                th.instance.x, th.instance.y = gs["x1"], gs["y1"]
                th.glide_state = None
            else:
                frac = (self.sim_time - gs["t0"]) / max(1e-6, gs["t1"] - gs["t0"])
                th.instance.x = gs["x0"] + (gs["x1"] - gs["x0"]) * frac
                th.instance.y = gs["y0"] + (gs["y1"] - gs["y0"]) * frac
                return
        if th.wait_until is not None:
            if self.sim_time + 1e-6 < th.wait_until:
                return
            th.wait_until = None

        safety = 0
        while th.stack and safety < 250000:
            safety += 1
            frame = th.stack[-1]
            ftype = frame["type"]
            if ftype == "block":
                th.stack.pop()
                warp = frame.get("warp", False)
                yield_now = self._run_stmt(th, frame["bid"], warp)
                if yield_now or th.finished:
                    return
            elif ftype == "repeat":
                if frame["left"] <= 0:
                    th.stack.pop()
                    if not frame["warp"]:
                        return
                    continue
                frame["left"] -= 1
                if not frame["warp"]:
                    # Yield after body finishes on next loop check
                    th.stack.append({"type": "yield_if", "warp": False})
                th.stack.append({"type": "block", "bid": frame["body"], "warp": frame["warp"]})
            elif ftype == "repeat_until":
                if _to_bool(self._eval_input(th.instance, frame["cond"])):
                    th.stack.pop()
                    if not frame["warp"]:
                        return
                    continue
                if not frame["warp"]:
                    th.stack.append({"type": "yield_if", "warp": False})
                th.stack.append({"type": "block", "bid": frame["body"], "warp": frame["warp"]})
            elif ftype == "yield_if":
                th.stack.pop()
                return
        if not th.stack:
            th.finished = True

    def step_frame(self) -> None:
        self.sim_time += self.dt
        self.last_frame_block_evals = 0
        self.last_frame_pen_strokes = 0
        for th in list(self.threads):
            if not th.finished:
                self._step_thread(th)
        self.threads = [t for t in self.threads if not t.finished and not t.instance.deleted]
        self.instances = [i for i in self.instances if not i.deleted]

    def step_seconds(self, secs: float) -> None:
        frames = int(round(secs * 30.0))
        for _ in range(frames):
            self.step_frame()
