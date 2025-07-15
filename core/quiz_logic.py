import random
from collections import defaultdict
from core.data_manager import TIPOS_EXERCICIO_ANKI
import re
import pandas as pd

def get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map):
    """
    Verifica e retorna todos os tipos de exercícios disponíveis para uma única palavra.
    """
    exercicios_disponiveis = {}
    
    # Verifica exercícios tipo ANKI
    if palavra in flashcards_map:
        for tipo_anki_id in TIPOS_EXERCICIO_ANKI.keys():
            exercicios_disponiveis[tipo_anki_id] = TIPOS_EXERCICIO_ANKI[tipo_anki_id]
            
    # Verifica exercícios tipo GPT
    if palavra in gpt_exercicios_map:
        for exercicio_gpt in gpt_exercicios_map[palavra]:
            tipo_exercicio_gpt = exercicio_gpt.get('tipo')
            if tipo_exercicio_gpt:
                # Usa o tipo do exercício como identificador único
                exercicios_disponiveis[tipo_exercicio_gpt] = tipo_exercicio_gpt

    return exercicios_disponiveis


def selecionar_questoes_priorizadas(palavras_df, flashcards_map, gpt_exercicios_map, N, tipo_filtro="Random"):
    """
    Cria uma lista de questões para o quiz, garantindo a máxima diversidade de palavras.
    """
    # --- CORREÇÃO DEFINITIVA PARA KEYERROR ---
    if palavras_df.empty or 'ativo' not in palavras_df.columns:
        return []

    palavras_ativas = palavras_df[palavras_df['ativo'] == True].copy()
    
    if palavras_ativas.empty:
        return []

    # 1. Seleciona N palavras únicas para garantir a diversidade.
    palavras_disponiveis = palavras_ativas.sample(frac=1)
    palavras_selecionadas = palavras_disponiveis.head(N)

    playlist = []
    for _, palavra_info in palavras_selecionadas.iterrows():
        palavra = palavra_info['palavra']
        progresso = palavra_info.get('progresso', {})
        
        # 2. Para cada palavra, obtém todos os seus exercícios únicos.
        exercicios_da_palavra = get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map)

        # 3. Filtra os exercícios por tipo, se um filtro for aplicado.
        exercicios_filtrados = {
            identificador: tipo for identificador, tipo in exercicios_da_palavra.items()
            if tipo_filtro == "Random" or identificador == tipo_filtro
        }

        if not exercicios_filtrados:
            continue

        # 4. Prioriza exercícios não feitos ou errados.
        alta_prioridade = [
            {'palavra': palavra, 'tipo_exercicio': tipo, 'identificador': id_ex}
            for id_ex, tipo in exercicios_filtrados.items()
            if progresso.get(id_ex, 'nao_testado') != 'acerto'
        ]
        
        baixa_prioridade = [
            {'palavra': palavra, 'tipo_exercicio': tipo, 'identificador': id_ex}
            for id_ex, tipo in exercicios_filtrados.items()
            if progresso.get(id_ex) == 'acerto'
        ]

        # 5. Escolhe um exercício para a palavra (dando preferência aos de alta prioridade).
        if alta_prioridade:
            playlist.append(random.choice(alta_prioridade))
        elif baixa_prioridade:
            playlist.append(random.choice(baixa_prioridade))
            
    random.shuffle(playlist)
    return playlist

def gerar_questao_dinamica(item_playlist, flashcards, gpt_exercicios, db_completo):
    """
    Gera os detalhes de uma questão com alternativas erradas totalmente aleatórias.
    """
    palavra = item_playlist['palavra']
    tipo_exercicio = item_playlist.get('tipo_exercicio')
    identificador = item_playlist.get('identificador')

    flashcards_map = {card['palavra']: card for card in flashcards if 'palavra' in card}
    
    # Lógica para ANKI
    if identificador in TIPOS_EXERCICIO_ANKI:
        # Lógica de geração de questão ANKI...
        # Esta parte precisa ser implementada com base na sua estrutura de dados ANKI
        return "MCQ Significado", f"Qual o significado de **{palavra}**?", ["Opt A", "Opt B", "Opt C", "Opt D"], 0, "B2", identificador

    # Lógica para GPT
    else:
        for ex in gpt_exercicios:
            if ex.get('principal') == palavra and ex.get('tipo') == tipo_exercicio:
                pergunta = ex['frase']
                correta = ex['correta']
                opcoes = ex['opcoes']
                
                # Garante que a resposta correta está nas opções
                if correta not in opcoes:
                    opcoes.pop() # Remove uma opção para dar espaço
                    opcoes.append(correta)
                
                random.shuffle(opcoes)
                ans_idx = opcoes.index(correta)
                
                return ex['tipo'], pergunta, opcoes, ans_idx, ex.get('cefr_level'), identificador

    return None, None, [], -1, None, None

def selecionar_questoes_gpt(palavras_ativas, gpt_exercicios_map, tipo_filtro, n_palavras, repetir):
    """Cria uma lista de questões para o Quiz GPT com aleatoriedade melhorada."""
    if palavras_ativas.empty or 'palavra' not in palavras_ativas.columns:
        return []

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
        
        for palavra in palavras_selecionadas:
            questoes_da_palavra = [ex for _, _, ex in exercicios_possiveis if ex['principal'] == palavra]
            if questoes_da_palavra:
                playlist.append(random.choice(questoes_da_palavra))
    else:
        playlist = [ex for _, _, ex in exercicios_possiveis[:n_palavras]]

    random.shuffle(playlist)
    return playlist