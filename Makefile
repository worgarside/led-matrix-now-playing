create-env:
	virtualenv -p 3.11 .venv
	$(MAKE) install-all

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

run:
	.venv/bin/python src/application/controller/rgb_led_matrix.py

update:
	git add .
	git stash save "Stash before update @ $(shell date)"
	git pull --prune
	@$(MAKE) install-all
