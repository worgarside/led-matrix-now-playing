include .env
export

clean:
	sudo rm -rf .venv
	sudo rm -rf rpi-rgb-led-matrix

create:
	virtualenv -p 3.12 .venv312
	$(MAKE) install-all

	sudo mkdir -p /var/cache/led-matrix-controller
	sudo chown -R root:root /var/cache/led-matrix-controller
	sudo chmod -R 777 /var/cache/led-matrix-controller

	git clone https://github.com/hzeller/rpi-rgb-led-matrix.git

	$(MAKE) -C rpi-rgb-led-matrix/bindings/python build-python PYTHON=/home/pi/led-matrix-controller/.venv312/bin/python
	$(MAKE) -C rpi-rgb-led-matrix/bindings/python install-python PYTHON=/home/pi/led-matrix-controller/.venv312/bin/python

	sudo rm -rf rpi-rgb-led-matrix

disable:
	sudo systemctl disable led_matrix_controller.service

enable:
	sudo systemctl enable led_matrix_controller.service

install-python:
	.venv312/bin/pip install -r requirements.txt

install-service:
	sudo cp service/led_matrix_controller.service /etc/systemd/system/
	sudo systemctl daemon-reload

install-all:
	@$(MAKE) install-python
	@$(MAKE) install-service

restart:
	sudo systemctl restart led_matrix_controller.service

run:
	sudo .venv312/bin/python src/application/controller/led_matrix_controller.py

start:
	sudo systemctl start led_matrix_controller.service

stop:
	sudo systemctl stop led_matrix_controller.service

tail:
	sudo journalctl -u led_matrix_controller.service -f -n 20

test:
	poetry run pytest -n auto --dist=load -v

update:
	git add .
	git stash save "Stash before update @ $(shell date)"
	git pull --prune
	@$(MAKE) install-all
