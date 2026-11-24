# 🕺 Jogo de Imitação de Poses — PDI (UFMA)

Sistema interativo de visão computacional desenvolvido para a disciplina de **Processamento Digital de Imagens (PDI)** da **Universidade Federal do Maranhão (UFMA)**. O software captura o vídeo da câmera em tempo real, extrai os 33 *landmarks* corporais via **MediaPipe Pose Landmarker**, calcula ângulos articulares invariantes à escala e posição e avalia a similaridade anatômica entre o jogador e a pose de referência com pontuação e telemetria em tempo real.

---

## 🚀 Como Rodar no Computador do Professor (1 Comando Só)

O projeto conta com um **inicializador automático inteligente** (`rodar.py`, `rodar.bat` e `rodar.sh`) que:
1. Verifica se as bibliotecas estão instaladas e instala automaticamente se necessário (`pip install -r requirements.txt`).
2. Faz busca ativa na rede pelo app **IP Webcam** e **conecta automaticamente** assim que você aperta *"Start server"* no celular.
3. Ativa gravação de evidências e modo espelho natural por padrão.

### 📱 Passo a Passo para a Apresentação:

1. **No Celular:**
   - Abra o app **IP Webcam** (Android).
   - Role até o final da tela e toque em **"Start server"** (ou *"Iniciar servidor"*).
2. **No Computador do Professor:**
   - **No Windows:** Dê dois cliques em **`rodar.bat`** (ou abra o terminal e digite `python rodar.py`).
   - **No Linux / macOS:** Execute `./rodar.sh` (ou `python3 rodar.py`).
3. **Pronto!** O script detecta o celular na rede local automaticamente e abre o jogo na hora.

> 💡 **Opções manuais adicionais:**
> - Se preferir usar a webcam integrada do notebook do professor: `python rodar.py 0`
> - Se preferir digitar o IP manualmente: `python rodar.py 192.168.1.15` (ou apenas os dígitos finais, ex: `python rodar.py 15`)

---

## 🏗️ Arquitetura do Sistema

```text
WEBCAM ──▶ OPENCV (Captura) ──▶ MEDIAPIPE POSE (33 Landmarks) ──▶ CÁLCULO DE ÂNGULOS ──▶ FILTRO TEMPORAL (Média Móvel) ──▶ INTERFACE & MÉTRICAS
```

### Estrutura de Arquivos

```text
jogo_poses/
├── pose_landmarker_full.task   # Modelo MediaPipe Full (já baixado na pasta)
├── pose_landmarker_lite.task   # Modelo MediaPipe Lite (já baixado na pasta)
├── poses_referencia.json       # Banco de poses alvo gravadas pelo usuário
├── utils_pose.py               # Definição das articulações, cálculo de ângulos e filtro temporal
├── gravar_poses.py             # Ferramenta para captura e cadastro de novas poses
├── jogo_poses.py               # Aplicação principal com pontuação e métricas em tempo real
└── README.md                   # Documentação do projeto
```

---

## ⚙️ Instalação e Configuração

O ambiente virtual já foi configurado na pasta do projeto com todas as dependências instaladas. Para ativá-lo no terminal:

```bash
source .venv/bin/activate
```

*(Caso use o shell fish: `source .venv/bin/activate.fish`)*

---

## 📱 Usando o Celular como Webcam (Pela Rede Wi-Fi)

Caso você não tenha webcam no computador, pode utilizar seu celular Android ou iOS conectado na mesma rede Wi-Fi:

1. **Baixe o app no celular:**
   * Recomendado: **IP Webcam** (Android - Gratuito na Play Store ou F-Droid) ou **DroidCam**.
2. **Inicie o servidor de vídeo:**
   * No app **IP Webcam**, desça até o final da tela e toque em **"Start server"** (ou "Iniciar servidor").
   * O aplicativo mostrará na tela um endereço de IP com porta, por exemplo: `http://192.168.1.15:8080`.
3. **Execute os scripts apontando para a URL do celular:**
   * Adicione `/video` ao final do endereço exibido:
     ```bash
     python jogo_poses.py http://192.168.1.15:8080/video
     ```
   * O mesmo vale para o gravador de poses:
     ```bash
     python gravar_poses.py http://192.168.1.15:8080/video
     ```

> **Dica contra desconexões:** 
> * No app **IP Webcam**, toque nos 3 pontinhos no canto superior direito e selecione **"Run in background"** (ou "Executar em segundo plano"). Isso impede que o Android suspenda a câmera quando você trocar de aplicativo ou apagar a tela.
> * Caso o sinal caia por qualquer motivo, os scripts agora entram em **reconexão automática**, mantendo sua pontuação e progresso intactos assim que o app for reaberto.

> **Sobre o Termux (ou Terminus):** Embora dê para rodar comandos no Termux, ele não possui aceleração de hardware nativa para transmissão contínua de vídeo em tempo real, gerando alto atraso (lag) e queda brusca de FPS. O uso do app nativo **IP Webcam** ou **DroidCam** resolve isso com streaming suave a 30 FPS diretamente para o OpenCV.

---

## 🎮 Como Usar

### Etapa 1: Gravar as Poses de Referência

Antes de iniciar o jogo, cadastre as poses que servirão de gabarito:

1. No terminal, execute:

```bash
python gravar_poses.py
```

2. **Clique uma vez dentro da janela do vídeo** para deixá-la em foco e posicione-se de corpo inteiro (a cerca de 2 a 2,5 metros da webcam) até visualizar o esqueleto verde com os marcadores vermelhos nas articulações ativas.
3. Faça a pose desejada e pressione **`S`** (maiúsculo ou minúsculo) na janela do vídeo.
4. O vídeo ficará pausado aguardando entrada no terminal: clique no terminal, digite o **nome da pose** (ex.: `Estrela`, `Guerreiro`) e pressione **`Enter`** para confirmar a captura e retomar a câmera.
5. Clique novamente na janela do vídeo e repita os passos 3 e 4 para cadastrar de **4 a 5 poses distintas**.
6. Com a janela do vídeo em foco, pressione **`Q`** ou **`ESC`** para salvar o arquivo `poses_referencia.json` e encerrar.

---

### Etapa 2: Executar o Jogo

Com o arquivo `poses_referencia.json` gerado na pasta (já configurado com 6 poses distintas):

1. No terminal, execute:

```bash
# Executar normalmente
.venv/bin/python jogo_poses.py http://192.168.1.9:8080/video

# OU Executar gravando vídeo da partida (salva gravacao_execucao.mp4)
.venv/bin/python jogo_poses.py http://192.168.1.9:8080/video --gravar
```

*(Ou `0` no lugar do link se for utilizar webcam USB padrão)*

2. **Fluxo do Jogo (Modo Demonstração de 5 segundos):**
   * **Fase de Preparação (5 segundos):** Antes de cada rodada, o jogo destaca a **pose alvo em tamanho grande no centro da tela** com um contador regressivo (`5s`, `4s`, `3s`...). Você tem esse tempo para memorizar e se posicionar!
   * **Fase da Rodada:** A pose alvo vai para a miniatura no canto superior direito e a avaliação é ativada.
   * **Sustentação (2 segundos):** Mantenha o esqueleto verde (`>= 82%`) por 2 segundos para pontuar (+100) e avançar para a próxima pose (com nova contagem de 5s).

3. **📱 Visualização no Celular (Fora do Quarto):**
   * O jogo inicia um servidor web local automaticamente.
   * Enquanto joga longe do computador, abra no navegador do seu celular (ou outro aparelho na mesma rede):
     ```text
     http://192.168.1.25:5000
     ```
   * O jogo completo (esqueletos, contagem regressiva, pontos e poses) será transmitido em tempo real na tela do celular!

4. **Controles e Atalhos no Teclado:**
   * **`G`**: Inicia ou pausa a **gravação de vídeo** (`🔴 REC`) em tempo real (salva em `gravacao_execucao.mp4`).
   * **`R`**: Gira o vídeo em 90° (0°, 90°, 180°, 270°) caso o celular esteja na vertical e a imagem fique de lado.
   * **`V`**: Inverte o vídeo verticalmente (corrige se a câmera frontal ficar de ponta-cabeça).
   * **`H`**: Inverte horizontalmente (ativa/desativa modo espelho).
   * **`ESPAÇO`**: Pula a contagem de 5 segundos e inicia a rodada imediatamente.
   * **`N`**: Pula para a próxima pose da lista.
   * **`Q`** ou **`ESC`**: Encerra o jogo e gera os relatórios.

5. **📊 Relatórios e Métricas Gerados Automaticamente:**
   Ao encerrar o jogo, são gerados automaticamente:
   * **`relatorio_partida.json`**: Estatísticas completas (pontuação final, tempo por pose, similaridades, FPS e latência média).
   * **`metricas_partida.csv`**: Dados quadro a quadro da execução prontos para importar no Excel/Sheets e gerar gráficos.
   * **`gravacao_execucao.mp4`**: Vídeo completo com os esqueletos e pontuações desenhados na tela para apresentação do trabalho.

---

## 🔧 Parâmetros e Calibração

Caso queira ajustar a dificuldade, a pontuação, as articulações monitoradas ou comparar o desempenho entre modelos, edite os parâmetros correspondentes:

| Parâmetro | Arquivo | Valor Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `MODELO` | `jogo_poses.py` | `"pose_landmarker_full.task"` | Alterne para `"pose_landmarker_lite.task"` (já incluso na pasta) para testar ganho de FPS. |
| `LIMIAR_ACERTO` | `jogo_poses.py` | `82.0` | Porcentagem mínima de similaridade para validar a pose (reduza para `75.0` se estiver muito rigoroso). |
| `TEMPO_CONFIRMACAO` | `jogo_poses.py` | `2.0` | Tempo (em segundos) que o jogador precisa manter a pose para pontuar. |
| `pontuacao += 100` | `jogo_poses.py` | `100` | Quantidade de pontos somados a cada pose concluída. |
| `ARTICULACOES` | `utils_pose.py` | `8 ângulos` | Define quais trios de *landmarks* entram no cálculo e ganham marcadores vermelhos na tela. |
| `CONEXOES_CORPO` | `utils_pose.py` | `12 segmentos` | Define quais linhas do esqueleto são desenhadas na interface. |
| `tamanho_janela` | `utils_pose.py` | `5` | Quantidade de quadros usados na média móvel do filtro de estabilidade. |

> **Nota:** Sempre que alterar o dicionário `ARTICULACOES` em `utils_pose.py`, execute `python gravar_poses.py` novamente para atualizar o arquivo `poses_referencia.json` com a nova estrutura de ângulos.

---

## 📊 Critérios de Avaliação Implementados

* **FPS (Quadros por Segundo):** Medido continuamente a cada ciclo de captura, inferência e renderização e exibido no rodapé da janela.
* **Latência (ms):** Tempo total de processamento por quadro entre a leitura da webcam e a atualização visual na tela.
* **Taxa de Acerto:** Baseada na comparação dos ângulos articulares definidos em `ARTICULACOES` (ombros, cotovelos, quadris e joelhos por padrão), tornando o reconhecimento invariante à altura do jogador e à distância da câmera.
* **Estabilidade:** Garantida por um filtro de média móvel temporal (`FiltroEstabilidade`) combinado à exigência de sustentação contínua por 2 segundos, evitando oscilações e falsos positivos.

---

## 💡 Recomendações para Apresentação Presencial

* **Enquadramento:** Posicione a webcam na altura do tronco e afaste o participante até que todas as articulações marcadas em vermelho estejam visíveis no quadro.
* **Iluminação:** Evite janelas ou luzes fortes diretamente atrás do jogador, pois o efeito de contraluz reduz o contraste da imagem e prejudica a detecção dos pontos articulares.