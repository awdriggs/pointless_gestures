FQBN        = esp32:esp32:XIAO_ESP32S3:PSRAM=opi
SKETCH      = camera
SERIAL_PORT = /dev/cu.usbmodem1101
BAUD_RATE   = 115200

.PHONY: help compile upload monitor run watch

help:
	@echo "Targets:"
	@echo "  make compile  - Compile sketch"
	@echo "  make upload   - Compile and flash"
	@echo "  make monitor  - Open serial monitor (Ctrl-A then K to exit)"
	@echo "  make run      - Upload then monitor"
	@echo "  make watch    - Auto-upload on save (requires watchexec)"

compile:
	arduino-cli compile --fqbn $(FQBN) .

upload: compile
	arduino-cli upload --fqbn $(FQBN) --port $(SERIAL_PORT) .

monitor:
	screen -T ansi $(SERIAL_PORT) $(BAUD_RATE),crnl

run: upload
	@sleep 2
	@$(MAKE) monitor

watch:
	watchexec -w $(SKETCH).ino make upload
