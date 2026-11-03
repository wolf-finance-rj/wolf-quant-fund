import pandas as pd
import numpy as np


def calcular_momentum_janela(df: pd.DataFrame, col_data: str, col_ativo: str, col_preco: str, janela: int) -> pd.DataFrame:
    
    
    df = df.sort_values(by=[col_ativo, col_data]).copy()
    
   
    df['momentum'] = df.groupby(col_ativo)[col_preco].pct_change(periods=janela)
    
    return df

def ranquear_ativos_cross_sectional(df_momentum: pd.DataFrame, col_data: str, col_ativo: str) -> pd.DataFrame:

    resultados = []
    
    for data, grupo in df_momentum.groupby(col_data):
        grupo = grupo.copy()
        
        
        mask_insuficiente = grupo['momentum'].isna()
        
        
        grupo.loc[mask_insuficiente, 'ranking'] = np.nan
        grupo.loc[mask_insuficiente, 'motivo_exclusao'] = 'Histórico insuficiente'
        
       
        ativos_validos = grupo[~mask_insuficiente].copy()
        ativos_validos['ranking'] = ativos_validos['momentum'].rank(ascending=False, method='min')
        ativos_validos['motivo_exclusao'] = 'Elegível'
        
       
        grupo.update(ativos_validos)
        resultados.append(grupo)
        
    if not resultados:
        return pd.DataFrame()
        
   
    df_final = pd.concat(resultados).sort_values(by=[col_data, 'ranking', col_ativo])
    return df_final

def processar_pipeline_momentum(df_bruto: pd.DataFrame, janela: int = 3) -> pd.DataFrame:
    df_calc = calcular_momentum_janela(df_bruto, 'data', 'ativo', 'preco', janela)
    df_ranqueado = ranquear_ativos_cross_sectional(df_calc, 'data', 'ativo')
    return df_ranqueado