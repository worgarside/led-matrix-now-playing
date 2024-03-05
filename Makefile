include .env
export

create:
	virtualenv -p 3.11 .venv
	$(MAKE) install-all

	sudo mkdir -p /var/cache/led-matrix-now-playing
	sudo chown -R root:root /var/cache/led-matrix-now-playing
	sudo chmod -R 755 /var/cache/led-matrix-now-playing

disable:
	sudo systemctl disable rgb_led_matrix.service

enable:
	sudo systemctl enable rgb_led_matrix.service

install-python:
	.venv/bin/pip install -r requirements.txt

install-service:
	@$(MAKE) stop
	sudo cp service/rgb_led_matrix.service /etc/systemd/system/
	echo "Service file copied to /etc/systemd/system/rgb_led_matrix.service"
	@$(MAKE) enable
	@$(MAKE) start

install-all:
	@$(MAKE) install-python
	@$(MAKE) install-service

run:
	sudo .venv/bin/python src/application/controller/rgb_led_matrix.py

start:
	sudo systemctl start rgb_led_matrix.service

stop:
	sudo systemctl stop rgb_led_matrix.service

tail:
	sudo journalctl -u rgb_led_matrix.service -f -n 20

update:
	git add .
	git stash save "Stash before update @ $(shell date)"
	git pull --prune
	@$(MAKE) install-all
