import cv2
import numpy as np
from collections import deque

# Pares de conexões principais para desenhar o esqueleto no OpenCV
CONEXOES_CORPO = [
    (11, 12), (11, 23), (12, 24), (23, 24), # Tronco
    (11, 13), (13, 15),                     # Braço esquerdo
    (12, 14), (14, 16),                     # Braço direito
    (15, 19), (16, 20),                     # Mãos/dedos (se adicionou punhos)
    # Comente ou apague as 2 linhas abaixo se quiser tirar as pernas:
    (23, 25), (25, 27),                     # Perna esquerda
    (24, 26), (26, 28)                      # Perna direita
]

# Trios de landmarks (A, B, C) onde B é o vértice do ângulo
ARTICULACOES = {
    "ombro_esq": (23, 11, 13),
    "ombro_dir": (24, 12, 14),
    "cotovelo_esq": (11, 13, 15),
    "cotovelo_dir": (12, 14, 16),
    "quadril_esq": (11, 23, 25),
    "quadril_dir": (12, 24, 26),
    "joelho_esq": (23, 25, 27),
    "joelho_dir": (24, 26, 28),
    "punho_esq": (13, 15, 19),
    "punho_dir": (14, 16, 20),
}

def calcular_angulo(a, b, c):
    """Calcula o ângulo (0 a 180 graus) no ponto B formado por A-B-C."""
    ba = np.array([a.x - b.x, a.y - b.y])
    bc = np.array([c.x - b.x, c.y - b.y])
    
    norma = np.linalg.norm(ba) * np.linalg.norm(bc)
    if norma == 0:
        return 0.0
    
    cosseno = np.clip(np.dot(ba, bc) / norma, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosseno)))

def extrair_vetor_angulos(landmarks):
    """Retorna um dicionário com os 8 ângulos corporais e o esqueleto normalizado."""
    angulos = {}
    for nome, (idx_a, idx_b, idx_c) in ARTICULACOES.items():
        angulos[nome] = calcular_angulo(landmarks[idx_a], landmarks[idx_b], landmarks[idx_c])
    
    # Salva pontos (x, y) para desenhar a miniatura da pose alvo na tela
    pontos_2d = [(lm.x, lm.y) for lm in landmarks]
    return angulos, pontos_2d

def calcular_similaridade(angulos_atual, angulos_alvo, tolerancia_max=60.0):
    """
    Compara os ângulos e retorna uma porcentagem de 0 a 100%.
    Diferença média de 0° = 100%; diferença média >= tolerancia_max° = 0%.
    Articulações principais (ombros, cotovelos) têm peso maior;
    pernas e punhos pesam menos para não penalizar por detalhes.
    """
    # Pesos: articulações do tronco/braço pesam mais
    pesos = {
        "ombro_esq": 2.0,
        "ombro_dir": 2.0,
        "cotovelo_esq": 1.5,
        "cotovelo_dir": 1.5,
        "quadril_esq": 0.5,
        "quadril_dir": 0.5,
        "joelho_esq": 0.3,
        "joelho_dir": 0.3,
        "punho_esq": 0.4,
        "punho_dir": 0.4,
    }
    soma_peso = 0.0
    soma_erro = 0.0
    for k in ARTICULACOES:
        peso = pesos.get(k, 1.0)
        soma_erro += abs(angulos_atual[k] - angulos_alvo[k]) * peso
        soma_peso += peso
    erro_medio_ponderado = soma_erro / max(soma_peso, 1e-6)
    similaridade = max(0.0, 100.0 * (1.0 - (erro_medio_ponderado / tolerancia_max)))
    return similaridade

class FiltroEstabilidade:
    """Suaviza a pontuação ao longo dos frames para evitar oscilações bruscas."""
    def __init__(self, tamanho_janela=5):
        self.historico = deque(maxlen=tamanho_janela)
        
    def atualizar(self, valor):
        self.historico.append(valor)
        return float(np.mean(self.historico))
    
    def limpar(self):
        self.historico.clear()

def desenhar_esqueleto_alvo(frame, pontos_2d, x0, y0, box_w, box_h, cor=(0, 255, 255), espessura=3):
    """Desenha o esqueleto normalizado e centralizado dentro de qualquer caixa delimitadora (x0, y0, box_w, box_h)."""
    xs = [pontos_2d[idx][0] for pair in CONEXOES_CORPO for idx in pair]
    ys = [pontos_2d[idx][1] for pair in CONEXOES_CORPO for idx in pair]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    diff_x = max(max_x - min_x, 1e-5)
    diff_y = max(max_y - min_y, 1e-5)

    pad = int(min(box_w, box_h) * 0.12)
    disp_w = box_w - 2 * pad
    disp_h = box_h - 2 * pad
    scale = min(disp_w / diff_x, disp_h / diff_y)

    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    target_cx = x0 + box_w / 2.0
    target_cy = y0 + box_h / 2.0

    def transform(x, y):
        px = int(target_cx + (x - cx) * scale)
        py = int(target_cy + (y - cy) * scale)
        return (px, py)

    for i, j in CONEXOES_CORPO:
        cv2.line(frame, transform(pontos_2d[i][0], pontos_2d[i][1]),
                        transform(pontos_2d[j][0], pontos_2d[j][1]), cor, espessura)
    for _, (a, b, c) in ARTICULACOES.items():
        for idx in (a, b, c):
            cv2.circle(frame, transform(pontos_2d[idx][0], pontos_2d[idx][1]), int(espessura * 1.8), (0, 0, 255), -1)
