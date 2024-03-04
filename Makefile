create-env:
	virtualenv -p 3.11 .venv
	$(MAKE) install-all

install-matrix:
	curl https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/main/rgb-matrix.sh >rgb-matrix.sh
	. .venv/bin/activate && sudo bash rgb-matrix.sh -y

install-python:
	.venv/bin/pip install -r requirements.txt

install-service:
	sudo systemctl stop rgb_led_matrix.service
	sudo cp service/rgb_led_matrix.service /etc/systemd/system/
	echo "Service file copied to /etc/systemd/system/rgb_led_matrix.service"
	sudo systemctl enable rgb_led_matrix.service
	sudo systemctl start rgb_led_matrix.service

install-all:
	@$(MAKE) install-python
	@$(MAKE) install-service

update:
	git add .
	git stash save "Stash before update @ $(shell date)"
	git pull --prune
	@$(MAKE) install-all
