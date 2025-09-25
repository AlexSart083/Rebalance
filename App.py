import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import Dict, List, Tuple

# Configurazione della pagina
st.set_page_config(
    page_title="Rebalance - Portfolio Manager",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

class PortfolioManager:
    def __init__(self):
        self.max_assets = 10
        
    def initialize_session_state(self):
        """Inizializza le variabili di sessione"""
        if 'portfolio_name' not in st.session_state:
            st.session_state.portfolio_name = ""
        if 'assets' not in st.session_state:
            st.session_state.assets = []
        if 'num_assets' not in st.session_state:
            st.session_state.num_assets = 3
    
    def validate_targets(self, assets: List[Dict]) -> Tuple[bool, float]:
        """Valida che la somma dei target sia 100%"""
        total_target = sum(asset['target'] for asset in assets if asset['target'] > 0)
        return abs(total_target - 100) < 0.01, total_target
    
    def calculate_portfolio_metrics(self, assets: List[Dict]) -> Dict:
        """Calcola le metriche del portafoglio"""
        total_value = sum(asset['current_value'] for asset in assets if asset['current_value'] > 0)
        
        if total_value == 0:
            return {'total_value': 0, 'assets_data': []}
        
        assets_data = []
        for asset in assets:
            if asset['current_value'] > 0:
                current_pct = (asset['current_value'] / total_value) * 100
                target_value = (asset['target'] / 100) * total_value
                difference = target_value - asset['current_value']
                
                assets_data.append({
                    'nome': asset['name'],
                    'valore_attuale': asset['current_value'],
                    'pct_attuale': current_pct,
                    'pct_target': asset['target'],
                    'valore_target': target_value,
                    'differenza': difference
                })
        
        return {
            'total_value': total_value,
            'assets_data': assets_data
        }
    
    def calculate_standard_rebalancing(self, portfolio_data: Dict) -> pd.DataFrame:
        """Calcola il ribilanciamento standard (acquisto/vendita)"""
        rebalancing_data = []
        
        for asset in portfolio_data['assets_data']:
            difference = asset['differenza']
            if abs(difference) > 0.01:  # Soglia minima di 1 centesimo
                action = "Acquista" if difference > 0 else "Vendi"
                amount = abs(difference)
                rebalancing_data.append({
                    'Asset': asset['nome'],
                    'Azione': action,
                    'Importo (€)': f"{amount:.2f}",
                    'Importo_num': amount
                })
        
        return pd.DataFrame(rebalancing_data)
    
    def calculate_lump_sum_rebalancing(self, portfolio_data: Dict) -> Dict:
        """Calcola l'importo necessario per il ribilanciamento completo senza vendite - VERSIONE CORRETTA"""
        
        current_total = portfolio_data['total_value']
        
        # Trova il valore minimo necessario del portafoglio per bilanciare tutti gli asset
        # Per ogni asset sovrapesato, calcola quale dovrebbe essere il valore totale del portafoglio
        # perché quell'asset non sia più sovrapesato
        min_total_needed = current_total
        
        for asset in portfolio_data['assets_data']:
            current_value = asset['valore_attuale']
            target_pct = asset['pct_target']
            
            if target_pct > 0:
                # Calcola quale dovrebbe essere il valore totale del portafoglio
                # perché questo asset abbia esattamente la percentuale target
                required_total = current_value / (target_pct / 100)
                min_total_needed = max(min_total_needed, required_total)
        
        total_needed = min_total_needed - current_total
        
        if total_needed <= 0.01:
            return {
                'total_needed': 0,
                'allocation': pd.DataFrame(),
                'message': 'Il portafoglio è già bilanciato!'
            }
        
        # Calcola l'allocazione: aggiungi denaro solo agli asset NON sovrapesati
        final_total = current_total + total_needed
        final_allocation = []
        
        for asset in portfolio_data['assets_data']:
            current_value = asset['valore_attuale']
            current_pct = asset['pct_attuale']
            target_pct = asset['pct_target']
            
            # Valore target con il nuovo totale
            target_value_final = (target_pct / 100) * final_total
            amount_to_add = target_value_final - current_value
            
            # Aggiungi solo se l'asset non è già sovrapesato e serve davvero aggiungere
            if current_pct <= target_pct and amount_to_add > 0.01:
                final_allocation.append({
                    'Asset': asset['nome'],
                    'Valore Attuale (€)': f"{current_value:.2f}",
                    'Target (%)': f"{target_pct:.1f}%",
                    'Valore Target (€)': f"{target_value_final:.2f}",
                    'Da Aggiungere (€)': f"{amount_to_add:.2f}",
                    'amount_num': amount_to_add
                })
        
        return {
            'total_needed': total_needed,
            'final_portfolio_value': final_total,
            'allocation': pd.DataFrame(final_allocation)
        }
    
    def calculate_pac_rebalancing(self, portfolio_data: Dict, monthly_amount: float) -> Dict:
        """Calcola il piano di accumulo con rate uguali - VERSIONE CORRETTA"""
        
        if monthly_amount <= 0:
            return {'months_needed': 0, 'plan': pd.DataFrame(), 'message': 'Importo mensile non valido'}
        
        # Prima calcola quanto serve in totale per il ribilanciamento
        lump_sum_result = self.calculate_lump_sum_rebalancing(portfolio_data)
        
        if lump_sum_result['total_needed'] <= 0.01:
            return {'months_needed': 0, 'plan': pd.DataFrame(), 'message': 'Il portafoglio è già bilanciato!'}
        
        total_needed = lump_sum_result['total_needed']
        
        # Calcola quanti mesi servono
        months_needed = int(np.ceil(total_needed / monthly_amount))
        
        # Calcola le percentuali di allocazione per ogni asset sottopesato
        allocation_percentages = {}
        
        if not lump_sum_result['allocation'].empty:
            for _, row in lump_sum_result['allocation'].iterrows():
                amount = row['amount_num']
                percentage = amount / total_needed if total_needed > 0 else 0
                allocation_percentages[row['Asset']] = percentage
        
        # Crea il piano mensile con rate uguali
        pac_plan = []
        
        for month in range(1, months_needed + 1):
            month_data = {'Mese': month}
            
            # Distribuisci l'importo mensile secondo le percentuali calcolate
            for asset_name, percentage in allocation_percentages.items():
                monthly_investment = monthly_amount * percentage
                if monthly_investment > 0.01:
                    month_data[f"{asset_name} (€)"] = f"{monthly_investment:.2f}"
            
            # Calcola il totale del mese (dovrebbe essere uguale a monthly_amount)
            month_total = monthly_amount
            month_data['Totale Mese (€)'] = f"{month_total:.2f}"
            
            pac_plan.append(month_data)
        
        # Calcolo finale
        total_invested = months_needed * monthly_amount
        final_portfolio_value = portfolio_data['total_value'] + total_invested
        
        # Verifica se l'importo totale investito copre il fabbisogno
        coverage_ratio = total_invested / total_needed if total_needed > 0 else 1
        is_sufficient = coverage_ratio >= 0.99  # 99% di copertura considerata sufficiente
        
        return {
            'months_needed': months_needed,
            'plan': pd.DataFrame(pac_plan),
            'total_invested': total_invested,
            'total_needed': total_needed,
            'final_portfolio_value': final_portfolio_value,
            'coverage_ratio': coverage_ratio,
            'is_sufficient': is_sufficient,
            'monthly_amount': monthly_amount
        }
    
    def create_portfolio_chart(self, portfolio_data: Dict):
        """Crea il grafico a torta comparativo"""
        if not portfolio_data['assets_data']:
            return None
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Composizione Attuale', 'Composizione Target'),
            specs=[[{'type':'domain'}, {'type':'domain'}]]
        )
        
        names = [asset['nome'] for asset in portfolio_data['assets_data']]
        current_values = [asset['pct_attuale'] for asset in portfolio_data['assets_data']]
        target_values = [asset['pct_target'] for asset in portfolio_data['assets_data']]
        
        colors = px.colors.qualitative.Set3[:len(names)]
        
        # Grafico attuale
        fig.add_trace(go.Pie(
            labels=names,
            values=current_values,
            name="Attuale",
            marker_colors=colors,
            textinfo='label+percent',
            textposition='auto'
        ), 1, 1)
        
        # Grafico target
        fig.add_trace(go.Pie(
            labels=names,
            values=target_values,
            name="Target",
            marker_colors=colors,
            textinfo='label+percent',
            textposition='auto'
        ), 1, 2)
        
        fig.update_layout(
            showlegend=False,
            height=400,
            font_size=12
        )
        
        return fig
    
    def save_portfolio(self, portfolio_name: str, assets: List[Dict]) -> str:
        """Salva il portafoglio in formato JSON"""
        portfolio_data = {
            'nome_portafoglio': portfolio_name,
            'assets': assets,
            'versione': '1.0'
        }
        return json.dumps(portfolio_data, indent=2, ensure_ascii=False)
    
    def load_portfolio(self, json_data: str) -> Tuple[str, List[Dict]]:
        """Carica il portafoglio da JSON"""
        try:
            data = json.loads(json_data)
            return data.get('nome_portafoglio', ''), data.get('assets', [])
        except json.JSONDecodeError:
            raise ValueError("File JSON non valido")

def main():
    portfolio_manager = PortfolioManager()
    portfolio_manager.initialize_session_state()
    
    # Titolo principale
    st.title("📊 Rebalance - Portfolio Manager")
    st.markdown("*App per il ribilanciamento del portafoglio titoli e la visualizzazione del bilanciamento attuale*")
    st.divider()
    
    # Sidebar per input
    with st.sidebar:
        st.header("🎯 Configurazione Portafoglio")
        
        # Nome portafoglio
        portfolio_name = st.text_input(
            "Nome del Portafoglio",
            value=st.session_state.portfolio_name,
            placeholder="Es: Portafoglio Diversificato 2025"
        )
        st.session_state.portfolio_name = portfolio_name
        
        # Caricamento portafoglio
        st.subheader("📁 Carica Portafoglio")
        uploaded_file = st.file_uploader("Scegli un file JSON", type=['json'])
        
        if uploaded_file is not None:
            try:
                json_data = uploaded_file.read().decode('utf-8')
                loaded_name, loaded_assets = portfolio_manager.load_portfolio(json_data)
                
                if st.button("Carica Dati"):
                    st.session_state.portfolio_name = loaded_name
                    st.session_state.assets = loaded_assets
                    st.session_state.num_assets = len([a for a in loaded_assets if a.get('name', '')])
                    st.success("Portafoglio caricato con successo!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Errore nel caricamento: {str(e)}")
        
        # Numero di asset
        st.subheader("📈 Asset del Portafoglio")
        num_assets = st.slider(
            "Numero di Asset (max 10)",
            min_value=1,
            max_value=portfolio_manager.max_assets,
            value=st.session_state.num_assets
        )
        st.session_state.num_assets = num_assets
        
        # Assicura che la lista assets abbia la dimensione corretta
        while len(st.session_state.assets) < num_assets:
            st.session_state.assets.append({'name': '', 'current_value': 0.0, 'target': 0.0})
        st.session_state.assets = st.session_state.assets[:num_assets]
        
        # Input per ogni asset
        for i in range(num_assets):
            with st.expander(f"Asset {i+1}", expanded=True):
                name = st.text_input(
                    "Nome Asset",
                    value=st.session_state.assets[i].get('name', ''),
                    key=f"name_{i}",
                    placeholder=f"Es: ETF S&P 500"
                )
                
                current_value = st.number_input(
                    "Valore Attuale (€)",
                    min_value=0.0,
                    value=float(st.session_state.assets[i].get('current_value', 0.0)),
                    step=100.0,
                    key=f"value_{i}"
                )
                
                target = st.number_input(
                    "Target (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.assets[i].get('target', 0.0)),
                    step=5.0,
                    key=f"target_{i}"
                )
                
                st.session_state.assets[i] = {
                    'name': name,
                    'current_value': current_value,
                    'target': target
                }
        
        # Validazione targets
        valid_assets = [asset for asset in st.session_state.assets if asset['name'] and asset['current_value'] > 0]
        is_valid, total_target = portfolio_manager.validate_targets(valid_assets)
        
        if valid_assets:
            if not is_valid:
                st.error(f"⚠️ Somma target: {total_target:.1f}% (deve essere 100%)")
            else:
                st.success(f"✅ Somma target: {total_target:.1f}%")
        
        # Parametri PAC (solo questo rimane)
        if valid_assets and is_valid:
            st.divider()
            st.subheader("📅 Piano di Accumulo")
            monthly_amount = st.number_input(
                "Importo Mensile Fisso (€)", 
                min_value=0.0, 
                value=500.0, 
                step=50.0,
                key="monthly_amount",
                help="L'app calcolerà automaticamente quanti mesi servono per raggiungere il bilanciamento target"
            )
        
        # Salvataggio portafoglio
        st.divider()
        st.subheader("💾 Salva Portafoglio")
        if st.button("Scarica Configurazione"):
            if portfolio_name and valid_assets:
                json_data = portfolio_manager.save_portfolio(portfolio_name, st.session_state.assets)
                st.download_button(
                    label="📥 Download JSON",
                    data=json_data,
                    file_name=f"{portfolio_name.replace(' ', '_')}_portfolio.json",
                    mime="application/json"
                )
            else:
                st.error("Inserisci nome portafoglio e almeno un asset valido")
    
    # Area principale
    if not valid_assets:
        st.info("👈 Configura il tuo portafoglio nella barra laterale per iniziare")
        return
    
    if not is_valid:
        st.warning("⚠️ Correggi la somma delle percentuali target prima di procedere")
        return
    
    # Calcola metriche portafoglio
    portfolio_data = portfolio_manager.calculate_portfolio_metrics(valid_assets)
    
    # Dashboard principale
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric("💰 Valore Totale Portafoglio", f"€ {portfolio_data['total_value']:,.2f}")
        st.metric("📊 Numero Asset", len(portfolio_data['assets_data']))
    
    with col2:
        # Grafico comparativo
        chart = portfolio_manager.create_portfolio_chart(portfolio_data)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
    
    # Tabella dettagliata
    st.subheader("📋 Riepilogo Dettagliato")
    
    if portfolio_data['assets_data']:
        df = pd.DataFrame(portfolio_data['assets_data'])
        df_display = df.copy()
        df_display['valore_attuale'] = df_display['valore_attuale'].apply(lambda x: f"€ {x:,.2f}")
        df_display['pct_attuale'] = df_display['pct_attuale'].apply(lambda x: f"{x:.1f}%")
        df_display['pct_target'] = df_display['pct_target'].apply(lambda x: f"{x:.1f}%")
        df_display['valore_target'] = df_display['valore_target'].apply(lambda x: f"€ {x:,.2f}")
        df_display['differenza'] = df_display['differenza'].apply(lambda x: f"€ {x:+,.2f}")
        
        df_display.columns = ['Nome', 'Valore Attuale', '% Attuale', '% Target', 'Valore Target', 'Differenza (€)']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    # Sezione Ribilanciamento
    st.divider()
    st.header("🔄 Calcola Ribilanciamento")
    
    if st.button("🚀 Avvia Calcoli", type="primary", use_container_width=True):
        
        # Tab per diverse modalità
        tab1, tab2, tab3 = st.tabs(["📊 Standard", "💰 Una Tantum", "📅 Piano di Accumulo"])
        
        with tab1:
            st.subheader("Ribilanciamento Standard (Acquisto/Vendita)")
            st.write("Operazioni necessarie per raggiungere immediatamente le percentuali target.")
            
            rebalancing_df = portfolio_manager.calculate_standard_rebalancing(portfolio_data)
            
            if not rebalancing_df.empty:
                # Rimuovi la colonna numerica per la visualizzazione
                display_df = rebalancing_df.drop('Importo_num', axis=1)
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # Riepilogo
                total_buy = rebalancing_df[rebalancing_df['Azione'] == 'Acquista']['Importo_num'].sum()
                total_sell = rebalancing_df[rebalancing_df['Azione'] == 'Vendi']['Importo_num'].sum()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("💚 Totale Acquisti", f"€ {total_buy:,.2f}")
                with col2:
                    st.metric("🔴 Totale Vendite", f"€ {total_sell:,.2f}")
            else:
                st.success("🎯 Il portafoglio è già perfettamente bilanciato!")
        
        with tab2:
            st.subheader("Ribilanciamento Una Tantum")
            st.write("Calcolo dell'importo necessario per raggiungere il bilanciamento target senza vendere asset esistenti.")
            
            lump_sum_result = portfolio_manager.calculate_lump_sum_rebalancing(portfolio_data)
            
            if lump_sum_result['total_needed'] > 0:
                # Mostra l'importo totale necessario
                st.metric("💰 Importo Totale Necessario", f"€ {lump_sum_result['total_needed']:,.2f}")
                
                # Mostra come deve essere suddiviso
                if not lump_sum_result['allocation'].empty:
                    st.subheader("📋 Suddivisione per Asset")
                    
                    # Rimuovi la colonna numerica per la visualizzazione
                    display_df = lump_sum_result['allocation'].drop('amount_num', axis=1)
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    # Mostra il valore finale del portafoglio
                    st.success(f"🎯 Valore finale del portafoglio: €{lump_sum_result['final_portfolio_value']:,.2f}")
                
            else:
                st.success("🎯 Il portafoglio è già perfettamente bilanciato! Non servono investimenti aggiuntivi.")
        
        with tab3:
            st.subheader("Piano di Accumulo (PAC) con Rate Uguali")
            st.write("Calcolo automatico del numero di mesi necessari per raggiungere il bilanciamento con rate mensili fisse.")
            
            if st.session_state.monthly_amount > 0:
                pac_result = portfolio_manager.calculate_pac_rebalancing(portfolio_data, st.session_state.monthly_amount)
                
                if pac_result['months_needed'] > 0:
                    # Informazioni principali
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📅 Mesi Necessari", pac_result['months_needed'])
                    with col2:
                        st.metric("💰 Rata Mensile", f"€{pac_result['monthly_amount']:,.2f}")
                    with col3:
                        st.metric("🎯 Investimento Totale", f"€{pac_result['total_invested']:,.2f}")
                    
                    # Informazioni su copertura
                    st.info(f"📊 Fabbisogno calcolato: €{pac_result['total_needed']:,.2f} | Copertura: {pac_result['coverage_ratio']*100:.1f}%")
                    
                    # Status
                    if pac_result['is_sufficient']:
                        st.success("✅ L'importo investito sarà sufficiente per raggiungere il bilanciamento target!")
                    else:
                        st.warning("⚠️ L'importo investito potrebbe non essere completamente sufficiente. Considera di aumentare la rata mensile.")
                    
                    # Piano dettagliato
                    st.subheader("📋 Piano Mensile Dettagliato")
                    st.dataframe(pac_result['plan'], use_container_width=True, hide_index=True)
                    
                    # Calcolo tempo
                    years = pac_result['months_needed'] / 12
                    if years >= 1:
                        st.info(f"⏱️ Tempo stimato: {years:.1f} anni ({pac_result['months_needed']} mesi)")
                    else:
                        st.info(f"⏱️ Tempo stimato: {pac_result['months_needed']} mesi")
                        
                elif 'message' in pac_result:
                    st.success(f"🎯 {pac_result['message']}")
                else:
                    st.success("🎯 Il portafoglio è già perfettamente bilanciato!")
            else:
                st.warning("⚠️ Imposta un importo mensile maggiore di 0€ nella configurazione laterale")

if __name__ == "__main__":
    main()
