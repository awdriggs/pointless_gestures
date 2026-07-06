#include "esp_camera.h"
#include <RadioLib.h>
#include <SPI.h>
#include <math.h>

#define LORA_FREQ      868.0
#define LORA_BW        125.0
#define LORA_SF        7
#define LORA_CR        5
#define LORA_POWER     14
#define SLEEP_SECONDS  60
#define SAMPLE_STEP    4

#define AVG_LINEAR_RGB       0
#define AVG_HSV_CIRCULAR     1
#define AVG_HSV_SAT_WEIGHTED 2
#define AVG_MODE             AVG_LINEAR_RGB

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
  if (esp_reset_reason() == ESP_RST_POWERON) delay(10000);
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
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;
  config.jpeg_quality = 10;
  config.fb_count     = 2;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.grab_mode    = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed — sleeping");
    sleep();
  }

  sensor_t* s = esp_camera_sensor_get();
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 0);      // fixed WB
  s->set_wb_mode(s, 1);       // sunny
  s->set_aec2(s, 0);
  s->set_exposure_ctrl(s, 0); // manual exposure
  s->set_aec_value(s, 7);

  // Drain frames to let sensor stabilize — 30 frames needed at low light/after standby
  for (int i = 0; i < 30; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    esp_camera_fb_return(fb);
  }

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Frame capture failed — sleeping");
    esp_camera_deinit();
    sleep();
  }

  uint8_t r, g, b;
  averageColor(fb, AVG_MODE, r, g, b);
  esp_camera_fb_return(fb);

  // Put OV3660 into hardware standby before deinit — PWDN is not wired on the
  // Sense expansion board so this register write is the only way to reduce
  // camera current in deep sleep (~40mA → ~1.4mA)
  s = esp_camera_sensor_get();
  s->set_reg(s, 0x3008, 0xFF, 0x42);

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

void averageColor(camera_fb_t* fb, uint8_t mode, uint8_t& outR, uint8_t& outG, uint8_t& outB) {
  int w = fb->width;
  int h = fb->height;

  // jpg2rgb565 produces standard RGB565: R in bits 15-11, G in 10-5, B in 4-0
  uint16_t* rgb = (uint16_t*)ps_malloc(w * h * 2);
  if (!rgb) {
    Serial.println("RGB buffer alloc failed");
    outR = outG = outB = 0;
    return;
  }

  if (!jpg2rgb565(fb->buf, fb->len, (uint8_t*)rgb, JPG_SCALE_NONE)) {
    Serial.println("JPEG decode failed");
    free(rgb);
    outR = outG = outB = 0;
    return;
  }

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
        uint16_t px = rgb[y * w + x];
        rSum += ((px >> 11) & 0x1F) * 255 / 31;
        gSum += ((px >>  5) & 0x3F) * 255 / 63;
        bSum += ( px        & 0x1F) * 255 / 31;
        count++;
      }
    }
    free(rgb);
    outR = rSum / count;
    outG = gSum / count;
    outB = bSum / count;
    return;
  }

  double sinSum = 0, cosSum = 0, sSum = 0, vSum = 0;
  int count = 0;

  for (int y = yStart; y < yEnd; y += SAMPLE_STEP) {
    for (int x = xStart; x < xEnd; x += SAMPLE_STEP) {
      uint16_t px = rgb[y * w + x];
      float r  = ((px >> 11) & 0x1F) / 31.0f;
      float gr = ((px >>  5) & 0x3F) / 63.0f;
      float b  = ( px        & 0x1F) / 31.0f;

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

      float sat    = (mx > 0.001f) ? (d / mx) : 0.0f;
      float weight = (mode == AVG_HSV_SAT_WEIGHTED) ? sat : 1.0f;
      float angle  = hue * TWO_PI;

      sinSum += weight * sin(angle);
      cosSum += weight * cos(angle);
      sSum   += sat;
      vSum   += mx;
      count++;
    }
  }

  free(rgb);

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
