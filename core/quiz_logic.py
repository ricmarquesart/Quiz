# core/quiz_logic.py

import random
from collections import defaultdict
from core.data_manager import TIPOS_EXERCICIO_ANKI

# --- FUNCTION MOVED HERE ---
def get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map):
    """
    Verifica e retorna todos os tipos de exercícios disponíveis para uma única palavra.
    """
    exercicios_disponiveis = {}
    
    # Verifica exercícios tipo ANKI
    if palavra in flashcards_map:
        for tipo_anki_id, tipo_anki_nome in TIPOS_EXERCICIO_ANKI.items():
            exercicios_disponiveis[tipo_anki_id] = tipo_anki_nome
            
    # Verifica exercícios tipo GPT
    if palavra in gpt_exercicios_map:
        for exercicio_gpt in gpt_exercicios_map[palavra]:
            for key in exercicio_gpt:
                # Assumindo que as chaves dos exercícios são os identificadores
                if key not in ['palavra', 'source', 'texto_cloze']:
                     exercicios_disponiveis[key] = key # Usa a própria chave como tipo

    return exercicios_disponiveis


def selecionar_questoes_priorizadas(palavras_df, flashcards_map, gpt_exercicios_map, num_questoes, tipo_exercicio="Random"):
    """Seleciona questões priorizando palavras com erros ou não testadas."""
    playlist = []
    candidatos = []

    palavras_ativas = palavras_df[palavras_df['ativa']].copy()
    
    for _, row in palavras_ativas.iterrows():
        palavra = row['palavra']
        progresso = row.get('progresso', {})
        
        exercicios_disponiveis = get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map)

        for id_exercicio, tipo_gen in exercicios_disponiveis.items():
            if tipo_exercicio == "Random" or tipo_gen == tipo_exercicio:
                status = progresso.get(id_exercicio, 'nao_testado')
                prioridade = {'erro': 0, 'nao_testado': 1, 'acerto': 2}.get(status, 2)
                candidatos.append({'palavra': palavra, 'tipo_exercicio': tipo_gen, 'identificador': id_exercicio, 'prioridade': prioridade})

    candidatos.sort(key=lambda x: x['prioridade'])
    
    if not candidatos:
        return []

    playlist = candidatos[:num_questoes]
    random.shuffle(playlist)
    
    return playlist


def gerar_questao_dinamica(item_playlist, flashcards_map, gpt_map, db_df):
    """Gera uma pergunta e opções dinamicamente com base no tipo de exercício."""
    palavra = item_playlist['palavra']
    tipo = item_playlist['tipo_exercicio']
    id_ex = item_playlist['identificador']
    
    pergunta, opts, ans_idx, cefr = "", [], None, "N/A"
    
    # Dados da palavra
    word_info = db_df[db_df['palavra'] == palavra].iloc[0]
    cefr = word_info.get('cefr', 'N/A')

    # Lógica para exercícios ANKI
    if tipo in TIPOS_EXERCICIO_ANKI.values():
        card = flashcards_map.get(palavra)
        if not card: return None, None, None, None, None, None

        # Gerar opções de distração
        outras_palavras = list(flashcards_map.keys())
        outras_palavras.remove(palavra)
        distracoes = random.sample(outras_palavras, min(3, len(outras_palavras)))
        
        if tipo == "gerar_mcq_significado":
            pergunta = f"Qual o significado de **{palavra}**?"
            opts = [card.get('definicao', '')] + [flashcards_map[d].get('definicao', '') for d in distracoes]
        elif tipo == "gerar_mcq_traducao_ingles":
            pergunta = f"Qual a tradução de **{palavra}**?"
            opts = [card.get('traducao', '')] + [flashcards_map[d].get('traducao', '') for d in distracoes]
        # Adicione outras lógicas de geração ANKI aqui...

    # Lógica para exercícios GPT
    else:
        exercicios_da_palavra = gpt_map.get(palavra, [])
        exercicio_especifico = next((ex.get(tipo) for ex in exercicios_da_palavra if tipo in ex), None)

        if exercicio_especifico:
            pergunta = exercicio_especifico.get('pergunta')
            opts = exercicio_especifico.get('opcoes', [])
            resposta_correta_str = exercicio_especifico.get('resposta')
            if resposta_correta_str in opts:
                ans_idx = opts.index(resposta_correta_str)

    if opts and ans_idx is not None:
        random.shuffle(opts)
        ans_idx = opts.index(pergunta) # Encontra o novo índice da resposta correta após embaralhar

    return tipo, pergunta, opts, ans_idx, cefr, id_ex

def selecionar_questoes_gpt(palavras_df, gpt_exercicios_map, tipo_exercicio, n_palavras, repetir_palavra):
    """Seleciona questões especificamente do pool GPT."""
    palavras_disponiveis = [p for p in gpt_exercicios_map if p in set(palavras_df['palavra'].values)]
    if not palavras_disponiveis:
        return []

    palavras_selecionadas = random.sample(palavras_disponiveis, min(n_palavras, len(palavras_disponiveis)))
    
    playlist = []
    for palavra in palavras_selecionadas:
        exercicios_da_palavra = gpt_exercicios_map[palavra]
        
        exercicios_candidatos = []
        for ex in exercicios_da_palavra:
            if tipo_exercicio == "Random":
                exercicios_candidatos.extend(ex.values())
            elif ex.get('tipo') == tipo_exercicio:
                exercicios_candidatos.append(ex)
        
        if not exercicios_candidatos:
            continue
            
        if repetir_palavra:
            playlist.extend(exercicios_candidatos)
        else:
            playlist.append(random.choice(exercicios_candidatos))
            
    random.shuffle(playlist)
    return playlist