import pandas as pd
import numpy as np
from momentum1 import processar_pipeline_momentum

def test_calculo_e_ranking_deterministico():
    
    datas = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04'])
    
    dados = {
        'data': list(datas) * 2 + list(datas)[2:], 
        'ativo': ['A']*4 + ['B']*4 + ['C']*2,
        'preco': [
            100, 110, 120, 130,  
            100, 90,  80,  70,   
            100, 105             
        ]
    }
    df = pd.DataFrame(dados)
    
    
    df_resultado = processar_pipeline_momentum(df, janela=2)
    
   
    dia_final = df_resultado[df_resultado['data'] == '2023-01-04'].set_index('ativo')
    
   
    assert dia_final.loc['A', 'ranking'] == 1.0
    
   
    assert dia_final.loc['B', 'ranking'] == 2.0
    
    
    assert np.isnan(dia_final.loc['C', 'ranking'])
    assert dia_final.loc['C', 'motivo_exclusao'] == 'Histórico insuficiente'

def test_ativos_faltantes():
   
    dados = {
        'data': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-01', '2023-01-02']),
        'ativo': ['A', 'A', 'B', 'B'],
        'preco': [100, 110, 100, 90]
    }
    df = pd.DataFrame(dados)
    

    df_res = processar_pipeline_momentum(df, janela=5)
    

    assert (df_res['motivo_exclusao'] == 'Histórico insuficiente').all()