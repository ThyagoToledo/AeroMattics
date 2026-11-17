# Documentacao Tecnica - Mundo Procedural 2.5D, Motor Mode-7 e Gameplay Matematica

**Projeto:** AeroMattics (`AeroMattics_MIT_Parkinson.sb3`)  
**Autoria exclusiva:** ThyagoToledo  
**Configuracao validada:** `33 targets`, `166 assets`, `23,930,082 bytes`, **`20/20` testes `OK`** (`18.525 s`)

---

## 1. Arquitetura Visual em 4 Camadas Sincronizadas

Para eliminar sobreposicoes confusas e garantir profundidade continua sem tremulacao ("vertigem"):

1. **Camada 1 — Horizonte Limpo e Sol Voxel (`cenario`, `Sol`)**  
   Panoramas `bioma1..4_vivo_q1..3.png` recortados com silhueta de horizonte limpa, espalhamento atmosferico e cirros altos; paralaxe suave `x = -0.08 * Posicao_X_Aviao`. O `Sol` usa blocos Voxel quadrados com 3 aneis de brilho em `(172, 130)` (`48%`, `ghost = 8`).
2. **Camada 2 — Ceu Alto (`Nuvens`)**  
   Pool enxuto de `2` clones de nuvens Voxel confinados ao topo da tela (`y = 82 + 56 * p(d)`, faixa `+82..+138`, escala `18%..38%`, `ghost = 28`), nunca bloqueando o rio ou o aviao.
3. **Camada 3 — Motor Pen Mode-7 + Marcos 3D Espacados (`Terreno Procedural` + `Vegetacao e Cenario Vivo`)**  
   Solo e rio redesenhados a `30 FPS` dentro de procedimento `warp` (`Run without screen refresh`), sincronizados ao mesmo avanco de `Z Mundo` dos `4` props laterais nas margens.
4. **Camada 4 — Raias Radiais de Jogo e Fauna Unica (`Passaros`, `Combustivel no ar`, `Brisa Favoravel`, `Aves Migratorias`, `Aviao`)**  
   Atores aereos convergem do ponto de fuga `(0, 44)` com surgimento atmosferico suave (`ghost` progressivo quando `d < 0.24`), exibindo sprites 3D Voxel exclusivos para cada bioma (`Arara-Vermelha`, `Tucano-Toco`, `Tuiuiu Pantaneiro`, `Arara-Azul`) e o bando de `Harpia Real` (`6` quadros articulados).

---

## 2. Equacoes do Motor Pen Mode-7 (`Terreno Procedural`)

A cada frame (`30 FPS`), o estagio avanca o mundo longitudinalmente de acordo com a fase atual (`Etapa` de `1` a `4`):

```
dZ_mundo(Etapa) = 0.10 + 0.01 * Etapa      (0.11 -> 0.12 -> 0.13 -> 0.14)
Curva Rio Fase  = 22 * timer()
```

Para cada linha horizontal `sy` do horizonte ao piso (`sy` de `+28` ate `-114` com largura adaptativa "fat-strip"):

```
dy          = max(2, 33 - sy)
z_rel       = 260 / dy
z_w         = Z_Mundo + z_rel
sx          = dy / 70
cam_x       = 0.45 * Posicao_X_Aviao
```

- **Eixo sinuoso do rio:**  
  `X_rio(z_w) = 42 * sin(12.6 * z_w + 63 * Etapa + 3.6 * 42) + 18 * cos(6.3 * z_w)`
- **Meia-largura e polilinha continua do rio (`18` nos conectados):**  
  - Areia / margem (`2 * (rhw + shw)`), Agua rasa turquesa (`2 * rhw`), Canal profundo (`1.60 * rhw`) tracados sem levantar o lapis (`pen_down` continuo de `sy = +29` ate `-115`), eliminando degraus e quebras horizontais.  
  - **`8` filetes de correnteza em loop periodico (`flux = mod(Z_Mundo * 2.1, 24)`):** cada filete desliza continuamente de `z_rel = 26.4` ate `2.4` seguindo o eixo curvo do rio sem saltos ou quebras de ciclo.
- **Terreno lateral calmo anti-tontura:** ondas simetricas em `4` fases (`floor(z_w * 0.56) mod 4`, contraste baixo `<= 14 RGB`), horizonte sem cintilacao (`dy < 34` com fog progressivo unico) mantendo exatos **`296` tracos/quadro** e `12.483..12.527` avaliacoes (`MAE_lum = 0.33..1.61`, `Horizon_MAE = 0.17..0.64`).

---

## 3. Sincronizacao de Props 3D e Reducao de Poluicao Visual

- **Pool enxuto de `4` clones:** distribuidos em ciclo `28.8 Z` (`7.2 Z` entre marcos sucessivos), evitando fila densa de objetos um atras do outro.
- **Ancoragem geometrica identica ao rio:** cada clone calcula `z_rel`, `dy = 260 / z_rel`, `Y = 33 - dy` e `Escala = min(85, 16 + 0.55 * dy)`, com neblina quadratica suave nas proximidades do horizonte (`z_rel > 16`).
- **Barcos exclusivos do canal central (`slot == 1`):** na Amazonia (`b1_prop2`) e no Pantanal (`b3_prop2`), barcos e chalanas aparecem exclusivamente no `slot 1` com `offset = 0` sobre `X_rio(z_w)`. Todos os demais slots ficam nas margens externas (`offset` entre `+-42` e `+-94`), com desvio extra na Fase 4.
- **Bioma 4 limpo (Mata Atlantica):** composto por `Araucaria` (`b4_prop1`), `Casarao Colonial` (`b4_prop2`) e **`Palmeira Real 3D Voxel` (`b4_prop3`)**, substituindo definitivamente a antiga cachoeira com barco.

---

## 4. Raias Radiais, Espacamento de Ondas e Matematica de Voo

As 5 raias no ar possuem ancora de tela `x0 in {-136, -68, 0, +68, +136}` sob projecao de perspectiva nao linear:

```
p(d) = d ^ 1.65                 (implementado via exp(1.65 * ln(d)), d in [0.04, 1.00])
Y(p) = 44 - 148 * p
X(p) = round(-0.10 * Px) + x0 * (0.22 + 0.78 * p)
```

- **Escalas no ar:**
  - `Passaros`: `22 + 34 * p(d)` (`d_passo = 0.0066 + 0.0005 * Etapa`)
  - `Combustivel no ar`: `26 + 28 * p(d)` (`+28%` combustivel, `+10` pts, `hitbox = 52`)
  - `Brisa Favoravel`: `24 + 32 * p(d)` (`Estabilidade -> round(0.35 * Estab)`, `+3%` combustivel, `15 + 5 * min(Brisas, 4)` pts, `hitbox = 56`)
- **Separacao modular disjunta:** para qualquer `Semente_Mundo`, `Ave`, `Combustivel` e `Brisa` ocupam `(S) mod 5`, `(S + 2) mod 5` e `(S + 4) mod 5`, respectivamente.
- **Ritmo de ondas (`Stage Loop 6`):** intervalo total de `6.2 s` (`2.0 s` + `2.0 s` + `2.2 s`) entre grupos de ondas aereas, com garantia adaptativa de combustivel sempre que `Combustivel < 35%`.
- **Contribuicao de equilibrio em pontos:** voar estabilizado (`|Estabilidade| <= 12`) garante `+3 pts/s` (`+2` base + `+1` equilibrio), contra `+2 pts/s` fora da zona de equilibrio.

---

## 5. Orcamento de Clones Simultaneos (Maximo: `15`)

| Grupo | Limite Maximo de Clones | Modo de Atualizacao |
| :--- | :--- | :--- |
| `Vegetacao e Cenario Vivo` | `4` | Ciclo fixo `28.8 Z` a `30 FPS` |
| `Nuvens` | `2` | Ciclo continuo no ceu alto a `30 FPS` |
| `Rajada de Vento` | `3` | Evento temporizado (`12 s` de cada fase, `6 s` de duracao) |
| `Combustivel no ar` | `1` | Onda controlada (`6.2 s`) + limiar `< 35%` |
| `Brisa Favoravel` | `1` | Onda alternada (`mod 2 == 1`) |
| `Passaros` | `1` | Onda por fase (`d` progressivo) |
| `Aves Migratorias` | `3` | Bando de `3` Harpias aos `25 s` de cada fase |
| **Total maximo simultaneo** | **`15`** | Muito abaixo do limite de `300` clones do Scratch |

---

## 6. Ferramentas e Praticas Recomendadas para Jogos 2.5D/3D em Scratch 3.0

1. **Compilacao programatica (`Python` + `project.json` + `zipfile`):** gera arvores de blocos verificaveis por scripts (`test_aeromattics.py`) e permite iteracao matematica rapida de formulas e custos em `30 FPS`.
2. **Linguagens que compilam para `.sb3`:** projetos como **`goboscript`** (compilador textual para `.sb3`), **`Tosh`** e **`TB3`** oferecem alternativa para estruturar codigo em arquivos de texto, mantendo portabilidade com o Scratch oficial.
3. **Execucao deterministica e TurboWarp:** blocos customizados marcados com `warp=true` (`Run without screen refresh`), evitamento de operacoes pesadas sem necessidade por pixel (agrupamento por faixas horizontais) e uso opcional do runtime JIT **TurboWarp** formam a base padrao de performance em motores 2.5D/Mode-7 na comunidade Scratch.
