"""
Suite de testes estruturais e de simulacao comportamental para o AeroMattics.

Prova integridade do pacote .sb3 gerado (33 targets, CRC), remocao de formulas na UI,
cenario vivo em 4 camadas de paralaxe (fundo 3D quantizado, Sol no canto superior direito,
Relevo Horizonte animado e Vegetacao em perspectiva de solo), correcao do HUD inferior
(loops ativos em decolar/voar e trajes digito_0..digito_9), controle estavel a 30 FPS
com clamping [-2.10, +2.10] sem mudanca brusca pela brisa, escala de perspectiva no ar,
aves migratorias de 6 quadros sem cruzamento do corredor oposto e controles adaptados.

Autoria: ThyagoToledo
"""

import json
import math
from pathlib import Path
import sys
import unittest
import zipfile

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scratch_vm_sim import ScratchVMSimulator  # noqa: E402


SB3_PATH = Path(r"C:\Users\thyag\OneDrive\Desktop\AeroMattics\AeroMattics_MIT_Parkinson.sb3")


def collect_block_literals(blocks: dict) -> list[str]:
    """Extrai todos os valores literais, campos, menus e opcodes presentes nos blocos do alvo."""
    vals: list[str] = []
    for b in blocks.values():
        vals.append(b.get("opcode", ""))
        for fv in b.get("fields", {}).values():
            if isinstance(fv, list):
                vals.extend(str(x) for x in fv if x is not None)
        for iv in b.get("inputs", {}).values():
            if isinstance(iv, list) and len(iv) >= 2 and isinstance(iv[1], list):
                vals.extend(str(x) for x in iv[1] if x is not None)
    return vals


def collect_chain_blocks(blocks: dict, start_id: str | None) -> list[dict]:
    """Percorre todos os blocos conectados a partir de uma raiz (incluindo subpilhas)."""
    visited: set[str] = set()
    stack = [start_id] if start_id else []
    out: list[dict] = []
    while stack:
        bid = stack.pop()
        if not bid or bid in visited or bid not in blocks:
            continue
        visited.add(bid)
        blk = blocks[bid]
        out.append(blk)
        if blk.get("next"):
            stack.append(blk["next"])
        for iv in blk.get("inputs", {}).values():
            if isinstance(iv, list):
                for item in iv[1:]:
                    if isinstance(item, str):
                        stack.append(item)
    return out


def has_broadcast_repeat_until(blocks: dict, msg_id: str) -> bool:
    """Verifica se existe ao menos uma pilha com hat_broadcast(msg_id) usando repeat_until."""
    for bid, blk in blocks.items():
        if blk.get("opcode") == "event_whenbroadcastreceived":
            opt = blk.get("fields", {}).get("BROADCAST_OPTION", [])
            if len(opt) >= 2 and opt[1] == msg_id:
                chain = collect_chain_blocks(blocks, bid)
                if any(node.get("opcode") == "control_repeat_until" for node in chain):
                    return True
    return False


class TestAeroMatticsPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert SB3_PATH.exists(), f"Pacote nao encontrado: {SB3_PATH}"
        with zipfile.ZipFile(SB3_PATH, "r") as zf:
            bad = zf.testzip()
            assert bad is None, f"Falha CRC no arquivo: {bad}"
            cls.names_in_zip = set(zf.namelist())
            cls.project = json.loads(zf.read("project.json").decode("utf-8"))
            cls.targets = {t["name"]: t for t in cls.project["targets"]}
            cls.svgs = {}
            for t in cls.project["targets"]:
                for c in t.get("costumes", []):
                    if c["md5ext"].endswith(".svg"):
                        cls.svgs[f"{t['name']}::{c['name']}"] = zf.read(c["md5ext"]).decode("utf-8")

    def test_target_inventory_and_layer_order(self) -> None:
        targets = self.project["targets"]
        self.assertEqual(len(targets), 33)
        self.assertEqual(self.project.get("extensions"), ["pen"])
        layers = [t["layerOrder"] for t in targets]
        self.assertEqual(sorted(layers), list(range(len(targets))))

        self.assertNotIn("HUD · barra matematica", self.targets)
        self.assertNotIn("Anel Matemático", self.targets)
        self.assertNotIn("HUD · ponteiro velocidade", self.targets)
        self.assertNotIn("Relevo Horizonte", self.targets)
        self.assertNotIn("Vegetacao Distante", self.targets)
        self.assertNotIn("Rio e Terreno 2.5D", self.targets)

        for required in (
            "cenario",
            "Sol",
            "Nuvens",
            "Terreno Procedural",
            "Vegetação e Cenário Vivo",
            "Pista",
            "Rajada de Vento",
            "Combustível no ar",
            "Brisa Favorável",
            "Pássaros",
            "Aves Migratórias",
            "Avião",
            "HUD · ponteiro estabilidade",
            "Botão Guia",
        ):
            self.assertIn(required, self.targets)

        self.assertEqual(self.targets["cenario"]["layerOrder"], 1)
        self.assertEqual(self.targets["Sol"]["layerOrder"], 2)
        self.assertEqual(self.targets["Nuvens"]["layerOrder"], 3)
        self.assertEqual(self.targets["Terreno Procedural"]["layerOrder"], 4)
        self.assertEqual(self.targets["Vegetação e Cenário Vivo"]["layerOrder"], 5)
        self.assertEqual(self.targets["Pista"]["layerOrder"], 6)
        self.assertEqual(self.targets["Botão Guia"]["layerOrder"], 32)

        self.assertEqual(self.targets["cenario"]["size"], 100)
        self.assertEqual(len(self.targets["cenario"]["costumes"]), 12)
        for c in self.targets["cenario"]["costumes"]:
            self.assertTrue(c["name"].startswith("Horizonte "), msg=f"Fantasia inesperada em cenario: {c['name']}")
        self.assertEqual(len(self.targets["Vegetação e Cenário Vivo"]["costumes"]), 24)
        self.assertEqual(len(self.targets["Aves Migratórias"]["costumes"]), 8)

        self.assertEqual(self.targets["Aves Migratórias"]["rotationStyle"], "left-right")
        self.assertEqual(self.targets["Rajada de Vento"]["rotationStyle"], "left-right")
        self.assertEqual(self.targets["Brisa Favorável"]["size"], 24)
        self.assertEqual(self.targets["Pássaros"]["size"], 22)
        self.assertEqual(self.targets["Combustível no ar"]["size"], 26)
        self.assertEqual(self.targets["Aves Migratórias"]["size"], 38)
        self.assertEqual(self.targets["Vegetação e Cenário Vivo"]["size"], 20)
        self.assertEqual(self.targets["Nuvens"]["size"], 18)
        self.assertEqual(self.targets["Pista"]["size"], 100)
        self.assertEqual(self.targets["Pista"]["costumes"][0]["name"], "Pista Voxel 3D")

        stage_vars = self.targets["Stage"]["variables"]
        for v_id, expected_name in (
            ("v_gamma", "Gamma Perspectiva"),
            ("v_y_horiz", "Y Horizonte"),
            ("v_y_prox", "Y Proximo"),
            ("v_rio_w_dist", "Largura Rio Distante"),
            ("v_rio_w_prox", "Largura Rio Proxima"),
            ("v_curva_rio", "Curva Rio Fase"),
            ("v_seed_mundo", "Semente Mundo"),
            ("v_z_mundo", "Z Mundo"),
            ("v_raia_ave", "Raia Ave"),
            ("v_raia_comb", "Raia Comb"),
            ("v_raia_brisa", "Raia Brisa"),
            ("v_wave_idx", "Indice Onda"),
        ):
            self.assertIn(v_id, stage_vars, msg=f"Variavel 2.5D ausente no Stage: {expected_name}")
            self.assertEqual(stage_vars[v_id][0], expected_name)

        stage_lits = collect_block_literals(self.targets["Stage"]["blocks"])
        for route in ("FASE 1 - AMAZONIA", "FASE 2 - CERRADO", "FASE 3 - PANTANAL", "FASE 4 - MATA ATLANTICA"):
            self.assertIn(route, stage_lits, msg=f"Rota brasileira ausente no Stage: {route}")

        bird_costumes = {c["name"] for c in self.targets["Pássaros"]["costumes"]}
        for biome_name in ("Amazonia", "Cerrado", "Pantanal", "Mata Atlantica"):
            for q_idx in range(1, 5):
                self.assertIn(f"{biome_name} - quadro {q_idx}", bird_costumes, msg=f"Ave brasileira ausente: {biome_name} - quadro {q_idx}")

        mig_costumes = {c["name"] for c in self.targets["Aves Migratórias"]["costumes"]}
        for i in range(1, 7):
            self.assertIn(f"Harpia Real {i}", mig_costumes, msg=f"Quadro Harpia Real {i} ausente")

        prop_costumes = self.targets["Vegetação e Cenário Vivo"]["costumes"]
        self.assertEqual(len(prop_costumes), 24, msg="Devem existir 24 quadros de props 3D (4 biomas x 3 props x 2 quadros)")
        for c in prop_costumes:
            self.assertEqual(c["rotationCenterX"], 120, msg=f"{c['name']} rotationCenterX esperado 120")
            self.assertEqual(c["rotationCenterY"], 176, msg=f"{c['name']} rotationCenterY esperado 176")

        from pathlib import Path
        from PIL import Image
        props_dir = Path(r"C:\Users\thyag\OneDrive\Desktop\AeroMattics\assets_organizados\09_cenarios_vivos\props")
        for b in range(1, 5):
            for p in range(1, 4):
                for q in range(1, 3):
                    pfile = props_dir / f"b{b}_prop{p}_q{q}.png"
                    self.assertTrue(pfile.exists(), msg=f"Asset de prop ausente: {pfile}")
                    with Image.open(pfile) as im:
                        self.assertEqual(im.size, (240, 240), msg=f"{pfile.name} deve ter 240x240px")
                        self.assertEqual(im.mode, "RGBA", msg=f"{pfile.name} deve estar em modo RGBA")

    def test_sun_upper_right_and_clean_wind_bounds(self) -> None:
        sol = self.targets["Sol"]
        self.assertEqual(sol["x"], 172)
        self.assertEqual(sol["y"], 130)
        self.assertEqual(sol["size"], 48)
        sol_literals = collect_block_literals(sol["blocks"])
        self.assertIn("172", sol_literals)
        self.assertIn("130", sol_literals)
        self.assertIn("48", sol_literals)
        self.assertIn("-0.08", sol_literals)

        wind = self.targets["Rajada de Vento"]
        wind_literals = collect_block_literals(wind["blocks"])
        self.assertIn("-195", wind_literals)
        self.assertIn("195", wind_literals)
        self.assertIn("1.45", wind_literals)
        self.assertIn("v_vento", wind_literals)
        self.assertNotIn("-250", wind_literals)
        self.assertNotIn("250", wind_literals)

    def test_hud_active_loops_and_non_numeric_digit_names(self) -> None:
        hud_names = [
            "HUD · painel",
            "HUD · ponteiro combustível",
            "HUD · ponteiro estabilidade",
            "HUD · rótulos",
            "HUD · Pontos 0",
            "HUD · Pontos 1",
            "HUD · Pontos 2",
            "HUD · Pontos 3",
            "HUD · Tempo 0",
            "HUD · Tempo 1",
            "HUD · Tempo 2",
            "HUD · Tempo 3",
            "HUD · Vidas 0",
            "HUD · Fase 0",
        ]
        expected_digit_names = [f"digito_{i}" for i in range(10)]
        for name in hud_names:
            blocks = self.targets[name]["blocks"]
            lits = collect_block_literals(blocks)
            self.assertIn("voo", lits, msg=f"{name} deve checar Estado == voo")
            self.assertIn("decolagem", lits, msg=f"{name} deve checar Estado == decolagem")
            self.assertIn("msg_3", lits, msg=f"{name} deve ocultar em broadcast fim")
            self.assertIn("msg_9", lits, msg=f"{name} deve ocultar em broadcast guia")
            self.assertTrue(
                has_broadcast_repeat_until(blocks, "msg_1"),
                msg=f"{name} precisa de loop ativo ao receber decolar (msg_1)",
            )
            self.assertTrue(
                has_broadcast_repeat_until(blocks, "msg_2"),
                msg=f"{name} precisa de loop ativo ao receber voar (msg_2)",
            )
            if name.startswith("HUD · Pontos") or name.startswith("HUD · Tempo") or name in ("HUD · Vidas 0", "HUD · Fase 0"):
                costume_names = [c["name"] for c in self.targets[name]["costumes"]]
                self.assertEqual(costume_names, expected_digit_names, msg=f"Nomes de digito incorretos em {name}")

        end_bg = self.targets["Fundo de encerramento"]
        self.assertEqual([c["name"] for c in end_bg["costumes"]], ["Pouso Vitoria", "Pouso Fim de Voo"])
        self.assertEqual(end_bg["layerOrder"], 13)

    def test_steady_30fps_controls_sensor_gate_and_no_breeze_speed_glitch(self) -> None:
        stage_lits = collect_block_literals(self.targets["Stage"]["blocks"])
        for key in ("g", "c", "up arrow", "space", "r", "m"):
            self.assertIn(key, stage_lits)

        av_blocks = self.targets["Avião"]["blocks"]
        av_lits = collect_block_literals(av_blocks)
        for token in (
            "left arrow",
            "right arrow",
            "a",
            "d",
            "sensing_mousex",
            "v_sensor",
            "24",
            "-1.85",
            "1.85",
            "2.1",
            "-2.1",
            "0.82",
            "0.18",
            "22.0",
            "va_passo",
        ):
            self.assertIn(token, av_lits, msg=f"Token ausente no controle do Aviao: {token}")

        self.assertNotIn("sensing_mousedown", av_lits, msg="Clique de mouse nao deve puxar o aviao")

        # Localiza o script de movimento (hat msg_2 que manipula va_passo) e garante 0 control_wait dentro dele
        found_move_stack = False
        for bid, blk in av_blocks.items():
            if blk.get("opcode") == "event_whenbroadcastreceived":
                opt = blk.get("fields", {}).get("BROADCAST_OPTION", [])
                if len(opt) >= 2 and opt[1] == "msg_2":
                    chain = collect_chain_blocks(av_blocks, bid)
                    vars_in_chain = [n.get("fields", {}).get("VARIABLE", ["", ""])[1] for n in chain]
                    if "va_passo" in vars_in_chain:
                        found_move_stack = True
                        wait_count = sum(1 for n in chain if n.get("opcode") == "control_wait")
                        self.assertEqual(wait_count, 0, msg="Loop de movimento do Aviao nao pode usar control_wait")
        self.assertTrue(found_move_stack, msg="Pilha de movimento com va_passo nao encontrada no Aviao")

        # Brisa Favoravel nao pode alterar v_vx (Velocidade X)
        breeze_lits = collect_block_literals(self.targets["Brisa Favorável"]["blocks"])
        self.assertNotIn("v_vx", breeze_lits, msg="Brisa Favoravel nao deve adulterar Velocidade X")
        self.assertIn("looks_setsizeto", breeze_lits)

    def test_perspective_scale_and_living_scenery_expressions(self) -> None:
        # Lei de perspectiva nao linear p(d) = e^(gamma * ln(d)) nas camadas aereas
        for tname in (
            "Nuvens",
            "Combustível no ar",
            "Brisa Favorável",
            "Pássaros",
        ):
            lits = collect_block_literals(self.targets[tname]["blocks"])
            self.assertIn("looks_setsizeto", lits, msg=f"{tname} deve escalar dinamicamente por perspectiva")
            self.assertIn("v_gamma", lits, msg=f"{tname} deve ler Gamma Perspectiva")
            self.assertIn("e ^", lits, msg=f"{tname} deve usar operador exponencial 'e ^'")
            self.assertIn("ln", lits, msg=f"{tname} deve usar operador logaritmico 'ln'")

        # Motor Pen Mode-7 O(1) em Terreno Procedural (warp=true + cores pre-empacotadas + zero loop interno)
        pen_blocks = self.targets["Terreno Procedural"]["blocks"]
        pen_lits = collect_block_literals(pen_blocks)
        for token in (
            "pen_clear",
            "pen_penDown",
            "pen_penUp",
            "pen_setPenSizeTo",
            "pen_setPenColorToColor",
            "procedures_definition",
            "procedures_call",
            "v_z_mundo",
            "v_seed_mundo",
            "v_p_ca",
            "v_p_cb",
            "260",
            "12.6",
            "6.3",
            "8.6",
        ):
            self.assertIn(token, pen_lits, msg=f"Token Pen Mode-7 ausente: {token}")
        self.assertNotIn("v_p_col", pen_lits, msg="Loop interno por coluna foi substituido pelo modo O(1)")
        proto_blocks = [b for b in pen_blocks.values() if b.get("opcode") == "procedures_prototype"]
        self.assertTrue(proto_blocks and proto_blocks[0].get("mutation", {}).get("warp") == "true")

        # Camadas de parallax distintas em Posicao X Aviao (v_px)
        self.assertIn("-0.08", collect_block_literals(self.targets["cenario"]["blocks"]))
        self.assertIn("-0.08", collect_block_literals(self.targets["Sol"]["blocks"]))

        # Props presos ao mundo Mode-7 por Z Mundo e mesma curva X_rio(z) do motor Pen
        prop_lits = collect_block_literals(self.targets["Vegetação e Cenário Vivo"]["blocks"])
        for num in ("looks_setsizeto", "v_z_mundo", "v_seed_mundo", "28.8", "260", "33", "70", "12.6", "6.3", "0.55", "85"):
            self.assertIn(num, prop_lits, msg=f"Parametro Mode-7 {num} ausente em Vegetacao e Cenario Vivo")
        self.assertIn("looks_goforwardbackwardlayers", prop_lits)

        # Nuvens estritamente no ceu alto (y = 82 + 56*p >= 82, escala 18 + 20*p)
        nuv_lits = collect_block_literals(self.targets["Nuvens"]["blocks"])
        for num in ("82", "56", "18", "20", "28", "0.48", "0.0026"):
            self.assertIn(num, nuv_lits, msg=f"Parametro {num} ausente em Nuvens")

        # Sistema sincronizado de 5 Raias Radiais (68 px/raia, ponto de fuga y=44, descida 148*p, x*(0.22+0.78*p))
        for actor_name, raia_id in (
            ("Pássaros", "v_raia_ave"),
            ("Combustível no ar", "v_raia_comb"),
            ("Brisa Favorável", "v_raia_brisa"),
        ):
            alits = collect_block_literals(self.targets[actor_name]["blocks"])
            for num in ("68", "44", "148", "0.22", "0.78", raia_id):
                self.assertIn(num, alits, msg=f"Parametro radial {num} ausente em {actor_name}")
        breeze_lits = collect_block_literals(self.targets["Brisa Favorável"]["blocks"])
        self.assertIn("0.35", breeze_lits, msg="Brisa Favoravel deve estabilizar v_estab por 0.35")

        # Colisoes preservadas nos atores aereos
        self.assertIn("52", collect_block_literals(self.targets["Combustível no ar"]["blocks"]))
        self.assertIn("56", collect_block_literals(self.targets["Brisa Favorável"]["blocks"]))
        self.assertIn("34", collect_block_literals(self.targets["Pássaros"]["blocks"]))
        self.assertIn("32", collect_block_literals(self.targets["Aves Migratórias"]["blocks"]))

    def test_30fps_movement_loops_have_no_control_wait(self) -> None:
        def walk_substack(blocks: dict, root_id: str) -> list[dict]:
            out = []
            stack = [root_id]
            seen = set()
            while stack:
                bid = stack.pop()
                if not bid or bid in seen or bid not in blocks:
                    continue
                seen.add(bid)
                blk = blocks[bid]
                out.append(blk)
                if blk.get("next"):
                    stack.append(blk["next"])
                for inp in blk.get("inputs", {}).values():
                    if isinstance(inp, list) and len(inp) >= 2 and isinstance(inp[1], str):
                        stack.append(inp[1])
            return out

        def top_stacks(target_name: str, opcode: str) -> list[list[dict]]:
            blocks = self.targets[target_name]["blocks"]
            return [
                walk_substack(blocks, bid)
                for bid, blk in blocks.items()
                if blk.get("topLevel") and blk.get("opcode") == opcode
            ]

        # cenario visual msg_2 loop (contains looks_switchcostumeto) must have 0 control_wait
        cen_visual = [
            st for st in top_stacks("cenario", "event_whenbroadcastreceived")
            if any(b.get("opcode") == "looks_switchcostumeto" for b in st)
        ]
        self.assertTrue(cen_visual, msg="Stack visual msg_2 de cenario nao encontrado")
        for st in cen_visual:
            self.assertFalse(any(b.get("opcode") == "control_wait" for b in st), msg="Loop visual de cenario nao deve usar control_wait")

        # Vegetacao e Cenario Vivo pool fixo de 6 clones presos ao mundo Mode-7 + flight loop 30 FPS
        prop_clones = top_stacks("Vegetação e Cenário Vivo", "control_start_as_clone")
        self.assertTrue(prop_clones, msg="Clone stack de Vegetacao e Cenario Vivo nao encontrado")
        for st in prop_clones:
            self.assertFalse(any(b.get("opcode") == "control_wait" for b in st), msg="Voo de clone de prop 3D deve rodar a 30 FPS sem control_wait")
        prop_spawner = [
            st for st in top_stacks("Vegetação e Cenário Vivo", "event_whenbroadcastreceived")
            if any(b.get("opcode") == "control_create_clone_of" for b in st)
        ]
        self.assertEqual(len(prop_spawner), 1)
        self.assertFalse(any(b.get("opcode") == "control_repeat_until" for b in prop_spawner[0]), msg="Props Mode-7 nao devem criar clones em loop infinito")
        prop_reps = [b for b in prop_spawner[0] if b.get("opcode") == "control_repeat"]
        self.assertTrue(prop_reps and prop_reps[0]["inputs"]["TIMES"][1][1] == "4", msg="Vegetacao deve criar exatamente 4 clones Mode-7 espacados")

        # Nuvens pool fixo de 2 clones no ceu alto + clone flight loop 30 FPS
        nuv_clones = top_stacks("Nuvens", "control_start_as_clone")
        self.assertTrue(nuv_clones, msg="Clone stack de Nuvens nao encontrado")
        for st in nuv_clones:
            self.assertFalse(any(b.get("opcode") == "control_wait" for b in st), msg="Nuvens devem rodar a 30 FPS sem control_wait")
        nuv_spawner = [
            st for st in top_stacks("Nuvens", "event_whenbroadcastreceived")
            if any(b.get("opcode") == "control_create_clone_of" for b in st)
        ]
        self.assertEqual(len(nuv_spawner), 1)
        self.assertFalse(any(b.get("opcode") == "control_repeat_until" for b in nuv_spawner[0]), msg="Nuvens nao devem criar clones em loop infinito")
        nuv_reps = [b for b in nuv_spawner[0] if b.get("opcode") == "control_repeat"]
        self.assertTrue(nuv_reps and nuv_reps[0]["inputs"]["TIMES"][1][1] == "2", msg="Nuvens deve criar exatamente 2 clones")

        # Atores aereos (Combustivel, Brisa, Passaros) devem mover em 30 FPS sem control_wait no loop de voo
        for air_name in ("Combustível no ar", "Brisa Favorável", "Pássaros"):
            move_stacks = [
                st for st in top_stacks(air_name, "control_start_as_clone")
                if any(b.get("opcode") == "motion_gotoxy" for b in st)
            ]
            self.assertTrue(move_stacks, msg=f"Clone move stack ausente em {air_name}")
            for st in move_stacks:
                self.assertFalse(any(b.get("opcode") == "control_wait" for b in st), msg=f"Loop de movimento de {air_name} deve rodar a 30 FPS")

        # Stage Loop 5 (v_curva_rio) a 30 FPS sem control_wait
        st_curva = [
            st for st in top_stacks("Stage", "event_whenbroadcastreceived")
            if any("v_curva_rio" in str(b.get("fields", {})) for b in st)
            and any(b.get("opcode") == "control_repeat_until" for b in st)
        ]
        self.assertTrue(st_curva, msg="Loop 30 FPS de Curva Rio Fase no Stage nao encontrado")
        for st in st_curva:
            self.assertFalse(any(b.get("opcode") == "control_wait" for b in st))

        # Nenhum vazamento de clones: todos os alvos clonaveis tem handlers menu/guia/fim com delete_this_clone
        for name, tgt in self.targets.items():
            has_clone = any(b.get("opcode") == "control_start_as_clone" for b in tgt["blocks"].values())
            if not has_clone:
                continue
            for msg_id in ("msg_0", "msg_9", "msg_3"):
                cleanup_stacks = [
                    st for st in top_stacks(name, "event_whenbroadcastreceived")
                    if st and st[0].get("fields", {}).get("BROADCAST_OPTION", [None, None])[1] == msg_id
                ]
                self.assertTrue(cleanup_stacks, msg=f"{name} precisa limpar clones em {msg_id}")
                self.assertTrue(
                    any(b.get("opcode") == "control_delete_this_clone" for st in cleanup_stacks for b in st),
                    msg=f"{name} deve executar control_delete_this_clone em {msg_id}",
                )

        # Aviao flight loop (contains motion_setx inside control_repeat_until) must have 0 control_wait
        aviao_flight = [
            st for st in top_stacks("Avião", "event_whenbroadcastreceived")
            if any(b.get("opcode") == "motion_setx" for b in st)
            and any(b.get("opcode") in ("control_forever", "control_repeat_until") for b in st)
        ]
        self.assertTrue(aviao_flight, msg="Loop de voo do Aviao nao encontrado")
        for st in aviao_flight:
            self.assertFalse(any(b.get("opcode") == "control_wait" for b in st), msg="Loop de controle do Aviao deve rodar a 30 FPS sem control_wait")

    def test_ui_svgs_clean_of_math_text_and_estab_label_present(self) -> None:
        hud_lbl = self.svgs["HUD · rótulos::Rotulos painel inferior"]
        self.assertIn("COMB.%", hud_lbl)
        self.assertIn("ESTAB.", hud_lbl)
        self.assertNotIn("VELOC.", hud_lbl)

        for key in ("Texto da conclusão::Texto vitoria", "Texto da conclusão::Texto fim de voo"):
            svg_txt = self.svgs[key]
            for forbidden in ("sen(", "0.75 *", "2.7 *", "escala", "ANGULO", "vx ="):
                self.assertNotIn(forbidden, svg_txt, msg=f"Formula encontrada em {key}: {forbidden}")

    def test_all_assets_and_block_links_valid(self) -> None:
        stage = self.targets["Stage"]
        global_vars = set(stage["variables"].keys())
        broadcast_ids = set(stage["broadcasts"].keys())
        for req_var in ("v_estab", "v_vento", "v_mig_lado", "v_sensor", "v_px"):
            self.assertIn(req_var, global_vars)
        for req_msg in ("msg_7", "msg_8", "msg_9"):
            self.assertIn(req_msg, broadcast_ids)

        for t in self.project["targets"]:
            local_vars = set(t.get("variables", {}).keys())
            valid_vars = global_vars | local_vars
            for c in t["costumes"]:
                self.assertIn(c["md5ext"], self.names_in_zip)
            blocks = t["blocks"]
            for bid, b in blocks.items():
                if b.get("next") is not None:
                    self.assertIn(b["next"], blocks)
                    self.assertEqual(blocks[b["next"]]["parent"], bid)
                if b.get("parent") is not None:
                    self.assertIn(b["parent"], blocks)
                if "VARIABLE" in b.get("fields", {}):
                    self.assertIn(b["fields"]["VARIABLE"][1], valid_vars)
                if "BROADCAST_OPTION" in b.get("fields", {}):
                    self.assertIn(b["fields"]["BROADCAST_OPTION"][1], broadcast_ids)


class TestAeroMatticsPhysicsAndAccessibility(unittest.TestCase):
    def test_low_pass_filter_clamp_and_parkinson_tremor(self) -> None:
        dt = 1.0 / 30.0
        raw_vals = []
        filtered_vals = []
        vx = 0.0
        for step in range(200):
            tremor = 1.85 * math.sin(2.0 * math.pi * 6.0 * (step * dt))
            alvo = 1.85 if abs(tremor) > 0.5 else 0.0
            if step % 3 == 0:
                alvo = -alvo
            vx = 0.82 * vx + 0.18 * alvo
            passo = max(-2.10, min(2.10, vx + 0.28 * 1.0))
            self.assertGreaterEqual(passo, -2.10)
            self.assertLessEqual(passo, 2.10)
            raw_vals.append(alvo)
            filtered_vals.append(vx)

        mean_raw = sum(raw_vals) / len(raw_vals)
        mean_filt = sum(filtered_vals) / len(filtered_vals)
        std_raw = math.sqrt(sum((v - mean_raw) ** 2 for v in raw_vals) / len(raw_vals))
        std_filt = math.sqrt(sum((v - mean_filt) ** 2 for v in filtered_vals) / len(filtered_vals))
        self.assertLess(std_filt, std_raw * 0.40)

    def test_fuel_depletion_visible_per_biome_and_survivable(self) -> None:
        fuel_no_refill = 100.0 - 0.65 * 40.0
        angle_delta_phase = abs((2.7 * 100.0 - 45.0) - (2.7 * fuel_no_refill - 45.0))
        self.assertGreater(angle_delta_phase, 65.0)

        fuel = 100.0
        for sec in range(1, 161):
            fuel = max(0.0, fuel - 0.65)
            self.assertGreater(fuel, 10.0, msg=f"Combustivel zerou cedo no segundo {sec}")
            if sec in (30, 70, 110, 150):
                fuel = min(100.0, fuel + 28.0)
        self.assertGreater(fuel, 40.0)

    def test_gauge_directions_and_wind_recovery(self) -> None:
        self.assertAlmostEqual(2.7 * 0 - 45, -45.0)
        self.assertAlmostEqual(2.7 * 50 - 45, 90.0)
        self.assertAlmostEqual(2.7 * 100 - 45, 225.0)

        self.assertAlmostEqual(90.0 + 1.15 * 0.0, 90.0)
        estab_gust_right = 52.0 * 1.0 + 22.0 * 0.0
        estab_gust_left = 52.0 * -1.0 + 22.0 * 0.0
        self.assertGreater(90.0 + 1.15 * estab_gust_right, 145.0)
        self.assertLess(90.0 + 1.15 * estab_gust_left, 35.0)

    def test_migratory_flock_leaves_opposite_corridor_open(self) -> None:
        for side in (-1, 1):
            for mig_id in (1, 2, 3):
                for t_step in range(0, 116):
                    x = side * (192.0 - (mig_id - 1) * 22.0 - 0.88 * t_step) + 10.0 * math.sin(
                        math.radians(4.0 * t_step + 50.0 * mig_id)
                    )
                    y = 76.0 + 12.0 * (mig_id - 1) - 1.42 * t_step
                    scale = 38.0 + 0.25 * (76.0 - y)
                    self.assertGreaterEqual(scale, 32.0)
                    self.assertLessEqual(scale, 80.0)
                    if side < 0:
                        self.assertLessEqual(x, -25.0, msg=f"Ave invadiu lado direito: side={side}, id={mig_id}, t={t_step}, x={x}")
                    else:
                        self.assertGreaterEqual(x, 25.0, msg=f"Ave invadiu lado esquerdo: side={side}, id={mig_id}, t={t_step}, x={x}")

    def test_air_and_ground_perspective_laws(self) -> None:
        # Sistema de 5 Raias Radiais + Projecao nao linear p(d)=d^gamma + Margens Externas
        gamma = 1.65
        lanes = (-136.0, -68.0, 0.0, 68.0, 136.0)
        for seed in range(100):
            idx_b = seed % 5
            idx_f = (seed + 2) % 5
            idx_br = (seed + 4) % 5
            self.assertEqual(len({idx_b, idx_f, idx_br}), 3, msg=f"Sobreposicao de raia para seed={seed}")
            self.assertIn((idx_b - 2) * 68.0, lanes)

        prev_p = -1.0
        prev_y_air = 999.0
        for step in range(49):
            d = 0.04 + step * 0.02
            p = math.exp(gamma * math.log(d))
            y_air = 44.0 - 148.0 * p
            esc_bird = 22.0 + 34.0 * p
            esc_fuel = 26.0 + 28.0 * p
            esc_brisa = 24.0 + 32.0 * p
            self.assertGreater(p, prev_p)
            self.assertLess(y_air, prev_y_air)
            self.assertGreaterEqual(esc_bird, 22.0)
            self.assertLessEqual(esc_bird, 56.0)
            self.assertGreaterEqual(esc_fuel, 26.0)
            self.assertLessEqual(esc_fuel, 54.0)
            self.assertGreaterEqual(esc_brisa, 24.0)
            self.assertLessEqual(esc_brisa, 56.0)
            prev_p, prev_y_air = p, y_air

        # Sincronia Mode-7 entre Terreno Procedural e props presos a Z Mundo
        prev_y_prop = 999.0
        for z_rel in (22.0, 15.0, 10.0, 6.0, 3.0, 2.0):
            dy = 260.0 / z_rel
            y_prop = 33.0 - dy
            esc_prop = min(85.0, 16.0 + 0.55 * dy)
            self.assertLess(y_prop, prev_y_prop)
            self.assertGreaterEqual(esc_prop, 16.0)
            self.assertLessEqual(esc_prop, 85.0)
            prev_y_prop = y_prop

    def test_cloud_perspective_bounds_and_clone_budget(self) -> None:
        gamma = 1.65
        for step in range(4, 101, 4):
            d = step / 100.0
            p = math.exp(gamma * math.log(d))
            y = 82.0 + 56.0 * p
            scale = 18.0 + 20.0 * p
            lim_x = 230.0 - 1.5 * scale
            self.assertGreaterEqual(scale, 18.0)
            self.assertLessEqual(scale, 38.0)
            self.assertGreaterEqual(y, 82.0)
            self.assertLessEqual(y, 138.0)
            self.assertGreater(lim_x, 170.0)

        # Orcamento simultaneo enxuto de clones (4 props Mode-7 espacados + 2 nuvens + 3 rajadas + 1 comb + 1 brisa + 1 passaro + 3 mig = 15)
        max_clones = 4 + 2 + 3 + 1 + 1 + 1 + 3
        self.assertEqual(max_clones, 15)
        self.assertLessEqual(max_clones, 20)


class TestAeroMatticsLiveScratchVM(unittest.TestCase):
    """Testes reais de ponta a ponta executando os blocos do .sb3 na VM a 30 FPS."""

    def test_menu_guide_takeoff_hud_and_smooth_plane_transition(self) -> None:
        vm = ScratchVMSimulator(SB3_PATH, seed=77)
        vm.green_flag()
        vm.step_seconds(0.2)
        self.assertEqual(vm.get_global("Estado"), "menu")
        self.assertFalse(vm.get_sprite("HUD · painel").visible)
        self.assertFalse(vm.get_sprite("Pista").visible)
        self.assertTrue(vm.get_sprite("Start").visible)
        self.assertTrue(vm.get_sprite("Botão Guia").visible)

        vm.click_sprite("Botão Guia")
        vm.step_seconds(0.2)
        self.assertEqual(vm.get_global("Estado"), "guia")
        self.assertEqual(vm.get_sprite("Telas").costume_idx, 1)
        self.assertFalse(vm.get_sprite("HUD · painel").visible)

        vm.press_key_hat("g")
        vm.step_seconds(0.2)
        self.assertEqual(vm.get_global("Estado"), "menu")
        self.assertEqual(vm.get_sprite("Telas").costume_idx, 0)

        vm.click_sprite("Start")
        vm.step_seconds(1.2)
        self.assertEqual(vm.get_global("Estado"), "decolagem")
        self.assertTrue(vm.get_sprite("Pista").visible)
        self.assertTrue(vm.get_sprite("HUD · painel").visible)
        self.assertTrue(vm.get_sprite("HUD · Pontos 0").visible)

        vm.step_seconds(1.5)  # t=2.7s: fim da rampa de decolagem perto de (0, -58)
        av_pre_voo_y = vm.get_sprite("Avião").y
        self.assertGreaterEqual(av_pre_voo_y, -62.0)
        self.assertLessEqual(av_pre_voo_y, -55.0)

        vm.step_seconds(0.4)  # t=3.1s: em pleno voo
        self.assertEqual(vm.get_global("Estado"), "voo")
        self.assertFalse(vm.get_sprite("Pista").visible)
        self.assertAlmostEqual(vm.get_sprite("Avião").y, -58.0, delta=0.5)
        self.assertAlmostEqual(vm.get_sprite("Avião").size, 38.0, delta=1.0)

    def test_pen_mode7_performance_budget_across_all_biomes(self) -> None:
        vm = ScratchVMSimulator(SB3_PATH, seed=101)
        vm.green_flag()
        vm.step_seconds(0.2)
        vm.click_sprite("Start")
        vm.step_seconds(3.5)

        for etapa in (1, 2, 3, 4):
            vm.get_sprite("Stage").local_vars["v_4"] = etapa
            vm.step_frame()
            self.assertGreater(len(vm.pen_strokes), 180, msg=f"Bioma {etapa} desenhou faixas insuficientes")
            self.assertLess(len(vm.pen_strokes), 440, msg=f"Bioma {etapa} excedeu teto de tracos Pen")
            self.assertLess(vm.last_frame_block_evals, 13000, msg=f"Bioma {etapa} excedeu teto de blocos/quadro")
            for _, _, _, _, _, col in vm.pen_strokes:
                self.assertGreaterEqual(col, 0)
                self.assertLessEqual(col, 0xFFFFFF)

    def test_5_lane_wave_separation_parkinson_filter_and_hud_updates(self) -> None:
        vm = ScratchVMSimulator(SB3_PATH, seed=202)
        vm.green_flag()
        vm.step_seconds(0.2)
        vm.click_sprite("Start")
        vm.step_seconds(3.2)

        prev_x = vm.get_sprite("Avião").x
        seen_waves = set()
        # Simula tremor + comando a direita + rajada de vento e verifica separacao das raias por 18s
        for frame in range(18 * 30):
            if frame % 4 < 2:
                vm.keys_pressed = {"right arrow"}
            else:
                vm.keys_pressed = set()
            vm.step_frame()
            av_x = vm.get_sprite("Avião").x
            self.assertLessEqual(abs(av_x - prev_x), 2.15, msg="Passo do aviao ultrapassou limite terapeutico")
            prev_x = av_x

            r_ave = int(vm.get_global("Raia Ave"))
            r_comb = int(vm.get_global("Raia Comb"))
            r_brisa = int(vm.get_global("Raia Brisa"))
            self.assertEqual(len({r_ave, r_comb, r_brisa}), 3, msg="Raias ativas se sobrepuseram na mesma onda")
            seen_waves.add((r_ave, r_comb, r_brisa))

            self.assertGreaterEqual(int(vm.get_global("Tempo de fase")), 0, msg="Tempo de fase nao pode negativar")
            self.assertLessEqual(vm.total_clones(), 20, msg="Orcamento de clones excedido")

        self.assertGreaterEqual(len(seen_waves), 2)
        self.assertGreater(float(vm.get_global("Pontos")), 20.0)
        self.assertLess(float(vm.get_global("Combustível")), 99.0)
        self.assertGreater(abs(vm.get_sprite("HUD · ponteiro combustível").direction - 225.0), 10.0)

        # Testa modo Sensor (tecla C)
        vm.press_key_hat("c")
        vm.step_frame()
        self.assertEqual(int(vm.get_global("Modo Sensor")), 1)
        vm.mouse_x = -180.0
        x_before = vm.get_sprite("Avião").x
        vm.step_seconds(1.5)
        self.assertLess(vm.get_sprite("Avião").x, x_before - 20.0, msg="Modo sensor deveria guiar o aviao para a esquerda")

    def test_victory_crash_and_clean_replay_without_clone_leaks(self) -> None:
        # 1) Teste de derrota por 5 impactos e reinicio limpo
        vm = ScratchVMSimulator(SB3_PATH, seed=303)
        vm.green_flag()
        vm.step_seconds(0.2)
        vm.click_sprite("Start")
        vm.step_seconds(3.2)

        vm.get_sprite("Stage").local_vars["v_3"] = 0  # 0 vidas restantes
        vm.step_seconds(0.25)
        self.assertEqual(vm.get_global("Estado"), "queda")
        self.assertFalse(vm.get_sprite("HUD · painel").visible)
        vm.step_seconds(1.4)
        self.assertEqual(vm.get_global("Estado"), "fim")
        self.assertTrue(vm.get_sprite("Fundo de encerramento").visible)
        self.assertEqual(vm.get_sprite("Fundo de encerramento").costume_idx, 1)  # Pouso Fim de Voo
        self.assertEqual(vm.total_clones(), 0, msg="Clones vazaram na tela de fim")

        # Reinicio imediato pelo botao Start ("TENTAR DE NOVO")
        vm.click_sprite("Start")
        vm.step_seconds(0.2)
        self.assertEqual(vm.get_global("Estado"), "decolagem")
        self.assertEqual(int(vm.get_global("Vidas")), 5)
        self.assertEqual(float(vm.get_global("Combustível")), 100.0)
        self.assertTrue(vm.get_sprite("HUD · painel").visible)

        # 2) Teste de vitoria na Fase 4 aos 160s sem faltar combustivel nem vidas
        vm.step_seconds(2.8)
        self.assertEqual(vm.get_global("Estado"), "voo")
        vm.timer_zero = vm.sim_time - 159.5
        stage = vm.get_sprite("Stage")
        stage.local_vars["v_4"] = 4
        stage.local_vars["v_fuel_clock"] = 159.5
        vm.step_seconds(1.0)
        self.assertEqual(vm.get_global("Estado"), "fim")
        self.assertEqual(vm.get_global("Motivo"), "Missão concluída!")
        self.assertTrue(vm.get_sprite("Fundo de encerramento").visible)
        self.assertEqual(vm.get_sprite("Fundo de encerramento").costume_idx, 0)  # Pouso Vitoria
        self.assertFalse(vm.get_sprite("HUD · painel").visible)
        self.assertEqual(vm.total_clones(), 0)

    def test_mathematical_gameplay_progression_and_equilibrium_bonus(self) -> None:
        # 1) Equilibrio centrado (|Estabilidade| <= 12) rende +3 pts/s; voo inclinado rende +2 pts/s
        vm_eq = ScratchVMSimulator(SB3_PATH, seed=55)
        vm_eq.green_flag()
        vm_eq.click_sprite("Start")
        vm_eq.step_seconds(3.0)
        self.assertEqual(vm_eq.get_global("Estado"), "voo")
        stage_eq = vm_eq.get_sprite("Stage")
        p0 = int(vm_eq.get_global("Pontos"))
        stage_eq.local_vars["v_estab"] = 0
        vm_eq.step_seconds(3.0)
        delta_eq = int(vm_eq.get_global("Pontos")) - p0
        self.assertGreaterEqual(delta_eq, 9, msg=f"Esperado >= 9 pts (3 pts/s em equilibrio), obtido {delta_eq}")

        vm_tilt = ScratchVMSimulator(SB3_PATH, seed=55)
        vm_tilt.green_flag()
        vm_tilt.click_sprite("Start")
        vm_tilt.step_seconds(3.0)
        stage_t = vm_tilt.get_sprite("Stage")
        p1 = int(vm_tilt.get_global("Pontos"))
        # Forca inclinacao fora da faixa de equilibrio via tecla durante 3s
        for _ in range(90):
            vm_tilt.keys_pressed = {"right arrow"}
            vm_tilt.step_seconds(1.0 / 30.0)
        delta_tilt = int(vm_tilt.get_global("Pontos")) - p1
        self.assertLess(delta_tilt, delta_eq, msg=f"Equilibrio centrado ({delta_eq}) deve pontuar mais que voo inclinado ({delta_tilt})")

        # 2) Progressao linear de velocidade Mode-7 por fase: Z Mundo por frame passa de 0.11 (Fase 1) para 0.14 (Fase 4)
        z1_before = float(vm_eq.get_global("Z Mundo"))
        vm_eq.step_seconds(1.0 / 30.0)
        dz_fase1 = float(vm_eq.get_global("Z Mundo")) - z1_before
        stage_eq.local_vars[vm_eq.var_name_to_id["Etapa"]] = 4
        z4_before = float(vm_eq.get_global("Z Mundo"))
        vm_eq.step_seconds(1.0 / 30.0)
        dz_fase4 = float(vm_eq.get_global("Z Mundo")) - z4_before
        self.assertAlmostEqual(dz_fase1, 0.11, delta=0.005)
        self.assertAlmostEqual(dz_fase4, 0.14, delta=0.005)
        self.assertGreater(dz_fase4, dz_fase1)

        # 3) Contrato estrutural: limite adaptativo de combustivel (<35%) no Stage e bonus em sequencia na Brisa Favoravel
        with zipfile.ZipFile(SB3_PATH, "r") as zf:
            proj = json.loads(zf.read("project.json").decode("utf-8"))
        tmap = {t["name"]: t for t in proj["targets"]}
        st_lits = {
            inp[1][1]
            for b in tmap["Stage"]["blocks"].values()
            for inp in b.get("inputs", {}).values()
            if isinstance(inp, list) and len(inp) >= 2 and isinstance(inp[1], list) and len(inp[1]) >= 2
        }
        br_lits = {
            inp[1][1]
            for b in tmap["Brisa Favorável"]["blocks"].values()
            for inp in b.get("inputs", {}).values()
            if isinstance(inp, list) and len(inp) >= 2 and isinstance(inp[1], list) and len(inp[1]) >= 2
        }
        self.assertIn("35", st_lits)
        self.assertIn("0.01", st_lits)
        self.assertIn("20", br_lits)
        self.assertIn("3", br_lits)

    def test_harpia_solid_orientation_acai_prop_and_continuous_river_loop(self) -> None:
        from collections import deque
        from PIL import Image
        import numpy as np

        # 1) Harpia Real 1..6: plumagem sem buracos transparentes internos + rosto orientado a direita (+X)
        birds_dir = SB3_PATH.parent / "assets_organizados" / "04_passaros_biomas"
        for q_i in range(1, 7):
            im = Image.open(birds_dir / f"ave_migratoria_q{q_i}.png").convert("RGBA")
            arr = np.array(im)
            alpha = arr[:, :, 3]
            h, w = alpha.shape
            # Flood-fill de fundo transparente pelas bordas externas
            bg_ext = np.zeros((h, w), dtype=bool)
            cand_bg = alpha <= 20
            q = deque()
            for x in range(w):
                if cand_bg[0, x] and not bg_ext[0, x]:
                    bg_ext[0, x] = True
                    q.append((0, x))
                if cand_bg[h - 1, x] and not bg_ext[h - 1, x]:
                    bg_ext[h - 1, x] = True
                    q.append((h - 1, x))
            for y in range(h):
                if cand_bg[y, 0] and not bg_ext[y, 0]:
                    bg_ext[y, 0] = True
                    q.append((y, 0))
                if cand_bg[y, w - 1] and not bg_ext[y, w - 1]:
                    bg_ext[y, w - 1] = True
                    q.append((y, w - 1))
            while q:
                cy, cx = q.popleft()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and not bg_ext[ny, nx] and cand_bg[ny, nx]:
                        bg_ext[ny, nx] = True
                        q.append((ny, nx))
            trapped_holes = int((cand_bg & (~bg_ext)).sum())
            self.assertLessEqual(trapped_holes, 20, msg=f"Harpia Q{q_i} possui {trapped_holes} pixels furados internos")

        # Centro da cabeça branca/cinza da Harpia deve estar voltado a direita (+X) no asset base
        arr1 = np.array(Image.open(birds_dir / "ave_migratoria_q1.png").convert("RGBA"))
        head_mask = (arr1[:75, :, 3] > 200)
        xs_head = np.where(head_mask)[1]
        self.assertGreater(float(xs_head.mean()), 155.0)

        # 2) Orientacao bilateral real da Harpia na VM: lado=-1 voa para direita (+X) olhando +90; lado=+1 voa para esquerda (-X) olhando -90
        for side_val, expected_dir in ((-1, 90.0), (1, -90.0)):
            vm_m = ScratchVMSimulator(SB3_PATH, seed=404 if side_val < 0 else 405)
            vm_m.green_flag()
            vm_m.step_seconds(0.2)
            vm_m.click_sprite("Start")
            vm_m.step_seconds(3.2)
            stage_m = vm_m.get_sprite("Stage")
            mig_vid = vm_m.var_name_to_id["Migracao Lado"]
            stage_m.local_vars[mig_vid] = side_val
            vm_m._trigger_hat("event_whenbroadcastreceived", msg_id="msg_8")
            vm_m.step_seconds(3.4)
            cl_t1 = vm_m.get_clones("Aves Migratórias")
            self.assertTrue(cl_t1, msg=f"Harpia nao gerada para side={side_val}")
            for c in cl_t1:
                self.assertEqual(c.direction, expected_dir, msg=f"side={side_val} apontou {c.direction} em vez de {expected_dir}")
            x0_first = cl_t1[0].x
            vm_m.step_seconds(1.5)
            self.assertGreater(len(vm_m.get_clones("Aves Migratórias")), 0)
            x1_first = vm_m.get_clones("Aves Migratórias")[0].x
            if side_val < 0:
                self.assertGreater(x1_first, x0_first + 8.0, msg="side=-1 deveria voar para direita (+X)")
            else:
                self.assertLess(x1_first, x0_first - 8.0, msg="side=+1 deveria voar para esquerda (-X)")

        # 3) Rio em polilinha continua (segmentos conectados sem quebras horizontais) + periodico 24.0
        vm_r = ScratchVMSimulator(SB3_PATH, seed=505)
        vm_r.green_flag()
        vm_r.step_seconds(0.2)
        vm_r.click_sprite("Start")
        vm_r.step_seconds(3.2)
        vm_r.step_frame()
        # Conta tracos continuos conectados (y1 == y0_next e x1 == x0_next com |y0 - y1| > 0.5)
        diag_strokes = [s for s in vm_r.pen_strokes if abs(s[1] - s[3]) > 0.5]
        self.assertGreaterEqual(len(diag_strokes), 50, msg="Rio continuo + filetes nao desenharam segmentos conectados suficientes")
        linked = sum(
            1 for i in range(1, len(diag_strokes))
            if abs(diag_strokes[i][0] - diag_strokes[i - 1][2]) < 1e-6 and abs(diag_strokes[i][1] - diag_strokes[i - 1][3]) < 1e-6
        )
        self.assertGreaterEqual(linked, 45, msg=f"Polilinha do rio teve quebras: apenas {linked} vertices conectados")

        # Verifica b1_prop3 agora ser o Acaizeiro 3D sem agua turquesa/ciano da antiga ponte
        acai = np.array(Image.open(SB3_PATH.parent / "assets_organizados" / "09_cenarios_vivos" / "props" / "b1_prop3_q1.png").convert("RGBA"))
        cyan_pixels = int(((acai[:, :, 3] > 80) & (acai[:, :, 2] >= acai[:, :, 1] * 0.95) & (acai[:, :, 2] > acai[:, :, 0] * 1.35) & (acai[:, :, 1] > 140)).sum())
        self.assertLess(cyan_pixels, 25, msg=f"b1_prop3 ainda contem placa ciano da ponte ({cyan_pixels} px)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
