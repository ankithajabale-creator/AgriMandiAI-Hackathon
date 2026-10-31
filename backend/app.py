import os
import re
import logging
from pathlib import Path

import pandas as pd
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai


# --------------------------------------------------
# APP CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.8-flash"

client = None

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)


# --------------------------------------------------
# CSV COLUMN NORMALIZATION
# --------------------------------------------------

COLUMN_ALIASES = {
    "Commodity": [
        "commodity", "crop", "crop name", "crop_name",
        "commodity name", "commodity_name", "item",
        "product"
    ],
    "State/UT": [
        "state", "state ut", "state/ut", "state name",
        "state_name"
    ],
    "District": [
        "district", "district name", "district_name"
    ],
    "Market": [
        "market", "mandi", "market name", "market_name",
        "mandi name"
    ],
    "Min Price": [
        "min price", "minimum price", "min_price",
        "minimum_price"
    ],
    "Max Price": [
        "max price", "maximum price", "max_price",
        "maximum_price"
    ],
    "Modal Price": [
        "modal price", "modal_price", "modal",
        "price", "price per quintal", "rate"
    ],
    "Arrival Quantity": [
        "arrival quantity", "arrival_quantity",
        "arrivals", "quantity", "arrival"
    ],
    "Arrival Unit": [
        "arrival unit", "arrival_unit", "unit"
    ],
    "Arrival Date": [
        "arrival date", "arrival_date", "date",
        "price date"
    ],
}


def clean_column_name(value):
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_columns(df):
    rename_map = {}

    cleaned_columns = {
        column: clean_column_name(column)
        for column in df.columns
    }

    for standard_name, aliases in COLUMN_ALIASES.items():
        possible_names = [
            clean_column_name(alias)
            for alias in aliases
        ]

        for original, cleaned in cleaned_columns.items():
            if cleaned in possible_names:
                rename_map[original] = standard_name
                break

    return df.rename(columns=rename_map)


# --------------------------------------------------
# LOAD ONE CSV FILE
# --------------------------------------------------

def read_csv_file(file_path):
    best_df = None
    best_score = -1

    # Some government CSV reports have title rows before headers.
    for skip_rows in [0, 1, 2, 3]:
        for encoding in ["utf-8", "latin1"]:
            try:
                df = pd.read_csv(
                    file_path,
                    skiprows=skip_rows,
                    encoding=encoding
                )

                if df.empty:
                    continue

                normalized = normalize_columns(df)

                score = sum(
                    column in normalized.columns
                    for column in [
                        "Commodity",
                        "Modal Price",
                        "Min Price",
                        "Max Price",
                        "Market",
                        "State/UT"
                    ]
                )

                if score > best_score:
                    best_score = score
                    best_df = normalized

            except Exception:
                continue

    return best_df


# --------------------------------------------------
# LOAD AND COMBINE ALL MARKET CSV FILES
# --------------------------------------------------

def load_all_mandi_data():
    all_data = []

    if not DATA_DIR.exists():
        logging.error("Data folder not found: %s", DATA_DIR)
        return pd.DataFrame()

    csv_files = list(DATA_DIR.glob("*.csv"))

    if not csv_files:
        logging.warning("No CSV files found in data folder.")
        return pd.DataFrame()

    for file_path in csv_files:
        try:
            df = read_csv_file(file_path)

            if df is None or df.empty:
                logging.warning(
                    "Could not read useful data from %s",
                    file_path.name
                )
                continue

            # Add missing columns so files can be combined.
            for column in COLUMN_ALIASES:
                if column not in df.columns:
                    df[column] = ""

            # Use a crop name from the filename only for
            # clearly crop-specific files with no crop column.
            if df["Commodity"].fillna("").astype(str).str.strip().eq("").all():
                filename = file_path.stem.lower()

                if "baby_corn" in filename:
                    df["Commodity"] = "Baby Corn"
                elif "beetroot" in filename or "beetrote" in filename:
                    df["Commodity"] = "Beetroot"

            df["Source File"] = file_path.name

            # Clean price columns.
            for column in [
                "Min Price",
                "Max Price",
                "Modal Price",
                "Arrival Quantity"
            ]:
                df[column] = pd.to_numeric(
                    df[column]
                    .astype(str)
                    .str.replace(",", "", regex=False)
                    .str.replace("₹", "", regex=False)
                    .str.strip(),
                    errors="coerce"
                )

            # Keep records with a crop name and a usable price.
            df["Commodity"] = (
                df["Commodity"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            df = df[
                (df["Commodity"] != "") &
                (df["Modal Price"].notna()) &
                (df["Modal Price"] > 0)
            ]

            if not df.empty:
                all_data.append(df)

                logging.info(
                    "Loaded %s usable records from %s",
                    len(df),
                    file_path.name
                )

        except Exception:
            logging.exception(
                "Error loading file %s",
                file_path.name
            )

    if not all_data:
        return pd.DataFrame()

    combined = pd.concat(
        all_data,
        ignore_index=True
    )

    combined = combined.drop_duplicates()

    return combined


# --------------------------------------------------
# HOME / HEALTH CHECK
# --------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "AgriMandiAI backend is running!",
        "data_folder": str(DATA_DIR),
        "gemini_configured": client is not None
    })


# --------------------------------------------------
# CROP SUBMISSION
# --------------------------------------------------

@app.route("/api/crop", methods=["POST"])
def add_crop():
    try:
        data = request.get_json(silent=True) or {}

        crop_name = str(data.get("cropName", "")).strip()
        quantity = float(data.get("quantity", 0))
        location = str(data.get("location", "")).strip()

        if not crop_name or quantity <= 0 or not location:
            return jsonify({
                "error": "Enter valid crop name, quantity and location."
            }), 400

        return jsonify({
            "message": "Crop details submitted successfully!",
            "cropName": crop_name,
            "quantity": quantity,
            "location": location
        }), 200

    except (ValueError, TypeError):
        return jsonify({
            "error": "Quantity must be a valid number."
        }), 400

    except Exception as error:
        logging.exception("Crop submission error")
        return jsonify({"error": str(error)}), 500


# --------------------------------------------------
# MARKET PRICE API
# --------------------------------------------------

@app.route("/api/market-prices", methods=["GET"])
def get_market_prices():
    try:
        df = load_all_mandi_data()

        if df.empty:
            return jsonify({
                "prices": [],
                "total": 0,
                "message": "No usable mandi price records found. Check your CSV files."
            }), 200

        crop = request.args.get("crop", "").strip().lower()
        state = request.args.get("state", "").strip().lower()
        district = request.args.get("district", "").strip().lower()

        if crop:
            df = df[
                df["Commodity"].str.lower().str.contains(
                    crop, na=False
                )
            ]

        if state:
            df = df[
                df["State/UT"].astype(str).str.lower().str.contains(
                    state, na=False
                )
            ]

        if district:
            df = df[
                df["District"].astype(str).str.lower().str.contains(
                    district, na=False
                )
            ]

        df = df.fillna("")

        records = df.to_dict(orient="records")

        return jsonify({
            "prices": records,
            "total": len(records)
        }), 200

    except Exception as error:
        logging.exception("Market price error")
        return jsonify({"error": str(error)}), 500


# --------------------------------------------------
# GEMINI AI RECOMMENDATION
# --------------------------------------------------

@app.route("/api/recommendation", methods=["POST"])
def get_recommendation():
    try:
        if client is None:
            return jsonify({
                "error": "Gemini API key is missing. Check backend/.env."
            }), 503

        data = request.get_json(silent=True) or {}

        crop_name = str(data.get("cropName", "")).strip()
        quantity = float(data.get("quantity", 0))
        location = str(data.get("location", "")).strip()

        transport_cost = float(data.get("transportCost", 0))
        storage_cost = float(data.get("storageCost", 0))
        harvest_days = int(data.get("harvestDays", 0))

        if not crop_name or quantity <= 0:
            return jsonify({
                "error": "Enter a valid crop name and quantity."
            }), 400

        df = load_all_mandi_data()

        if df.empty:
            return jsonify({
                "error": "No usable mandi price data is available."
            }), 404

        matching = df[
            df["Commodity"].astype(str).str.lower().str.contains(
                crop_name.lower(), na=False
            )
        ].copy()

        if matching.empty:
            return jsonify({
                "error": (
                    f"No mandi price records were found for {crop_name}. "
                    "Add a CSV containing actual prices for this crop."
                )
            }), 404

        # Prefer the requested state or district when matching records.
        if location:
            local_matches = matching[
                matching["State/UT"].astype(str).str.lower().str.contains(
                    location.lower(), na=False
                )
                |
                matching["District"].astype(str).str.lower().str.contains(
                    location.lower(), na=False
                )
                |
                matching["Market"].astype(str).str.lower().str.contains(
                    location.lower(), na=False
                )
            ]

            if not local_matches.empty:
                matching = local_matches

        # Limit the amount of CSV data sent to Gemini.
        price_records = matching[
            [
                "Commodity",
                "State/UT",
                "District",
                "Market",
                "Min Price",
                "Max Price",
                "Modal Price",
                "Arrival Date",
                "Source File"
            ]
        ].tail(40).to_dict(orient="records")

        prompt = f"""
You are an agricultural mandi market analysis assistant.

Analyze the farmer's information using ONLY the supplied mandi records.

FARMER INFORMATION:
Crop: {crop_name}
Quantity: {quantity} kg
Location: {location}
Transport cost: Rs. {transport_cost}
Storage cost: Rs. {storage_cost}
Days until harvest: {harvest_days}

ACTUAL MANDI RECORDS:
{price_records}

IMPORTANT RULES:
1. Do not invent prices, market names, dates or trends.
2. Mandi prices are generally reported per quintal.
3. Clearly state that 1 quintal equals 100 kg when discussing prices.
4. Do not assume every record has the same date or market.
5. Mention the number of records available.
6. If the data is insufficient for a reliable decision, say so.
7. Consider transport and storage costs.
8. Do not claim to predict future prices from a single day's data.

Give the farmer a practical answer with these sections:

1. Available Market Data
2. Best Available Mandi Options
3. Estimated Gross Value (only if units are clear)
4. Cost Considerations
5. Recommendation: SELL, WAIT or SPLIT
6. Reason for the Recommendation
7. Data Limitations

Make the answer clear and easy for a farmer to understand.
"""

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        result = response.text

        if not result:
            return jsonify({
                "error": "Gemini returned an empty response. Please try again."
            }), 502

        return jsonify({
            "recommendation": result,
            "records_used": len(matching)
        }), 200

    except (ValueError, TypeError):
        return jsonify({
            "error": "Please enter valid numeric values."
        }), 400

    except Exception as error:
        logging.exception("AI recommendation error")
        return jsonify({
            "error": str(error)
        }), 500


# --------------------------------------------------
# WEATHER API - OPEN METEO
# --------------------------------------------------

@app.route("/weather", methods=["GET"])
def get_weather():
    try:
        location = request.args.get(
            "location", "Bengaluru"
        ).strip()

        if not location:
            return jsonify({
                "error": "Please enter a city name."
            }), 400

        # Find city coordinates.
        geo_response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json"
            },
            timeout=15
        )

        geo_response.raise_for_status()
        geo_data = geo_response.json()

        results = geo_data.get("results", [])

        if not results:
            return jsonify({
                "error": f"Location '{location}' was not found."
            }), 404

        place = results[0]

        latitude = place["latitude"]
        longitude = place["longitude"]

        # Get current weather and forecast.
        weather_response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "weather_code,"
                    "wind_speed_10m"
                ),
                "daily": (
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_probability_max"
                ),
                "forecast_days": 5,
                "timezone": "auto"
            },
            timeout=20
        )

        weather_response.raise_for_status()
        weather_data = weather_response.json()

        return jsonify({
            "location": {
                "name": place.get("name"),
                "country": place.get("country"),
                "latitude": latitude,
                "longitude": longitude
            },
            "current": weather_data.get("current", {}),
            "daily": weather_data.get("daily", {}),
            "timezone": weather_data.get("timezone")
        }), 200

    except requests.RequestException as error:
        logging.exception("Weather API connection error")
        return jsonify({
            "error": f"Weather service connection failed: {str(error)}"
        }), 502

    except Exception as error:
        logging.exception("Weather error")
        return jsonify({"error": str(error)}), 500


# --------------------------------------------------
# START FLASK SERVER
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )