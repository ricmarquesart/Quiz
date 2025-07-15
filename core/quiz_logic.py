import random
from collections import defaultdict
import re
import pandas as pd
from core.data_manager import TIPOS_EXERCICIO_ANKI

def get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map):
    """Verifica e retorna todos os tipos de exercícios disponíveis para uma única palavra."""
    exercicios_disponiveis = {}
    if palavra in flashcards_map:
        card = flashcards_map[palavra]
        for tipo_id, func in TIPOS_EXERCICIO_ANKI.items():
            # Usamos o nome da função como identificador único para o tipo de exercício ANKI
            exercicios_disponiveis[func.__name__] = tipo_id
            
    if palavra in gpt_exercicios_map:
        for exercicio_gpt in gpt_exercicios_map[palavra]:
            tipo_exercicio_gpt = exercicio_gpt.get('tipo')
            if tipo_exercicio_gpt:
                # Usamos o tipo do exercício GPT como identificador
                exercicios_disponiveis[tipo_exercicio_gpt] = tipo_exercicio_gpt
    return exercicios_disponiveis

def selecionar_questoes_priorizadas(palavras_df, flashcards_map, gpt_exercicios_map, N, tipo_filtro="Random"):
    """Cria uma lista de questões para o quiz, garantindo a máxima diversidade de palavras."""
    if palavras_df.empty or 'ativo' not in palavras_df.columns:
        return []
    palavras_ativas = palavras_df[palavras_df['ativo']].copy()
    if palavras_ativas.empty:
        return []

    palavras_disponiveis = palavras_ativas.sample(frac=1)
    palavras_selecionadas = palavras_disponiveis.head(N)

    playlist = []
    for _, palavra_info in palavras_selecionadas.iterrows():
        palavra = palavra_info['palavra']
        progresso = palavra_info.get('progresso', {})
        exercicios_da_palavra = get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map)

        exercicios_filtrados = {
            identificador: tipo for identificador, tipo in exercicios_da_palavra.items()
            if tipo_filtro == "Random" or tipo == tipo_filtro
        }
        if not exercicios_filtrados: continue

        alta_prioridade = [{'palavra': palavra, 'tipo_exercicio': tipo, 'identificador': id_ex}
                           for id_ex, tipo in exercicios_filtrados.items() if progresso.get(id_ex, 'nao_testado') != 'acerto']
        baixa_prioridade = [{'palavra': palavra, 'tipo_exercicio': tipo, 'identificador': id_ex}
                            for id_ex, tipo in exercicios_filtrados.items() if progresso.get(id_ex) == 'acerto']

        if alta_prioridade:
            playlist.append(random.choice(alta_prioridade))
        elif baixa_prioridade:
            playlist.append(random.choice(baixa_prioridade))
            
    random.shuffle(playlist)
    return playlist

def gerar_questao_dinamica(item_playlist, flashcards, gpt_exercicios, db_completo):
    """Gera os detalhes de uma questão de forma robusta."""
    palavra = item_playlist['palavra']
    identificador = item_playlist.get('identificador')

    flashcards_map = {card['palavra']: card for card in flashcards if 'palavra' in card}
    
    # Lógica para ANKI
    # Verifica se o identificador corresponde a uma função geradora do ANKI
    anki_generator_func = next((func for func_name, func in TIPOS_EXERCICIO_ANKI.items() if func.__name__ == identificador), None)
    if anki_generator_func:
        cartao = flashcards_map.get(palavra)
        if cartao:
            # Chama a função geradora específica (ex: gerar_mcq_significado)
            return anki_generator_func(cartao, list(flashcards_map.values()))

    # Lógica para GPT
    else:
        for ex in gpt_exercicios:
            # Verifica se o exercício corresponde à palavra e ao tipo (identificador)
            if ex.get('principal') == palavra and ex.get('tipo') == identificador:
                pergunta = ex['frase']
                correta = ex['correta']
                opcoes = ex['opcoes']
                random.shuffle(opcoes)
                if correta not in opcoes and len(opcoes) > 0:
                    opcoes[random.randint(0, len(opcoes)-1)] = correta
                elif correta not in opcoes:
                    opcoes.append(correta)
                ans_idx = opcoes.index(correta)
                return ex['tipo'], pergunta, opcoes, ans_idx, ex.get('cefr_level'), identificador

    return None, None, [], -1, None, None

def selecionar_questoes_gpt(palavras_ativas, gpt_exercicios_map, tipo_filtro, n_palavras, repetir):
    """Cria uma lista de questões para o Quiz GPT."""
    if palavras_ativas.empty: return []

    exercicios_elegiveis = []
    palavras_ativas_set = set(palavras_ativas['palavra'])
    for palavra, exercicios in gpt_exercicios_map.items():
        if palavra in palavras_ativas_set:
            for ex in exercicios:
                if tipo_filtro == "Random" or ex.get('tipo') == tipo_filtro:
                    exercicios_elegiveis.append(ex)
    
    if not exercicios_elegiveis: return []

    playlist = []
    if not repetir:
        random.shuffle(exercicios_elegiveis)
        palavras_ja_usadas = set()
        for ex in exercicios_elegiveis:
            if len(playlist) >= n_palavras: break
            if ex['principal'] not in palavras_ja_usadas:
                playlist.append(ex)
                palavras_ja_usadas.add(ex['principal'])
    else:
        playlist = random.choices(exercicios_elegiveis, k=n_palavras) if len(exercicios_elegiveis) < n_palavras else random.sample(exercicios_elegiveis, k=n_palavras)
            
    return playlist