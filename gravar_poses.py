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
from utils_pose import extrair_vetor_angulos, CONEXOES_CORPO, ARTICULACOES

MODELO = "pose_landmarker_full.task"
ARQUIVO_SAIDA = "poses_referencia.json"

base_options = python.BaseOptions(model_asset_path=MODELO)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO
)

# -------------------------------------------------------------
# SERVIDOR WEB DE TRANSMISSÃO (Para gravar vendo pelo celular)
# -------------------------------------------------------------
frame_jpeg_atual = None
lock_frame = threading.Lock()

class StreamingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Gravador de Poses - Celular</title>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; padding: 0; background: #000; color: #fff; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .container { width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; }
        img { width: 100%; height: 100%; object-fit: contain; }
        .info { position: absolute; bottom: 12px; background: rgba(0,0,0,0.75); padding: 6px 14px; border-radius: 8px; font-size: 13px; color: #ffcc00; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <img src="/stream.mjpg" alt="Video Gravador" />
        <div class="info">Posicione o corpo inteiro e aperte S no PC para capturar</div>
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
                    time.sleep(0.04)
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
        print("="*60 + "\n")
        return True
    except Exception:
        return False

iniciar_servidor_web(porta=5000)

fonte_cam = sys.argv[1] if len(sys.argv) > 1 else 0
if isinstance(fonte_cam, str) and fonte_cam.isdigit():
    fonte_cam = int(fonte_cam)

print(f"Tentando conectar na câmera: {fonte_cam}...")
cap = cv2.VideoCapture(fonte_cam)
if not cap.isOpened():
    print(f"\n[ERRO] Não foi possível abrir a fonte de vídeo: {fonte_cam}")
    print("Dicas:")
    print(" 1. Se estiver usando o celular (IP Webcam), confirme se o app está ativo na tela.")
    print(" 2. Verifique se o celular e o PC estão na mesma rede Wi-Fi.")
    print(" 3. Exemplo de execução: python gravar_poses.py http://192.168.1.9:8080/video\n")
    exit(1)

# Carrega poses existentes para não perder o que já tem gravado
try:
    with open(ARQUIVO_SAIDA, "r", encoding="utf-8") as f:
        poses_salvas = json.load(f)
    print(f"Banco existente carregado com {len(poses_salvas)} poses.")
except Exception:
    poses_salvas = []

rotacao = 0          # 0, 90, 180, 270 graus (tecla R)
inverter_v = False   # Ponta-cabeça (tecla V)
inverter_h = False   # Espelho desativado por padrão (tecla H alterna)

# Contagem regressiva de captura
contagem_captura = None
DURACAO_CONTAGEM = 3.0  # 3 segundos para se posicionar após apertar S
ultimo_landmarks = None

print("\nComandos:")
print(" [S] Iniciar contagem de 3s para capturar a pose")
print(" [R] Girar vídeo 90 graus")
print(" [V] Inverter vídeo (corrige ponta-cabeça)")
print(" [H] Inverter horizontalmente (espelho)")
print(" [Q] Salvar arquivo e sair\n")

cv2.namedWindow("Gravador de Poses", cv2.WINDOW_NORMAL)

with vision.PoseLandmarker.create_from_options(options) as detector:
    while True:
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
                cv2.putText(frame_aviso, "Pressione [Q] para salvar as poses gravadas e sair", (60, 460),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (150, 150, 150), 2)

                _, buf = cv2.imencode('.jpg', frame_aviso, [cv2.IMWRITE_JPEG_QUALITY, 60])
                with lock_frame:
                    frame_jpeg_atual = buf.tobytes()

                cv2.imshow("Gravador de Poses", frame_aviso)
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

            if not reconectado:
                break

        # 1. Rotação manual (R)
        if rotacao == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotacao == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotacao == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # 2. Inversão Vertical (V)
        if inverter_v:
            frame = cv2.flip(frame, 0)

        # 3. Inversão Horizontal (H)
        if inverter_h:
            frame = cv2.flip(frame, 1)

        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int(time.time() * 1000)

        resultado = detector.detect_for_video(mp_image, timestamp_ms)

        if resultado.pose_landmarks:
            ultimo_landmarks = resultado.pose_landmarks[0]
            for i, j in CONEXOES_CORPO:
                pt1 = (int(ultimo_landmarks[i].x * w), int(ultimo_landmarks[i].y * h))
                pt2 = (int(ultimo_landmarks[j].x * w), int(ultimo_landmarks[j].y * h))
                cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

            for _, (a, b, c) in ARTICULACOES.items():
                for idx in (a, b, c):
                    px, py = int(ultimo_landmarks[idx].x * w), int(ultimo_landmarks[idx].y * h)
                    cv2.circle(frame, (px, py), 6, (0, 0, 255), -1)

        # Lógica de contagem regressiva para captura
        if contagem_captura is not None:
            tempo_decorrido = time.perf_counter() - contagem_captura
            tempo_restante = DURACAO_CONTAGEM - tempo_decorrido
            if tempo_restante > 0:
                cv2.putText(frame, f"CAPTURANDO EM: {tempo_restante:.1f}s",
                            (w // 2 - 180, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 3)
            else:
                contagem_captura = None
                if ultimo_landmarks is not None:
                    nome_padrao = f"Pose {len(poses_salvas) + 1}"
                    angulos, pontos_2d = extrair_vetor_angulos(ultimo_landmarks)
                    poses_salvas.append({
                        "nome": nome_padrao,
                        "angulos": angulos,
                        "pontos_2d": pontos_2d
                    })
                    print(f"\n[SUCESSO] '{nome_padrao}' capturada com sucesso! (Total: {len(poses_salvas)})")

        v_label = "SIM" if inverter_v else "NAO"
        cv2.putText(frame, f"Poses: {len(poses_salvas)} | [S] Capturar (3s) | [R] Girar ({rotacao} deg) | [V] Ponta-cabeca ({v_label}) | [Q] Sair",
                    (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 0), 2)

        # Atualiza buffer de streaming
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with lock_frame:
            frame_jpeg_atual = buf.tobytes()

        # Ajusta tamanho para não achatar no monitor
        frame_display = frame
        if h > 900:
            escala = 850.0 / h
            frame_display = cv2.resize(frame, (int(w * escala), 850), interpolation=cv2.INTER_AREA)

        cv2.imshow("Gravador de Poses", frame_display)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord('r'):
            rotacao = (rotacao + 90) % 360
        elif tecla == ord('v'):
            inverter_v = not inverter_v
        elif tecla == ord('h'):
            inverter_h = not inverter_h
        elif tecla == ord('s'):
            contagem_captura = time.perf_counter()
        elif tecla == ord('q') or tecla == 27:
            break

cap.release()
cv2.destroyAllWindows()

if poses_salvas:
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(poses_salvas, f, indent=2, ensure_ascii=False)
    print(f"\n{len(poses_salvas)} poses salvas com sucesso em '{ARQUIVO_SAIDA}'.")
