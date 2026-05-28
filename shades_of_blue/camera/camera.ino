#include "esp_camera.h"
#include <RadioLib.h>
#include <SPI.h>
#include <math.h>

#define LORA_FREQ      868.0
#define LORA_BW        125.0
#define LORA_SF        7
#define LORA_CR        5
#define LORA_POWER     14
#define SLEEP_SECONDS  45
#define SAMPLE_STEP    4

#define AVG_LINEAR_RGB       0
#define AVG_HSV_CIRCULAR     1
#define AVG_HSV_SAT_WEIGHTED 2
#define AVG_MODE             AVG_HSV_SAT_WEIGHTED


// Camera pins — XIAO ESP32-S3 Sense
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

// Wio-SX1262 via B2B connector
SPIClass loraSPI(FSPI);
SX1262 radio = new Module(D4, D1, D2, D3, loraSPI);  // NSS, DIO1, RST, BUSY

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- wake ---");

  // --- Camera ---
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_RGB565;
  config.frame_size   = FRAMESIZE_QVGA;
  config.fb_count     = 1;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed — sleeping");
    sleep();
  }

  sensor_t* s = esp_camera_sensor_get();
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_wb_mode(s, 0);   // auto WB
  s->set_aec2(s, 0);      // disable night-mode AEC — don't compensate for fading light
  s->set_ae_level(s, 0);

  // Drain frames to let AEC settle before taking the real reading
  for (int i = 0; i < 10; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    esp_camera_fb_return(fb);
  }

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Frame capture failed — sleeping");
    esp_camera_deinit();
    sleep();
  }

  debugPixels(fb);

  uint8_t r, g, b;
  averageColor(fb, AVG_MODE, r, g, b);
  esp_camera_fb_return(fb);
  esp_camera_deinit();

  Serial.printf("RGB: %d,%d,%d\n", r, g, b);

  // --- LoRa ---
  loraSPI.begin(D8, D9, D10, D4);
  pinMode(D5, OUTPUT);
  digitalWrite(D5, HIGH);  // RF_SW

  int state = radio.begin(LORA_FREQ, LORA_BW, LORA_SF, LORA_CR,
                          RADIOLIB_SX126X_SYNC_WORD_PRIVATE, LORA_POWER);
  if (state != RADIOLIB_ERR_NONE) {
    Serial.printf("LoRa init failed, code %d — sleeping\n", state);
    sleep();
  }

  char packet[16];
  snprintf(packet, sizeof(packet), "%d,%d,%d", r, g, b);
  state = radio.transmit(packet);
  if (state != RADIOLIB_ERR_NONE) {
    Serial.printf("TX failed, code %d\n", state);
  }

  radio.sleep();
  sleep();
}

void loop() {}

void sleep() {
  Serial.printf("sleeping %ds\n", SLEEP_SECONDS);
  Serial.flush();
  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_SECONDS * 1000000ULL);
  esp_deep_sleep_start();
}

void debugPixels(camera_fb_t* fb) {
  int w = fb->width;
  int h = fb->height;
  uint16_t* pixels = (uint16_t*)fb->buf;
  int cx = w / 2;
  int cy = h / 2;

  Serial.println("-- center pixel samples (raw px, as-BGR, byte-swapped-BGR) --");
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      uint16_t px = pixels[(cy + dy) * w + (cx + dx)];
      uint16_t sw = (px << 8) | (px >> 8);

      uint8_t b1 = ((px >> 11) & 0x1F) * 255 / 31;
      uint8_t g1 = ((px >>  5) & 0x3F) * 255 / 63;
      uint8_t r1 = ( px        & 0x1F) * 255 / 31;

      uint8_t b2 = ((sw >> 11) & 0x1F) * 255 / 31;
      uint8_t g2 = ((sw >>  5) & 0x3F) * 255 / 63;
      uint8_t r2 = ( sw        & 0x1F) * 255 / 31;

      Serial.printf("px=0x%04X  BGR=(%3d,%3d,%3d)  swapped-BGR=(%3d,%3d,%3d)\n",
                    px, r1, g1, b1, r2, g2, b2);
    }
  }
}

void averageColor(camera_fb_t* fb, uint8_t mode, uint8_t& outR, uint8_t& outG, uint8_t& outB) {
  int w = fb->width;
  int h = fb->height;
  uint16_t* pixels = (uint16_t*)fb->buf;

  // center crop: ~50% of pixels (sqrt(0.5) of each dimension)
  int xStart = (int)(w * 0.146f);
  int xEnd   = w - xStart;
  int yStart = (int)(h * 0.146f);
  int yEnd   = h - yStart;

  if (mode == AVG_LINEAR_RGB) {
    uint32_t rSum = 0, gSum = 0, bSum = 0;
    int count = 0;
    for (int y = yStart; y < yEnd; y += SAMPLE_STEP) {
      for (int x = xStart; x < xEnd; x += SAMPLE_STEP) {
        uint16_t raw = pixels[y * w + x];
        uint16_t px  = (raw << 8) | (raw >> 8);
        rSum += (px & 0x1F) * 255 / 31;
        gSum += ((px >> 5) & 0x3F) * 255 / 63;
        bSum += ((px >> 11) & 0x1F) * 255 / 31;
        count++;
      }
    }
    outR = rSum / count;
    outG = gSum / count;
    outB = bSum / count;
    return;
  }

  double sinSum = 0, cosSum = 0, sSum = 0, vSum = 0;
  int count = 0;

  for (int y = yStart; y < yEnd; y += SAMPLE_STEP) {
    for (int x = xStart; x < xEnd; x += SAMPLE_STEP) {
      uint16_t raw = pixels[y * w + x];
      uint16_t px  = (raw << 8) | (raw >> 8);  // OV3660: big-endian BGR565
      float b  = ((px >> 11) & 0x1F) / 31.0f;
      float gr = ((px >>  5) & 0x3F) / 63.0f;
      float r  = (px & 0x1F) / 31.0f;

      float mx = max(r, max(gr, b));
      float mn = min(r, min(gr, b));
      float d  = mx - mn;

      float hue = 0;
      if (d > 0.001f) {
        if (mx == r)       hue = fmod((gr - b) / d, 6.0f);
        else if (mx == gr) hue = (b - r) / d + 2.0f;
        else               hue = (r - gr) / d + 4.0f;
        hue /= 6.0f;
        if (hue < 0) hue += 1.0f;
      }

      float sat   = (mx > 0.001f) ? (d / mx) : 0.0f;
      float weight = (mode == AVG_HSV_SAT_WEIGHTED) ? sat : 1.0f;
      float angle  = hue * TWO_PI;

      sinSum += weight * sin(angle);
      cosSum += weight * cos(angle);
      sSum   += sat;
      vSum   += mx;
      count++;
    }
  }

  float avgSat = sSum / count;
  float avgVal = vSum / count;

  float avgHue = 0;
  if (sinSum * sinSum + cosSum * cosSum > 0.0001f) {
    avgHue = fmod(atan2(sinSum, cosSum) / TWO_PI + 1.0f, 1.0f);
  }

  int i = (int)(avgHue * 6) % 6;
  float f = (avgHue * 6) - i;
  float p = avgVal * (1 - avgSat);
  float q = avgVal * (1 - f * avgSat);
  float t = avgVal * (1 - (1 - f) * avgSat);

  float fr, fg, fb2;
  switch (i) {
    case 0: fr = avgVal; fg = t;      fb2 = p;      break;
    case 1: fr = q;      fg = avgVal; fb2 = p;      break;
    case 2: fr = p;      fg = avgVal; fb2 = t;      break;
    case 3: fr = p;      fg = q;      fb2 = avgVal; break;
    case 4: fr = t;      fg = p;      fb2 = avgVal; break;
    default: fr = avgVal; fg = p;     fb2 = q;      break;
  }

  outR = (uint8_t)(fr * 255);
  outG = (uint8_t)(fg * 255);
  outB = (uint8_t)(fb2 * 255);
}
