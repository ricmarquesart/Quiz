import random
from collections import defaultdict
import re
import pandas as pd
from core.data_manager import TIPOS_EXERCICIO_ANKI

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
            # Assumindo que a chave 'tipo' identifica o exercício
            tipo_exercicio_gpt = exercicio_gpt.get('tipo')
            if tipo_exercicio_gpt:
                exercicios_disponiveis[tipo_exercicio_gpt] = tipo_exercicio_gpt

    return exercicios_disponiveis


def selecionar_questoes_priorizadas(palavras_df, flashcards_map, gpt_exercicios_map, num_questoes, tipo_exercicio="Random"):
    """Seleciona questões priorizando palavras com erros ou não testadas."""
    
    # --- CORREÇÃO DEFINITIVA PARA KEYERROR ---
    if palavras_df.empty or 'ativo' not in palavras_df.columns:
        return []

    palavras_ativas = palavras_df[palavras_df['ativo']].copy()
    
    if palavras_ativas.empty:
        return []

    playlist = []
    candidatos = []
    
    for _, row in palavras_ativas.iterrows():
        palavra = row['palavra']
        progresso = row.get('progresso', {})
        
        exercicios_disponiveis = get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map)

        for id_exercicio, tipo_gen in exercicios_disponiveis.items():
            if tipo_exercicio == "Random" or tipo_gen == tipo_exercicio or id_exercicio == tipo_exercicio:
                status = progresso.get(id_exercicio, 'nao_testado')
                prioridade = {'erro': 0, 'nao_testado': 1, 'acerto': 2}.get(status, 2)
                candidatos.append({'palavra': palavra, 'tipo_exercicio': tipo_gen, 'identificador': id_exercicio, 'prioridade': prioridade})

    if not candidatos:
        return []

    candidatos.sort(key=lambda x: x['prioridade'])
    
    num_a_selecionar = min(num_questoes, len(candidatos))
    playlist = candidatos[:num_a_selecionar]
    random.shuffle(playlist)
    
    return playlist


def gerar_questao_dinamica(item_playlist, flashcards, gpt_exercicios, db_completo):
    """
    Gera os detalhes de uma questão com alternativas erradas totalmente aleatórias.
    """
    palavra = item_playlist['palavra']
    tipo_exercicio = item_playlist['tipo_exercicio']
    identificador = item_playlist.get('identificador')

    flashcards_map = {card['palavra']: card for card in flashcards if 'palavra' in card}
    
    # Lógica para ANKI
    if tipo_exercicio in TIPOS_EXERCICIO_ANKI.values():
        card = flashcards_map.get(palavra)
        if not card: return None, None, [], -1, None, None

        # Gerar opções de distração
        outras_palavras = list(flashcards_map.keys())
        if palavra in outras_palavras:
            outras_palavras.remove(palavra)
        distracoes = random.sample(outras_palavras, min(3, len(outras_palavras)))
        
        resposta_correta = None
        opcoes_distracao = []
        
        if tipo_exercicio == "gerar_mcq_significado":
            pergunta = f"Qual o significado de **{palavra}**?"
            resposta_correta = card.get('significado')
            opcoes_distracao = [flashcards_map[d].get('significado') for d in distracoes]
        elif tipo_exercicio == "gerar_mcq_traducao_ingles":
            pergunta = f"Qual a tradução de **{palavra}**?"
            resposta_correta = card.get('tradução')
            opcoes_distracao = [flashcards_map[d].get('tradução') for d in distracoes]
        
        if resposta_correta:
            opts = [resposta_correta] + [opt for opt in opcoes_distracao if opt]
            opts = list(dict.fromkeys(opts)) # Remove duplicados
            random.shuffle(opts)
            ans_idx = opts.index(resposta_correta)
            cefr = card.get('cefr', 'N/A')
            return tipo_exercicio, pergunta, opts, ans_idx, cefr, identificador

    # Lógica para GPT
    else:
        for ex in gpt_exercicios:
            if ex.get('principal') == palavra and ex.get('tipo') == tipo_exercicio:
                pergunta = ex['frase']
                correta = ex['correta']
                opcoes = ex['opcoes']
                random.shuffle(opcoes)
                if correta not in opcoes:
                    if len(opcoes) > 0:
                        opcoes[random.randint(0, len(opcoes)-1)] = correta
                    else:
                        opcoes.append(correta)
                ans_idx = opcoes.index(correta)
                cefr = ex.get('cefr_level', 'N/A')
                return ex['tipo'], pergunta, opcoes, ans_idx, cefr, identificador

    return None, None, [], -1, None, None

def selecionar_questoes_gpt(palavras_ativas, gpt_exercicios_map, tipo_filtro, n_palavras, repetir):
    """Cria uma lista de questões para o Quiz GPT com aleatoriedade melhorada."""
    if palavras_ativas.empty: return []

    exercicios_possiveis = []
    palavras_ativas_set = set(palavras_ativas['palavra'].values)
    
    for palavra, exercicios in gpt_exercicios_map.items():
        if palavra in palavras_ativas_set:
            for ex in exercicios:
                if tipo_filtro == "Random" or ex.get('tipo') == tipo_filtro:
                    progresso_palavra = palavras_ativas[palavras_ativas['palavra'] == palavra].iloc[0].get('progresso', {})
                    status = progresso_palavra.get(ex.get('frase'), 'nao_testado')
                    prioridade = 0 if status != 'acerto' else 1
                    exercicios_possiveis.append((prioridade, random.random(), ex))

    exercicios_possiveis.sort()

    playlist = []
    if not repetir:
        palavras_unicas = list(set(ex['principal'] for _, _, ex in exercicios_possiveis))
        random.shuffle(palavras_unicas)
        palavras_selecionadas = palavras_unicas[:n_palavras]
        
        for palavra_sel in palavras_selecionadas:
            questoes_da_palavra = [ex for _, _, ex in exercicios_possiveis if ex['principal'] == palavra_sel]
            if questoes_da_palavra:
                playlist.append(random.choice(questoes_da_palavra))
    else:
        playlist = [ex for _, _, ex in exercicios_possiveis[:n_palavras]]

    random.shuffle(playlist)
    return playlist