#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Inicialização Automática de 1 Comando (Multiplataforma)
Projeto: Jogo de Imitação de Poses Corporais em Tempo Real (PDI - UFMA)

Ideal para rodar no computador do professor:
1. Verifica e instala dependências automaticamente se faltar alguma.
2. Faz busca ativa na rede pelo app IP Webcam no celular.
3. Conecta automaticamente assim que o usuário toca em "Start server" no celular.
"""

import sys
import os
import time
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

# -------------------------------------------------------------
# 1. VERIFICAÇÃO E INSTALAÇÃO AUTOMÁTICA DE DEPENDÊNCIAS
# -------------------------------------------------------------
def verificar_dependencias():
    pacotes_faltantes = []
    
    try:
        import cv2
    except ImportError:
        pacotes_faltantes.append("opencv-python")
        
    try:
        import mediapipe
    except ImportError:
        pacotes_faltantes.append("mediapipe")
        
    try:
        import numpy
    except ImportError:
        pacotes_faltantes.append("numpy")

    if pacotes_faltantes:
        print("\n" + "="*65)
        print("📦 CONFIGURAÇÃO INICIAL NO COMPUTADOR DO PROFESSOR")
        print("="*65)
        print(f"Instalando bibliotecas necessárias ({', '.join(pacotes_faltantes)})...")
        print("Isso acontece apenas uma vez.\n")
        try:
            req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
            if os.path.exists(req_file):
                cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
            else:
                cmd = [sys.executable, "-m", "pip", "install"] + pacotes_faltantes
            subprocess.check_call(cmd)
            print("\n✅ Dependências instaladas com sucesso!\n")
        except Exception as e:
            print(f"\n⚠️  Aviso ao instalar automaticamente: {e}")
            print(f"Por favor, execute: pip install {' '.join(pacotes_faltantes)}\n")

# -------------------------------------------------------------
# 2. DESCOBERTA AUTOMÁTICA DO IP WEBCAM NA REDE
# -------------------------------------------------------------
def obter_ips_locais():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    try:
        hostnames = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in hostnames:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    if not ips:
        ips.append("192.168.1.100")
        ips.append("192.168.0.100")
        ips.append("192.168.43.100")
    return ips

def testar_ip_webcam(ip, porta=8080, timeout=0.35):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        res = sock.connect_ex((ip, porta))
        if res == 0:
            req = f"GET /video HTTP/1.1\r\nHost: {ip}:{porta}\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n"
            sock.sendall(req.encode())
            resposta = sock.recv(128)
            sock.close()
            if b"HTTP/" in resposta:
                return f"http://{ip}:{porta}/video"
        sock.close()
    except Exception:
        pass
    return None

def escanear_rede_ip_webcam(ips_base):
    # 1. Testa rotas de Ponto de Acesso (Hotspot) do celular primeiro (ultra rápido)
    rotas_hotspot = ["192.168.43.1", "192.168.137.1", "172.20.10.1", "10.0.0.1", "192.168.0.1", "192.168.1.1"]
    for ip in rotas_hotspot:
        resultado = testar_ip_webcam(ip, timeout=0.25)
        if resultado:
            return resultado

    # 2. Varredura paralela na sub-rede local
    todos_candidatos = []
    for ip_local in ips_base:
        partes = ip_local.split(".")
        if len(partes) == 4:
            prefixo = ".".join(partes[:3])
            todos_candidatos.extend([f"{prefixo}.{i}" for i in range(1, 255)])

    # Remove duplicatas mantendo ordem
    candidatos_unicos = list(dict.fromkeys(todos_candidatos))

    with ThreadPoolExecutor(max_workers=60) as executor:
        resultados = executor.map(lambda ip: testar_ip_webcam(ip, timeout=0.35), candidatos_unicos)
        for res in resultados:
            if res:
                return res

    return None

# -------------------------------------------------------------
# 3. ROTINA PRINCIPAL DO INICIALIZADOR
# -------------------------------------------------------------
def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    verificar_dependencias()

    # Se o usuário passou um argumento na linha de comando
    if len(sys.argv) > 1:
        param = sys.argv[1].strip()
        if param == "0":
            url_alvo = "0"
            print("\n" + "="*65)
            print("🎥 [WEBCAM DO PROFESSOR]")
            print("Iniciando o jogo diretamente com a câmera integrada do notebook (0)...")
            print("="*65 + "\n")
        elif param.isdigit() and len(param) <= 3:
            # Usuário digitou só o final (ex: '15' para 192.168.1.15)
            ips = obter_ips_locais()
            prefixo = ".".join(ips[0].split(".")[:3])
            url_alvo = f"http://{prefixo}.{param}:8080/video"
            print(f"\n🚀 Conectando diretamente ao celular em: {url_alvo}\n")
        elif ":" in param or "." in param:
            url_alvo = param if param.startswith("http") else f"http://{param}"
            if not url_alvo.endswith("/video"):
                url_alvo = url_alvo.rstrip("/") + "/video"
            print(f"\n🚀 Conectando diretamente ao celular em: {url_alvo}\n")
        else:
            url_alvo = param
            print(f"\n🚀 Conectando em: {url_alvo}\n")
        cmd = [sys.executable, "jogo_poses.py", url_alvo, "--gravar", "--espelho"]
        sys.exit(subprocess.call(cmd))

    # Busca automática
    print("\n" + "="*65)
    print("   🎮 JOGO DE IMITAÇÃO DE POSES - PDI UFMA")
    print("="*65)
    print("📱 CONEXÃO AUTOMÁTICA COM O APP 'IP WEBCAM' DO CELULAR:")
    print("   1. Abra o app IP Webcam no celular")
    print("   2. Role a tela até o final e toque em: >>> 'Start server' <<<")
    print("   3. O jogo detectará e conectará sozinho em instantes!")
    print("="*65)

    ips_locais = obter_ips_locais()
    print(f"📡 Monitorando sub-rede local ({', '.join(ips_locais)})...")
    print("⏳ Aguardando você tocar em 'Start server' no celular...\n")

    tentativas = 0
    url_encontrada = None

    while True:
        tentativas += 1
        url_encontrada = escanear_rede_ip_webcam(ips_locais)
        if url_encontrada:
            break
        
        # Feedback visual a cada tentativa
        print(f"   [Tentativa {tentativas}] Celular ainda não iniciou a transmissão. Procurando... ", end="\r", flush=True)
        time.sleep(1.0)

    print("\n" + "-"*65)
    print(f"✅ SUCESSO! Celular detectado: {url_encontrada}")
    print("🚀 Iniciando o jogo agora...")
    print("-"*65 + "\n")

    cmd = [sys.executable, "jogo_poses.py", url_encontrada, "--gravar", "--espelho"]
    sys.exit(subprocess.call(cmd))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nEncerrado pelo usuário.")
        sys.exit(0)
