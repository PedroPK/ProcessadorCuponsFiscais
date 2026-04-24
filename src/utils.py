"""
Funções utilitárias compartilhadas entre os módulos do projeto.
"""
import pandas as pd


def filtrar_produtos(df: pd.DataFrame, busca: str) -> pd.DataFrame:
    """
    Filtra o DataFrame pelo campo 'produto' usando busca por tokens.

    Cada palavra da string de busca é aplicada como um filtro independente
    (lógica AND), o que permite encontrar "LEITE NINHO 750G INT" ao digitar
    "leite ninho 750 int" — mesmo que os termos não sejam substrings contíguas.

    Parâmetros
    ----------
    df : pd.DataFrame
        DataFrame com ao menos a coluna 'produto'.
    busca : str
        Texto digitado pelo usuário. Vazio ou só espaços retorna o df inteiro.

    Retorna
    -------
    pd.DataFrame
        Subconjunto das linhas cujo 'produto' contém todos os tokens.
    """
    if not busca or not busca.strip():
        return df

    tokens = busca.strip().split()
    mask = pd.Series(True, index=df.index)
    for token in tokens:
        mask &= df['produto'].str.contains(token, case=False, na=False, regex=False)
    return df[mask]
