# %% [markdown]
# # Dashboard Load
# Running this file creates a link to an interactive dashboard where co-ops can record what sites they've looked at and identified. So far I've suggested 'Unexamined','Potentially suitable','Confirmed unsuitable','Confirmed project','further examination', these can be changed. I believe the data is stored in reviews.db which is a SQL db hosted here (not sure how that works with multiple users!).
# 
# The dots on the map are bigger or smaller based on roof size and redder or yellower based on solar potential (bounded to encourage graduation).
# 
# Will tidy it up so its not just one big code block.
# 
# Using the dashboard: so far, just click the link, then click the layers button (three sheets on top o each other) to filter between reviewed, potential etc. When you find a roof that looks good simply click on the dot for that roof, check the address and some details on google maps, record the info and why you're assigning it to a category, then submit it. It should then live update the map. The only issue is that it seems to crash slightly... so need to look into where the bottlenecks are!
# 
# quick AI explanation of the process:
# 
# 'The dashboard is currently hosted locally on your computer. Running the notebook starts a Dash web server, and your browser opens the dashboard through a local address.
# 
# Your Python code handles the map and reviews, while reviews.db stores the saved reviews on your computer. Esri supplies the background imagery over the internet.
# 
# It isn’t deployed online: other volunteers don’t automatically have access, and it stops being available when the Python server stops.'

# %%

import os
import psycopg
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd
import geopandas as gpd
import dash_leaflet as dl

from branca.colormap import linear
from dash import (
    Dash, html, dcc,
    Input, Output, State,
    ALL, ctx, Patch, no_update,
)
from dash.exceptions import PreventUpdate
from pathlib import Path
import requests
from functools import lru_cache

# %% [markdown]
# Filtering southwark sites by criteria:
# - >300m^2 roof size (from the Repowering guide)
# - >30,000 Annual kWh potential (where the LSOM starts to turn 'red', can change to kW peak using solar wizard)

BASE_DIR = Path(__file__).resolve().parent

GPKG_PATH = BASE_DIR / "Southwark" / "southwark_joined_solar.gpkg"
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Set it to your Neon connection string."
    )


def connect_db():
    return psycopg.connect(
        DATABASE_URL,
        connect_timeout=15,
    )

# %%
#the joined OS geometry and solar potential data for Southwark
southwark = gpd.read_file(GPKG_PATH)

#filtering by roof size and kWh potential
candidates_m2_kwh = southwark[
    (southwark["area3d_in_potential"] >= 300)
    & (southwark["sum_total_potential"] >= 30000)
].copy()

# %% [markdown]
# Now, this whole thing, just run it and click on the link it creates, this is where the dashboard lives (may need to host this somewhere... Repowering, Southwark council?)

# %%
TOID_COLUMN = "TOID"

STATUS_LAYERS = {
    "Unreviewed": "unreviewed-markers",
    "Needs investigation": "investigation-markers",
    "Potentially suitable": "potential-markers",
    "Confirmed Site/Being Developed": "confirmed-markers",
    "Unsuitable": "unsuitable-markers",
}


# --------------------------------------------------
# Prepare candidate points
# --------------------------------------------------

points = candidates_m2_kwh.to_crs(4326).copy()

points = points.dropna(
    subset=[
        TOID_COLUMN,
        "geometry",
        "area3d_in_potential",
        "sum_total_potential",
    ]
)

points = points.loc[~points.geometry.is_empty].copy()
points[TOID_COLUMN] = points[TOID_COLUMN].astype(str)

if points.empty:
    raise ValueError("No valid candidates.")

if points[TOID_COLUMN].duplicated().any():
    raise ValueError(
        "Duplicate TOIDs: resolve these before reviewing sites."
    )

if not points.geometry.geom_type.eq("Point").all():
    raise ValueError("Candidate geometries must all be Points.")

points = points.set_index(TOID_COLUMN, drop=False)


# --------------------------------------------------
# Append-only review history
# --------------------------------------------------

# --------------------------------------------------
# Append-only review history in Neon/Postgres
# --------------------------------------------------

with connect_db() as con:
    con.execute("""
        CREATE TABLE IF NOT EXISTS review_database (
            review_id BIGINT GENERATED ALWAYS AS IDENTITY
                PRIMARY KEY,
            toid TEXT NOT NULL,
            status TEXT NOT NULL,
            comment TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            reviewed_at TIMESTAMPTZ NOT NULL
        )
    """)
    con.execute("""
        ALTER TABLE review_database
        ADD COLUMN IF NOT EXISTS address TEXT NOT NULL DEFAULT ''
    """)

    con.execute("""
        ALTER TABLE review_database
        ADD COLUMN IF NOT EXISTS solar_wizard_kwp DOUBLE PRECISION
    """)

    con.execute("""
        CREATE INDEX IF NOT EXISTS review_database_toid_review_idx
        ON review_database (toid, review_id DESC)
    """)


def get_map_points():
    with connect_db() as con:
        rows = con.execute("""
            SELECT DISTINCT ON (toid)
                toid, status
            FROM review_database
            ORDER BY toid, review_id DESC
        """).fetchall()

    latest_reviews = pd.DataFrame(
        rows,
        columns=["toid", "status"],
    )

    status_by_toid = latest_reviews.set_index("toid")["status"]

    map_points = points.copy()
    map_points["status"] = (
        map_points[TOID_COLUMN]
        .map(status_by_toid)
        .fillna("Unreviewed")
    )

    map_points["status"] = map_points["status"].replace({
        "Confirmed site": "Confirmed Site/Being Developed",
    })

    return map_points


def latest_review(toid):
    with connect_db() as con:
        return con.execute(
            """
            SELECT status, comment, reviewer, reviewed_at,
                    address, solar_wizard_kwp
            FROM review_database
            WHERE toid = %s
            ORDER BY review_id DESC
            LIMIT 1
            """,
            (str(toid),),
        ).fetchone()

# --------------------------------------------------
# Marker and details helpers
# --------------------------------------------------

colours = linear.YlOrRd_09.scale(30_000, 2_000_000)


def make_markers(frame):
    markers = []

    for toid, row in frame.sort_values(
        "area3d_in_potential",
        ascending=False,
    ).iterrows():
        markers.append(
            dl.CircleMarker(
                id={"type": "site", "toid": toid},
                n_clicks=0,
                center=[row.geometry.y, row.geometry.x],
                radius=float(
                    5 * np.sqrt(
                        np.clip(
                            row["area3d_in_potential"],
                            300,
                            2_000,
                        ) / 300
                    )
                ),
                color="white",
                weight=1,
                fillColor=colours(float(
                    np.clip(
                        row["sum_total_potential"],
                        30_000,
                        2_000_000,
                    )
                )),
                fillOpacity=0.9,
                children=dl.Tooltip(
                    f"{row['area3d_in_potential']:,.0f} m² | "
                    f"Potential: {row['sum_total_potential']:,.0f} | "
                    f"Status: {row['status']}"
                ),
            )
        )

    return markers

@lru_cache(maxsize=2048)
def nearby_postcode(latitude, longitude):
    try:
        response = requests.get(
            "https://api.postcodes.io/postcodes",
            params={
                "lat": latitude,
                "lon": longitude,
                "limit": 1,
                "radius": 500,
            },
            timeout=5,
        )
        response.raise_for_status()

        results = response.json().get("result") or []

        if not results:
            return None

        match = results[0]

        return (
            match["postcode"],
            match["distance"],
        )

    except (requests.RequestException, ValueError, KeyError):
        return None
    
def site_details(toid, row):
    saved = latest_review(toid)

    postcode_match = nearby_postcode(
        float(row.geometry.y),
        float(row.geometry.x),
    )

    maps_url = (
        "https://www.google.com/maps/search/?api=1"
        f"&query={row.geometry.y},{row.geometry.x}"
    )

    details = [
        #html.P(f"TOID: {toid}"),
        html.P(
            f"Roof area: {row['area3d_in_potential']:,.0f} m²"
        ),
        html.P(
            f"Potential: {row['sum_total_potential']:,.0f}"
        ),
    ]

    # if "avg_tilt" in row.index:
    #     details.append(
    #         html.P(f"Average roof tilt: {row['avg_tilt']}")
    #     )

    if "lidar_date" in row.index and pd.notna(row["lidar_date"]):
        details.append(
            html.P(f"LiDAR year: {int(row['lidar_date'])}")
        )
    if postcode_match:
        postcode, distance = postcode_match

        details.append(
            html.P(
                f"Nearby postcode: {postcode} "
                f"(postcode location {distance:.0f} m away; "
                "check the correct building)"
            )
        )
    else:
        details.append(
            html.P("Nearby postcode lookup unavailable.")
        )
    details.extend([
        html.P(
            f"Saved status: {saved[0] if saved else 'Unreviewed'}"
        ),
        html.P(
            f"Last reviewed by {saved[2]} at {saved[3]}"
            if saved else "Not yet reviewed."
        ),
        html.A(
            "Open Google Maps",
            href=maps_url,
            target="_blank",
            rel="noopener noreferrer",
        ),

        html.Br(),

        html.A(
            "Open Solar Wizard",
            href="https://solarwizard.org.uk/wizard",
            target="_blank",
            rel="noopener noreferrer",
        ),
    ])

    return details


# --------------------------------------------------
# Layout
# --------------------------------------------------

west, south, east, north = points.total_bounds

app = Dash(__name__)
server = app.server


def data_sources_panel():
    def link(label, url):
        return html.A(label, href=url, target="_blank", rel="noopener noreferrer")

    return html.Div([
        html.P([
            "Solar data: Greater London Authority / UCL London Solar Opportunity Map. ",
            "Locations: Ordnance Survey OS Open TOID. ",
            html.A("Data sources & licences", href="#data-sources"),
        ], style={"marginBottom": "8px"}),
        html.Details([
            html.Summary("Data sources, licences & limitations"),
            html.P("Draft research tool developed by Odhrán Dooley for Southwark Community Energy. "
                   "Screening results are indicative, not engineering or legal assessments. "
                   "Acknowledgement does not imply endorsement by data providers."),
            html.H4("London Solar Opportunity Map (LSOM)"),
            html.P("Source: Greater London Authority, developed with UCL Energy Institute and "
                   "UCL Centre for Advanced Spatial Analysis. Used for roof-area and solar-potential "
                   "estimates, filtered and joined to locations using TOIDs. The published dataset "
                   "lists Open Government Licence v3 and the notice: "
                   "© Crown copyright and database rights 2023."),
            html.P([
                link("LSOM dataset and notices", "https://data.london.gov.uk/dataset/london-solar-opportunity-map-lsom-vdxyl"),
                " | ", link("Open Government Licence v3", "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"),
            ]),
            html.P("LSOM potential is not installed peak capacity (kWp). The raw potential uses a "
                   "100% utilisation assumption; LSOM's public-map assumption is 11.9%. "
                   "The publisher describes 2017 building outlines and LiDAR collected between "
                   "2006 and 2016. Check each record's LiDAR year; later changes may be absent."),
            html.H4("Ordnance Survey OS Open TOID"),
            html.P("Used for generalised feature locations linked by TOID, not building footprints. "
                   "Licensed under Open Government Licence v3. Contains OS data © Crown copyright "
                   "and database right. See the original download for the applicable copyright year "
                   "and any additional notices."),
            html.P(link("OS Open TOID", "https://www.ordnancesurvey.co.uk/products/os-open-toid")),
            html.H4("Satellite imagery"),
            html.P("Esri World Imagery and its credited imagery providers supply the background. "
                   "Provider attribution is displayed on the map. Imagery is not distributed under "
                   "this project's software licence."),
            html.H4("Nearby postcode lookup"),
            html.P(["Postcode lookup is supplied by ", link("Postcodes.io", "https://postcodes.io/"),
                    ". The nearest postcode is a navigation aid, not a verified building address. ",
                    link("Postcodes.io data sources and licences", "https://postcodes.io/about/"), "."]),
            html.H4("External review tools and ownership research"),
            html.P([
                link("Google Maps", "https://www.google.com/maps"), "; ",
                link("Solar Wizard", "https://solarwizard.org.uk/wizard"), "; ",
                link("LandExplorer", "https://landexplorer.coop/"), "; ",
                link("Carbon & Place Land Ownership Explorer", "https://www.carbon.place/landownership/"),
                ". External tools have their own terms. Listing them does not mean their data "
                "is embedded, licensed for extraction, or endorsed for this workflow.",
            ]),
            html.P("HM Land Registry INSPIRE, CCOD and OCOD are not loaded directly by this dashboard "
                   "script. Any separate processing or recorded ownership findings must retain "
                   "their source, date and applicable licence notices. Permission to store, publish "
                   "or use ownership findings for outreach must be checked separately."),
            html.H4("Software and data licences are separate"),
            html.P("Any open-source licence for this project's original code does not override "
                   "third-party data, imagery, API or software terms. Preserve the original "
                   "dataset notices with exports. Review statuses and comments are volunteer "
                   "assessments, not confirmation of ownership or solar feasibility."),
        ], id="data-sources", style={"lineHeight": "1.5"}),
    ], style={"padding": "12px 16px", "borderTop": "1px solid #ddd", "fontSize": "14px"})

app.layout = html.Div([
    html.H2("Community Energy — Site Screening"),

    dcc.Store(id="selected-toid"),
    dcc.Store(id="review-saved-event", data=None),
    dcc.Store(id="layer-toids", data=None),

    html.Div([
        dl.Map(
            [
                dl.TileLayer(
                    url=(
                        "https://server.arcgisonline.com/"
                        "ArcGIS/rest/services/World_Imagery/"
                        "MapServer/tile/{z}/{y}/{x}"
                    ),
                    attribution=(
                        "Tiles © Esri — Sources: Esri, "
                        "DigitalGlobe, GeoEye, i-cubed, USDA FSA, "
                        "USGS, AEX, Getmapping, Aerogrid, IGN, "
                        "IGP, swisstopo, and the GIS User Community"
                        " | Contains OS data &copy; Crown copyright and database right"
                    ),
                ),

                dl.LayersControl(
                    [
                        dl.Overlay(
                            dl.LayerGroup(
                                id=layer_id,
                                children=[],
                            ),
                            name=status,
                            checked=True,
                        )
                        for status, layer_id
                        in STATUS_LAYERS.items()
                    ],
                    position="topright",
                ),
            ],
            center=[
                (south + north) / 2,
                (west + east) / 2,
            ],
            zoom=13,
            style={
                "height": "80vh",
                "flex": "1",
                "minWidth": "0",
            },
        ),

        html.Div([
            html.H3("Site review"),

            html.Div(
                id="site-info",
                children="Click a site on the map.",
            ),

            html.Hr(),

            html.Label("Status"),
            dcc.Dropdown(
                id="review-status",
                options=list(STATUS_LAYERS),
                value="Unreviewed",
                clearable=False,
            ),

            html.Label("Site address"),
            dcc.Input(
                id="review-address",
                type="text",
                placeholder="Building name, street and postcode",
                style={"width": "100%"},
            ),

            html.Label("Solar Wizard peak capacity (kWp)"),
            dcc.Input(
                id="review-solar-kwp",
                type="number",
                min=0,
                step="any",
                placeholder="Enter capacity in kWp",
                style={"width": "100%"},
            ),

            html.Label("Your name"),
            dcc.Input(
                id="reviewer",
                placeholder="Reviewer name",
                style={"width": "100%"},
            ),

            html.Label("Comment / reason"),
            dcc.Textarea(
                id="review-comment",
                style={
                    "width": "100%",
                    "height": "120px",
                },
            ),

            html.Button(
                "Save review",
                id="save-review",
                n_clicks=0,
                disabled=True,
                style={"marginTop": "12px"},
            ),

            html.Div(id="save-message"),
        ], style={
            "width": "340px",
            "padding": "16px",
            "boxSizing": "border-box",
        }),
    ], style={"display": "flex"}),
    data_sources_panel(),
])


# --------------------------------------------------
# Initial map load, then targeted marker updates
# --------------------------------------------------

@app.callback(
    [
        Output(layer_id, "children")
        for layer_id in STATUS_LAYERS.values()
    ] + [
        Output("layer-toids", "data"),
    ],
    Input("review-saved-event", "data"),
    State("layer-toids", "data"),
)
def refresh_map(save_event, layer_toids):
    statuses = list(STATUS_LAYERS)

    # Full build only when this browser page first loads.
    if layer_toids is None:
        map_points = get_map_points()

        unknown_statuses = (
            set(map_points["status"].unique()) - set(statuses)
        )

        if unknown_statuses:
            raise ValueError(
                "Some saved statuses do not match STATUS_LAYERS: "
                f"{sorted(unknown_statuses)}"
            )

        layer_children = []
        ordered_toids = {}

        for status in statuses:
            frame = map_points.loc[
                map_points["status"] == status
            ].sort_values(
                "area3d_in_potential",
                ascending=False,
            )

            layer_children.append(make_markers(frame))
            ordered_toids[status] = frame.index.tolist()

        return layer_children + [ordered_toids]

    if not save_event:
        raise PreventUpdate

    toid = save_event["toid"]
    new_status = save_event["status"]

    old_status = None
    old_index = None

    # Find this marker in the browser's existing layer order.
    for status in statuses:
        try:
            old_index = layer_toids[status].index(toid)
            old_status = status
            break
        except ValueError:
            continue

    if old_status is None:
        raise ValueError(
            f"Cannot find marker for TOID {toid}. "
            "Refresh the page to rebuild the map."
        )

    # No map change is needed for a comment/name-only update.
    if old_status == new_status:
        raise PreventUpdate

    # Construct only the one changed marker.
    frame = points.loc[[toid]].copy()
    frame["status"] = new_status
    updated_marker = make_markers(frame)[0]

    remove_patch = Patch()
    del remove_patch[old_index]

    add_patch = Patch()
    add_patch.append(updated_marker)

    layer_updates = [no_update] * len(statuses)
    layer_updates[statuses.index(old_status)] = remove_patch
    layer_updates[statuses.index(new_status)] = add_patch

    # Keep the TOID ordering aligned with the marker ordering.
    index_patch = Patch()
    del index_patch[old_status][old_index]
    index_patch[new_status].append(toid)

    return layer_updates + [index_patch]


# --------------------------------------------------
# Site selection and review saving
# --------------------------------------------------

@app.callback(
    Output("selected-toid", "data"),
    Output("site-info", "children"),
    Output("review-status", "value"),
    Output("review-comment", "value"),
    Output("save-review", "disabled"),
    Output("save-message", "children"),
    Output("review-saved-event", "data"),
    Output("review-address", "value"),
    Output("review-solar-kwp", "value"),

    Input({"type": "site", "toid": ALL}, "n_clicks"),
    Input("save-review", "n_clicks"),

    State({"type": "site", "toid": ALL}, "id"),
    State("selected-toid", "data"),
    State("review-status", "value"),
    State("review-comment", "value"),
    State("reviewer", "value"),
    State("review-address", "value"),
    State("review-solar-kwp", "value"),

    prevent_initial_call=True,
)
def review_site(
    clicks,
    save_clicks,
    marker_ids,
    toid,
    status,
    comment,
    reviewer,
    address,
    solar_kwp,
):
    trigger = ctx.triggered_id
    message = ""
    save_event = no_update

    if isinstance(trigger, dict):
        # Newly inserted markers have n_clicks=0.
        # Ignore insertion/removal events rather than selecting them.
        clicked_count = next(
            (
                count
                for marker_id, count in zip(marker_ids, clicks)
                if marker_id == trigger
            ),
            None,
        )

        if not clicked_count:
            raise PreventUpdate

        toid = trigger["toid"]

    elif trigger == "save-review":
        if not toid or not save_clicks:
            raise PreventUpdate

        row = points.loc[toid]

        if not reviewer or not reviewer.strip():
            return (
                toid,
                site_details(toid, row),
                status,
                comment,
                False,
                "Please enter your name.",
                no_update,
            )

        if status not in STATUS_LAYERS:
            return (
                toid,
                site_details(toid, row),
                status,
                comment,
                False,
                "Please choose a valid status.",
                no_update,
            )

        clean_comment = (comment or "").strip()

        if status == "Unsuitable" and not clean_comment:
            return (
                toid,
                site_details(toid, row),
                status,
                comment,
                False,
                "Please enter a reason for marking this site unsuitable.",
                no_update,
            )

        with connect_db() as con:
            con.execute(
                """
                INSERT INTO review_database
                    (
                        toid,
                        status,
                        comment,
                        reviewer,
                        reviewed_at,
                        address,
                        solar_wizard_kwp
                    )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(toid),
                    status,
                    clean_comment,
                    reviewer.strip(),
                    datetime.now(timezone.utc),
                    (address or "").strip(),
                    float(solar_kwp) if solar_kwp is not None else None,
                ),
            )

        message = "Review saved."

        # save_event = {
        #     "toid": toid,
        #     "status": status,
        #     "event_id": str(uuid4()),
        # }
        save_event = no_update

    else:
        raise PreventUpdate

    row = points.loc[toid]
    saved = latest_review(toid)

    saved_status = saved[0] if saved else "Unreviewed"

    if saved_status == "Confirmed site":
        saved_status = "Confirmed Site/Being Developed"

    return (
        toid,
        site_details(toid, row),
        saved_status,
        saved[1] if saved else "",
        False,
        message,
        save_event,
        (saved[4] or "") if saved else "",
        saved[5] if saved else None,
    )


if __name__ == "__main__":
    app.run(debug=True)


