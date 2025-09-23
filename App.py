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
    
    def calculate_lump_sum_rebalancing(self, portfolio_data: Dict, additional_amount: float) -> pd.DataFrame:
        """Calcola il ribilanciamento con aggiunta una tantum - VERSIONE CORRETTA"""
        # Calcola il nuovo valore totale del portafoglio
        new_total_value = portfolio_data['total_value'] + additional_amount
        
        allocation_data = []
        total_to_invest = 0
        
        for asset in portfolio_data['assets_data']:
            # Calcola il nuovo valore target basato sul valore finale
            new_target_value = (asset['pct_target'] / 100) * new_total_value
            
            # Calcola quanto investire in questo asset
            amount_to_invest = new_target_value - asset['valore_attuale']
            
            if amount_to_invest > 0.01:  # Solo se c'è da investire
                allocation_data.append({
                    'Asset': asset['nome'],
                    'Valore Attuale (€)': f"{asset['valore_attuale']:.2f}",
                    'Valore Target (€)': f"{new_target_value:.2f}",
                    'Da Investire (€)': f"{amount_to_invest:.2f}",
                    'Importo_num': amount_to_invest
                })
                total_to_invest += amount_to_invest
        
        df = pd.DataFrame(allocation_data)
        
        # Verifica che il totale da investire non superi l'importo disponibile
        if not df.empty and total_to_invest > additional_amount:
            st.warning(f"⚠️ Servirebbero €{total_to_invest:.2f} per il ribilanciamento completo, ma hai solo €{additional_amount:.2f} disponibili.")
            st.info("💡 Gli importi sono stati ridotti proporzionalmente:")
            
            # Scala proporzionalmente
            scale_factor = additional_amount / total_to_invest
            df['Da Investire (€)'] = df['Importo_num'].apply(lambda x: f"{x * scale_factor:.2f}")
            df['Importo_num'] = df['Importo_num'] * scale_factor
        
        return df.drop('Importo_num', axis=1) if not df.empty else df
    
    def calculate_pac_rebalancing(self, portfolio_data: Dict, num_rates: int, max_rate: float) -> pd.DataFrame:
        """Calcola il piano di accumulo (PAC) - VERSIONE CORRETTA"""
        pac_plan = []
        
        # Simula il portafoglio che cresce ad ogni rata
        current_values = {asset['nome']: asset['valore_attuale'] for asset in portfolio_data['assets_data']}
        
        for rate in range(1, num_rates + 1):
            rate_data = {'Rata': rate}
            
            # Calcola il valore totale dopo questa rata
            current_total = sum(current_values.values())
            new_total_after_rate = current_total + max_rate
            
            # Calcola quanto investire in ogni asset per questa rata
            investments_this_rate = {}
            total_needed = 0
            
            for asset in portfolio_data['assets_data']:
                # Valore target per questo asset dopo la rata
                target_value_after_rate = (asset['pct_target'] / 100) * new_total_after_rate
                
                # Quanto manca per raggiungere il target
                current_value = current_values[asset['nome']]
                needed = max(0, target_value_after_rate - current_value)
                
                if needed > 0.01:
                    investments_this_rate[asset['nome']] = needed
                    total_needed += needed
            
            # Distribuisci la rata proporzionalmente ai bisogni
            if total_needed > 0:
                for asset_name, needed in investments_this_rate.items():
                    # Calcola quanto investire proporzionalmente
                    investment = min(needed, (needed / total_needed) * max_rate)
                    
                    if investment > 0.01:
                        rate_data[f"{asset_name} (€)"] = f"{investment:.2f}"
                        # Aggiorna il valore corrente per la prossima iterazione
                        current_values[asset_name] += investment
            
            if len(rate_data) > 1:  # Se ci sono allocazioni per questa rata
                pac_plan.append(rate_data)
            else:
                # Se non serve investire nulla, il portafoglio è già bilanciato
                break
        
        return pd.DataFrame(pac_plan)
    
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
        
        # Parametri di ribilanciamento
        if valid_assets and is_valid:
            st.divider()
            st.subheader("⚙️ Parametri Ribilanciamento")
            
            # Parametri Una Tantum
            with st.expander("💰 Una Tantum", expanded=True):
                additional_amount = st.number_input(
                    "Importo da Aggiungere (€)",
                    min_value=0.0,
                    value=1000.0,
                    step=100.0,
                    key="additional_amount"
                )
            
            # Parametri PAC
            with st.expander("📅 Piano di Accumulo", expanded=True):
                num_rates = st.number_input(
                    "Numero di Rate", 
                    min_value=1, 
                    max_value=120, 
                    value=6, 
                    step=1,
                    key="num_rates"
                )
                max_rate = st.number_input(
                    "Importo Massimo per Rata (€)", 
                    min_value=0.0, 
                    value=500.0, 
                    step=50.0,
                    key="max_rate"
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
            st.subheader("Ribilanciamento con Aggiunta Una Tantum")
            st.write("Alloca denaro aggiuntivo senza vendere asset esistenti per raggiungere le percentuali target.")
            st.info(f"📊 Parametri configurati: €{st.session_state.additional_amount:,.2f}")
            
            if st.session_state.additional_amount > 0:
                lump_sum_df = portfolio_manager.calculate_lump_sum_rebalancing(portfolio_data, st.session_state.additional_amount)
                
                if not lump_sum_df.empty:
                    st.dataframe(lump_sum_df, use_container_width=True, hide_index=True)
                    
                    # Mostra il valore finale del portafoglio
                    final_value = portfolio_data['total_value'] + st.session_state.additional_amount
                    st.success(f"🎯 Valore finale del portafoglio: €{final_value:,.2f}")
                    
                else:
                    st.success("🎯 Il portafoglio è già perfettamente bilanciato! Non servono investimenti aggiuntivi.")
            else:
                st.warning("⚠️ Imposta un importo maggiore di 0€ nella configurazione laterale")
        
        with tab3:
            st.subheader("Piano di Accumulo (PAC)")
            st.write("Ribilanciamento progressivo nel tempo attraverso rate periodiche per raggiungere le percentuali target.")
            st.info(f"📊 Parametri configurati: {st.session_state.num_rates} rate da max €{st.session_state.max_rate:,.2f}")
            
            if st.session_state.max_rate > 0:
                pac_df = portfolio_manager.calculate_pac_rebalancing(portfolio_data, st.session_state.num_rates, st.session_state.max_rate)
                
                if not pac_df.empty:
                    st.dataframe(pac_df, use_container_width=True, hide_index=True)
                    
                    # Calcola investimento effettivo
                    actual_rates = len(pac_df)
                    actual_investment = actual_rates * st.session_state.max_rate
                    final_value = portfolio_data['total_value'] + actual_investment
                    
                    st.success(f"🎯 Investimento totale: €{actual_investment:,.2f} in {actual_rates} rate")
                    st.success(f"🎯 Valore finale del portafoglio: €{final_value:,.2f}")
                    
                    if actual_rates < st.session_state.num_rates:
                        st.info(f"💡 Il portafoglio raggiungerà il bilanciamento target dopo {actual_rates} rate invece di {st.session_state.num_rates}")
                        
                else:
                    st.success("🎯 Il portafoglio è già perfettamente bilanciato! Non serve un piano di accumulo.")
            else:
                st.warning("⚠️ Imposta un importo rata maggiore di 0€ nella configurazione laterale")

if __name__ == "__main__":
    main()
