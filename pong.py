import math
import sys
import pygame

# ==========================
# Configurações principais
# ==========================
LARGURA = 900
ALTURA = 600
FPS = 60

COR_FUNDO = (10, 10, 15)
COR_LINHAS = (220, 220, 220)
COR_TEXTO = (240, 240, 240)

# Controles:
# Jogador da esquerda: W (cima) / S (baixo)
# Jogador da direita: ↑ (cima) / ↓ (baixo)
# P = pausa, R = reinicia, ESC = sair

class Raquete:
    def __init__(self, x, y, largura=14, altura=100, velocidade=420):
        self.rect = pygame.Rect(x, y, largura, altura)
        self.vel = velocidade

    def mover(self, direcao, dt):
        # direcao: -1 para cima, +1 para baixo, 0 parado
        self.rect.y += int(self.vel * direcao * dt)
        # limitar nos limites da tela
        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > ALTURA:
            self.rect.bottom = ALTURA

    def desenhar(self, tela):
        pygame.draw.rect(tela, COR_LINHAS, self.rect, border_radius=4)


class Bola:
    def __init__(self, x, y, raio=9, vel_inicial=420, angulo_inicial=0):
        self.x = float(x)
        self.y = float(y)
        self.raio = raio
        self.vel = vel_inicial
        # vetor unitário baseado no ângulo (em radianos)
        # se angulo_inicial=0 a bola vai para a direita
        self.dirx = math.cos(angulo_inicial)
        self.diry = math.sin(angulo_inicial)

        # para evitar lançamento 100% horizontal
        if abs(self.diry) < 0.15:
            self.diry = 0.2 * (1 if self.diry >= 0 else -1)
            self._normalize()

        # aceleração por colisão com raquete
        self.incremento_vel = 20
        self.vel_max = 900
        self.angulo_max = math.radians(60)  # máximo de 60° de inclinação

    def _normalize(self):
        mag = math.hypot(self.dirx, self.diry)
        if mag == 0:
            self.dirx, self.diry = 1.0, 0.0
        else:
            self.dirx /= mag
            self.diry /= mag

    def resetar(self, lado: int = 1):
        # lado: 1 lança para a direita, -1 lança para a esquerda
        self.x = LARGURA / 2
        self.y = ALTURA / 2
        self.vel = 420
        self.dirx = lado
        self.diry = 0.0
        # quebra a horizontalidade perfeita
        self.diry = 0.2
        self._normalize()

    def mover(self, dt):
        self.x += self.dirx * self.vel * dt
        self.y += self.diry * self.vel * dt

        # colisão superior/inferior
        if self.top <= 0:
            self.y = self.raio
            self.diry *= -1
        elif self.bottom >= ALTURA:
            self.y = ALTURA - self.raio
            self.diry *= -1

    @property
    def left(self):
        return self.x - self.raio

    @property
    def right(self):
        return self.x + self.raio

    @property
    def top(self):
        return self.y - self.raio

    @property
    def bottom(self):
        return self.y + self.raio

    @property
    def rect(self):
        return pygame.Rect(int(self.left), int(self.top), self.raio * 2, self.raio * 2)

    def desenhar(self, tela):
        pygame.draw.circle(tela, COR_LINHAS, (int(self.x), int(self.y)), self.raio)

    def colide_com_raquete(self, raquete: Raquete, eh_esquerda: bool):
        if self.rect.colliderect(raquete.rect):
            # ponto de contato relativo no eixo Y (-1 topo, 0 centro, +1 base)
            centro_raquete = raquete.rect.centery
            distancia = (self.y - centro_raquete)
            relativo = distancia / (raquete.rect.height / 2)
            relativo = max(-1.0, min(1.0, relativo))

            # ângulo de saída baseado no ponto de contato
            angulo = relativo * self.angulo_max
            self.dirx = math.cos(angulo)
            self.diry = math.sin(angulo)

            # garantir que a bola vá para o lado oposto da raquete
            self.dirx = abs(self.dirx)
            if eh_esquerda:
                # bateu na esquerda -> vai para direita
                pass
            else:
                # bateu na direita -> vai para esquerda
                self.dirx *= -1

            self._normalize()

            # empurrar a bola para fora da raquete para não "grudar"
            if eh_esquerda:
                self.x = raquete.rect.right + self.raio + 1
            else:
                self.x = raquete.rect.left - self.raio - 1

            # acelerar um pouco a cada batida
            self.vel = min(self.vel + self.incremento_vel, self.vel_max)
            return True
        return False


class Jogo:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pong Local - 2 Jogadores")
        self.tela = pygame.display.set_mode((LARGURA, ALTURA))
        self.clock = pygame.time.Clock()
        self.fonte = pygame.font.SysFont("arial", 48, bold=True)
        self.fonte_small = pygame.font.SysFont("arial", 22)

        margem = 36
        self.raquete_esq = Raquete(x=margem, y=ALTURA//2 - 50)
        self.raquete_dir = Raquete(x=LARGURA - margem - 14, y=ALTURA//2 - 50)

        self.bola = Bola(LARGURA/2, ALTURA/2)

        self.placar_esq = 0
        self.placar_dir = 0
        self.pausado = False

    def _desenhar_campo(self):
        self.tela.fill(COR_FUNDO)
        # linha central tracejada
        dash_h = 18
        gap = 14
        x = LARGURA // 2
        y = 0
        while y < ALTURA:
            pygame.draw.rect(self.tela, COR_LINHAS, (x-2, y, 4, dash_h), border_radius=2)
            y += dash_h + gap

    def _desenhar_ui(self):
        # placar
        placar = f"{self.placar_esq}   {self.placar_dir}"
        txt = self.fonte.render(placar, True, COR_TEXTO)
        self.tela.blit(txt, (LARGURA//2 - txt.get_width()//2, 20))

        # dicas
        dicas = "W/S (esq) • ↑/↓ (dir) | P: pausa | R: reinicia | ESC: sair"
        txt2 = self.fonte_small.render(dicas, True, (180, 180, 200))
        self.tela.blit(txt2, (LARGURA//2 - txt2.get_width()//2, ALTURA - 32))

        if self.pausado:
            overlay = self.fonte.render("PAUSADO", True, (255, 210, 60))
            self.tela.blit(overlay, (LARGURA//2 - overlay.get_width()//2, ALTURA//2 - overlay.get_height()//2))

    def reiniciar_round(self, quem_marco: str):
        # quem_marco: "esq" ou "dir" (só pra decidir sentido do saque)
        lado = -1 if quem_marco == "esq" else 1
        self.bola.resetar(lado=lado)

    def atualizar(self, dt):
        if self.pausado:
            return

        # mover bola
        self.bola.mover(dt)

        # colisões com raquetes
        self.bola.colide_com_raquete(self.raquete_esq, eh_esquerda=True)
        self.bola.colide_com_raquete(self.raquete_dir, eh_esquerda=False)

        # ponto?
        if self.bola.right < 0:
            self.placar_dir += 1
            self.reiniciar_round("dir")
        elif self.bola.left > LARGURA:
            self.placar_esq += 1
            self.reiniciar_round("esq")

    def processar_inputs(self, dt):
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if evento.key == pygame.K_p:
                    self.pausado = not self.pausado
                if evento.key == pygame.K_r:
                    # reinicia placar e bola
                    self.placar_esq = 0
                    self.placar_dir = 0
                    self.bola.resetar(lado=1)

        # teclas pressionadas para mover as raquetes
        keys = pygame.key.get_pressed()
        dir_esq = 0
        dir_dir = 0

        # esquerda: W/S
        if keys[pygame.K_w]:
            dir_esq -= 1
        if keys[pygame.K_s]:
            dir_esq += 1

        # direita: ↑/↓
        if keys[pygame.K_UP]:
            dir_dir -= 1
        if keys[pygame.K_DOWN]:
            dir_dir += 1

        self.raquete_esq.mover(dir_esq, dt)
        self.raquete_dir.mover(dir_dir, dt)

    def desenhar(self):
        self._desenhar_campo()
        self.raquete_esq.desenhar(self.tela)
        self.raquete_dir.desenhar(self.tela)
        self.bola.desenhar(self.tela)
        self._desenhar_ui()
        pygame.display.flip()

    def loop(self):
        self.reiniciar_round("dir")
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.processar_inputs(dt)
            self.atualizar(dt)
            self.desenhar()


def main():
    Jogo().loop()

if __name__ == "__main__":
    main()
