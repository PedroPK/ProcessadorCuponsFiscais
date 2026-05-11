"""
Funções utilitárias compartilhadas entre os módulos do projeto.
"""
import pandas as pd
from pathlib import Path


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


def resolver_danfe(arquivo_origem: str, raiz: Path) -> Path | None:
    """
    Devolve o caminho do DANFE em PDF correspondente a um valor de
    'arquivo_origem' do CSV, ou None se não for possível determinar.

    Regras de resolução
    -------------------
    - ``"nota.xml"``
        → ``resources/outputData/danfe/nota.pdf``
    - ``"notas.zip::consulta.xml"``
        → ``resources/outputData/danfe/notas__consulta.pdf``
    - ``"danfe.pdf"``   (PDF avulso — já é o DANFE)
        → ``resources/notas_fiscais/danfe.pdf``
    - ``"notas.zip::danfe.pdf"``   (PDF dentro de ZIP — não extraível diretamente)
        → None

    Parâmetros
    ----------
    arquivo_origem : str
        Valor da coluna 'arquivo_origem' do CSV.
    raiz : Path
        Diretório raiz do projeto.

    Retorna
    -------
    Path | None
        Caminho absoluto do PDF se existir em disco, caso contrário None.
    """
    if not arquivo_origem:
        return None

    pasta_danfe    = raiz / 'resources' / 'outputData' / 'danfe'
    pasta_notas    = raiz / 'resources' / 'notas_fiscais'

    # Caso: "zip::arquivo" (separador "::")
    if '::' in arquivo_origem:
        zip_nome, interno = arquivo_origem.split('::', 1)
        ext_interno = Path(interno).suffix.lower()

        if ext_interno == '.xml':
            # "notas.zip::consulta.xml" → "notas__consulta.pdf"
            stem_zip    = Path(zip_nome).stem
            stem_xml    = Path(interno).stem
            candidato   = pasta_danfe / f'{stem_zip}__{stem_xml}.pdf'
            return candidato if candidato.exists() else None

        # PDF dentro de ZIP — não temos acesso direto sem extrair
        return None

    # Caso: arquivo avulso
    ext = Path(arquivo_origem).suffix.lower()

    if ext == '.xml':
        # "nota.xml" → "danfe/nota.pdf"
        candidato = pasta_danfe / (Path(arquivo_origem).stem + '.pdf')
        return candidato if candidato.exists() else None

    if ext == '.pdf':
        # PDF avulso — aponta para o original em notas_fiscais/
        candidato = pasta_notas / arquivo_origem
        return candidato if candidato.exists() else None

    return None
