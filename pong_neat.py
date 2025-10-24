import sys
import os
import math
import time
import pickle
import random
from typing import Optional, Callable

import pygame
import neat

ARQ_CAMPEAO = os.path.join(os.path.dirname(__file__), "melhor_genoma.pkl")

# ==========================
# CONFIG VISUAL / JOGO
# ==========================
LARGURA = 900
ALTURA = 600
FPS = 60

COR_FUNDO = (10, 10, 15)
COR_LINHAS = (220, 220, 220)
COR_TEXTO = (240, 240, 240)
COR_CINZA = (170, 170, 185)

# Modos de jogo
MODO_HH = "Humano vs Humano"
MODO_HAI = "Humano vs IA"
MODO_AIAI = "IA vs IA"
MODO_TREINO = "Treinar IA (NEAT)"

pygame.init()
pygame.display.set_caption("Pong + NEAT")
TELA = pygame.display.set_mode((LARGURA, ALTURA))
CLOCK = pygame.time.Clock()
FONTE = pygame.font.SysFont("arial", 44, bold=True)
FONTE_M = pygame.font.SysFont("arial", 26)
FONTE_P = pygame.font.SysFont("arial", 20)

# ==========================
# ENTIDADES
# ==========================
class Raquete:
    def __init__(self, x, y, largura=14, altura=100, velocidade=420):
        self.rect = pygame.Rect(x, y, largura, altura)
        self.vel = velocidade

    def mover(self, direcao, dt):
        # direcao: -1 cima / +1 baixo / 0 parado
        self.rect.y += int(self.vel * direcao * dt)
        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > ALTURA:
            self.rect.bottom = ALTURA

    def desenhar(self, tela):
        pygame.draw.rect(tela, COR_LINHAS, self.rect, border_radius=4)


class Bola:
    def __init__(self, x, y, raio=9, vel_inicial=420):
        self.x = float(x)
        self.y = float(y)
        self.raio = raio
        self.vel = vel_inicial
        # Direção inicial ligeiramente inclinada
        ang = random.uniform(-0.35, 0.35)
        self.dirx = 1.0 * math.cos(ang)
        self.diry = math.sin(ang)

        self.incremento_vel = 24
        self.vel_max = 1000
        self.angulo_max = math.radians(60)

    def _normalize(self):
        m = math.hypot(self.dirx, self.diry)
        if m == 0:
            self.dirx, self.diry = 1.0, 0.0
        else:
            self.dirx /= m
            self.diry /= m

    def resetar(self, lado=1):
        self.x = LARGURA / 2
        self.y = ALTURA / 2
        self.vel = 420
        self.dirx = 1.0 * lado
        self.diry = random.choice([-0.25, 0.25])
        self._normalize()

    def mover(self, dt):
        self.x += self.dirx * self.vel * dt
        self.y += self.diry * self.vel * dt

        # colisão vertical
        if self.top <= 0:
            self.y = self.raio
            self.diry *= -1
        elif self.bottom >= ALTURA:
            self.y = ALTURA - self.raio
            self.diry *= -1

    @property
    def left(self): return self.x - self.raio
    @property
    def right(self): return self.x + self.raio
    @property
    def top(self): return self.y - self.raio
    @property
    def bottom(self): return self.y + self.raio
    @property
    def rect(self): return pygame.Rect(int(self.left), int(self.top), self.raio*2, self.raio*2)

    def desenhar(self, tela):
        pygame.draw.circle(tela, COR_LINHAS, (int(self.x), int(self.y)), self.raio)

    def colide_com_raquete(self, rq: Raquete, eh_esquerda: bool):
        if self.rect.colliderect(rq.rect):
            # ponto de contato relativo
            centro = rq.rect.centery
            relativo = (self.y - centro) / (rq.rect.height / 2)
            relativo = max(-1.0, min(1.0, relativo))
            ang = relativo * self.angulo_max
            self.dirx = math.cos(ang)
            self.diry = math.sin(ang)
            self.dirx = abs(self.dirx)
            if not eh_esquerda:
                self.dirx *= -1
            self._normalize()

            # empurra para fora
            if eh_esquerda:
                self.x = rq.rect.right + self.raio + 1
            else:
                self.x = rq.rect.left - self.raio - 1

            self.vel = min(self.vel + self.incremento_vel, self.vel_max)
            return True
        return False

# ==========================
# JOGO BASE
# ==========================
class JogoPong:
    def __init__(self):
        margem = 36
        self.raq_esq = Raquete(margem, ALTURA//2 - 50)
        self.raq_dir = Raquete(LARGURA - margem - 14, ALTURA//2 - 50)
        self.bola = Bola(LARGURA/2, ALTURA/2)
        self.placar_esq = 0
        self.placar_dir = 0
        self.pausado = False

    def reiniciar_round(self, quem_marco: str):
        # quem_marco: "esq" ou "dir"
        lado = -1 if quem_marco == "esq" else 1
        self.bola.resetar(lado)

    def _desenhar_campo(self, tela):
        tela.fill(COR_FUNDO)
        # tracejado central
        dash_h, gap = 18, 14
        x = LARGURA // 2
        y = 0
        while y < ALTURA:
            pygame.draw.rect(tela, COR_LINHAS, (x-2, y, 4, dash_h), border_radius=2)
            y += dash_h + gap

    def _ui(self, tela, extra_lines=None):
        txt = FONTE.render(f"{self.placar_esq}   {self.placar_dir}", True, COR_TEXTO)
        tela.blit(txt, (LARGURA//2 - txt.get_width()//2, 18))
        dicas = "W/S (esq) • ↑/↓ (dir) | P: pausa | R: reinicia | ESC: sair"
        d = FONTE_P.render(dicas, True, COR_CINZA)
        tela.blit(d, (LARGURA//2 - d.get_width()//2, ALTURA - 30))
        if extra_lines:
            y = 64
            for line in extra_lines:
                t = FONTE_P.render(line, True, (200, 210, 240))
                tela.blit(t, (LARGURA//2 - t.get_width()//2, y))
                y += 22

    def step(self, dt, ctrl_esq: Callable[[dict], int], ctrl_dir: Callable[[dict], int]):
        # controladores retornam -1/0/+1 com base no estado
        estado = {
            "ball_x": self.bola.x,
            "ball_y": self.bola.y,
            "ball_vx": self.bola.dirx * self.bola.vel,
            "ball_vy": self.bola.diry * self.bola.vel,
            "left_y": self.raq_esq.rect.centery,
            "right_y": self.raq_dir.rect.centery,
        }
        self.raq_esq.mover(ctrl_esq(estado), dt)
        self.raq_dir.mover(ctrl_dir(estado), dt)

        self.bola.mover(dt)
        col_esq = self.bola.colide_com_raquete(self.raq_esq, True)
        col_dir = self.bola.colide_com_raquete(self.raq_dir, False)

        ponto = None
        if self.bola.right < 0:
            self.placar_dir += 1
            self.reiniciar_round("dir")
            ponto = "dir"
        elif self.bola.left > LARGURA:
            self.placar_esq += 1
            self.reiniciar_round("esq")
            ponto = "esq"

        return col_esq, col_dir, ponto

    def desenhar(self, tela, extra=None):
        self._desenhar_campo(tela)
        self.raq_esq.desenhar(tela)
        self.raq_dir.desenhar(tela)
        self.bola.desenhar(tela)
        self._ui(tela, extra_lines=extra)
        pygame.display.flip()

    def reset_placar(self):
        self.placar_dir = 0
        self.placar_esq = 0
        self.reiniciar_round("dir")

# ==========================
# CONTROLADORES
# ==========================
def ctrl_humano_esquerda(estado):
    keys = pygame.key.get_pressed()
    d = 0
    if keys[pygame.K_w]: d -= 1
    if keys[pygame.K_s]: d += 1
    return d

def ctrl_humano_direita(estado):
    keys = pygame.key.get_pressed()
    d = 0
    if keys[pygame.K_UP]: d -= 1
    if keys[pygame.K_DOWN]: d += 1
    return d

def ctrl_ai_heuristico(lag=0.0, erro=0.0, lado="dir"):
    # IA simples que segue a bola com pequena latência/ruído
    alvo = {"dir": "ball_y", "esq": "ball_y"}[lado]
    acumulador = {"y": 0.0}
    def _ctrl(estado):
        y_target = estado[alvo] + random.uniform(-erro, erro)
        # simular lag: aproxima o alvo gradualmente
        acumulador["y"] = (1 - lag) * acumulador.get("y", y_target) + lag * y_target
        paddle_y = estado["right_y"] if lado == "dir" else estado["left_y"]
        if paddle_y < acumulador["y"] - 8: return +1
        if paddle_y > acumulador["y"] + 8: return -1
        return 0
    return _ctrl

def ctrl_por_rede(neural_net, lado="dir"):
    # Entrada: [ball_x_norm, ball_y_norm, vx_norm, vy_norm, paddle_y_norm]
    def _norm(v, lo, hi):
        return (v - lo) / (hi - lo) * 2 - 1.0
    def _ctrl(estado):
        bx = _norm(estado["ball_x"], 0, LARGURA)
        by = _norm(estado["ball_y"], 0, ALTURA)
        vx = _norm(estado["ball_vx"], -1000, 1000)
        vy = _norm(estado["ball_vy"], -1000, 1000)
        py = _norm(estado["right_y"] if lado == "dir" else estado["left_y"], 0, ALTURA)
        out = neural_net.activate([bx, by, vx, vy, py])[0]
        # saída > 0.33 = descer, < -0.33 = subir
        if out > 0.33: return +1
        if out < -0.33: return -1
        return 0
    return _ctrl

# ==========================
# MENU
# ==========================
def menu_inicial():
    opcoes = [MODO_HH, MODO_HAI, MODO_AIAI, MODO_TREINO]
    selecionado = 0
    while True:
        CLOCK.tick(FPS)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q):
                    pygame.quit(); sys.exit()
                if e.key in (pygame.K_DOWN, pygame.K_s):
                    selecionado = (selecionado + 1) % len(opcoes)
                if e.key in (pygame.K_UP, pygame.K_w):
                    selecionado = (selecionado - 1) % len(opcoes)
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return opcoes[selecionado]

        TELA.fill(COR_FUNDO)
        titulo = FONTE.render("Pong + NEAT", True, COR_TEXTO)
        TELA.blit(titulo, (LARGURA//2 - titulo.get_width()//2, 80))
        subt = FONTE_M.render("Escolha um modo e pressione ENTER", True, COR_CINZA)
        TELA.blit(subt, (LARGURA//2 - subt.get_width()//2, 140))

        y = 220
        for i, opc in enumerate(opcoes):
            cor = (255, 235, 120) if i == selecionado else COR_TEXTO
            t = FONTE_M.render(opc, True, cor)
            TELA.blit(t, (LARGURA//2 - t.get_width()//2, y))
            y += 44

        dica = FONTE_P.render("↑/↓ seleciona • ENTER confirma • ESC sai", True, COR_CINZA)
        TELA.blit(dica, (LARGURA//2 - dica.get_width()//2, ALTURA - 40))
        pygame.display.flip()

# ==========================
# PARTIDAS (JOGAR)
# ==========================
def jogar(modo: str, rede_campeao: Optional[neat.nn.FeedForwardNetwork] = None):
    jogo = JogoPong()
    jogo.reset_placar()

    if modo == MODO_HH:
        ctrl_esq = ctrl_humano_esquerda
        ctrl_dir = ctrl_humano_direita
        overlay = ["Modo: Humano vs Humano"]

    elif modo == MODO_HAI:
        ctrl_esq = ctrl_humano_esquerda
        if rede_campeao:
            ctrl_dir = ctrl_por_rede(rede_campeao, "dir")
            overlay = ["Modo: Humano vs IA (NEAT)", "Campeão carregado ✔"]
        else:
            ctrl_dir = ctrl_ai_heuristico(lag=0.2, erro=12, lado="dir")
            overlay = ["Modo: Humano vs IA (heurística)", "Nenhum campeão encontrado ✖"]

    elif modo == MODO_AIAI:
        if rede_campeao:
            ctrl_esq = ctrl_por_rede(rede_campeao, "esq")
            ctrl_dir = ctrl_por_rede(rede_campeao, "dir")
            overlay = ["Modo: IA (NEAT) vs IA (NEAT)", "Campeão carregado ✔"]
        else:
            ctrl_esq = ctrl_ai_heuristico(lag=0.22, erro=10, lado="esq")
            ctrl_dir = ctrl_ai_heuristico(lag=0.25, erro=12, lado="dir")
            overlay = ["Modo: IA heurística vs IA heurística", "Nenhum campeão encontrado ✖"]
    else:
        return

    while True:
        dt = CLOCK.tick(FPS) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return
                if e.key == pygame.K_p:
                    jogo.pausado = not jogo.pausado
                if e.key == pygame.K_r:
                    jogo.reset_placar()

        if not jogo.pausado:
            jogo.step(dt, ctrl_esq, ctrl_dir)

        jogo.desenhar(TELA, extra=overlay)

# ==========================
# TREINAMENTO NEAT
# ==========================
geracao = 0

def avaliar_genoma(genome, config, render=False, tempo_max=5.0):
    """
    Avalia o genoma em múltiplos trials curtos:
      - controla À DIREITA e À ESQUERDA
      - serve começando dos dois lados
      - adversário heurístico com lag/erro variados

    Shaping (por trial):
      +2.5 por rebatida (defesa)
      +3.0 por ponto a favor
      -8.0 por ponto contra
      - distância raquete-bola quando a bola vem para o seu lado
      +0.01 por sobrevivência (pequeno)

    Retorna a média dos trials.
    """
    net = neat.nn.FeedForwardNetwork.create(genome, config)

    def _ctrl_by_net(lado):
        return ctrl_por_rede(net, lado=lado)

    def _trial(lado_ctrl: str, serve_para: str) -> float:
        jogo = JogoPong()
        jogo.reset_placar()
        # força o primeiro saque para um lado
        jogo.reiniciar_round("esq" if serve_para == "esq" else "dir")

        # adversário heurístico com ruído/latência variados
        lag = random.uniform(0.15, 0.35)
        erro = random.uniform(6, 14)

        if lado_ctrl == "dir":
            ctrl_esq = ctrl_ai_heuristico(lag=lag, erro=erro, lado="esq")
            ctrl_dir = _ctrl_by_net("dir")
        else:  # controla a esquerda
            ctrl_esq = _ctrl_by_net("esq")
            ctrl_dir = ctrl_ai_heuristico(lag=lag, erro=erro, lado="dir")

        inicio = time.time()
        fit = 0.0

        while True:
            dt = (CLOCK.tick(FPS) / 1000.0) if render else (CLOCK.tick(240) / 1000.0)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    # permite cancelar o treino com ESC
                    raise KeyboardInterrupt

            col_esq, col_dir, ponto = jogo.step(dt, ctrl_esq, ctrl_dir)

            # sobrevivência (bem pequeno agora)
            fit += 0.01

            # RECOMPENSA DEFESA (contato da RAQUETE controlada)
            if lado_ctrl == "dir" and col_dir:
                fit += 2.5
            if lado_ctrl == "esq" and col_esq:
                fit += 2.5

            # PONTUAÇÃO
            if lado_ctrl == "dir":
                if ponto == "dir":  # ponto a favor
                    fit += 3.0
                elif ponto == "esq":  # tomou gol
                    fit -= 8.0
            else:  # controla a esquerda
                if ponto == "esq":
                    fit += 3.0
                elif ponto == "dir":
                    fit -= 8.0

            # CUSTO DE DISTÂNCIA quando a bola VEM para o seu lado
            vem_para_dir = jogo.bola.dirx > 0
            vem_para_esq = jogo.bola.dirx < 0
            if lado_ctrl == "dir" and vem_para_dir and jogo.bola.x > LARGURA * 0.5:
                dy = abs(jogo.raq_dir.rect.centery - jogo.bola.y) / (ALTURA / 2)
                fit -= 0.003 * dy  # pequeno, por frame
            if lado_ctrl == "esq" and vem_para_esq and jogo.bola.x < LARGURA * 0.5:
                dy = abs(jogo.raq_esq.rect.centery - jogo.bola.y) / (ALTURA / 2)
                fit -= 0.003 * dy

            if time.time() - inicio > tempo_max:
                break

            if render:
                jogo.desenhar(TELA, extra=[f"Treino • Geração {geracao}", f"Fitness: {fit:.2f}"])

        return fit

    # 4 trials: controla dir/esq × serve dir/esq
    trials = [
        ("dir", "dir"),
        ("dir", "esq"),
        ("esq", "dir"),
        ("esq", "esq"),
    ]
    total = 0.0
    for lado, serve in trials:
        total += _trial(lado, serve)

    return total / len(trials)


def func_avaliacao(genomas, config):
    global geracao
    geracao += 1

    total = len(genomas)
    inicio_geracao = time.time()

    for idx, (_, g) in enumerate(genomas, start=1):
        g.fitness = avaliar_genoma(g, config, render=False)

        # --- Barra de progresso simples ---
        elapsed = time.time() - inicio_geracao
        perc = idx / total
        est_total = elapsed / perc if perc > 0 else 0
        restante = max(0, est_total - elapsed)

        # Atualiza a tela (sem travar o treino)
        TELA.fill((20, 20, 30))
        t1 = FONTE_M.render(f"Treinando geração {geracao}", True, (255, 255, 255))
        t2 = FONTE_P.render(f"Avaliando genoma {idx}/{total}", True, (200, 200, 220))
        t3 = FONTE_P.render(f"Tempo decorrido: {elapsed:5.1f}s", True, (180, 180, 200))
        t4 = FONTE_P.render(f"Estimado restante: {restante:5.1f}s", True, (180, 180, 200))
        
        # Barra
        bar_w = int(LARGURA * 0.7)
        bar_h = 20
        x0 = (LARGURA - bar_w) // 2
        y0 = ALTURA // 2 + 60
        pygame.draw.rect(TELA, (60, 60, 90), (x0, y0, bar_w, bar_h), border_radius=4)
        pygame.draw.rect(TELA, (120, 200, 120), (x0, y0, int(bar_w * perc), bar_h), border_radius=4)

        TELA.blit(t1, (LARGURA // 2 - t1.get_width() // 2, ALTURA // 2 - 60))
        TELA.blit(t2, (LARGURA // 2 - t2.get_width() // 2, ALTURA // 2 - 25))
        TELA.blit(t3, (LARGURA // 2 - t3.get_width() // 2, ALTURA // 2 + 20))
        TELA.blit(t4, (LARGURA // 2 - t4.get_width() // 2, ALTURA // 2 + 40))

        pygame.display.flip()

def treinar_neat(caminho_config: str, geracoes=30, salvar_em="melhor_genoma.pkl"):
    config = neat.config.Config(neat.DefaultGenome,
                                neat.DefaultReproduction,
                                neat.DefaultSpeciesSet,
                                neat.DefaultStagnation,
                                caminho_config)

    pop = neat.Population(config)
    pop.add_reporter(neat.StdOutReporter(True))
    pop.add_reporter(neat.StatisticsReporter())

    campeao = pop.run(func_avaliacao, geracoes)

    # salva campeão
    with open(ARQ_CAMPEAO, "wb") as f:
        pickle.dump(campeao, f)

    # tenta exibir o campeão jogando
    rede = neat.nn.FeedForwardNetwork.create(campeao, config)
    mostrar_campeao(rede, titulo="Treino concluído! Campeão em ação (ESC volta ao menu)")

def mostrar_campeao(rede, titulo="Campeão (ESC para sair)"):
    jogo = JogoPong()
    jogo.reset_placar()
    ctrl_esq = ctrl_ai_heuristico(lag=0.22, erro=10, lado="esq")
    ctrl_dir = ctrl_por_rede(rede, "dir")

    while True:
        dt = CLOCK.tick(FPS) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                return
        jogo.step(dt, ctrl_esq, ctrl_dir)
        jogo.desenhar(TELA, extra=[titulo])

def carregar_rede_campeao(caminho_config: str, arquivo: str = ARQ_CAMPEAO):
    if not os.path.exists(arquivo):
        return None
    with open(arquivo, "rb") as f:
        campeao = pickle.load(f)
    config = neat.config.Config(neat.DefaultGenome,
                                neat.DefaultReproduction,
                                neat.DefaultSpeciesSet,
                                neat.DefaultStagnation,
                                caminho_config)
    return neat.nn.FeedForwardNetwork.create(campeao, config)

# ==========================
# MAIN
# ==========================
def main():
    base = os.path.dirname(__file__)
    caminho_cfg = os.path.join(base, "config-neat.txt")
    rede_campeao = carregar_rede_campeao(caminho_cfg)

    while True:
        modo = menu_inicial()
        if modo == MODO_TREINO:
            treinar_neat(caminho_cfg, geracoes=30, salvar_em="melhor_genoma.pkl")
            rede_campeao = carregar_rede_campeao(caminho_cfg)  # recarrega campeão após treino
        else:
            jogar(modo, rede_campeao=rede_campeao)

if __name__ == "__main__":
    main()
