import pandas as pd
import plotly.express as px
import streamlit as st 
import streamlit_authenticator as stauth
import io
import yaml 
import funcoes
import os
from datetime import datetime
import re
import fitz # PyMuPDF


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


# --- CONSTANTES GLOBAIS DE CATEGORIAS ---
DETAILED_REVENUE_CATEGORIES = ['Cotas Condominiais (Até dia 08)', 'Rendimentos']
DETAILED_VARIABLE_EXPENSE_CATEGORIES = ['Água (venc. Dia 10)', 'Luz  (venc. Dia 21)', 'Faxina ']
ORIGINAL_EXTRA_EXPENSE_CATEGORIES = ['Obras', 'Consertos', 'Outros']
UPDATED_EXTRA_EXPENSE_CATEGORIES = ['Obras', 'Consertos e Outros']


# --- Carregamento de Dados Iniciais ---
@st.cache_data
def load_moradores_mapping(path):
    """Carrega o mapeamento de nomes de moradores para apartamentos de um arquivo YAML."""
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file).get('mapeamento', {})
    except Exception as e:
        st.error(f"Não foi possível carregar o arquivo de mapeamento de moradores: {e}")
        return {}

# --- Configuração da Autenticação ---

# Tenta carregar as credenciais do Streamlit Secrets (para deploy na nuvem)
try:
    # Converte o objeto Secrets em um dicionário Python padrão e mutável
    config_credentials = st.secrets["credentials"].to_dict()
    config_cookie = st.secrets["cookie"].to_dict()
# Se falhar (rodando localmente), carrega do arquivo secrets.yaml
except (FileNotFoundError, KeyError):
    with open('secrets.yaml') as file:
        config = yaml.safe_load(file)
    config_credentials = config['credentials']
    config_cookie = config['cookie']

# Cria o objeto autenticador
# A biblioteca armazena os detalhes do usuário em config_credentials['usernames']
authenticator = stauth.Authenticate(
    config_credentials,
    config_cookie['name'],
    config_cookie['key'],
    config_cookie['expiry_days']
)

def render_admin_page():
    """
    Renderiza a página de gerenciamento de usuários, visível apenas para administradores.
    """
    st.title("Gerenciamento de Usuários")

    st.subheader("Registrar Novo Usuário")

    try:
        # Formulário para registrar um novo usuário
        if authenticator.register_user('Registrar usuário', location='main'):
            st.success('Usuário registrado com sucesso!')
            
            # ATENÇÃO: A biblioteca atualiza o dicionário 'config_credentials' em memória.
            # Para persistir a mudança na nuvem, o admin precisa atualizar os Secrets.
            # Vamos exibir o novo conteúdo para ser copiado.
            
            # Converte o dicionário Python atualizado para o formato YAML para fácil leitura
            updated_yaml = yaml.dump({'credentials': config_credentials})
            
            st.subheader("Atualize seus 'Secrets' no Streamlit Cloud")
            st.info("Para que o novo usuário seja permanente, copie o texto abaixo e cole na seção 'Secrets' do seu aplicativo, substituindo o conteúdo de 'credentials'. Lembre-se de converter para o formato TOML.")
            st.code(updated_yaml, language='yaml')

    except Exception as e:
        st.error(e)

    # Futuramente, podemos adicionar aqui a funcionalidade de listar e remover usuários.
    st.subheader("Usuários Existentes")
    st.write(list(config_credentials['usernames'].keys()))

def style_dataframe(df):
    """Aplica a formatação de moeda a um DataFrame."""
    # Aplica a formatação a todas as colunas
    return df.style.format(funcoes.format_currency_brl, na_rep='-')

def render_fluxo_caixa_page():
    """
    Renderiza uma página para visualizar as tabelas de dados do Fluxo de Caixa.
    """
    st.title("Visualização de Dados: Fluxo de Caixa")
    excel_master_path = 'planilhas/Contabilidade Condominio.xlsx'

    try:
        xls = pd.ExcelFile(excel_master_path)
        sheet_names = xls.sheet_names
        year_pattern = re.compile(r'(\d{4})')

        for sheet in sheet_names:
            match = year_pattern.search(sheet)
            if match and "fluxo de caixa" in sheet.lower():
                with st.expander(f"Dados da Planilha: {sheet}"):
                    # Carrega a planilha pulando as linhas de cabeçalho
                    df_full_raw = pd.read_excel(excel_master_path, sheet_name=sheet, skiprows=4, index_col=0)
                    
                    # Cria um grupo para cada bloco de linhas separado por uma linha nula
                    # Uma linha nula no índice indica a separação
                    group_ids = (df_full_raw.index.isna()).cumsum()
                    
                    # Agrupa por esses IDs e exibe cada grupo como uma tabela separada
                    for _, group_df in df_full_raw.groupby(group_ids):
                        # Remove a linha nula (se houver) e aplica o estilo
                        st.dataframe(style_dataframe(group_df.dropna(how='all').fillna(0)))

    except FileNotFoundError:
        st.error(f"Arquivo mestre não encontrado em: '{excel_master_path}'")
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar os dados do fluxo de caixa: {e}")



def render_upload_page():
    """
    Renderiza a página para upload e processamento de comprovantes em PDF.
    """
    st.title("Upload e Análise de Comprovantes")

    uploaded_file = st.file_uploader(
        "Escolha um arquivo PDF", 
        type="pdf",
        help="Faça o upload de um comprovante de depósito ou pagamento."
    )

    if uploaded_file is not None:
        try:
            # --- 1. Salvar o arquivo PDF no diretório 'comprovantes' ---
            comprovantes_dir = "comprovantes"
            os.makedirs(comprovantes_dir, exist_ok=True) # Cria o diretório se não existir

            # Cria um nome de arquivo único com timestamp para evitar sobreposição
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Limpa o nome do arquivo original para segurança
            safe_filename = "".join(c for c in uploaded_file.name if c.isalnum() or c in ('.', '_')).rstrip()
            new_filename = f"{timestamp}_{safe_filename}"
            save_path = os.path.join(comprovantes_dir, new_filename)

            # Salva o arquivo no disco
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"Comprovante '{uploaded_file.name}' salvo com sucesso!")

            # Lê o conteúdo do arquivo em memória
            pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            
            text = ""
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text += page.get_text()

            st.subheader("Texto Extraído do PDF")
            st.text_area("Conteúdo", text, height=300)

            # --- PRÓXIMO PASSO: Análise do Texto com Regex ---
            st.subheader("Informações Encontradas (Análise Preliminar)")

            # Padrões de Regex para encontrar informações
            # Padrão para valor em R$ (ex: 1.234,56)
            padrao_valor = r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
            # Padrão para data no formato dd/mm/yyyy
            padrao_data = r'\b(\d{2}/\d{2}/\d{4})\b'

            # Encontra todas as ocorrências dos padrões no texto
            valores_encontrados = re.findall(padrao_valor, text)
            datas_encontradas = re.findall(padrao_data, text)

            # --- Identificação do Apartamento ---
            moradores_map = load_moradores_mapping('moradores.yaml')
            apartamento_encontrado = None
            nome_encontrado = None

            for nome, apto in moradores_map.items():
                # Procura pelo nome do morador no texto do PDF (ignorando maiúsculas/minúsculas)
                if re.search(nome, text, re.IGNORECASE):
                    apartamento_encontrado = apto
                    nome_encontrado = nome
                    break # Para no primeiro nome que encontrar

            col1, col2, col3 = st.columns(3)
            with col1:
                st.write("**Valores (R$):**")
                st.write(valores_encontrados[0] if valores_encontrados else "Nenhum valor encontrado.")
            with col2:
                st.write("**Datas:**")
                unique_datas = list(set(datas_encontradas))
                st.write(unique_datas[0] if unique_datas else "Nenhuma data encontrada.")
            with col3:
                st.write("**Morador Identificado:**")
                st.write(f"{nome_encontrado} (Apto: {apartamento_encontrado})" if nome_encontrado else "Nenhum morador identificado.")

            # --- Formulário para Confirmação e Classificação ---
            if valores_encontrados and datas_encontradas:
                st.markdown("---")
                st.subheader("Confirmar e Lançar Transação")

                # Define as categorias possíveis para o lançamento

                with st.form("lancamento_form"):
                    st.write("Por favor, confirme os dados extraídos e classifique a transação.")
                    
                    # Seleciona o valor principal (geralmente o primeiro ou o maior)
                    valor_selecionado = st.selectbox("Valor da Transação (R$)", options=valores_encontrados)
                    
                    # Seleciona a data da transação
                    data_selecionada = st.selectbox("Data da Transação", options=list(set(datas_encontradas))) # Usa set para remover datas duplicadas

                    # Lógica condicional para a categoria
                    username = st.session_state.get("username")
                    if username == 'felona117':
                        categoria_selecionada = 'Cotas Condominiais (Até dia 08)'
                        st.info(f"Categoria definida automaticamente: **{categoria_selecionada}**")
                    else:
                        todas_categorias = DETAILED_REVENUE_CATEGORIES + DETAILED_VARIABLE_EXPENSE_CATEGORIES + ORIGINAL_EXTRA_EXPENSE_CATEGORIES
                        categoria_selecionada = st.selectbox("Categoria", options=todas_categorias)

                    # Cria colunas para o botão e a mensagem
                    col_btn, col_msg = st.columns([1, 2])
                    with col_btn:
                        # O botão é desabilitado, então 'submitted' será sempre False
                        submitted = st.form_submit_button("Lançar no Sistema", disabled=True)
                    with col_msg:
                        st.info("Funcionalidade de lançamento em desenvolvimento.")

                    # A lógica abaixo é mantida, mas não será executada porque o botão está desabilitado.
                    if submitted:
                        if apartamento_encontrado:
                            try:
                                # Converte valor para float
                                valor_float = float(valor_selecionado.replace('.', '').replace(',', '.'))
                                # Converte data para objeto datetime
                                data_obj = datetime.strptime(data_selecionada, '%d/%m/%Y')

                                # Chama a função para atualizar o arquivo Excel
                                excel_path = 'planilhas/Contabilidade Condominio.xlsx'
                                success, message = funcoes.update_taxa_condominio(
                                    excel_path, 'TaxaCondominio', apartamento_encontrado, data_obj, valor_float
                                )

                                if success:
                                    st.success(message)
                                    st.cache_data.clear() # Limpa o cache para forçar a releitura dos dados
                                else:
                                    st.error(message)
                            except Exception as e:
                                st.error(f"Erro ao processar o lançamento: {e}")
                        else:
                            st.error("Não foi possível identificar um morador no comprovante. Lançamento não realizado.")

        except Exception as e:
            st.error(f"Ocorreu um erro ao processar o PDF: {e}")

def render_cotas_dashboard():
    """
    Renderiza o dashboard de análise das cotas condominiais pagas.
    """
    st.title("Cotas do Condomínio")

    excel_master_path = 'planilhas/Contabilidade Condominio.xlsx'
    sheet_name_cotas = "TaxaCondominio"

    try:
        # Carrega os dados da aba específica, pulando as 4 primeiras linhas para encontrar o cabeçalho correto.
        df_cotas_raw = pd.read_excel(excel_master_path, sheet_name=sheet_name_cotas, skiprows=3, index_col=0, header=0)
        df_cotas_raw = df_cotas_raw.dropna(how='all').dropna(axis=1, how='all') # Remove linhas e colunas vazias

        # --- Limpeza Adicional: Remove linhas/colunas de totais ---
        # Remove a linha de 'Total' se ela existir no índice (muito comum em planilhas)
        if 'Total' in df_cotas_raw.index:
            df_cotas_raw = df_cotas_raw.drop('Total')

        # Remove a coluna 'Total' se ela existir
        if 'Total' in df_cotas_raw.columns:
            df_cotas_raw = df_cotas_raw.drop(columns=['Total'])

        # Garante que o índice e as colunas sejam do tipo string para evitar erros e avisos
        # Itera sobre as colunas e formata aquelas que são do tipo datetime para o formato 'Mês/Ano'
        new_columns = []
        for col in df_cotas_raw.columns:
            if isinstance(col, datetime):
                # Formata a data para 'MêsAbreviado/AnoCurto' (ex: 'Jan/25')
                new_columns.append(col.strftime('%b/%y'))
            else:
                new_columns.append(str(col))
        df_cotas_raw.columns = new_columns
        df_cotas_raw.index = df_cotas_raw.index.astype(str)

        # --- Transformação dos Dados (Unpivot) ---
        # Transforma o DataFrame do formato largo para o formato longo
        df_cotas = df_cotas_raw.reset_index().melt(
            id_vars=df_cotas_raw.index.name,
            var_name='Mês Referência',
            value_name='Valor Pago'
        )
        # Renomeia a coluna de apartamentos se necessário
        df_cotas.rename(columns={df_cotas.columns[0]: 'Apartamento'}, inplace=True)
        
        # Limpa e converte a coluna 'Valor Pago' para numérico, tratando erros
        df_cotas['Valor Pago'] = pd.to_numeric(df_cotas['Valor Pago'], errors='coerce').fillna(0)
        
        st.markdown("### Visão Geral dos Pagamentos")
        # Preenche valores nulos com 0 e aplica a formatação de moeda
        st.dataframe(
            df_cotas_raw.fillna(0)
        )

        st.markdown("---")
        st.subheader("Total Arrecadado por Mês de Referência")
        pagamentos_por_mes = df_cotas.groupby('Mês Referência')['Valor Pago'].sum().reset_index()
        pagamentos_por_mes = pagamentos_por_mes[pagamentos_por_mes['Valor Pago'] > 0] # Remove meses sem arrecadação
        
        # Ordena os meses corretamente se eles tiverem um formato que permita ordenação
        try:
            # Converte a coluna de meses para um formato de data real para ordenação
            # e cria uma nova coluna para o texto do rótulo (ex: 'Jan/24')
            pagamentos_por_mes['sort_key'] = pd.to_datetime(pagamentos_por_mes['Mês Referência'], format='%b/%y', errors='coerce')
            pagamentos_por_mes.dropna(subset=['sort_key'], inplace=True) # Remove meses que não puderam ser convertidos
            pagamentos_por_mes.sort_values(by='sort_key', inplace=True)
        except Exception:
            pass # Se a conversão de data falhar, usa a ordem alfabética padrão

        if not pagamentos_por_mes.empty:
            fig = px.bar(pagamentos_por_mes, x='Mês Referência', y='Valor Pago', title='Total Arrecadado por Mês', text_auto='.2s')
            fig.update_traces(textangle=0, textposition="outside")
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False})
        else:
            st.info("Não há dados de arrecadação para exibir no gráfico.")

    except FileNotFoundError:
        st.error(f"Arquivo mestre não encontrado em: '{excel_master_path}'")
    except ValueError:
        st.error(f"Aba '{sheet_name_cotas}' não encontrada na planilha. Por favor, verifique o nome exato da aba.")

def render_full_dashboard():
    """
    Função que renderiza o dashboard completo para administradores.
    """

    # --- Carregamento e Preparação dos Dados (somente após login) ---
    # Caminhos para os arquivos CSV
    # Aponta para o único arquivo Excel mestre
    excel_master_path = 'planilhas/Contabilidade Condominio.xlsx'

    # --- Carregamento Dinâmico de Abas ---
    all_dfs = []
    try:
        xls = pd.ExcelFile(excel_master_path)
        sheet_names = xls.sheet_names
        year_pattern = re.compile(r'(\d{4})') # Padrão para encontrar um ano de 4 dígitos

        for sheet in sheet_names:
            match = year_pattern.search(sheet)
            if match and "fluxo de caixa" in sheet.lower():
                year = int(match.group(1))
                df = funcoes.load_and_process_data(excel_master_path, sheet, year)
                if df is not None:
                    all_dfs.append(df)
    except FileNotFoundError:
        st.error(f"Arquivo mestre não encontrado em: '{excel_master_path}'")
        st.stop()

    df_combined = pd.concat(all_dfs) if all_dfs else pd.DataFrame()

    # Adiciona uma verificação para garantir que os dados foram carregados
    if df_combined.empty:
        st.error("Nenhuma aba com um ano no nome (ex: 'Fluxo de Caixa 2024') foi encontrada ou carregada com sucesso da planilha.")
        st.stop()

    # Garante que as colunas de categorias detalhadas existam no DataFrame combinado.
    # Se uma coluna estiver faltando em algum dos CSVs, ela será adicionada com valores zero para evitar erros.
    all_detail_cols = DETAILED_REVENUE_CATEGORIES + DETAILED_VARIABLE_EXPENSE_CATEGORIES + ORIGINAL_EXTRA_EXPENSE_CATEGORIES
    for col in all_detail_cols:
        if col not in df_combined.columns:
            df_combined[col] = 0.0

    # Cria a nova coluna somando 'Consertos' e 'Outros'
    df_combined['Consertos e Outros'] = df_combined['Consertos'] + df_combined['Outros']

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

    # Dropdown para seleção de mês para a visualização detalhada
    all_periods = sorted(filtered_df['Período'].unique())
    selected_period_detail = st.sidebar.selectbox(
        "Selecione um Mês para Detalhes:",
        options=['Todos os Meses'] + all_periods,
        index=0 # Padrão para 'Todos os Meses'
    )

    # --- Botão de Download da Planilha Estática ---
    # ATENÇÃO: Substitua 'NOME_DA_SUA_PLANILHA.xlsx' pelo nome real do seu arquivo.
    planilha_path = 'planilhas/Contabilidade Condominio.xlsx'

    try:
        with open(planilha_path, "rb") as fp:
            st.sidebar.download_button(
                label="📥 Baixar Planilha Original",
                data=fp,
                file_name="planilha_condominio.xlsx", # Nome que o arquivo terá no download
                mime="application/vnd.ms-excel"
            )
    except FileNotFoundError:
        st.sidebar.error(f"Arquivo não encontrado em: {planilha_path}")

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

    # SUGESTÃO 1: Usar duas linhas de duas colunas para melhor responsividade em celulares.
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Receitas", funcoes.format_currency_brl(total_receitas))
    with col2:
        st.metric("Total de Despesas", funcoes.format_currency_brl(total_despesas))
    with col3:
        st.metric("Saldo Final", funcoes.format_currency_brl(saldo_final))

    # col3, col4 = st.columns(2)
    # with col3:
    #     st.metric("Saldo Final", funcoes.format_currency_brl(saldo_final))
    # with col4:
    #     st.metric("Média Mensal de Saldo", funcoes.format_currency_brl(filtered_df_for_plot['SALDO Total (Caixa)'].mean()))


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
    st.plotly_chart(fig_saldo, use_container_width=True, config={'scrollZoom': False})

    st.markdown("---")

    # Gráfico 2: Comparativo de Receitas e Despesas
    st.subheader("Comparativo: Receitas vs. Despesas")
    # SUGESTÃO 2: Mudar para 'stack' para melhor visualização em telas pequenas.
    fig_comparativo = px.bar(
        filtered_df_for_plot,
        x='Período',
        y=['RECEITAS', 'DESPESAS VARIÁVEIS', 'DESPESAS EXTRAS'],
        title='Comparativo: Receitas vs. Despesas',
        barmode='stack',
        labels={'value': 'Valor (R$)', 'variable': 'Categoria', 'Período': 'Período de Referência'},
        hover_data={'Ano': False, 'Mês': True}
    )
    st.plotly_chart(fig_comparativo, use_container_width=True, config={'scrollZoom': False})

    st.markdown("---")

    # --- Detalhamento por Categoria ---
    st.subheader("Detalhe por Categoria")

    if selected_period_detail == 'Todos os Meses':
        df_detail = filtered_df.copy()
        detail_title_suffix = f" ({', '.join(map(str, selected_years))})"
    else:
        df_detail = filtered_df[filtered_df['Período'] == selected_period_detail].copy()
        detail_title_suffix = f" ({selected_period_detail})"

    if not df_detail.empty:
        # Prepara os dados para as receitas detalhadas
        df_revenue_detail = df_detail[DETAILED_REVENUE_CATEGORIES].sum().reset_index()
        df_revenue_detail.columns = ['Categoria', 'Valor']
        df_revenue_detail = df_revenue_detail[df_revenue_detail['Valor'] > 0] # Filtra valores zero

        # Prepara os dados para as despesas detalhadas (variáveis e extras)
        # Define as categorias de despesa para o gráfico, usando a nova coluna combinada
        all_expense_categories = DETAILED_VARIABLE_EXPENSE_CATEGORIES + UPDATED_EXTRA_EXPENSE_CATEGORIES

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
                st.plotly_chart(fig_revenue_pie, use_container_width=True, config={'scrollZoom': False})
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
                st.plotly_chart(fig_expense_pie, use_container_width=True, config={'scrollZoom': False})
            else:
                st.info("Nenhuma despesa detalhada para exibir no período selecionado.")
    else:
        st.info("Nenhum dado disponível para o período selecionado para detalhamento.")

def main_dashboard():
    """
    Função principal que atua como um roteador, verificando a role do usuário
    e renderizando a visualização apropriada.
    """
    # Adiciona o botão de logout na barra lateral para todos os usuários logados
    authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
    st.sidebar.title(f'Bem-vindo, *{st.session_state["name"]}*')

    # Verifica se o usuário ainda está autenticado após o logout
    if not st.session_state.get("authentication_status"):
        return

    # Pega o nome de usuário da sessão
    username = st.session_state["username"]
    # Busca a role do usuário no dicionário de credenciais
    user_role = config_credentials['usernames'][username].get('role', 'user')  # Padrão para 'user'

    # Define as páginas disponíveis para cada tipo de usuário
    admin_pages = {
        "Dashboard Principal": render_full_dashboard,
        "Fluxo de Caixa (Dados)": render_fluxo_caixa_page,
        "Gerenciar Usuários": render_admin_page,
        "Upload de Comprovantes": render_upload_page,
        "Condominio Mensal": render_cotas_dashboard
    }
    user_pages = {
        "Dashboard Principal": render_full_dashboard,
        "Fluxo de Caixa (Dados)": render_fluxo_caixa_page,
        "Upload de Comprovantes": render_upload_page,
        "Condominio Mensal": render_cotas_dashboard
    }

    # Define as páginas com base na role
    if user_role == 'admin':
        st.sidebar.success("Você está logado como **Administrador**.")
        pages_to_show = admin_pages
    else:
        st.sidebar.info("Você está logado como **Usuário**.")
        pages_to_show = user_pages

    # Renderiza o menu de navegação e a página selecionada
    selected_page = st.sidebar.radio("Navegação", options=list(pages_to_show.keys()))
    pages_to_show[selected_page]()


# --- Lógica Principal da Aplicação ---
# Renderiza sempre o formulário de login primeiro
authenticator.login(fields={'Form name': 'Login'}, location='main')

# Verifica o status da autenticação
if st.session_state.get("authentication_status"):
    main_dashboard()
elif st.session_state.get("authentication_status") is False:
    st.error('Usuário ou senha incorreto.')
elif st.session_state.get("authentication_status") is None:
    st.warning('Por favor, insira seu usuário e senha.')