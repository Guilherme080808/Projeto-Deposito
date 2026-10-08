
import base64
import math
import urllib.parse
import folium
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# -----------------------------------------------------------------------------
# 1. REGRAS INTERNAS DE CARGA DA MOTO (100% INVISÍVEIS NA INTERFACE)
# -----------------------------------------------------------------------------
PESO_AGUA = 8
PESO_GAS = 11
CAPACIDADE_MOTO = 30

# -----------------------------------------------------------------------------
# 2. CONFIGURAÇÃO DA PÁGINA E PALETA DA FÁBIO GÁS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Fábio Gás & Água - Roteirizador",
    page_icon="🚚",
    layout="wide",
)

# CSS Personalizado ajustado para texto preto, fundo branco e sidebar verde
st.markdown(
    """
    <style>
    /* Fundo da aplicação em branco */
    .stApp {
        background-color: #FFFFFF !important;
    }

    /* Cor da fonte principal forçada para PRETO */
    .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, 
    .stApp span, .stApp label, .stApp div, .stApp li, .stApp caption, .stApp td, .stApp th {
        color: #000000 !important;
    }

    /* Barra lateral em VERDE */
    [data-testid="stSidebar"] {
        background-color: #16a34a !important;
    }

    /* Texto da barra lateral em BRANCO para contraste */
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    /* Customizações do Banner */
    .banner-fabio {
        background-color: #A3DEC4;
        padding: 18px 25px;
        border-radius: 15px;
        display: flex;
        align-items: center;
        gap: 20px;
        border-bottom: 5px solid #1E8449;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.08);
    }
    .titulo-red {
        color: #B30000 !important;
        font-size: 36px;
        font-weight: 900;
        font-family: 'Arial Black', sans-serif;
        margin: 0;
        line-height: 1;
    }
    .titulo-yellow {
        color: #D4AC0D !important;
        font-size: 36px;
        font-weight: 900;
        font-family: 'Arial Black', sans-serif;
        margin: 0;
        line-height: 1;
    }
    .subtitulo-verde {
        color: #1E8449 !important;
        font-size: 18px;
        font-weight: bold;
        margin-top: 5px;
    }
    .badge-slogan {
        background-color: #FFD700;
        color: #B30000 !important;
        font-weight: bold;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 14px;
        display: inline-block;
        margin-top: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .card-viagem {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        border-left: 8px solid #27AE60;
        margin-bottom: 20px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.06);
    }
    .stButton>button {
        background-color: #27AE60 !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: bold !important;
        font-size: 17px !important;
        padding: 10px 20px !important;
    }
    .stButton>button:hover {
        background-color: #1E8449 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Logo oficial convertida em Base64
LOGO_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAfQAAAH0CAYAAAD152D5AAAABHNCSVQICAgIfAhkiAAAAAlwSFlz"
    # ... String Base64 integrada internamente ...
)

# -----------------------------------------------------------------------------
# 3. CABEÇALHO DA EMPRESA
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="banner-fabio">
        <img src="data:image/png;base64,{LOGO_BASE64}" width="130" style="border-radius: 10px;">
        <div>
            <div>
                <span class="titulo-red">FÁBIO </span>
                <span class="titulo-yellow">GÁS & ÁGUA</span>
            </div>
            <div class="subtitulo-verde">Painel Logístico de Roteamento de Entregas</div>
            <div class="badge-slogan">⚡ PEDIU, CHEGOU! | 📞 (81) 98515-4965 / (81) 98696-1220</div>
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 4. MEMÓRIA DE SESSÃO DA APLICAÇÃO
# -----------------------------------------------------------------------------
if "rotas_calculadas" not in st.session_state:
    st.session_state.rotas_calculadas = False
if "dados_resultado" not in st.session_state:
    st.session_state.dados_resultado = None

# -----------------------------------------------------------------------------
# 5. BARRA LATERAL (DEPÓSITO E CONTATOS)
# -----------------------------------------------------------------------------
st.sidebar.markdown("### 🏬 **Fábio Gás - Depósito**")
endereco_deposito_padrao = st.sidebar.text_input(
    "Endereço do Depósito", value="Fábio Gás, Jaboatão dos Guararapes, PE"
)

st.sidebar.divider()
st.sidebar.markdown("### 📞 **Central de Atendimento**")
st.sidebar.success(
    "📱 **WhatsApp 1:** (81) 98515-4965\n\n📱 **WhatsApp 2:** (81) 98696-1220\n\n📸"
    " **Instagram:** @fabiogasoficial"
)


@st.cache_resource
def get_geocoders():
    geolocator = Nominatim(user_agent="fabio_gas_roteirizador_app")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    return geocode


geocode_func = get_geocoders()

# Tabela Padrão Inicial
dados_exemplo = pd.DataFrame([
    {
        "cliente": "Fábio Gás (Depósito)",
        "endereco": endereco_deposito_padrao,
        "agua": 0,
        "gas": 0,
    },
    {
        "cliente": "Cliente Dona Maria",
        "endereco": "Rua Candeias, 120, Jaboatão dos Guararapes, PE",
        "agua": 1,
        "gas": 0,
    },
    {
        "cliente": "Cliente Seu João",
        "endereco": "Av. Ayrton Senna, 500, Jaboatão dos Guararapes, PE",
        "agua": 1,
        "gas": 1,
    },
    {
        "cliente": "Padaria Pão Bom",
        "endereco": "Rua do Sol, 45, Jaboatão dos Guararapes, PE",
        "agua": 1,
        "gas": 0,
    },
    {
        "cliente": "Mercadinho Silva",
        "endereco": "Rua das Ninfas, 88, Jaboatão dos Guararapes, PE",
        "agua": 0,
        "gas": 2,
    },
    {
        "cliente": "Dona Lúcia",
        "endereco": "Rua Curcurana, 300, Jaboatão dos Guararapes, PE",
        "agua": 2,
        "gas": 0,
    },
])

st.subheader("📋 Pedidos do Dia")

modo_entrada = st.radio(
    "Como deseja inserir os pedidos?",
    ["Tabela Editável no Painel", "Carregar Planilha Excel/CSV"],
)

if modo_entrada == "Tabela Editável no Painel":
    df_pedidos = st.data_editor(
        dados_exemplo, num_rows="dynamic", width="stretch"
    )
else:
    arquivo = st.file_uploader(
        "Suba a planilha Excel (.xlsx) ou CSV", type=["xlsx", "csv"]
    )
    if arquivo:
        if arquivo.name.endswith(".csv"):
            df_pedidos = pd.read_csv(arquivo)
        else:
            df_pedidos = pd.read_excel(arquivo)
        st.dataframe(df_pedidos, width="stretch")
    else:
        df_pedidos = dados_exemplo

if not df_pedidos.empty:
    df_pedidos.iloc[0, df_pedidos.columns.get_loc("cliente")] = (
        "Fábio Gás (Depósito)"
    )
    df_pedidos.iloc[0, df_pedidos.columns.get_loc("endereco")] = (
        endereco_deposito_padrao
    )

# -----------------------------------------------------------------------------
# 6. PROCESSAMENTO E OTIMIZAÇÃO
# -----------------------------------------------------------------------------
if st.button("🚀 Otimizar Rotas das Motos", type="primary"):
    if df_pedidos.empty:
        st.warning("Adicione os pedidos do dia para calcular as rotas.")
    else:
        with st.spinner(
            "Buscando coordenadas e gerando a melhor sequência de entregas..."
        ):
            lats, lngs = [], []
            for idx, row in df_pedidos.iterrows():
                try:
                    location = geocode_func(row["endereco"])
                    if location:
                        lats.append(location.latitude)
                        lngs.append(location.longitude)
                    else:
                        lats.append(-8.1633 + idx * 0.002)
                        lngs.append(-34.9125 + idx * 0.002)
                except Exception:
                    lats.append(-8.1633 + idx * 0.002)
                    lngs.append(-34.9125 + idx * 0.002)

            df_pedidos["lat"] = lats
            df_pedidos["lng"] = lngs
            df_pedidos["peso_pts"] = (
                df_pedidos["agua"] * PESO_AGUA + df_pedidos["gas"] * PESO_GAS
            )

            st.session_state.dados_resultado = df_pedidos
            st.session_state.rotas_calculadas = True

# -----------------------------------------------------------------------------
# 7. EXIBIÇÃO
# -----------------------------------------------------------------------------
if (
    st.session_state.rotas_calculadas
    and st.session_state.dados_resultado is not None
):
    df_proc = st.session_state.dados_resultado
    num_locais = len(df_proc)

    def calc_dist(p1, p2):
        dx = (p1["lat"] - p2["lat"]) * 111000
        dy = (p1["lng"] - p2["lng"]) * 111000 * math.cos(math.radians(-8.16))
        return int(math.sqrt(dx * dx + dy * dy))

    matriz_distancias = [
        [calc_dist(df_proc.iloc[i], df_proc.iloc[j]) for j in range(num_locais)]
        for i in range(num_locais)
    ]

    NUM_VIAGENS = max(6, num_locais)
    manager = pywrapcp.RoutingIndexManager(num_locais, NUM_VIAGENS, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return matriz_distancias[manager.IndexToNode(from_index)][
            manager.IndexToNode(to_index)
        ]

    transit_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

    def demand_callback(from_index):
        return int(df_proc.iloc[manager.IndexToNode(from_index)]["peso_pts"])

    demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_index, 0, [CAPACIDADE_MOTO] * NUM_VIAGENS, True, "Capacidade_Moto"
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        st.subheader("📍 Itinerário e Sequência de Entregas")

        mapa = folium.Map(
            location=[df_proc.iloc[0]["lat"], df_proc.iloc[0]["lng"]], zoom_start=13
        )
        folium.Marker(
            [df_proc.iloc[0]["lat"], df_proc.iloc[0]["lng"]],
            popup="🏬 Fábio Gás (Depósito)",
            icon=folium.Icon(color="green", icon="home"),
        ).add_to(mapa)

        cores = ["green", "cadetblue", "blue", "purple", "orange", "darkred"]
        viagem_count = 1

        for vehicle_id in range(NUM_VIAGENS):
            index = routing.Start(vehicle_id)
            route_nodes = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_nodes.append(node_index)
                index = solution.Value(routing.NextVar(index))
            node_index = manager.IndexToNode(index)
            route_nodes.append(node_index)

            if len(route_nodes) > 2:
                st.markdown(
                    f'<div class="card-viagem"><h3 style="color:#1E8449;'
                    f' margin-top:0;">🚲 Viagem {viagem_count}</h3>',
                    unsafe_allow_html=True,
                )

                tot_agua, tot_gas = 0, 0
                pontos_coordenadas = []
                resumo_whatsapp = []

                for n in route_nodes:
                    c = df_proc.iloc[n]
                    pontos_coordenadas.append((c["lat"], c["lng"]))
                    if n != 0:
                        detalhe_itens = []
                        if c["agua"] > 0:
                            detalhe_itens.append(f"{c['agua']}x Galão de Água")
                        if c["gas"] > 0:
                            detalhe_itens.append(f"{c['gas']}x Botijão de Gás")

                        txt_itens = (
                            ", ".join(detalhe_itens) if detalhe_itens else "Entrega"
                        )

                        st.write(f"➔ **{c['cliente']}**: {txt_itens}")
                        st.caption(f"📍 {c['endereco']}")

                        tot_agua += c["agua"]
                        tot_gas += c["gas"]
                        resumo_whatsapp.append(
                            f"{c['cliente']} ({txt_itens}) - {c['endereco']}"
                        )

                resumo_carga_txt = []
                if tot_agua > 0:
                    resumo_carga_txt.append(f"{tot_agua} Galão(ões) de Água")
                if tot_gas > 0:
                    resumo_carga_txt.append(f"{tot_gas} Botijão(ões) de Gás")

                txt_carga_final = " e ".join(resumo_carga_txt)
                st.success(f"📦 **Carga Total da Moto:** {txt_carga_final}")

                enderecos = [df_proc.iloc[n]["endereco"] for n in route_nodes]
                origem = urllib.parse.quote(enderecos[0])
                destino = urllib.parse.quote(enderecos[-1])
                waypoints = "|".join([urllib.parse.quote(e) for e in enderecos[1:-1]])
                link_maps = f"https://www.google.com/maps/dir/?api=1&origin={origem}&destination={destino}&waypoints={waypoints}"

                texto_wa = (
                    f"🔥 *FÁBIO GÁS & ÁGUA - VIAGEM {viagem_count}*\n\n*Paradas de"
                    " Entrega:*\n"
                )
                for idx_p, item in enumerate(resumo_whatsapp, 1):
                    texto_wa += f"{idx_p}. {item}\n"
                texto_wa += f"\n📦 *Carga:* {txt_carga_final}\n"
                texto_wa += (
                    f"🗺️ *Navegação GPS:* {link_maps}\n\n_Fábio Gás - Pediu, Chegou!_"
                )

                link_wa = (
                    f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wa)}"
                )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    st.link_button("📲 Abrir GPS no Maps", link_maps, width="stretch")
                with col_btn2:
                    st.link_button(
                        "💬 Disparar p/ WhatsApp do Motoqueiro", link_wa, width="stretch"
                    )

                st.markdown("</div>", unsafe_allow_html=True)

                cor = cores[(viagem_count - 1) % len(cores)]
                folium.PolyLine(
                    pontos_coordenadas,
                    color=cor,
                    weight=5,
                    opacity=0.8,
                    popup=f"Viagem {viagem_count}",
                ).add_to(mapa)
                for n in route_nodes[1:-1]:
                    c = df_proc.iloc[n]
                    folium.Marker(
                        [c["lat"], c["lng"]],
                        popup=(
                            f"<b>{c['cliente']}</b><br>{c['agua']}x Água, {c['gas']}x Gás"
                        ),
                        icon=folium.Icon(color=cor, icon="shopping-cart"),
                    ).add_to(mapa)

                viagem_count += 1

        st.subheader("🗺️ Mapa Interativo de Entregas")
        st_folium(mapa, width=1000, height=500)