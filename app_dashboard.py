import pandas as pd
import plotly.express as px
import streamlit as st 
import streamlit_authenticator as stauth 
import yaml 
import funcoes


# --- Configuração e Layout do Streamlit (deve ser a primeira chamada Streamlit) ---
st.set_page_config(
    layout="wide", 
    page_title="Dashboard Financeiro Condomínio",
    menu_items={
        'Get Help': 'mailto:fernandolona117@gmail.com', # Substitua pelo seu e-mail de contato
        'Report a bug': "mailto:fernandolona117@gmail.com", # Ou um link para abrir uma issue no GitHub
        'About': "# Dashboard Financeiro do Condomínio\nEste aplicativo foi desenvolvido para analisar o fluxo de caixa."
    }
)


# --- Configuração da Autenticação ---

# Tenta carregar as credenciais do Streamlit Secrets (para deploy na nuvem)
try:
    # Converte o objeto Secrets em um dicionário Python padrão e mutável
    config_credentials = st.secrets["credentials"].to_dict()
    config_cookie = st.secrets["cookie"].to_dict()
# Se falhar (rodando localmente), carrega do arquivo config.yaml
except (FileNotFoundError, KeyError):
    with open('config.yaml') as file:
        config = yaml.safe_load(file)
    config_credentials = config['credentials']
    config_cookie = config['cookie']

# Cria o objeto autenticador
authenticator = stauth.Authenticate(
    config_credentials,
    config_cookie['name'],
    config_cookie['key'],
    config_cookie['expiry_days']
)

def main_dashboard():
    """
    Função principal que renderiza o dashboard após a autenticação.
    """
    # Adiciona o botão de logout na barra lateral
    authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
    st.sidebar.title(f'Bem-vindo, *{st.session_state["name"]}*')

    # --- Carregamento e Preparação dos Dados (somente após login) ---
    # Caminhos para os arquivos CSV
    #file_path_2025 = r'c:\Condominio\arquivos_csv\FLUXO DE CAIXA 2025.csv' # Usar os.path.join seria mais robusto
    #file_path_2024 = r'c:\Condominio\arquivos_csv\FLUXO DE CAIXA 2024.csv' # Usar os.path.join seria mais robusto
    file_path_2025 = 'arquivos_csv/FLUXO DE CAIXA 2025.csv'
    file_path_2024 = 'arquivos_csv/FLUXO DE CAIXA 2024.csv'

    # Carrega e processa os dados para cada ano
    df_2025 = funcoes.load_and_process_data(file_path_2025, 2025)
    df_2024 = funcoes.load_and_process_data(file_path_2024, 2024)

    # Combina os DataFrames dos dois anos
    df_combined = pd.concat([df for df in [df_2024, df_2025] if df is not None])

    # Define as categorias detalhadas com base nas colunas esperadas do CSV
    # ATENÇÃO: Os nomes devem ser exatamente iguais aos do CSV, incluindo espaços.
    DETAILED_REVENUE_CATEGORIES = ['Cotas Condominiais (Até dia 08)', 'Rendimentos']
    DETAILED_VARIABLE_EXPENSE_CATEGORIES = ['Água (venc. Dia 10)', 'Luz  (venc. Dia 21)', 'Faxina ']
    DETAILED_EXTRA_EXPENSE_CATEGORIES = ['Obras', 'Consertos', 'Outras']

    # Garante que as colunas de categorias detalhadas existam no DataFrame combinado.
    # Se uma coluna estiver faltando em algum dos CSVs, ela será adicionada com valores zero para evitar erros.
    all_detail_cols = DETAILED_REVENUE_CATEGORIES + DETAILED_VARIABLE_EXPENSE_CATEGORIES + DETAILED_EXTRA_EXPENSE_CATEGORIES
    for col in all_detail_cols:
        if col not in df_combined.columns:
            df_combined[col] = 0.0

    if df_combined.empty:
        st.error("Nenhum dado foi carregado. Verifique os caminhos dos arquivos CSV.")
        st.stop()

    st.title("Dashboard Financeiro do Condomínio")
    st.markdown("Análise do fluxo de caixa ao longo dos anos.")

    # --- Sidebar para Filtros ---
    st.sidebar.header("Filtros")

    # Anos disponíveis para seleção
    available_years = sorted(df_combined['Ano'].unique(), reverse=True)
    selected_years = st.sidebar.multiselect(
        "Selecione o(s) Ano(s):",
        options=available_years,
        default=available_years # Seleciona todos por padrão
    )

    # Verifica se algum ano foi selecionado
    if not selected_years:
        st.warning("Por favor, selecione pelo menos um ano para visualizar os dados.")
        st.stop() # Interrompe a execução se nenhum ano for selecionado

    # Filtra o DataFrame com base nos anos selecionados
    filtered_df = df_combined[df_combined['Ano'].isin(selected_years)].copy()

    # Remove meses que não têm dados de 'SALDO Total (Caixa)' para um gráfico mais limpo
    filtered_df_for_plot = filtered_df[filtered_df['SALDO Total (Caixa)'] > 0].copy()

    # --- Conteúdo Principal - Cards de Resumo ---
    st.subheader("Resumo Financeiro")

    # Calcula as métricas de resumo para o período selecionado
    total_receitas = filtered_df_for_plot['RECEITAS'].sum()
    total_despesas_variaveis = filtered_df_for_plot['DESPESAS VARIÁVEIS'].sum()
    total_despesas_extras = filtered_df_for_plot['DESPESAS EXTRAS'].sum()
    total_despesas = total_despesas_variaveis + total_despesas_extras

    # O saldo final é o último saldo disponível no DataFrame filtrado
    saldo_final = filtered_df_for_plot['SALDO Total (Caixa)'].iloc[-1] if not filtered_df_for_plot.empty else 0

    

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Receitas", funcoes.format_currency_brl(total_receitas))
    with col2:
        st.metric("Total de Despesas", funcoes.format_currency_brl(total_despesas))
    with col3:
        st.metric("Saldo Final", funcoes.format_currency_brl(saldo_final))
    with col4:
        st.metric("Média Mensal de Saldo", funcoes.format_currency_brl(filtered_df_for_plot['SALDO Total (Caixa)'].mean()))


    st.markdown("---")

    # --- Conteúdo Principal - Gráficos Gerais ---

    # Gráfico 1: Evolução do Saldo Total
    st.subheader("Evolução do Saldo Total do Caixa")
    fig_saldo = px.line(
        filtered_df_for_plot,
        x='Período',
        y='SALDO Total (Caixa)',
        color='Ano', # Colore as linhas por ano
        title='Evolução do Saldo Total do Caixa',
        markers=True,
        labels={'SALDO Total (Caixa)': 'Saldo (R$)', 'Período': 'Período de Referência'},
        hover_data={'Ano': False, 'Mês': True} # Mostra o Mês no tooltip, esconde o Ano (já está na cor)
    )
    fig_saldo.update_traces(line=dict(width=3))
    st.plotly_chart(fig_saldo, use_container_width=True)

    st.markdown("---")

    # Gráfico 2: Comparativo de Receitas e Despesas
    st.subheader("Comparativo: Receitas vs. Despesas")
    fig_comparativo = px.bar(
        filtered_df_for_plot,
        x='Período',
        y=['RECEITAS', 'DESPESAS VARIÁVEIS', 'DESPESAS EXTRAS'],
        title='Comparativo: Receitas vs. Despesas',
        barmode='group',
        labels={'value': 'Valor (R$)', 'variable': 'Categoria', 'Período': 'Período de Referência'},
        hover_data={'Ano': False, 'Mês': True}
    )
    st.plotly_chart(fig_comparativo, use_container_width=True)

    st.markdown("---")

    # --- Detalhamento por Categoria ---
    st.subheader("Detalhe por Categoria")

    # Dropdown para seleção de mês para a visualização detalhada
    all_periods = sorted(filtered_df['Período'].unique())
    selected_period_detail = st.sidebar.selectbox(
        "Selecione um Mês para Detalhes:",
        options=['Todos os Meses'] + all_periods,
        index=0 # Padrão para 'Todos os Meses'
    )

    if selected_period_detail == 'Todos os Meses':
        df_detail = filtered_df.copy()
        detail_title_suffix = f" (Agregado de {', '.join(map(str, selected_years))})"
    else:
        df_detail = filtered_df[filtered_df['Período'] == selected_period_detail].copy()
        detail_title_suffix = f" ({selected_period_detail})"

    if not df_detail.empty:
        # Prepara os dados para as receitas detalhadas
        df_revenue_detail = df_detail[DETAILED_REVENUE_CATEGORIES].sum().reset_index()
        df_revenue_detail.columns = ['Categoria', 'Valor']
        df_revenue_detail = df_revenue_detail[df_revenue_detail['Valor'] > 0] # Filtra valores zero

        # Prepara os dados para as despesas detalhadas (variáveis e extras)
        all_expense_categories = DETAILED_VARIABLE_EXPENSE_CATEGORIES + DETAILED_EXTRA_EXPENSE_CATEGORIES
        df_expense_detail = df_detail[all_expense_categories].sum().reset_index()
        df_expense_detail.columns = ['Categoria', 'Valor']
        df_expense_detail = df_expense_detail[df_expense_detail['Valor'] > 0]

        col_detail1, col_detail2 = st.columns(2)

        with col_detail1:
            st.markdown(f"#### Receitas Detalhadas{detail_title_suffix}")
            if not df_revenue_detail.empty:
                fig_revenue_pie = px.pie(
                    df_revenue_detail,
                    values='Valor',
                    names='Categoria',
                    title=f'Distribuição das Receitas',
                    hole=0.4 # Para fazer um gráfico de donut
                )
                st.plotly_chart(fig_revenue_pie, use_container_width=True)
            else:
                st.info("Nenhuma receita detalhada para exibir no período selecionado.")

        with col_detail2:
            st.markdown(f"#### Despesas Detalhadas{detail_title_suffix}")
            if not df_expense_detail.empty:
                fig_expense_pie = px.pie(
                    df_expense_detail,
                    values='Valor',
                    names='Categoria',
                    title=f'Distribuição das Despesas',
                    hole=0.4 # Para fazer um gráfico de donut
                )
                st.plotly_chart(fig_expense_pie, use_container_width=True)
            else:
                st.info("Nenhuma despesa detalhada para exibir no período selecionado.")
    else:
        st.info("Nenhum dado disponível para o período selecionado para detalhamento.")


# --- Lógica Principal da Aplicação ---

# Verifica o status da autenticação ANTES de renderizar qualquer coisa
if st.session_state.get("authentication_status"):
    # Se o usuário estiver autenticado, mostra o dashboard
    main_dashboard()
else:
    # Se não estiver autenticado, mostra a tela de login
    authenticator.login(location='main')
    if st.session_state.get("authentication_status") is False:
        st.error('Usuário ou senha incorreto.')
    elif st.session_state.get("authentication_status") is None:
        st.warning('Por favor, insira seu usuário e senha.')