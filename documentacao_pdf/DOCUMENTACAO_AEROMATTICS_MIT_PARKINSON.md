# AeroMattics - Simulacao Aerea Terapeutica e Matematica Aplicada (MIT / Parkinson)

**Autoria exclusiva:** ThyagoToledo  
**Pacote compilado:** `AeroMattics_MIT_Parkinson.sb3` (`33 targets`, `166 assets`, `23,930,082 bytes`)  
**Motor:** Scratch 3.0 programmatic build (`scripts/build_aeromattics.py`) validado a `30 FPS` em VM Scratch deterministica (`scripts/scratch_vm_sim.py`).

---

## 1. Proposito Clinico e Pedagogico

O **AeroMattics** combina estimulacao motora suave para pacientes em reabilitacao com Doenca de Parkinson (bradicinesia, rigidez e tremor postural tipico de `4 Hz` a `6 Hz`) com **modelagem matematica explicita** no funcionamento interno do jogo.

As equacoes guiam o voo, a fisica anti-tremor, o consumo energetico, o equilibrio aerodinamico e a projecao de perspectiva 2.5D sem poluir o campo visual do jogador com textos ou formulas na tela.

---

## 2. Arquitetura Matematica da Gameplay e Acessibilidade (30 FPS)

Todos os lacos de voo, controle, camera, cenario e HUD rodam de forma sincrona a `30 FPS` (sem `control_wait` dentro dos loops de movimento) e desativam o HUD fora de `decolagem` e `voo`.

### 2.1 Controle Motor com Filtro Passa-Baixa (IIR de 1a Ordem)

Para suavizar oscilacoes involuntarias de `4-6 Hz` sem gerar sensacao de atraso pesado:

```
vx(t) = 0.82 * vx(t - 1) + 0.18 * alvo(t)
Passo X = clamp(vx(t) + 0.28 * Direcao_vento, -2.10, +2.10)
```

- **Entradas aceitas:** setas esquerda/direita, teclas `A`/`D`, Makey Makey e **Modo Sensor (`C`)**, com acompanhamento suave do cursor (`mouse_x / 24`, limitado a `[-1.85, +1.85]`).
- **Amortecimento:** o ganho `alpha = 0.18` reduz em mais de `60%` o desvio padrao de sinais alternados a `6 Hz`, mantendo resposta previsivel ao comando intencional.

### 2.2 Equilibrio Matematico e Pontuacao Progressiva

O indicador `ESTAB.` calcula a inclinacao instantanea do aviao como combinacao linear entre a rajada lateral e a velocidade horizontal filtrada:

```
Estabilidade = clamp(round(52 * Direcao_vento + 22 * vx), -95, +95)
Direcao do ponteiro ESTAB. = 90 + 1.15 * Estabilidade
```

Na pontuacao continua em voo:

- **Taxa base:** `+2` pontos por segundo inteiro de voo.
- **Bonus de Equilibrio:** `+1` ponto adicional por segundo (`+3 pts/s` no total) enquanto `|Estabilidade| <= 12`, recompensando o piloto por recentralizar a aeronave apos desvios ou rajadas.
- **Sequencia de Brisas (`Brisa Favoravel`):** ao coletar uma brisa, a instabilidade e reduzida imediatamente para `round(0.35 * Estabilidade)`, o tanque ganha `+3%` de combustivel e a pontuacao escala pela sequencia coletada (`15 + 5 * min(Brisas Coletadas, 4)` -> `15, 20, 25, 30, 35` pontos).

### 2.3 Economia de Combustivel e Garantia Adaptativa

O sistema energetico cria tensao real no mostrador `COMB.%` (`Direcao = 2.7 * Combustivel - 45`) ao longo de `4` fases de `40 s` (`160 s` totais):

- **Consumo continuo:** `-0.65%/s` (`-104%` ao longo de `160 s` completos).
- **Reabastecimento no ar (`Galao Voxel`):** `+28%` de combustivel e `+10` pontos por coleta.
- **Garantia Adaptativa de Resgate (`Stage Loop 6`):** normalmente o galao surge quando `Indice Onda mod 3 != 0`; sempre que `Combustivel < 35%`, a condicao adaptativa (`Combustivel < 35 OU Indice Onda mod 3 != 0`) libera um galao obrigatorio na onda atual, evitando bloqueio matematico injusto.
- **Alerta sonoro e visual:** abaixo de `25%` dispara aviso sonoro intermitente se `Som = 1`.

### 2.4 Curva Progressiva por Bioma (4 Fases x 40 s = 160 s)

| Fase | Tempo | Bioma Brasileiro | Ave 3D Nativa | Avanco Mode-7 (`dZ/frame`) | Velocidade Ave (`d/frame`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `0-40 s` | Amazonia | Arara-Vermelha 3D | `0.11` | `0.0071` |
| 2 | `40-80 s` | Cerrado | Tucano-Toco 3D | `0.12` | `0.0076` |
| 3 | `80-120 s` | Pantanal | Tuiuiu Pantaneiro 3D | `0.13` | `0.0081` |
| 4 | `120-160 s` | Mata Atlantica | Arara-Azul 3D | `0.14` | `0.0086` |

- Formula geral do solo: `Z Mundo += 0.10 + 0.01 * Etapa` por frame (`30 FPS`).
- Formula geral das aves: `d_ave += 0.0066 + 0.0005 * Etapa` por frame (`30 FPS`).
- **Eventos de bioma controlados:** `1` rajada de vento por fase aos `12 s` (`6 s` de duracao) e `1` bando de `3` Harpias Reais em migracao aos `25 s`, sempre mantendo o corredor oposto aberto (`|X| >= 25`) para fuga segura.

---

## 3. Geracao Procedural: Raias Radiais e Mundo Mode-7

### 3.1 Cinco Raias Radiais Disjuntas no Ar

Os atores aereos (`Passaros`, `Combustivel no ar` e `Brisa Favoravel`) convergem a partir do ponto de fuga `(0, 44)` com curva nao linear de profundidade `p(d) = d^1.65` (`d in [0.04, 1.00]`):

```
Y(p) = 44 - 148 * p
X(p) = round(-0.10 * Posicao_X_Aviao) + x0 * (0.22 + 0.78 * p),  x0 in {-136, -68, 0, +68, +136}
```

A aritmetica modular garante que passaro, galao e brisa nunca ocupem a mesma raia:
- `Raia Ave = Semente_Mundo mod 5`
- `Raia Comb = (Semente_Mundo + 2) mod 5`
- `Raia Brisa = (Semente_Mundo + 4) mod 5`

As ondas seguem ciclo amplo de `6.2 s` (`2.0 s` + `2.0 s` + `2.2 s`), evitando poluicao na tela.

### 3.2 Motor Mode-7 em Pen Warp e Props Espacados

O sprite `Terreno Procedural` desenha o solo calmo e o rio em **polilinha continua de `18` nos** (zero quebras horizontais) a `30 FPS` dentro de um bloco customizado `warp=true`, com margens arenosas, agua rasa turquesa, canal profundo e `8` filetes de correnteza em loop periodico perfeito (`mod(Z_Mundo * 2.1, 24)`).

Os marcos `3D Voxel` de `Vegetacao e Cenario Vivo` usam um pool enxuto de **`4` clones** ancorados ao mesmo `Z Mundo` em ciclo de **`28.8 Z`** (`7.2 Z` de espacamento):
- **Bioma 1 (Amazonia):** Castanheira 3D (`prop1`), Barco Amazonico (`prop2`, sem placa ciano, restrito ao `slot == 1`), **Acaizeiro 3D (`prop3`, substituindo a antiga ponte)**.
- **Bioma 2 (Cerrado):** Ipe-Amarelo 3D, Buriti Limpo 3D, Igreja Colonial 3D.
- **Bioma 3 (Pantanal):** Caranda 3D, Chalana Pantaneira (`prop2`, sem placa ciano, restrita ao `slot == 1`), Tuiuiu em Pe.
- **Bioma 4 (Mata Atlantica):** Araucaria 3D (`prop1`), Casarao Colonial 3D (`prop2`), **Palmeira Real 3D (`prop3`, substituindo o antigo barco com cachoeira)**.

---

## 4. Inventario do Projeto e Camadas (`33 targets`)

| Ordem / Papel | Targets | Funcao Principal |
| :--- | :--- | :--- |
| Palco | `Stage` | Maquina de estados, loops `1-6` de voo, economia e eventos |
| Fundo / Ceu | `cenario`, `Sol`, `Terreno Procedural` | Panoramas nitidos, Sol Voxel `(172, 130)` e shader Pen Mode-7 |
| Ambiente Vivo | `Vegetacao e Cenario Vivo`, `Nuvens`, `Rajada de Vento`, `Pista` | `4` props Mode-7, `2` nuvens altas, `3` fitas de vento, pista de decolagem |
| Objetos Aereos | `Combustivel no ar`, `Brisa Favoravel`, `Passaros`, `Aves Migratorias` | Galoes, brisas estabilizadoras, aves 3D e Harpia Real |
| Protagonista | `Aviao` | Controle `30 FPS` com filtro anti-tremor e inclinacao |
| Telemetria (`HUD`) | `HUD · painel`, `HUD · Ponteiro Comb`, `HUD · Ponteiro Estab`, `HUD · Pontos 0..3`, `HUD · Tempo 0..3`, `HUD · Vidas`, `HUD · Fase`, `HUD · Alerta Comb` | Painel de cabine ativo somente em `decolagem` e `voo` |
| Telas / Botoes | `Fundo de encerramento`, `Camada de conclusao`, `Texto da conclusao`, `Telas`, `Start`, `Botao Guia` | Menu inicial, Tela Guia (`G`), pouso de vitoria e fim de voo |

---

## 5. Resultados Verificados (Build, Suite Automatizada e Playtest 160s)

- **Compilacao (`scripts/build_aeromattics.py`):** `33 targets`, `166 assets`, `23,930,082 bytes`, pacotes sincronizados em Desktop e Downloads, incluindo `5` sprites 3D Voxel exclusivos (`Arara-Vermelha`, `Tucano-Toco`, `Tuiuiu Pantaneiro`, `Arara-Azul` e `Harpia Real` 100% opaca orientada para esquerda e direita) e rio continuo (`296` tracos/quadro, `Horizon_MAE = 0.17..0.64`).
- **Suite de Regressao (`scripts/test_aeromattics.py`):** **`20/20` testes aprovados (`OK`)** em `18.525 s` executando os blocos reais na VM `ScratchVMSimulator` (inclui verificacao de solidez da Harpia, direcao bilateral `+90/-90`, Acaizeiro limpo e conectividade da polilinha do rio).
- **Simulacoes completas de `160 s` na VM (seed `2026`, `decolagem` + `160 s` de `voo`):**
  - `idle` (sem comando): queda na Fase 2 (`queda@62.7s`, `5` impactos, `0` vidas, `228` pts) — confirma que piloto inativo nao vence.
  - `skillful` (desvio e coleta ativa): vitoria na Fase 4 (`fim@162.9s`, `1,189` pts, `5` vidas, `2` galoes, `12` brisas, `57.4%` do tempo em equilibrio, combustivel final `92.8%`).
  - `tremor_sensor_c` (Modo Sensor `C` + tremor simulado `6 Hz`): vitoria na Fase 4 (`fim@162.9s`, `1,099` pts, `4` vidas, `3` galoes, `11` brisas, `68.7%` do tempo em equilibrio, combustivel final `81.3%`) — comprova fluidez terapeutica sob tremor motor severo.

---

## 6. Engenharia Programatica em Scratch 3.0 (Pesquisa e Ferramentas)

O **AeroMattics** adota uma pipeline engenheirada via codigo em vez de arrastar blocos manualmente no editor grafico:

1. **Geracao Direta de `.sb3` via Python (`zipfile` + `project.json` + `ScriptBuilder`):** cada sprite, fantasia SVG/PNG com hash MD5 e bloco (`opcode`, `inputs`, `fields`, `parent`, `next`) e compilado deterministicamente, permitindo versionamento em Git e testes automatizados por VM.
2. **Compiladores Textuais e Editores Alternativos:** ferramentas da comunidade como **`goboscript`** (linguagem textual inspirada em Rust/C que compila direto para `.sb3`), **`Tosh`** e **`TB3`** permitem escrever logica matematica complexa em texto puro e converter em blocos nativos.
3. **Otimizacao de Motores 2.5D/Mode-7 a `30 FPS`:**
   - usar blocos customizados **`Run without screen refresh` (`warp=true`)** para concluir toda a varredura de chao e rio dentro de um unico tick de `33.3 ms`;
   - reduzir passadas redundantes com largura de pincel proporcional a perspectiva ("fat pixel strips");
   - empregar **Look-Up Tables (LUTs)** ou limites fixos de passos e clones (`<= 15` clones simultaneos no AeroMattics) para evitar picos de latencia;
   - quando necessario validar ou demonstrar cenarios ainda mais pesados, **TurboWarp** suporta execucao compilada JIT de blocos Scratch mantendo compatibilidade integral com `.sb3`.
