import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const API = "http://localhost:5000";

function App() {
  const [page, setPage] = useState("Dashboard");
  const [crop, setCrop] = useState({ cropName: "", quantity: "", location: "" });
  const [savedCrop, setSavedCrop] = useState(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [marketLoading, setMarketLoading] = useState(false);
  const [prices, setPrices] = useState([]);
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [priceError, setPriceError] = useState("");

  const [rec, setRec] = useState({
    cropName: "", quantity: "", location: "",
    transportCost: "0", storageCost: "0", harvestDays: "0"
  });
  const [result, setResult] = useState("");
  const [recError, setRecError] = useState("");
  const [recLoading, setRecLoading] = useState(false);

  const [city, setCity] = useState("Bengaluru");
  const [weather, setWeather] = useState(null);
  const [weatherError, setWeatherError] = useState("");
  const [weatherLoading, setWeatherLoading] = useState(false);

  const updateCrop = (e) =>
    setCrop({ ...crop, [e.target.name]: e.target.value });

  const updateRec = (e) =>
    setRec({ ...rec, [e.target.name]: e.target.value });

  // Submit crop
  const submitCrop = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const r = await axios.post(`${API}/api/crop`, {
        ...crop, quantity: Number(crop.quantity)
      });
      setSavedCrop(r.data);
      setMessage(r.data.message || "Crop submitted successfully!");
      setCrop({ cropName: "", quantity: "", location: "" });
    } catch (err) {
      setMessage(err.response?.data?.error || "Crop submission failed.");
    } finally {
      setLoading(false);
    }
  };

  // Load all CSV market records
  const loadPrices = async () => {
  if (marketLoading) return;

  setMarketLoading(true);
  setPriceError("");

  try {
    const response = await axios.get(
      `${API}/api/market-prices?limit=100`
    );

    const rows = Array.isArray(response.data)
      ? response.data
      : response.data.prices || [];

    setPrices(rows);
    setPriceError(
      rows.length === 0 ? "No market prices found." : ""
    );
  } catch (error) {
    console.error("Market price error:", error);
    setPriceError("Unable to load market prices.");
  } finally {
    setMarketLoading(false);
  }
};

  useEffect(() => {
    if (page === "Market Prices") loadPrices();
  }, [page]);

  const filtered = prices.filter((p) =>
    String(p.Commodity || "").toLowerCase().includes(search.toLowerCase()) &&
    String(p["State/UT"] || "").toLowerCase().includes(state.toLowerCase())
  );

  const states = [...new Set(prices.map(p => p["State/UT"]).filter(Boolean))].sort();
  const crops = [...new Set(prices.map(p => p.Commodity).filter(Boolean))];

  // Gemini recommendation
  const getRecommendation = async (e) => {
    e.preventDefault();
    setRecError("");
    setResult("");

    if (!rec.cropName.trim() || Number(rec.quantity) <= 0) {
      setRecError("Enter a valid crop name and quantity.");
      return;
    }

    setRecLoading(true);
    try {
      const r = await axios.post(`${API}/api/recommendation`, {
        ...rec,
        quantity: Number(rec.quantity),
        transportCost: Number(rec.transportCost || 0),
        storageCost: Number(rec.storageCost || 0),
        harvestDays: Number(rec.harvestDays || 0)
      });
      setResult(r.data.recommendation || "No recommendation returned.");
    } catch (err) {
      setRecError(err.response?.data?.error || "AI recommendation failed.");
    } finally {
      setRecLoading(false);
    }
  };

  // Weather
  const getWeather = async (e) => {
    if (e) e.preventDefault();
    setWeatherError("");
    setWeather(null);
    setWeatherLoading(true);
    try {
      const r = await axios.get(`${API}/weather`, {
        params: { location: city }
      });
      setWeather(r.data);
    } catch (err) {
      setWeatherError(err.response?.data?.error || "Weather loading failed.");
    } finally {
      setWeatherLoading(false);
    }
  };

  useEffect(() => {
    if (page === "Weather" && !weather && !weatherLoading) getWeather();
  }, [page]);

  const weatherText = (code) => {
    if (code === 0) return "Clear sky";
    if ([1, 2, 3].includes(code)) return "Partly cloudy";
    if ([45, 48].includes(code)) return "Fog";
    if ([51, 53, 55].includes(code)) return "Drizzle";
    if ([61, 63, 65].includes(code)) return "Rain";
    if ([80, 81, 82].includes(code)) return "Rain showers";
    if ([95, 96, 99].includes(code)) return "Thunderstorm";
    return "Weather information";
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>🌱 AgriMandiAI</h2>
        <p className="side-subtitle">Smart Agriculture Platform</p>
        {["Dashboard", "Crop Details", "Market Prices", "AI Recommendation", "Weather"].map(item =>
          <button key={item} className={page === item ? "nav active" : "nav"}
            onClick={() => setPage(item)}>{item}</button>
        )}
        <div className="side-footer">Smart Farming<br />Better Future 🌾</div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><h1>{page}</h1><p>Welcome to your smart farming assistant.</p></div>
          <span className="profile">👨‍🌾 Farmer</span>
        </header>

        {page === "Dashboard" && <>
          <section className="welcome">
            <h2>Welcome to AgriMandiAI!</h2>
            <p>Make smarter crop-selling decisions with market data, AI and weather.</p>
            <button onClick={() => setPage("Crop Details")}>Enter Crop Details →</button>
          </section>
          <section className="cards">
            {[
              ["🌾", "Crop Details", "Submit crop information."],
              ["💰", "Market Prices", "Explore mandi prices."],
              ["🤖", "AI Recommendation", "Get selling guidance."],
              ["🌦️", "Weather", "Check local weather."]
            ].map(([icon, name, desc]) =>
              <div className="card" key={name}>
                <span>{icon}</span><h3>{name}</h3><p>{desc}</p>
                <button onClick={() => setPage(name)}>Open</button>
              </div>
            )}
          </section>
        </>}

        {page === "Crop Details" && <section className="panel">
          <h2>🌾 Enter Crop Details</h2>
          <form onSubmit={submitCrop}>
            <label>Crop Name</label>
            <input name="cropName" value={crop.cropName} onChange={updateCrop} placeholder="Tomato" required />
            <label>Quantity (kg)</label>
            <input name="quantity" type="number" min="1" value={crop.quantity} onChange={updateCrop} required />
            <label>Location</label>
            <input name="location" value={crop.location} onChange={updateCrop} placeholder="Mysuru" required />
            <button className="submit" disabled={loading}>{loading ? "Submitting..." : "Submit Crop Details"}</button>
          </form>
          {message && <p className="message">{message}</p>}
          {savedCrop && <div className="result">
            <h3>Submitted Crop</h3>
            <p>Crop: {savedCrop.cropName}</p>
            <p>Quantity: {savedCrop.quantity} kg</p>
            <p>Location: {savedCrop.location}</p>
          </div>}
        </section>}

        {page === "Market Prices" && <section className="panel">
          <h2>💰 Market Prices</h2>
          <label>Search crop</label>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Tomato, Onion, Apple..." />
          <label>Filter state</label>
          <select value={state} onChange={e => setState(e.target.value)}>
            <option value="">All States</option>
            {states.map(s => <option key={s}>{s}</option>)}
          </select>
          {priceError && <p className="message">{priceError}</p>}
          {!priceError && <>
            <p>Records: {prices.length} | Crop types: {crops.length} | Matching: {filtered.length}</p>
            <div className="table-container"><table>
              <thead><tr>
                <th>Crop</th><th>State</th><th>District</th><th>Mandi</th>
                <th>Min</th><th>Max</th><th>Modal</th><th>Arrival</th><th>Date</th><th>Source</th>
              </tr></thead>
              <tbody>{filtered.map((p, i) => <tr key={i}>
                <td>{p.Commodity}</td><td>{p["State/UT"]}</td><td>{p.District}</td>
                <td>{p.Market}</td><td>{p["Min Price"]}</td><td>{p["Max Price"]}</td>
                <td>{p["Modal Price"]}</td>
                <td>{p["Arrival Quantity"]} {p["Arrival Unit"]}</td>
                <td>{p["Arrival Date"]}</td><td>{p["Source File"]}</td>
              </tr>)}</tbody>
            </table></div>
          </>}
          <button className="submit" onClick={loadPrices} disabled={marketLoading}>
            {marketLoading ? "Loading..." : "Refresh Prices"}
          </button>
          {marketLoading && <p>Loading market prices...</p>}
        </section>}

        {page === "AI Recommendation" && <section className="panel">
          <h2>🤖 AI Crop Selling Recommendation</h2>
          <form onSubmit={getRecommendation}>
            <label>Crop Name</label>
            <input name="cropName" value={rec.cropName} onChange={updateRec} placeholder="Tomato" required />
            <label>Quantity (kg)</label>
            <input name="quantity" type="number" min="1" value={rec.quantity} onChange={updateRec} required />
            <label>Location</label>
            <input name="location" value={rec.location} onChange={updateRec} placeholder="Mysuru" />
            <label>Transport Cost (₹)</label>
            <input name="transportCost" type="number" min="0" value={rec.transportCost} onChange={updateRec} />
            <label>Storage Cost (₹)</label>
            <input name="storageCost" type="number" min="0" value={rec.storageCost} onChange={updateRec} />
            <label>Days Until Harvest</label>
            <input name="harvestDays" type="number" min="0" value={rec.harvestDays} onChange={updateRec} />
            <button className="submit" disabled={recLoading}>
              {recLoading ? "Analyzing..." : "Get AI Recommendation"}
            </button>
          </form>
          {recError && <p className="message">{recError}</p>}
          {result && <div className="result">
            <h3>AI Recommendation</h3>
            <div style={{ whiteSpace: "pre-wrap" }}>{result}</div>
          </div>}
        </section>}

        {page === "Weather" && <section className="panel">
          <h2>🌦️ Weather Information</h2>
          <form onSubmit={getWeather}>
            <label>Enter City</label>
            <input value={city} onChange={e => setCity(e.target.value)} placeholder="Bengaluru" required />
            <button className="submit" disabled={weatherLoading}>
              {weatherLoading ? "Loading..." : "Get Weather"}
            </button>
          </form>
          {weatherError && <p className="message">{weatherError}</p>}
          {weather?.current && <div className="result">
            <h3>📍 {weather.location?.name || city}</h3>
            <h1>{weather.current.temperature_2m}°C</h1>
            <p>{weatherText(weather.current.weather_code)}</p>
            <p>Feels like: {weather.current.apparent_temperature}°C</p>
            <p>Humidity: {weather.current.relative_humidity_2m}%</p>
            <p>Wind: {weather.current.wind_speed_10m} km/h</p>
            <p>Precipitation: {weather.current.precipitation} mm</p>
            {weather.daily?.time && <>
              <h3>Five-Day Forecast</h3>
              <div className="table-container"><table>
                <thead><tr><th>Date</th><th>Max °C</th><th>Min °C</th><th>Rain chance</th></tr></thead>
                <tbody>{weather.daily.time.map((date, i) => <tr key={date}>
                  <td>{date}</td>
                  <td>{weather.daily.temperature_2m_max?.[i]}°C</td>
                  <td>{weather.daily.temperature_2m_min?.[i]}°C</td>
                  <td>{weather.daily.precipitation_probability_max?.[i] ?? "—"}%</td>
                </tr>)}</tbody>
              </table></div>
            </>}
          </div>}
        </section>}

        <footer>© 2026 AgriMandiAI | Smart Agriculture for Everyone</footer>
      </main>
    </div>
  );
}

export default App;