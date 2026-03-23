import requests
import joblib
import time
import pandas as pd

try:
    # ----------------------------
    # LOAD MODEL + SCALER + LABELS
    # ----------------------------
    model = joblib.load("best_model.pkl")      # ML or DL model
    scaler = joblib.load("scaler.pkl")
    le = joblib.load("label_encoder.pkl")       # Restore labels

    print("✅ Loaded: Model + Scaler + Label Encoder")

    ESP_IP = "192.168.137.112"
    STATUS_URL = f"http://{ESP_IP}/status"
    FAULT_URL  = f"http://{ESP_IP}/1"
    NORMAL_URL = f"http://{ESP_IP}/2"

    # ===== FLASK DASHBOARD =====
    FLASK_URL = "http://localhost:5000/api/hardware/data"  # Flask endpoint

    THINGSPEAK_API_KEY = "3J6LJDI7PCAU2IVL"
    THINGSPEAK_URL     = "https://api.thingspeak.com/update"


    # ----------------------------
    # READ ESP DATA FUNCTION
    # ----------------------------
    def read_esp_data():
        try:
            r = requests.get(STATUS_URL, timeout=50)
            lines = [x.strip() for x in r.text.replace("\r","").split("\n") if x.strip()]

            if len(lines) < 2:
                print("⚠ Incomplete ESP Data!")
                return None

            voltage   = float(lines[0].split(":")[1].replace("V",""))
            current   = float(lines[1].split(":")[1].replace("mA","")) * 20
            frequency = float(lines[2].split(":")[1].replace("Hz","")) if len(lines)>=3 else 50.0

            return voltage, current, frequency

        except Exception as e:
            print("⚠ ESP ERROR:", e)
            return None


    # ----------------------------
    # MAIN LOOP ----------------------------
    while True:
        try:
            data = read_esp_data()
            if data is None:
                time.sleep(3)
                continue

            voltage, current, frequency = data
            print(f"\n📥 {voltage} V | {current} mA | {frequency} Hz")

            X = pd.DataFrame([[voltage, current, frequency]], columns=["voltage","current","frequency"])
            X_scaled = scaler.transform(X)

            # Prediction
            pred = model.predict(X_scaled)[0]
            fault_name = le.inverse_transform([pred])[0]

            print("🔎 PREDICTION:", fault_name)

            # Relay control with increased timeout and error handling
            try:
                if fault_name != "NORMAL":
                    print("🚨 FAULT DETECTED — TRIP RELAY")
                    requests.get(FAULT_URL, timeout=10)  # Increased timeout
                else:
                    print("✅ NORMAL — RELAY RESET")
                    requests.get(NORMAL_URL, timeout=10)  # Increased timeout
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Relay Control Error: {e}")

            # ===== POST TO FLASK DASHBOARD =====
            flask_payload = {
                "voltage": voltage,
                "current": current,
                "frequency": frequency,
                "fault": fault_name
            }
            try:
                flask_res = requests.post(FLASK_URL, json=flask_payload, timeout=5)
                if flask_res.status_code == 200:
                    print("📊 Dashboard Updated ✓")
                else:
                    print(f"⚠️ Dashboard Error: {flask_res.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Dashboard Connection Error: {e}")

            # Upload to ThingSpeak (optional)
            payload = {
                "api_key": THINGSPEAK_API_KEY,
                "field1": voltage,
                "field2": current,
                "field3": frequency,
                "field4": fault_name
            }

            try:
                ts = requests.post(THINGSPEAK_URL, data=payload, timeout=10)
                print("☁️ ThingSpeak:", ts.text)
            except requests.exceptions.RequestException as e:
                print(f"⚠️ ThingSpeak Upload Error: {e}")

        except Exception as e:
            print("❌ MAIN LOOP ERROR:", e)

        time.sleep(2)

except KeyboardInterrupt:
    print("\n🛑 Test interrupted by user. Exiting gracefully...")
    import sys
    sys.exit(0)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import sys
    sys.exit(1)