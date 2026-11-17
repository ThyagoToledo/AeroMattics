# Indice Geral de Assets Organizados - AeroMattics

Autor: ThyagoToledo

Este diretorio contem todos os arquivos extraidos do pacote original `AeroMattics.sb3` e os novos assets criados para a versao educativa matematica (registro MIT), tematizada nos 4 Biomas do Brasil (`Amazonia`, `Cerrado`, `Pantanal` e `Mata Atlantica`) e adaptada para reabilitacao motora de pacientes com Doenca de Parkinson.

## Estrutura de Pastas

1. `01_cenarios_biomas/`
   - `00_pista_decolagem.png`: Pista utilizada na animacao de decolagem.
   - `01_principal_bioma1_campo.png` a `04_principal_bioma4_neve.png`: Cenarios iniciais preservados para referencia historica.
   - `05_extra_bioma5_cerejeiras.png`: Cenario extra preservado do pacote original.
   - `06_fundo_missao_concluida_4x3.png`: Cenario de pouso historico (480x360).
   - `quadro_002_*` ate `quadro_131_*`: Quadros originais preservados para arquivo historico.

2. `02_aviao_voxel/`
   - `01_*` ate `47_*`: Todos os 47 quadros do aviao voxel sem fundo (voo reto, inclinacao a esquerda e inclinacao a direita).

3. `03_hud_cockpit/`
   - `aeromattics_hud_inferior_medidores_circulares.png`: Painel inferior com 4 visores e 2 mostradores circulares (`480x360` RGBA).
   - `aeromattics_hud_ponteiro_combustivel.png`: Ponteiro dourado assimetrico e afiado do medidor angular de combustivel (`64x64` RGBA).
   - `aeromattics_hud_ponteiro_estabilidade.png`: Ponteiro ciano assimetrico do medidor angular de estabilidade lateral (`64x64` RGBA).
   - `aeromattics_hud_ponteiro_velocidade.png`: Ponteiro ciano historico preservado (`64x64` RGBA).
   - `aeromattics_simbolo_combustivel.png`: Icone de combustivel (`64x64` RGBA).
   - `digito_0.png` a `digito_9.png`: Fontes dos digitos de `0` a `9` (integrados com nomes `digito_0`..`digito_9` no `.sb3` para Pontos, Tempo, Vidas e Fase).
   - `hud_painel_original_topo.png` e `aeromattics_hud_cockpit_tempo.png`: Paineis historicos preservados.

4. `04_passaros_biomas/`
   - `aeromattics_passaro_bioma1_campo_q1.png` a `q4.png`: 4 quadros animados da **Arara-Vermelha** (Fase 1 - Amazonia, `320x180` RGBA).
   - `aeromattics_passaro_bioma2_floresta_q1.png` a `q4.png`: 4 quadros animados do **Tucano-Toco** (Fase 2 - Cerrado, `320x180` RGBA).
   - `aeromattics_passaro_bioma3_deserto_q1.png` a `q4.png`: 4 quadros animados do **Tuiuiu Pantaneiro** (Fase 3 - Pantanal, `320x180` RGBA).
   - `aeromattics_passaro_bioma4_neve_q1.png` a `q4.png`: 4 quadros animados da **Arara-Azul** (Fase 4 - Mata Atlantica, `320x180` RGBA).
   - `ave_migratoria_q1.png` a `ave_migratoria_q6.png`: 6 quadros animados da **Harpia Real Brasileira** (`Harpia harpyja`) em estilo voxel (`320x180` RGBA).
   - Folhas `2x2` (`_4frames.png`) atualizadas e historicas preservadas no mesmo diretorio.

5. `05_nuvens_voxel/`
   - `nuvem_quadro_1.png` a `nuvem_quadro_4.png`: 4 quadros volumetricos em perspectiva (`320x180` RGBA).
   - `sol_voxel_q1.png` a `sol_voxel_q3.png`: 3 quadros de sol animado em estilo voxel com pulsacao lenta de raios (`160x160` RGBA, usado no canto superior direito `(162, 124)`).
   - `rajada_vento_q1.png` e `rajada_vento_q2.png`: 2 quadros animados de rajada de vento lateral translucida (`320x180` RGBA).
   - `aeromattics_nuvens_sprite_sheet_4frames.png`: Folha original 2x2 (`640x360` RGBA).

6. `06_itens_e_aneis/`
   - `aeromattics_combustivel_galao_pixel.png`: Galao voxel coletavel de combustivel (`96x96` RGBA).
   - `brisa_favoravel_q1.png` a `q3.png`: 3 quadros animados da corrente de ar ascendente natural (`Brisa Favorável`, `160x160` RGBA).
   - `anel_matematico_q1.png` a `q3.png`: Quadros historicos do antigo anel preservados para comparacao.

7. `07_telas_e_overlays/`
   - `alerta_migracao_esq.png` e `alerta_migracao_dir.png`: Indicadores visuais discretos nas bordas do ceu antes da passagem da Harpia Real (`120x120` RGBA).
   - `pouso_vitoria_raw.png`: Cenario de pouso ao por do sol em estilo voxel 3D gerado para a tela de vitoria (`1200x896` RGBA).
   - `pouso_gameover_raw.png`: Cenario acolhedor de pouso seguro em gramado ao entardecer gerado para a tela de fim de voo (`1200x896` RGBA).
   - `tela_Capa_Menu_Limpa.png`: Capa principal higienizada com legenda de controles adaptados (`Setas`, `Makey Makey`, `Sensor C`, `Guia G`, `Som M`) (`960x720` RGBA).
   - `tela_Guia_AeroMattics.png`: Tela ilustrada `GUIA - COMO VOAR` com fundo amazonico e 4 cartoes visuais em fonte grande explicando `1. AVES DO BRASIL E HARPIA`, brisa/vento, combustivel e controles Mattics (`960x720` RGBA).
   - `tela_Fim_Pouso_Vitoria.png`: Tela final limpa de pouso concluido sem sobreposicao de HUD (`960x720` RGBA).
   - `tela_Fim_Pouso_GameOver.png`: Tela final limpa de fim de voo terapeutico sem sobreposicao de HUD (`960x720` RGBA).
   - `botao_menu_decolar.png`, `botao_menu_guia.png`, `botao_guia_voltar.png`, `botao_fim_jogar_novamente.png`, `botao_fim_tentar_novamente.png`, `botao_fim_menu.png`: Botoes alados em estilo voxel (`260x84` RGBA).
   - `tela_Capa_AeroMattics.jpg`, `aeromattics_missao_concluida_moldura_limpa.png`, `aeromattics_missao_concluida_moldura_alpha_4x3.png`, `aeromattics_tela_fim_missao_overlay_alpha.png`, `botao_Botao_da_capa.png`, `botao_START.png`, `tela_Inicio.png`, `tela_Game_over.png`: Overlays, molduras e telas originais preservadas.

8. `08_sons/`
   - `01_Decolagem.wav` ate `08_Cloud_Glider.wav`: Todos os efeitos sonoros e trilha ambiente extraidos do projeto original.

9. `09_cenarios_vivos/`
   - `raw_bioma1.png` a `raw_bioma4.png`: Panoramas 3D Minecraft voxel originais (`1200x896`) gerados para Amazonia, Cerrado, Pantanal e Mata Atlantica.
   - `bioma1_vivo_q1.png` a `bioma4_vivo_q3.png`: `12` quadros quantizados (`1120x760`) em loop calmo com cintilacao suave d'agua (`<= 5%`) no canal fluvial de cada bioma brasileiro.
   - `relevo_bioma1_q1.png` a `relevo_bioma4_q2.png`: `8` camadas transparentes (`1200x360` RGBA) com bruma atmosferica desfocada nas extremidades laterais e centro livre.
   - `refs/`: `14` recortes de referencia extraidos diretamente de `raw_bioma1..4.png` para orientar a geracao 3D consistente dos props.
   - `props/raw_props_bioma1.png` a `raw_props_bioma4.png`: `4` folhas `16:9` (`1376x768`) geradas em estilo 3D Minecraft voxel sobre fundo branco neutro.
   - `props/b1_prop1_q1.png` a `b4_prop3_q2.png`: `24` quadros individuais recortados e ancorados (`240x240` RGBA, centro `(120, 176)`): `Sumauma`, `Barco Gaiola`, `Pier Vitoria-Regia`, `Ipe-Amarelo`, `Buritis`, `Igreja Colonial`, `Ipe-Rosa`, `Chalana e Capivara`, `Ninho de Tuiuiu`, `Araucaria`, `Casarao Colonial` e `Cachoeira e Barco` (com pedestais de agua suavizados em `b1_prop2`, `b1_prop3` e `b3_prop2`).
   - `raw_terreno_base_voxel.png` e `raw_terreno_bioma1.png` a `raw_terreno_bioma4.png`: `5` mapas de terreno e rio 3D voxel limpos (`1200x896`) sem casas, barcos ou arvores estaticas.
   - `floresta_distante_b1_q1.png` a `floresta_distante_b4_q2.png`: `8` camadas de dossel 3D voxel real de horizonte (`1200x240` RGBA, ancora `(600, 130)`).
   - `segmentos_25d/segmento_rio_b1_v1_q1.png` a `b4_v3_q2.png`: `24` fatias 3D voxel de largura total (`1200x180` RGBA, ancora `(600, 90)`) em 3 zonas de profundidade (`v1`, `v2`, `v3`) e 2 quadros de correnteza (`q1`, `q2`).
