# ESTE ARQUIVO CONTÉM AS FUNÇÕES ADICIONAIS PARA MULTIPROCESSAMENTO E CO-EVOLUÇÃO
# Cole estas funções no pong_neat.py nas posições indicadas

# =========================
# ADICIONAR APÓS LINHA ~260 (depois de ctrl_ai_heuristico)
# =========================

def ctrl_por_rede(neural_net, lado="dir"):
    """
    Controlador baseado em rede neural.
    Usa 8 inputs e 3 outputs (cima, parado, baixo).
    """
    def _norm(v, lo, hi):
        return (v - lo) / (hi - lo) * 2 - 1.0

    def _ctrl(estado):
        # Inputs originais (5)
        bx = _norm(estado["ball_x"], 0, LARGURA)
        by = _norm(estado["ball_y"], 0, ALTURA)
        vx = _norm(estado["ball_vx"], -1000, 1000)
        vy = _norm(estado["ball_vy"], -1000, 1000)
        py = _norm(
            estado["right_y"] if lado == "dir" else estado["left_y"],
            0, ALTURA
        )

        # Novos inputs (3)
        paddle_y = estado["right_y"] if lado == "dir" else estado["left_y"]
        dist_y_norm = by - py
        
        if lado == "dir":
            dist_x = _norm(LARGURA - estado["ball_x"], 0, LARGURA)
        else:
            dist_x = _norm(estado["ball_x"], 0, LARGURA)

        direction_toward_me = 1.0 if (
            (lado == "dir" and estado["ball_vx"] > 0) or
            (lado == "esq" and estado["ball_vx"] < 0)
        ) else -1.0

        # 8 inputs total
        inputs = [bx, by, vx, vy, py, dist_y_norm, dist_x, direction_toward_me]

        # 3 outputs com argmax
        outputs = neural_net.activate(inputs)
        max_idx = outputs.index(max(outputs))
        
        if max_idx == 0: return -1  # Cima
        if max_idx == 2: return +1  # Baixo
        return 0  # Parado

    return _ctrl


def carregar_ctrl_adversario(config, lado_oposto: str, arquivo_pkl: str):
    """
    Carrega adversário NEAT treinado ou retorna heurístico.
    """
    if os.path.exists(arquivo_pkl):
        try:
            with open(arquivo_pkl, "rb") as f:
                campeao = pickle.load(f)
            net_adversario = neat.nn.FeedForwardNetwork.create(campeao, config)
            return ctrl_por_rede(net_adversario, lado=lado_oposto), "NEAT"
        except Exception:
            pass

    # Fallback heurístico
    lag = random.uniform(0.15, 0.35)
    erro = random.uniform(6, 14)
    return ctrl_ai_heuristico(lag=lag, erro=erro, lado=lado_oposto), "HEURISTICA"


# =========================
# ADICIONAR APÓS avaliar_genoma (antes de func_avaliacao)
# =========================

def parallel_wrapper(genome, config_passed):
    """
    Wrapper para ParallelEvaluator.
    """
    fitness = avaliar_genoma(genome, config_passed, render=False)
    return fitness


# =========================
# SUBSTITUIR A FUNÇÃO MAIN COMPLETAMENTE
# =========================

def main():
    base = os.path.dirname(__file__)
    caminho_cfg = os.path.join(base, "config-neat.txt")

    # Parâmetros de treinamento co-evolutivo
    NUM_RODADAS = 1
    GENS_POR_RODADA = 10

    while True:
        modo = menu_inicial()
        if modo == MODO_TREINO:
            treinar_co_evolutivo(caminho_cfg, 
                                 num_rodadas=NUM_RODADAS, 
                                 geracoes_por_rodada=GENS_POR_RODADA)
        else:
            jogar(modo, rede_campeao=None)


def treinar_co_evolutivo(caminho_cfg: str, num_rodadas: int, geracoes_por_rodada: int):
    """
    Treinamento co-evolutivo com bootstrap.
    """
    global geracao, TEMPOS_GERACOES
    
    TEMPOS_GERACOES.clear()
    geracao = 0

    # BOOTSTRAP: Copia melhor_genoma.pkl como base
    if os.path.exists(ARQ_CAMPEAO):
        print(f"\n📚 Bootstrap: Copiando {os.path.basename(ARQ_CAMPEAO)} como base...")
        shutil.copy(ARQ_CAMPEAO, ARQ_IA_1)
        shutil.copy(ARQ_CAMPEAO, ARQ_IA_2)
        print(f"   ✓ IA_1 e IA_2 iniciadas com conhecimento base\n")
    else:
        print(f"\n⚠ {os.path.basename(ARQ_CAMPEAO)} não encontrado - começando do zero\n")

    print(f"\n{'='*60}")
    print(f"TREINAMENTO CO-EVOLUTIVO")
    print(f"{'='*60}")
    print(f"Rodadas: {num_rodadas}")
    print(f"Gerações por rodada: {geracoes_por_rodada}")
    print(f"Total de gerações: {num_rodadas * geracoes_por_rodada * 2}")
    print(f"{'='*60}\n")

    for i in range(1, num_rodadas + 1):
        print(f"\n{'='*60}")
        print(f"RODADA {i}/{num_rodadas}")
        print(f"{'='*60}\n")

        # Treina IA_2 contra IA_1
        print(f"→ Treinando IA_2 contra IA_1...")
        try:
            _treinar_lado(caminho_cfg, ARQ_IA_2, ARQ_IA_1, geracoes_por_rodada)
        except KeyboardInterrupt:
            print(f"\n⚠ Treinamento interrompido na Rodada {i}")
            return

        # Treina IA_1 contra IA_2
        print(f"\n→ Treinando IA_1 contra IA_2...")
        try:
            _treinar_lado(caminho_cfg, ARQ_IA_1, ARQ_IA_2, geracoes_por_rodada)
        except KeyboardInterrupt:
            print(f"\n⚠ Treinamento interrompido na Rodada {i}")
            return

    print(f"\n{'='*60}")
    print(f"✓ TREINAMENTO CO-EVOLUTIVO CONCLUÍDO!")
    print(f"{'='*60}\n")


def _treinar_lado(caminho_config: str, arquivo_saida: str, adversario_pkl: str, geracoes=10):
    """
    Treina uma IA com MULTIPROCESSAMENTO.
    """
    global geracao
    
    config = neat.config.Config(neat.DefaultGenome,
                                neat.DefaultReproduction,
                                neat.DefaultSpeciesSet,
                                neat.DefaultStagnation,
                                caminho_config)

    pop = neat.Population(config)
    pop.add_reporter(neat.StdOutReporter(True))
    pop.add_reporter(neat.StatisticsReporter())

    nome_adversario = os.path.basename(adversario_pkl) if os.path.exists(adversario_pkl) else 'Heurística'
    print(f"   Arquivo de saída: {os.path.basename(arquivo_saida)}")
    print(f"   Adversário: {nome_adversario}")
    print(f"   Gerações: {geracoes}")

    # MULTIPROCESSAMENTO
    num_cores = multiprocessing.cpu_count()
    
    if num_cores > 1:
        evaluator = neat.ParallelEvaluator(num_cores, parallel_wrapper)
        print(f"   🚀 Treinando com {num_cores} núcleos\n")
        campeao = pop.run(evaluator.evaluate, geracoes)
    else:
        print(f"   ⚠ CPU com 1 núcleo - modo sequencial\n")
        campeao = pop.run(func_avaliacao, geracoes)

    with open(arquivo_saida, "wb") as f:
        pickle.dump(campeao, f)

    print(f"\n   ✓ Campeão salvo em {os.path.basename(arquivo_saida)}\n")
    
    return campeao
