#include <RadioLib.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "secrets.h"

#define LORA_FREQ      868.0
#define LORA_BW        125.0
#define LORA_SF        7
#define LORA_CR        5
#define LED_FLASH_MS   100
#define DEVICE_NAME    "ams-rx"
#define DEVICE_ID      "ams01"
#define SERVER_URL     "https://micro-api.awdokku.site/api/readings/shades-of-blue"
#define TZ             "CET-1CEST,M3.5.0,M10.5.0/3"

SX1262 radio = new Module(SS, DIO0, RST_LoRa, BUSY_LoRa);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, RST_OLED, SCL_OLED, SDA_OLED);

uint8_t lastR = 0, lastG = 0, lastB = 0;
char lastSent[9] = "--:--:--";  // HH:MM:SS
bool hasReading = false;

void setup() {
  Serial.begin(115200);

  pinMode(Vext, OUTPUT);
  digitalWrite(Vext, HIGH);
  delay(100);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  display.begin();
  showMessage("Connecting WiFi...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  Serial.printf("WiFi connected: %s\n", WiFi.localIP().toString().c_str());

  configTzTime(TZ, "pool.ntp.org");

  showMessage("Initializing LoRa...");
  int state = radio.begin(LORA_FREQ, LORA_BW, LORA_SF, LORA_CR);
  if (state != RADIOLIB_ERR_NONE) {
    Serial.printf("LoRa init failed, code %d\n", state);
    showMessage("LoRa failed");
    while (true);
  }
  radio.setDio2AsRfSwitch(true);

  updateDisplay();
  Serial.println("Ready");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(2000);
    return;
  }

  char packet[32];
  int state = radio.receive((uint8_t*)packet, sizeof(packet) - 1);

  if (state == RADIOLIB_ERR_NONE) {
    packet[sizeof(packet) - 1] = '\0';
    Serial.printf("RX: %s  RSSI: %.1f dBm\n", packet, radio.getRSSI());

    uint8_t r, g, b;
    if (sscanf(packet, "%hhu,%hhu,%hhu", &r, &g, &b) == 3) {
      postReading(r, g, b);
      flashLED();
    }
  } else if (state != RADIOLIB_ERR_RX_TIMEOUT) {
    Serial.printf("RX error, code %d\n", state);
  }
}

void postReading(uint8_t r, uint8_t g, uint8_t b) {
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  char body[64];
  snprintf(body, sizeof(body), "{\"r\":%d,\"g\":%d,\"b\":%d,\"device_id\":\"%s\"}", r, g, b, DEVICE_ID);

  int code = http.POST(body);
  if (code > 0) {
    Serial.printf("POST %d\n", code);
    lastR = r; lastG = g; lastB = b;
    hasReading = true;
    stampTime();
    updateDisplay();
  } else {
    Serial.printf("POST failed: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

void stampTime() {
  struct tm t;
  if (getLocalTime(&t)) {
    snprintf(lastSent, sizeof(lastSent), "%02d:%02d:%02d", t.tm_hour, t.tm_min, t.tm_sec);
  }
}

void updateDisplay() {
  char line[24];
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  // Row 1: device name (left) + wifi status (right)
  display.drawStr(0, 10, DEVICE_NAME);
  const char* wifiStatus = (WiFi.status() == WL_CONNECTED) ? "WiFi:ok" : "WiFi:--";
  display.drawStr(128 - display.getStrWidth(wifiStatus), 10, wifiStatus);

  // Row 2: last sent time
  snprintf(line, sizeof(line), "last: %s", lastSent);
  display.drawStr(0, 26, line);

  // Row 3: RGB values
  if (hasReading) {
    snprintf(line, sizeof(line), "R:%d G:%d B:%d", lastR, lastG, lastB);
  } else {
    snprintf(line, sizeof(line), "R:-- G:-- B:--");
  }
  display.drawStr(0, 46, line);

  display.sendBuffer();
}

void showMessage(const char* msg) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);
  display.drawStr(0, 20, msg);
  display.sendBuffer();
}

void flashLED() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(LED_FLASH_MS);
  digitalWrite(LED_BUILTIN, LOW);
}
