import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objs as go
import os
import requests

# --- 1. Conexión a la API FastAPI
API_URL = os.environ.get("API_URL", "https://<tu-app-runner>.awsapprunner.com")

def cargar_datos_desde_api():
    try:
        response = requests.get(f"{API_URL}/datos-todos")
        if response.status_code == 200:
            items = response.json().get("items", [])
            df = pd.DataFrame(items)

            df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
            df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
            df["\u03c3"] = pd.to_numeric(df["\u03c3"], errors="coerce")
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date.astype(str)
            df["vencimiento"] = pd.to_datetime(df["vencimiento"], errors="coerce").dt.date.astype(str)
            return df
        else:
            print(f"⚠️ Error en API: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        print(f"❌ Error accediendo a la API: {e}")
        return pd.DataFrame()

# --- 2. Inicializar Dash
app = dash.Dash(__name__)
server = app.server
app.title = "Superficie de Volatilidad - MINI IBEX"

# --- 3. Layout dinámico para actualizar fechas y tipo
def serve_layout():
    df = cargar_datos_desde_api()
    fechas_disponibles = sorted(df["fecha"].dropna().unique())

    return html.Div([
        html.H1("📊 Superficie de Volatilidad - MINI IBEX", style={"textAlign": "center"}),

        html.Div([
            html.Label("Tipo de opción:", style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='tipo-dropdown',
                options=[{'label': tipo, 'value': tipo} for tipo in ['Call', 'Put']],
                value='Call',
                style={'marginBottom': '15px'}
            ),

            html.Label("Fecha de datos:", style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='fecha-dropdown',
                options=[{'label': f, 'value': f} for f in fechas_disponibles],
                value=fechas_disponibles[-1] if fechas_disponibles else None
            )
        ], style={
            'width': '40%',
            'margin': '0 auto 30px auto',
            'backgroundColor': '#ffffff',
            'padding': '20px',
            'borderRadius': '10px',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'
        }),

        dcc.Graph(id='vol-surface-graph', style={'height': '700px'}),

        html.Div(id='data-table', style={
            'width': '90%',
            'margin': '30px auto',
            'backgroundColor': '#ffffff',
            'padding': '20px',
            'borderRadius': '10px',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'
        })
    ])

app.layout = serve_layout

# --- 4. Callback para actualizar gráfica y tabla
@app.callback(
    Output('vol-surface-graph', 'figure'),
    Output('data-table', 'children'),
    Input('tipo-dropdown', 'value'),
    Input('fecha-dropdown', 'value')
)
def update_surface(tipo, fecha):
    df_actualizado = cargar_datos_desde_api()
    df_filtrado = df_actualizado[(df_actualizado['tipo'] == tipo) & (df_actualizado['fecha'] == fecha)]
    df_filtrado = df_filtrado[df_filtrado["σ"] > 1.0]

    if df_filtrado.empty:
        return go.Figure(), html.Div("⚠️ No hay datos para la combinación seleccionada.")

    # Crear matriz con pivot_table
    pivot = df_filtrado.pivot_table(index="vencimiento", columns="strike", values="σ", aggfunc="mean")
    pivot = pivot.sort_index().sort_index(axis=1)

    if pivot.isnull().all().all():
        return go.Figure(), html.Div("⚠️ No hay superficie válida para graficar.")

    fig = go.Figure(data=[go.Surface(
        z=pivot.values,
        x=pivot.columns,      # strike
        y=pivot.index,        # vencimiento
        colorscale='Viridis'
    )])

    fig.update_layout(
        title=f"Superficie de Volatilidad - {tipo} ({fecha})",
        scene=dict(
            xaxis_title='Strike',
            yaxis_title='Vencimiento',
            zaxis_title='Volatilidad Implícita (σ)'
        ),
        margin=dict(l=0, r=0, t=40, b=0)
    )

    tabla = html.Div([
        dash_table.DataTable(
            columns=[{"name": col, "id": col} for col in ['fecha', 'vencimiento', 'strike', 'tipo', 'precio', 'σ']],
            data=df_filtrado[['fecha', 'vencimiento', 'strike', 'tipo', 'precio', 'σ']].to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'center', 'padding': '8px'},
            style_header={
                'backgroundColor': '#2f3640',
                'color': 'white',
                'fontWeight': 'bold'
            },
            style_data_conditional=[
                {
                    'if': {'column_id': 'σ'},
                    'backgroundColor': '#f0f9ff'
                }
            ],
            page_size=20
        )
    ])

    return fig, tabla

# --- 5. Ejecutar servidor
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)
