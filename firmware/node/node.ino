/*
 * ColdGuard sensor node - NodeMCU ESP8266 (ESP-12E) + DHT11
 *
 * Publishes every 2 s to  coldguard/TRK-07/telemetry
 *     {"truck_id":"TRK-07","air_c":3.4,"hum_pct":86,"door_open":false}
 * The backend adds the timestamp, the position along route R1, the product and
 * the quantity (CLAUDE.md section 6).
 *
 * Wiring
 *   DHT11 +/VCC  -> 3V3
 *   DHT11 -/GND  -> G
 *   DHT11 S/DATA -> D2 (GPIO4)
 *   optional lid switch between D5 (GPIO14) and G: closed lid = contact closed
 *
 * Arduino IDE 2
 *   Boards Manager URL  http://arduino.esp8266.com/stable/package_esp8266com_index.json
 *   Board               NodeMCU 1.0 (ESP-12E Module)
 *   Libraries           DHT sensor library (Adafruit), Adafruit Unified Sensor,
 *                       PubSubClient
 *
 * The Wi-Fi password lives here and nowhere else in the project. Do not commit
 * a real one: fill it in on the demo laptop just before the event.
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

// ---------------------------------------------------------------- settings
const char* WIFI_SSID = "YOUR_HOTSPOT";       // 2.4 GHz only - the ESP8266 has no 5 GHz
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* MQTT_HOST = "192.168.1.50";       // the laptop's fixed IP on the demo network
const uint16_t MQTT_PORT = 1883;

const char* TRUCK_ID  = "TRK-07";
const char* TOPIC     = "coldguard/TRK-07/telemetry";
const char* CLIENT_ID = "coldguard-node1";

const uint8_t DHT_PIN  = 4;                   // D2
const uint8_t DOOR_PIN = 14;                  // D5, optional lid switch (LOW = closed)
const bool    HAS_DOOR_SWITCH = false;        // set true once the switch is fitted

const unsigned long PUBLISH_MS   = 2000;      // one reading every 2 s
const unsigned long RETRY_MS     = 1000;      // between reconnect attempts
const uint8_t       LED_PIN      = LED_BUILTIN;   // on = not connected

DHT dht(DHT_PIN, DHT11);
WiFiClient net;
PubSubClient mqtt(net);

unsigned long lastPublish = 0;
unsigned long lastRetry   = 0;
unsigned long published   = 0;
float lastGoodC = NAN;                        // last valid reading, for the log

// ------------------------------------------------------------------ helpers
void setLed(bool on) { digitalWrite(LED_PIN, on ? LOW : HIGH); }   // active low

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  setLed(true);
  if (millis() - lastRetry < RETRY_MS) return;
  lastRetry = millis();
  Serial.printf("wifi: reconnecting to %s\n", WIFI_SSID);
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void ensureMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqtt.connected()) return;
  if (millis() - lastRetry < RETRY_MS) return;
  lastRetry = millis();
  Serial.printf("mqtt: connecting to %s:%u ... ", MQTT_HOST, MQTT_PORT);
  if (mqtt.connect(CLIENT_ID)) {
    Serial.println("ok");
  } else {
    Serial.printf("failed, state %d\n", mqtt.state());
  }
}

bool doorOpen() {
  if (!HAS_DOOR_SWITCH) return false;
  return digitalRead(DOOR_PIN) == HIGH;       // open contact = lid lifted
}

// -------------------------------------------------------------------- setup
void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println();
  Serial.println("ColdGuard node starting");

  pinMode(LED_PIN, OUTPUT);
  setLed(true);
  if (HAS_DOOR_SWITCH) pinMode(DOOR_PIN, INPUT_PULLUP);

  dht.begin();
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(15);
  mqtt.setSocketTimeout(5);
}

// --------------------------------------------------------------------- loop
void loop() {
  ensureWifi();
  ensureMqtt();
  mqtt.loop();
  setLed(!mqtt.connected());

  if (millis() - lastPublish < PUBLISH_MS) return;
  lastPublish = millis();

  float t = dht.readTemperature();
  float h = dht.readHumidity();

  // A failed read is real information: the backend treats -127 as a sensor
  // fault and pauses the freshness clock rather than guessing (section 7.2).
  if (isnan(t) || isnan(h)) {
    Serial.println("dht: read failed, reporting sensor fault");
    t = -127.0;
    h = 0.0;
  } else {
    lastGoodC = t;
  }

  char msg[128];
  snprintf(msg, sizeof(msg),
           "{\"truck_id\":\"%s\",\"air_c\":%.1f,\"hum_pct\":%.0f,\"door_open\":%s}",
           TRUCK_ID, t, h, doorOpen() ? "true" : "false");

  if (mqtt.connected() && mqtt.publish(TOPIC, msg)) {
    published++;
  } else {
    Serial.println("mqtt: publish failed, will retry");
  }
  Serial.printf("%lu %s\n", published, msg);
}
