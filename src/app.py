import dash
from dash import dcc, html, Input, Output
from dash import dash_table
import sys
import math
import pandas as pd
import datetime as dt
from urllib.parse import unquote

gsheetid = "18J-v9okQdfKxaBDloRa1KIxzr39WewsgtRb0XM6Eb-0"


def build_url(sheet_name: str, sheet_id: str):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return url

def time_in_seconds(duration: str):
    ftr = [3600, 60, 1]
    seconds = sum([a * b for a, b in zip(ftr, map(int, duration.split(':')))])
    return seconds

def seconds_in_time(duration: int):
    duration_str = str(dt.timedelta(seconds=duration))
    return duration_str
def calc_buildtime(building_name: str, stage: int, senat_stage: int, baukran: bool, worldspeed: int, df_senat, df_bauzeiten):
    df_senat = pd.read_csv(build_url("Baukostenreduktion_Senat", gsheetid), keep_default_na=False)
    df_bauzeiten = pd.read_csv(build_url("Grundzeiten", gsheetid), keep_default_na=False)
    if baukran:
        baukran_factor = 0.85
    else:
        baukran_factor = 1
    senat_factor = float(df_senat["Bauzeit"][df_senat.Stufe == senat_stage].to_string(index=False).replace(",", ".").strip('%'))/100.0
    base_buildtime_str = df_bauzeiten[building_name][df_bauzeiten.Stufe == stage].to_string(index=False)
    base_buildtime_sec = time_in_seconds(base_buildtime_str)
    buildtime_sec = int(round(base_buildtime_sec*senat_factor*baukran_factor/worldspeed, ndigits=0))
    buildtime_str = seconds_in_time(buildtime_sec)
    return buildtime_str

def calculate_gold_cost(build_time_sec, df_goldcost):
    for row in df_goldcost.iterrows():
        row = row[1]
        if build_time_sec >= row["von_Zeit_sec"] and build_time_sec < row["bis_Zeit_sec"]:
            return row["Goldkosten"]
    print("Fehler, keine Goldkosten gefunden. Abbruch")
    sys.exit()

def get_unitspeed_from_unit_name(unit_name, df_unitspeed, worldspeed):
    return int(df_unitspeed.query(f'Einheit == "{unit_name}"')['Speed'])*worldspeed

def get_unittype_from_unit_name(unit_name, df_unitspeed):
    return df_unitspeed.query(f'Einheit == "{unit_name}"')['Typ'].to_string(index=False)

def modify_unitspeed(unitname, unitspeed, unittype, dict_modifiers):
    modified_unitspeed = 1
    if dict_modifiers["Meteorologie"] and unittype == "Land":
        modified_unitspeed += 0.1
    if dict_modifiers["Kartografie"] and unittype == "See":
        modified_unitspeed += 0.1
    if dict_modifiers["Segel setzen"] and unitname == "Kolonieschiff":
        modified_unitspeed += 0.1
    if dict_modifiers["Verbesserte Truppenbewegung"]:
        modified_unitspeed += 0.3
    if dict_modifiers["Leuchtturm"] and unittype == "See":
        modified_unitspeed += 0.15
    if dict_modifiers["Atalanta Stufe"] > 0:
        modified_unitspeed += (dict_modifiers["Atalanta Stufe"]+10)/100
    if dict_modifiers["Anzahl Sirenen"] > 0:
        modified_unitspeed += 0.02*dict_modifiers["Anzahl Sirenen"]
    return modified_unitspeed*unitspeed

def calculate_traveltime(start_town_id, end_town_id, unitname, worldspeed, df_towns, df_unitspeed, dict_modifiers: dict):
    df_quelle = df_towns[df_towns.id == start_town_id]
    df_ziel = df_towns[df_towns.id == end_town_id]

    quelle_x = int(df_quelle['coord_x'])
    quelle_y = int(df_quelle['coord_y'])
    ziel_x = int(df_ziel['coord_x'])
    ziel_y = int(df_ziel['coord_y'])
    dist = math.sqrt((quelle_x - ziel_x) ** 2 + (quelle_y - ziel_y) ** 2)

    ruestzeit = 900 / worldspeed

    unitspeed = get_unitspeed_from_unit_name(unitname, df_unitspeed, worldspeed)
    unittype = get_unittype_from_unit_name(unitname, df_unitspeed)
    modified_unitspeed = modify_unitspeed(unitname, unitspeed, unittype, dict_modifiers)  # modify_unitspeed()

    traveltime = math.floor(ruestzeit + dist * 50 / modified_unitspeed)
    traveltime_str = seconds_in_time(traveltime)

    # print(f"Konfiguration:")
    # print(json.dumps(dict_modifiers, indent=4))
    # print(f"Die Laufzeit von Stadt {df_quelle['name'].to_string(index=False)} (ID={start_town_id}) zu Stadt "
    #       f"{df_ziel['name'].to_string(index=False)} (ID={end_town_id}) beträgt mit der Einheit {unitname}:")
    # print(f"{traveltime_str")
    return traveltime, traveltime_str

def get_dataframes_for_world():
    df_islands = pd.read_csv(build_url('Islands','1rbuFTzvioNza7yXpczy4q836x5WHhcy7XHBPdMo3qIE'), keep_default_na=False,
                             names= ['id', 'island_x', 'island_y', 'island_type_number', 'available_towns',
                                   'resources_advantage', 'resources_disadvantage'])

    df_alliances = pd.read_csv(build_url('Alliances', '1rbuFTzvioNza7yXpczy4q836x5WHhcy7XHBPdMo3qIE'), keep_default_na=False,
                               names= ['id', 'name', 'points', 'towns', 'members', 'rank'])
    df_alliances = df_alliances.fillna('')
    df_alliances["name"] = df_alliances["name"].apply(lambda row: unquote(str(row).replace('+', ' ')))

    df_players = pd.read_csv(build_url('Players','1rbuFTzvioNza7yXpczy4q836x5WHhcy7XHBPdMo3qIE'), keep_default_na=False,
                             names= ['id', 'name', 'alliance_id', 'points', 'rank', 'towns'])
    df_players["name"] = df_players["name"].apply(lambda row: unquote(str(row).replace('+', ' ')))
    df_players = df_players.fillna('')
    df_players["id"] = df_players["id"].apply(lambda row: int(row))
    df_players['alliance_id'] = pd.to_numeric(df_players['alliance_id'], errors='coerce')

    df_players = df_players.merge(df_alliances[['id', 'name']], left_on='alliance_id', right_on='id')
    df_players.drop(columns=['id_y'], inplace=True)
    df_players.rename(columns={'id_x': 'id', 'name_y': 'alliance_name', 'name_x': 'name'}, inplace=True)

    df_island_types = pd.read_csv(build_url('Islandtypes','1rbuFTzvioNza7yXpczy4q836x5WHhcy7XHBPdMo3qIE'), keep_default_na=False)

    df_town_info = pd.read_csv(build_url('Grepotags', '1rbuFTzvioNza7yXpczy4q836x5WHhcy7XHBPdMo3qIE'), keep_default_na=False,
                               names=['id', 'unit_info', 'color'])
    df_town_info['color'] = df_town_info['id'].apply(lambda row: row.split('~')[2])
    df_town_info['unit_info'] = df_town_info['id'].apply(lambda row: row.split('~')[1])
    df_town_info['id'] = df_town_info['id'].apply(lambda row: row.split('~')[0])
    df_town_info["id"] = df_town_info["id"].apply(lambda row: int(row.replace('stad', '')))

    df_towns = pd.read_csv(build_url('Towns','1rbuFTzvioNza7yXpczy4q836x5WHhcy7XHBPdMo3qIE'), keep_default_na=False,
                           names= ['id', 'player_id', 'name', 'island_x', 'island_y', 'slot_number_on_island', 'points'])
    df_towns = df_towns.fillna('')
    df_towns["name"] = df_towns["name"].apply(lambda row: unquote(str(row).replace('+', ' ')))
    df_towns["id"] = df_towns["id"].apply(lambda row: int(row))
    df_towns['player_id'] = pd.to_numeric(df_towns['player_id'], errors='coerce')

    df_towns = df_towns.merge(df_players[['id','name', 'alliance_id', 'alliance_name']], left_on='player_id', right_on='id')
    df_towns.drop(columns=['id_y'], inplace=True)
    df_towns.rename(columns={'id_x': 'id',
                           'name_y': 'player_name',
                           'name_x': 'name'}, inplace=True)

    df_towns = df_towns.merge(df_islands[['island_x', 'island_y', 'island_type_number']], on=['island_x', 'island_y'])
    df_towns = df_towns.merge(df_island_types, left_on=['island_type_number', 'slot_number_on_island'], right_on=['island', 'position'])
    df_towns.drop(columns=['island', 'position'], inplace=True)

    df_towns["coord_x"] = df_towns.apply(calc_coord_x, axis=1)
    df_towns["coord_y"] = df_towns.apply(calc_coord_y, axis=1)

    df_towns = df_towns.merge(df_town_info[['id', 'unit_info']], on='id', how='left')
    df_towns = df_towns.fillna('')

    df_unitspeed = pd.read_csv(build_url("Einheitenspeed", "18J-v9okQdfKxaBDloRa1KIxzr39WewsgtRb0XM6Eb-0"),
                               keep_default_na=False)

    return df_islands, df_towns, df_island_types, df_unitspeed

def calc_coord_x(row):
    coord_x = 128 * row["island_x"] + row["offsetx"]
    return coord_x

def calc_coord_y(row):
    if row["island_x"]%2 == 0:
        coord_y = 128 * row["island_y"] + row["offsety"]
    else:
        coord_y = 64 + 128* row["island_y"] + row["offsety"]
    return coord_y

def calc_go_plan_of_alliance(alliance_name, target_city_id, worldspeed, df_towns, df_unitspeed ,dict_modifiers):
    result = df_towns.query(f'alliance_name == "{alliance_name}"')

    df_traveltimes = pd.DataFrame(
        columns=['Stadtname', 'StadtId', 'Stadtinfo', 'Spielername', 'Kolo in s', 'Kolo', 'MD', 'FS', 'lahme Bremse'])

    for row in result.iterrows():
        row = row[1]
        traveltime_kolo, traveltime_str_kolo = calculate_traveltime(row['id'], target_city_id, "Kolonieschiff",
                                                                                worldspeed, df_towns, df_unitspeed,
                                                                                dict_modifiers)
        traveltime_md, traveltime_str_md = calculate_traveltime(row['id'], target_city_id, "Bireme", worldspeed,
                                                                            df_towns, df_unitspeed, dict_modifiers)
        traveltime_fs, traveltime_str_fs = calculate_traveltime(row['id'], target_city_id, "Feuerschiff", worldspeed,
                                                                            df_towns, df_unitspeed, dict_modifiers)
        traveltime_lahme_bremse, traveltime_str_lahme_bremse = calculate_traveltime(row['id'], target_city_id,
                                                                                                "Transportboot",
                                                                                                worldspeed, df_towns,
                                                                                                df_unitspeed,
                                                                                                dict_modifiers)
        new_data = [
            {
                'Stadtname': row['name'],
                'StadtId': row['id'],
                'Stadtinfo': row['unit_info'],
                'Spielername': row['player_name'],
                'Kolo in s': traveltime_kolo,
                'Kolo': traveltime_str_kolo,
                'MD': traveltime_str_md,
                'FS': traveltime_str_fs,
                'lahme Bremse': traveltime_str_lahme_bremse,
                'BBCode': f'[town]{row["id"]}[/town]',
            }
        ]
        df_traveltimes = pd.concat([df_traveltimes, pd.DataFrame(new_data)], ignore_index=True)
    df_traveltimes = df_traveltimes.sort_values(by='Kolo in s')

    return df_traveltimes

# Initialisierung des Dashboards
app = dash.Dash(__name__, update_title='Calculating...')
server = app.server

# Ausführung der Funktion get_dataframes_for_world() einmal zu Beginn
df_islands, df_towns, df_island_types, df_unitspeed = get_dataframes_for_world()

# Layout des Dashboards
app.layout = html.Div([
    html.Div([
        # Links oben: Checkboxen und Eingabefelder
        # Checkboxen
        dcc.Checklist(
            id='checkboxes',
            options=[
                {'label': 'Meteorologie', 'value': 'Meteorologie'},
                {'label': 'Kartografie', 'value': 'Kartografie'},
                {'label': 'Segel setzen', 'value': 'Segel setzen'},
                {'label': 'Verbesserte Truppenbewegung', 'value': 'Verbesserte Truppenbewegung'},
                {'label': 'Leuchtturm', 'value': 'Leuchtturm'}
            ],
            value=['Meteorologie', 'Kartografie', 'Segel setzen'],  # Standardwerte hier setzen
        ),
        html.Div([
            html.Label('Atalanta Stufe:'),
            dcc.Input(id='atalanta-stufe-input', type='number', placeholder='Atalanta Stufe', value=0),
        ], style={'margin': '10px'}),
        html.Div([
            html.Label('Anzahl Sirenen:'),
            dcc.Input(id='anzahl-sirenen-input', type='number', placeholder='Anzahl Sirenen', value=0)
        ], style={'margin': '10px'}),
    ], style={'width': '49%', 'display': 'inline-block'}),

    html.Div([
        # Rechts oben: Eingabefeld für worldspeed, Eingabefelder und Button
        html.Div([
            html.Label('Weltgeschwindigkeit:'),
            dcc.Input(id='worldspeed-input', type='number', placeholder='Weltgeschwindigkeit', value=1),
        ]),
        html.Div([
            html.Label('Allianzname:'),
            dcc.Input(id='allianz-input', type='text', placeholder='Allianzname'),
        ]),
        html.Div([
            html.Label('StadtId:'),
            dcc.Input(id='stadt-id-input', type='number', placeholder='StadtId'),
        ]),
        html.Button('Daten abrufen', id='submit-button', n_clicks=0)
    ], style={'width': '49%', 'display': 'inline-block'}),

    # Links unten: Container für die Tabelle mit fixierten Header-Zeilen
    html.Div(
        id='table-container',
        children=[
            dash_table.DataTable(
                id='table',
                columns=[
                    {'name': 'Stadtname', 'id': 'Stadtname'},
                    {'name': 'StadtId', 'id': 'StadtId'},
                    {'name': 'Stadtinfo', 'id': 'Stadtinfo'},
                    {'name': 'Spielername', 'id': 'Spielername'},
                    {'name': 'Kolo in s', 'id': 'Kolo in s'},
                    {'name': 'Kolo', 'id': 'Kolo'},
                    {'name': 'MD', 'id': 'MD'},
                    {'name': 'FS', 'id': 'FS'},
                    {'name': 'lahme Bremse', 'id': 'lahme Bremse'}
                ],
                data=[],
                style_table={'height': '400px', 'overflowY': 'auto'},
                style_header={
                    'backgroundColor': 'white',
                    'fontWeight': 'bold'
                },
            )
        ],
        style={'width': '49%', 'display': 'inline-block'}
    ),

    # Rechts unten: Container für die Tabelle (identisch zum table-container)
    html.Div(
        id='table-container-right',
        children=[
            dash_table.DataTable(
                id='table-right',
                columns=[
                    {'name': 'Stadtname', 'id': 'Stadtname'},
                    {'name': 'StadtId', 'id': 'StadtId'},
                    {'name': 'Stadtinfo', 'id': 'Stadtinfo'},
                    {'name': 'Spielername', 'id': 'Spielername'},
                    {'name': 'Kolo in s', 'id': 'Kolo in s'},
                    {'name': 'Kolo', 'id': 'Kolo'},
                    {'name': 'MD', 'id': 'MD'},
                    {'name': 'FS', 'id': 'FS'},
                    {'name': 'lahme Bremse', 'id': 'lahme Bremse'}
                ],
                data=[],
                style_table={'height': '400px', 'overflowY': 'auto'},
                style_header={
                    'backgroundColor': 'white',
                    'fontWeight': 'bold'
                },
            )
        ],
        style={'width': '49%', 'display': 'inline-block'}
    )

])

# Callback-Funktion für die Aktualisierung der Tabelle
@app.callback(
    [Output('table-container', 'children'), Output('table-container-right', 'children')],
    [Input('submit-button', 'n_clicks')],
    [dash.dependencies.State('allianz-input', 'value'),
     dash.dependencies.State('stadt-id-input', 'value'),
     dash.dependencies.State('atalanta-stufe-input', 'value'),
     dash.dependencies.State('anzahl-sirenen-input', 'value'),
     dash.dependencies.State('worldspeed-input', 'value'),
     dash.dependencies.State('checkboxes', 'value')]
)
def update_table(n_clicks, alliance_name, target_city_id, atalanta_stufe, anzahl_sirenen, worldspeed, checkbox_values):
    # Rufen Sie die Funktion calc_go_plan_of_alliance mit den entsprechenden Argumenten auf
    dict_modifiers = {
        'Atalanta Stufe': atalanta_stufe,
        'Anzahl Sirenen': anzahl_sirenen,
        'Meteorologie': 'Meteorologie' in checkbox_values,
        'Kartografie': 'Kartografie' in checkbox_values,
        'Segel setzen': 'Segel setzen' in checkbox_values,
        'Verbesserte Truppenbewegung': 'Verbesserte Truppenbewegung' in checkbox_values,
        'Leuchtturm': 'Leuchtturm' in checkbox_values
    }
    result_df = calc_go_plan_of_alliance(alliance_name, target_city_id, worldspeed, df_towns, df_unitspeed, dict_modifiers)

    # Erstellen der aktualisierten Tabelle
    table = dash_table.DataTable(
        id='table',
        columns=[
            {'name': 'Stadtname', 'id': 'Stadtname', 'type': 'text'},
            {'name': 'StadtId', 'id': 'StadtId', 'type': 'numeric'},
            {'name': 'Stadtinfo', 'id': 'Stadtinfo', 'type': 'text'},
            {'name': 'Spielername', 'id': 'Spielername', 'type': 'text'},
            {'name': 'Kolo in s', 'id': 'Kolo in s', 'type': 'numeric'},
            {'name': 'Kolo', 'id': 'Kolo', 'type': 'text'},
            {'name': 'MD', 'id': 'MD', 'type': 'text'},
            {'name': 'FS', 'id': 'FS', 'type': 'text'},
            {'name': 'lahme Bremse', 'id': 'lahme Bremse', 'type': 'text'},
            {'name': 'BBCode', 'id': 'BBCode', 'type': 'text'},
        ],
        data=result_df.to_dict('records'),
        style_table={'height': '400px', 'overflowY': 'auto'},
        style_header={
            'backgroundColor': 'white',
            'fontWeight': 'bold'
        },
    )

    return table, table

if __name__ == '__main__':
    app.run_server(debug=True)
