import cv2
import json
import sys
import time
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from utils_pose import (
    extrair_vetor_angulos,
    calcular_similaridade,
    FiltroEstabilidade,
    CONEXOES_CORPO, ARTICULACOES,
    desenhar_esqueleto_alvo
)

MODELO = "pose_landmarker_full.task"
ARQUIVO_POSES = "poses_referencia.json"
LIMIAR_ACERTO = 65.0          # % mínima de similaridade (reduzido para poses reais)
TEMPO_CONFIRMACAO = 1.5       # segundos mantendo a pose
DURACAO_PREPARACAO = 5.0      # segundos de demonstração da pose antes da rodada

with open(ARQUIVO_POSES, "r", encoding="utf-8") as f:
    poses = json.load(f)

base_options = python.BaseOptions(model_asset_path=MODELO)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO
)

# -------------------------------------------------------------
# PARÂMETROS DE EXECUÇÃO E GRAVAÇÃO DE VÍDEO
# -------------------------------------------------------------
gravar_video_arg = False
inverter_h_arg = True
fonte_cam = 0

for arg in sys.argv[1:]:
    if arg in ("--gravar", "--video", "-g"):
        gravar_video_arg = True
    elif arg in ("--sem-espelho", "--no-flip"):
        inverter_h_arg = False
    elif arg in ("--espelho", "-e"):
        inverter_h_arg = True
    else:
        fonte_cam = arg

if isinstance(fonte_cam, str):
    if fonte_cam.isdigit():
        fonte_cam = int(fonte_cam)
    elif ":" in fonte_cam and not fonte_cam.startswith("http"):
        fonte_cam = f"http://{fonte_cam}"
    if isinstance(fonte_cam, str) and fonte_cam.startswith("http"):
        # Se passou apenas a URL base do IP Webcam, completa com /video
        if not (fonte_cam.endswith("/video") or fonte_cam.endswith("/shot.jpg") or fonte_cam.endswith(".mjpg")):
            fonte_cam = fonte_cam.rstrip("/") + "/video"

nome_video_saida = "gravacao_execucao.mp4"
gravando_video = gravar_video_arg
video_writer = None
ultimo_tamanho_gravacao = None

# -------------------------------------------------------------
# SERVIDOR WEB DE TRANSMISSÃO (Para visualizar no celular)
# -------------------------------------------------------------
frame_jpeg_atual = None
lock_frame = threading.Lock()

class StreamingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return  # silencia logs para manter o terminal limpo

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Jogo de Poses - Tela Celular</title>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; padding: 0; background: #000; color: #fff; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .container { width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; }
        img { width: 100%; height: 100%; object-fit: contain; }
        .info { position: absolute; bottom: 12px; background: rgba(0,0,0,0.75); padding: 6px 14px; border-radius: 8px; font-size: 13px; color: #00ffcc; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <img src="/stream.mjpg" alt="Video do Jogo" />
        <div class="info">Olhe a pose por 5s e depois reproduza!</div>
    </div>
</body>
</html>"""
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', '0')
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with lock_frame:
                        data = frame_jpeg_atual
                    if data is not None:
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        self.wfile.write(b'\r\n')
                    time.sleep(0.04)  # ~25 FPS
            except Exception:
                pass
        else:
            self.send_error(404)

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def obter_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return 'localhost'

def iniciar_servidor_web(porta=5000):
    try:
        server = ThreadingHTTPServer(('0.0.0.0', porta), StreamingHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        ip = obter_ip_local()
        print("\n" + "="*60)
        print("📱 VISUALIZAÇÃO NO CELULAR / NAVEGADOR:")
        print(f"👉 Abra no navegador do celular: http://{ip}:{porta}")
        if gravando_video:
            print("🔴 GRAVAÇÃO DE VÍDEO ATIVADA (--gravar)")
        print("="*60 + "\n")
        return True
    except Exception as e:
        print(f"Aviso: Servidor web na porta {porta} não pôde ser iniciado: {e}")
        return False

# Inicia o servidor web em segundo plano
iniciar_servidor_web(porta=5000)

print(f"Tentando conectar na câmera: {fonte_cam}...")
cap = cv2.VideoCapture(fonte_cam)
if not cap.isOpened():
    print(f"\n[AVISO] Câmera ainda não encontrada em: {fonte_cam}")
    print("O servidor web em http://{}:5000 CONTINUA ATIVO.".format(obter_ip_local()))
    print("Inicie a transmissão no app do celular que o jogo conectará automaticamente!\n")

indice_pose = 0
pontuacao = 0
inicio_acerto = None
filtro = FiltroEstabilidade(tamanho_janela=5)
tempo_frame_anterior = time.perf_counter()

# Estado inicial: PREPARACAO (5 segundos mostrando a pose)
estado = "PREPARACAO"
tempo_inicio_prep = time.perf_counter()
tempo_inicio_pose_atual = time.perf_counter()

# Controles de orientação da câmera
rotacao = 0          # 0, 90, 180, 270 graus (tecla R)
inverter_v = False   # Inverte de cabeça para baixo (tecla V)
inverter_h = inverter_h_arg   # Modo espelho natural ativado por padrão (tecla H alterna)

# -------------------------------------------------------------
# ESTRUTURA PARA COLETA DE RESULTADOS E MÉTRICAS
# -------------------------------------------------------------
tempo_inicio_jogo = time.perf_counter()
historico_fps = []
historico_latencia = []
historico_sim = []
poses_concluidas_log = []
dados_csv_linhas = []

cv2.namedWindow("Jogo de Imitacao de Poses - PDI", cv2.WINDOW_NORMAL)

with vision.PoseLandmarker.create_from_options(options) as detector:
    while True:
        t_inicio_ciclo = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            print("\n[AVISO] Sinal da câmera perdido. Tentando reconectar ao celular...")
            cap.release()
            reconectado = False

            while not reconectado:
                frame_aviso = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(frame_aviso, "SINAL DA CAMERA PERDIDO", (60, 260),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 165, 255), 3)
                cv2.putText(frame_aviso, "Tentando reconectar ao celular automaticamente...", (60, 330),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (200, 200, 200), 2)
                cv2.putText(frame_aviso, "Dica: Mantenha o app IP Webcam aberto ou use 'Run in background'", (60, 390),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                cv2.putText(frame_aviso, "Pressione [Q] para encerrar o jogo", (60, 460),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (150, 150, 150), 2)

                _, buf = cv2.imencode('.jpg', frame_aviso, [cv2.IMWRITE_JPEG_QUALITY, 60])
                with lock_frame:
                    frame_jpeg_atual = buf.tobytes()

                cv2.imshow("Jogo de Imitacao de Poses - PDI", frame_aviso)
                tecla = cv2.waitKey(1000) & 0xFF
                if tecla == ord('q') or tecla == 27:
                    break

                cap = cv2.VideoCapture(fonte_cam)
                if cap.isOpened():
                    ret_teste, frame_teste = cap.read()
                    if ret_teste:
                        print("[SUCESSO] Câmera do celular reconectada!")
                        frame = frame_teste
                        reconectado = True
                        tempo_frame_anterior = time.perf_counter()
                        filtro.limpar()

            if not reconectado:
                break

        # 1. Rotação manual (R: 0, 90, 180, 270 graus)
        if rotacao == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotacao == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotacao == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # 2. Inversão Vertical (V: corrige imagem de cabeça para baixo)
        if inverter_v:
            frame = cv2.flip(frame, 0)

        # 3. Inversão Horizontal (H: modo espelho para ficar natural)
        if inverter_h:
            frame = cv2.flip(frame, 1)

        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int(time.time() * 1000)

        resultado = detector.detect_for_video(mp_image, timestamp_ms)
        pose_atual = poses[indice_pose]
        similaridade_suave = 0.0

        # Desenha esqueleto do jogador se detectado
        if resultado.pose_landmarks:
            landmarks = resultado.pose_landmarks[0]
            angulos_usuario, _ = extrair_vetor_angulos(landmarks)
            sim_bruta = calcular_similaridade(angulos_usuario, pose_atual["angulos"])
            similaridade_suave = filtro.atualizar(sim_bruta)

            # Cor do esqueleto do usuário
            cor = (0, 255, 0) if (estado == "JOGANDO" and similaridade_suave >= LIMIAR_ACERTO) else (0, 165, 255)
            for i, j in CONEXOES_CORPO:
                pt1 = (int(landmarks[i].x * w), int(landmarks[i].y * h))
                pt2 = (int(landmarks[j].x * w), int(landmarks[j].y * h))
                cv2.line(frame, pt1, pt2, cor, 3)

            for _, (a, b, c) in ARTICULACOES.items():
                for idx in (a, b, c):
                    px, py = int(landmarks[idx].x * w), int(landmarks[idx].y * h)
                    cv2.circle(frame, (px, py), 6, (0, 0, 255), -1)

            # Lógica de confirmação da pose por tempo
            if estado == "JOGANDO":
                if similaridade_suave >= LIMIAR_ACERTO:
                    if inicio_acerto is None:
                        inicio_acerto = time.perf_counter()
                    tempo_segurando = time.perf_counter() - inicio_acerto
                    if tempo_segurando >= TEMPO_CONFIRMACAO:
                        pontuacao += 100
                        tempo_gasto = time.perf_counter() - tempo_inicio_pose_atual

                        # Registra resultado da pose acertada
                        poses_concluidas_log.append({
                            "pose": pose_atual["nome"],
                            "tempo_segundos": round(tempo_gasto, 2),
                            "similaridade_final": round(similaridade_suave, 1),
                            "pontuacao_acumulada": pontuacao
                        })

                        indice_pose = (indice_pose + 1) % len(poses)
                        inicio_acerto = None
                        filtro.limpar()
                        # Ao acertar, inicia 5 segundos de preparação para a próxima pose
                        estado = "PREPARACAO"
                        tempo_inicio_prep = time.perf_counter()
                        tempo_inicio_pose_atual = time.perf_counter()
                else:
                    inicio_acerto = None

        # -------------------------------------------------------------
        # FASE 1: PREPARAÇÃO (Mostra a pose completa por 5 segundos)
        # -------------------------------------------------------------
        if estado == "PREPARACAO":
            tempo_passado = time.perf_counter() - tempo_inicio_prep
            segundos_restantes = max(0, int(DURACAO_PREPARACAO - tempo_passado) + 1)

            # Card centralizado com destaque
            box_w = min(int(w * 0.85), 460)
            box_h = min(int(h * 0.75), 520)
            x0 = (w - box_w) // 2
            y0 = (h - box_h) // 2

            # Fundo escurecido semi-transparente
            overlay = frame.copy()
            cv2.rectangle(overlay, (x0, y0), (x0 + box_w, y0 + box_h), (25, 25, 25), -1)
            cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
            cv2.rectangle(frame, (x0, y0), (x0 + box_w, y0 + box_h), (0, 255, 255), 3)

            cv2.putText(frame, "PREPARE-SE!", (x0 + 20, y0 + 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 255), 2)
            cv2.putText(frame, f"Pose: {pose_atual['nome']}", (x0 + 20, y0 + 72),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Comeca em: {segundos_restantes}s", (x0 + 20, y0 + 108),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # Esqueleto grande da pose alvo
            desenhar_esqueleto_alvo(frame, pose_atual["pontos_2d"], x0 + 20, y0 + 120, box_w - 40, box_h - 165, cor=(0, 255, 255), espessura=4)

            cv2.putText(frame, "Olhe a pose e assuma a posicao!", (x0 + 20, y0 + box_h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            if tempo_passado >= DURACAO_PREPARACAO:
                estado = "JOGANDO"
                inicio_acerto = None
                filtro.limpar()
                tempo_inicio_pose_atual = time.perf_counter()

        # -------------------------------------------------------------
        # FASE 2: JOGANDO (Avaliação em tempo real e miniatura alvo)
        # -------------------------------------------------------------
        else:
            # Miniatura compacta da pose alvo (canto superior direito, semi-transparente)
            box_w = max(110, min(140, int(w * 0.2)))
            box_h = int(box_w * 1.15)
            x0, y0 = w - box_w - 15, 15

            overlay_alvo = frame[y0:y0+box_h, x0:x0+box_w].copy()
            cv2.rectangle(overlay_alvo, (0, 0), (box_w, box_h), (25, 25, 25), -1)
            cv2.addWeighted(overlay_alvo, 0.75, frame[y0:y0+box_h, x0:x0+box_w], 0.25, 0, frame[y0:y0+box_h, x0:x0+box_w])
            cv2.rectangle(frame, (x0, y0), (x0 + box_w, y0 + box_h), (0, 255, 255), 2)
            cv2.putText(frame, "ALVO", (x0 + 8, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
            desenhar_esqueleto_alvo(frame, pose_atual["pontos_2d"], x0 + 4, y0 + 18, box_w - 8, box_h - 22, cor=(0, 255, 255), espessura=2)

            # HUD compacto no canto inferior esquerdo (NÃO cobre a cabeça nem o corpo)
            hud_w = min(280, int(w * 0.46))
            hud_h = 75
            hud_x = 15
            hud_y = max(10, h - 35 - hud_h)

            if hud_y + hud_h <= h and hud_x + hud_w <= w:
                overlay_hud = frame[hud_y:hud_y+hud_h, hud_x:hud_x+hud_w].copy()
                cv2.rectangle(overlay_hud, (0, 0), (hud_w, hud_h), (20, 20, 20), -1)
                cv2.addWeighted(overlay_hud, 0.75, frame[hud_y:hud_y+hud_h, hud_x:hud_x+hud_w], 0.25, 0, frame[hud_y:hud_y+hud_h, hud_x:hud_x+hud_w])
                cv2.rectangle(frame, (hud_x, hud_y), (hud_x + hud_w, hud_y + hud_h), (70, 70, 70), 1)

            cv2.putText(frame, f"Pose: {pose_atual['nome']}", (hud_x + 8, hud_y + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            cv2.putText(frame, f"Pontos: {pontuacao}", (hud_x + 8, hud_y + 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

            # Barra de similaridade horizontal compacta
            bar_w = min(150, hud_w - 70)
            bar_x = hud_x + 8
            bar_y = hud_y + 44
            largura_preenchida = int((similaridade_suave / 100.0) * bar_w)
            cor_barra = (0, 255, 0) if similaridade_suave >= LIMIAR_ACERTO else (0, 165, 255)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 10), (50, 50, 50), -1)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + largura_preenchida, bar_y + 10), cor_barra, -1)
            cv2.putText(frame, f"{similaridade_suave:.0f}%", (bar_x + bar_w + 6, bar_y + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)

            # Indicador de sustentação da pose
            if inicio_acerto is not None:
                tempo_seg = time.perf_counter() - inicio_acerto
                tempo_restante = max(0.0, TEMPO_CONFIRMACAO - tempo_seg)
                cv2.putText(frame, f"SEGURE: {tempo_restante:.1f}s", (hud_x + 8, hud_y + 68),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 0), 2)
            else:
                cv2.putText(frame, f"Meta: {LIMIAR_ACERTO:.0f}%", (hud_x + 8, hud_y + 68),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)

        # Métricas técnicas de desempenho
        t_fim_ciclo = time.perf_counter()
        latencia_ms = (t_fim_ciclo - t_inicio_ciclo) * 1000
        fps = 1.0 / max(t_fim_ciclo - tempo_frame_anterior, 1e-6)
        tempo_frame_anterior = t_fim_ciclo

        historico_fps.append(fps)
        historico_latencia.append(latencia_ms)
        if estado == "JOGANDO" and similaridade_suave > 0:
            historico_sim.append(similaridade_suave)

        # Coleta para arquivo CSV
        t_corrido = t_fim_ciclo - tempo_inicio_jogo
        dados_csv_linhas.append(f"{timestamp_ms},{t_corrido:.2f},{estado},{pose_atual['nome']},{similaridade_suave:.1f},{fps:.1f},{latencia_ms:.1f},{pontuacao}\n")

        # Barra inferior com atalhos
        h_label = "SIM" if inverter_h else "NAO"
        v_label = "SIM" if inverter_v else "NAO"
        info_txt = f"FPS: {fps:.0f} | [H] Espelho ({h_label}) | [R] Girar ({rotacao} deg) | [V] Invert ({v_label}) | [G] Gravar | [Q] Sair"
        cv2.putText(frame, info_txt, (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 255, 200), 1)

        # Indicador de gravação de vídeo na tela
        if gravando_video:
            cv2.circle(frame, (w - 30, h - 25), 8, (0, 0, 255), -1)
            cv2.putText(frame, "REC", (w - 75, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Grava frame no vídeo se ativado
        if gravando_video:
            h_f, w_f = frame.shape[:2]
            if video_writer is None or ultimo_tamanho_gravacao != (w_f, h_f):
                if video_writer is not None:
                    video_writer.release()
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(nome_video_saida, fourcc, 25.0, (w_f, h_f))
                ultimo_tamanho_gravacao = (w_f, h_f)
            video_writer.write(frame)

        # Atualiza o buffer de streaming para o navegador/celular
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with lock_frame:
            frame_jpeg_atual = buf.tobytes()

        # Ajusta tamanho para a janela do desktop caber sem achatar
        frame_display = frame
        if h > 900:
            escala = 850.0 / h
            frame_display = cv2.resize(frame, (int(w * escala), 850), interpolation=cv2.INTER_AREA)

        cv2.imshow("Jogo de Imitacao de Poses - PDI", frame_display)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord('q') or tecla == 27:
            break
        elif tecla == ord('g'):  # Alterna gravação de vídeo
            gravando_video = not gravando_video
            print(f"Gravação de vídeo: {'ATIVADA 🔴' if gravando_video else 'PAUSADA ⏹️'}")
        elif tecla == ord('r'):
            rotacao = (rotacao + 90) % 360
        elif tecla == ord('v'):
            inverter_v = not inverter_v
        elif tecla == ord('h'):
            inverter_h = not inverter_h
        elif tecla == ord(' '):  # Barra de espaço pula a preparação
            if estado == "PREPARACAO":
                estado = "JOGANDO"
                inicio_acerto = None
                filtro.limpar()
                tempo_inicio_pose_atual = time.perf_counter()
        elif tecla == ord('n'):  # N pula para a próxima pose
            indice_pose = (indice_pose + 1) % len(poses)
            estado = "PREPARACAO"
            tempo_inicio_prep = time.perf_counter()
            tempo_inicio_pose_atual = time.perf_counter()

cap.release()
cv2.destroyAllWindows()

# -------------------------------------------------------------
# FINALIZAÇÃO: SALVAR VÍDEO, CSV E RELATÓRIO JSON
# -------------------------------------------------------------
if video_writer is not None:
    video_writer.release()
    # Converte para H.264 para ser compatível com qualquer reprodutor/navegador/celular
    import subprocess
    import os
    if os.path.exists(nome_video_saida):
        nome_temp = "temp_" + nome_video_saida
        try:
            print("\nFinalizando e otimizando vídeo em H.264 compatível...")
            cmd = ["ffmpeg", "-y", "-i", nome_video_saida, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22", nome_temp]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            os.replace(nome_temp, nome_video_saida)
            print("✅ Vídeo final salvo em H.264 universal!")
        except Exception:
            if os.path.exists(nome_temp):
                os.remove(nome_temp)

tempo_total_partida = time.perf_counter() - tempo_inicio_jogo
fps_medio = float(np.mean(historico_fps)) if historico_fps else 0.0
latencia_media = float(np.mean(historico_latencia)) if historico_latencia else 0.0
sim_media = float(np.mean(historico_sim)) if historico_sim else 0.0

# 1. Salva arquivo CSV
with open("metricas_partida.csv", "w", encoding="utf-8") as f:
    f.write("timestamp_ms,tempo_corrido_s,estado,pose_alvo,similaridade_pct,fps,latencia_ms,pontos\n")
    f.writelines(dados_csv_linhas)

# 2. Salva relatório em JSON
relatorio = {
    "data_hora": time.strftime("%Y-%m-%d %H:%M:%S"),
    "duracao_total_segundos": round(tempo_total_partida, 2),
    "pontuacao_final": pontuacao,
    "total_poses_acertadas": len(poses_concluidas_log),
    "detalhes_poses": poses_concluidas_log,
    "fps_medio": round(fps_medio, 2),
    "latencia_media_ms": round(latencia_media, 2),
    "similaridade_media_pct": round(sim_media, 2),
    "video_gravado": nome_video_saida if gravando_video or video_writer is not None else None
}

with open("relatorio_partida.json", "w", encoding="utf-8") as f:
    json.dump(relatorio, f, indent=2, ensure_ascii=False)

print("\n" + "="*60)
print("📊 RESUMO DOS RESULTADOS DA SUA EXECUÇÃO (PDI)")
print("="*60)
print(f"🏆 Pontuação Final: {pontuacao} pontos")
print(f"⏱️  Duração Total da Partida: {tempo_total_partida:.1f} segundos")
print(f"🎯 Poses Concluídas com Sucesso: {len(poses_concluidas_log)}")
for p in poses_concluidas_log:
    print(f"   ✓ {p['pose']}: {p['tempo_segundos']}s (Similaridade: {p['similaridade_final']}%)")
print(f"📈 Similaridade Média: {sim_media:.1f}%")
print(f"⚡ Desempenho Técnico: {fps_medio:.1f} FPS médio | Latência média: {latencia_media:.1f} ms")
print(f"\n💾 Arquivos salvos na pasta:")
print(f"   • relatorio_partida.json (Estatísticas consolidadas da sessão)")
print(f"   • metricas_partida.csv (Dados brutos para gráficos/planilha)")
if gravando_video or video_writer is not None:
    print(f"   • {nome_video_saida} (Vídeo gravado da execução com overlays)")
print("="*60 + "\n")
